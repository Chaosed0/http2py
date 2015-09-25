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
        if self.callbacks['send'](connection_preface):
            # Report send error
            return

        initial_settings_frame = frames.settings_frame()
        if self.callbacks['send'](initial_settings_frame.encode()):
            # Report send error
            return

    def process_bytes(self, some_bytes):
        self.recv_buffer.extend(some_bytes)
        while True:
            if len(self.recv_buffer) < 3:
                # We can't even read the length yet
                break

            # Got length
            length = int.from_bytes(self.recv_buffer[0:3], 'big')
            if length > len(self.recv_buffer) - 3:
                # We don't have the whole frame yet
                break

            # Have a whole frame, decode it
            frame,read = frames.frame.decode_static(self.recv_buffer)

            if frame is None:
                # Error decoding frame, report it and maybe send an error
                self.recv_buffer = bytearray()
                break

            self.recv_buffer = self.recv_buffer[read+1:]
            logger.debug("Read %d bytes from recv_buffer, %d left", read, len(self.recv_buffer))

            self.process_frame(frame)

    def process_frame(self, frame):
        logger.debug("Decoded frame: %s", frame)

        if self.waiting_for_preface:
            if frame.frame_type is not frames.frame_type.SETTINGS:
                # send connection error
                return

            # Apply the settings in the frame
            
            logger.debug("Got connection preface")
            self.waiting_for_preface = False
        else:
            # Is it something we need to handle?
            switcher = {
                    frames.frame_type.PUSH_PROMISE: handle_push_promise,
                    frames.frame_type.PING: handle_ping,
                    frames.frame_type.GOAWAY: handle_goaway,
            }
            handler = switcher.get(frame.frame_type, pass_frame_to_stream)
            handler(frame)

    def handle_push_promise(self, frame):
        return

    def handle_ping(self, frame):
        return

    def handle_goaway(self, frame):
        return

    def pass_frame_to_stream(self, frame):
        if frame.stream_identifier not in self.streams:
            # new stream
            # TODO: There are definitely qualifications on the stream id of a
            # new stream
            self.open_stream(frame.stream_identifier)
        self.streams[frame.stream_identifier].handle_frame(frame)

    def open_stream(self, stream_identifier, reserved_state=stream.reserved.NONE):
        self.streams[stream_identifier] = stream.stream(stream_identifier, reserved_state)

    def send_request(self, headers, data):
        self.streams[self.next_stream_id] = stream.stream(self.next_stream_id)
        self.next_stream_id += 2
