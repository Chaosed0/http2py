from enum import IntEnum
from . import frames
from . import stream
import hpack
import logging
import hexdump

connection_preface = bytearray("PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n", "ascii")

logger = logging.getLogger('connection')

class connection:
    def __init__(self, callbacks, is_client = True):
        self.waiting_for_preface = True
        self.is_client = is_client
        self.next_stream_id = (1 if is_client else 2)
        self.hpack_ctx = hpack.hpack.ctx()
        self.streams = { }
        self.callbacks = callbacks
        self.recv_buffer = bytearray()

    def initiate(self):
        logger.debug("Sending connection preface")
        if self.callbacks['send'](connection_preface):
            # Report send error
            return

        initial_settings_frame = frames.settings_frame(0x0)
        logger.debug("Sending initial settings frame %s", initial_settings_frame)
        if self.callbacks['send'](initial_settings_frame.encode()):
            # Report send error
            return

    def process_bytes(self, some_bytes):
        self.recv_buffer.extend(some_bytes)

        # 9 bytes is the size of a frame header, so minimum size of frame
        while len(self.recv_buffer) >= 9:
            length = int.from_bytes(self.recv_buffer[0:3], 'big')
            logger.debug("LENGTH %d %s", length, self.recv_buffer[0:3])
            # Length is of payload only
            if length > len(self.recv_buffer) - 9:
                # We don't have the whole frame yet
                logger.debug("Waiting on more bytes: have %d, need %d", len(self.recv_buffer) - 9, length)
                break

            # Have a whole frame, decode it
            frame,read = frames.frame.decode_static(self.recv_buffer)

            if frame is None:
                logger.debug("Error occured when decoding a frame: %s", read)
                self.recv_buffer = bytearray()
                break

            self.recv_buffer = self.recv_buffer[read:]
            logger.debug("Decoded frame: %s", frame)
            logger.debug("Read %d bytes from recv_buffer, %d left", read, len(self.recv_buffer))

            self.process_frame(frame)

    def process_frame(self, frame):
        if self.waiting_for_preface:
            if frame.frame_type is not frames.frame_type.SETTINGS:
                # send connection error
                return

            # Was this an acknowledgement to ours?
            if frame.is_flag_set(frames.settings_flags.ACK):
                logger.debug("Got connection preface")
                self.waiting_for_preface = False

            # Either way, we need to apply the settings in the frame
            self.handle_settings(frame)
        else:
            switcher = {
                    frames.frame_type.PUSH_PROMISE: self.handle_push_promise,
                    frames.frame_type.PING: self.handle_ping,
                    frames.frame_type.GOAWAY: self.handle_goaway,
                    frames.frame_type.SETTINGS: self.handle_settings,
            }
            handler = switcher.get(frame.frame_type, self.pass_frame_to_stream)
            connection_error = handler(frame)
            if connection_error is not frames.error.NO_ERROR:
                logger.debug("connection error: %s", connection_error)
                self.callbacks['send'](frames.goaway_frame(error=connection_error).encode())

    def handle_push_promise(self, frame):
        logger.debug("Connection handling PUSH_PROMISE frame")
        return frames.error.NO_ERROR

    def handle_ping(self, frame):
        logger.debug("Connection handling PING frame")
        return frames.error.NO_ERROR

    def handle_goaway(self, frame):
        logger.debug("Connection handling GOAWAY frame")
        return frames.error.NO_ERROR

    def handle_settings(self, frame):
        logger.debug("Connection handling SETTINGS frame")
        return frames.error.NO_ERROR

    def pass_frame_to_stream(self, frame):
        if frame.stream_identifier not in self.streams:
            # new stream
            # TODO: There are definitely qualifications on the stream id of a
            # new stream
            self.open_stream(frame.stream_identifier)
        stream = self.streams[frame.stream_identifier]
        rc = stream.handle_recv_frame(frame)
        self.flush_stream_send(stream)
        self.handle_stream_messages(stream)
        return rc

    def open_stream(self, stream_identifier, reserved_state=stream.reserved.NONE):
        self.streams[stream_identifier] = stream.stream(stream_identifier, reserved_state)

    def send_request(self, headers, data=None):
        new_stream = stream.stream(self.next_stream_id, self.hpack_ctx)
        self.streams[self.next_stream_id] = new_stream
        self.next_stream_id += 2

        new_stream.handle_send_message(headers, data)
        self.flush_stream_send(new_stream)

    def flush_stream_send(self, stream):
        frames = stream.flush_send_queue()
        if len(frames) > 0:
            logger.debug("Sending frames %s on stream id %d", frames, stream.identifier)
            encoded_frames = bytearray()
            for frame in frames:
                encoded_frames.extend(frame.encode())
            self.callbacks['send'](encoded_frames)

    def handle_stream_messages(self, stream):
        messages = stream.flush_message_queue()
        for message in messages:
            self.callbacks['handle_message'](message)
