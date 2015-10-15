from enum import IntEnum
from . import frames
import logging

logger = logging.getLogger('stream')

class stream_state(IntEnum):
    IDLE = 0
    RESERVED_LOCAL = 1
    RESERVED_REMOTE = 2
    OPEN = 3
    HALF_CLOSED_LOCAL = 4
    HALF_CLOSED_REMOTE = 5
    CLOSED = 6

class http_state(IntEnum):
    HEADERS = 0
    CONTINUATION = 1
    DATA = 2
    TRAILERS = 3
    TRAILERS_CONTINUATION = 3
    DONE = 4

class reserved(IntEnum):
    NONE = 0
    LOCAL = 1
    REMOTE = 2

class message_type(IntEnum):
    REQUEST = 0
    RESPONSE = 1

class http_message:
    def __init__(self, headers, data = None, message_type = message_type.RESPONSE):
        self.headers = headers
        self.data = data
        self.message_type = message_type.RESPONSE

# Stream essentially represents one request/response pair
class stream:
    def __init__(self, identifier, hpack_ctx):
        self.identifier = identifier
        self.http_state = http_state.HEADERS
        self.hpack_ctx = hpack_ctx
        self.header_bytes = bytearray()
        self.data_bytes = bytearray()
        self.state = stream_state.IDLE
        self.send_queue = []
        self.message_queue = []

    def queue_stream_error(self, error=frames.error.PROTOCOL_ERROR):
        self.send_queue.append(frames.rst_stream_frame(self.identifier, error))

    def handle_recv_frame(self, frame):
        # Normal request processing is HEADERS, followed by CONTINUATION,
        # followed by DATA. Intermingled with these can be PRIORITY, WINDOW_UPDATE,
        # and RST_STREAM.
        # PUSH_PROMISE, PING, SETTINGS, and GOAWAY are handled by the connection.

        logger.debug("Stream id %d handling %s frame", self.identifier, frame.frame_type)

        switcher = {
                frames.frame_type.HEADERS: self.handle_headers,
                frames.frame_type.CONTINUATION: self.handle_continuation,
                frames.frame_type.DATA: self.handle_data,
                frames.frame_type.RST_STREAM: self.handle_rst_stream,
        }
        handler = switcher.get(frame.frame_type, self.handle_invalid_frame_type)
        return handler(frame)

    def handle_headers(self, frame):
        if self.http_state is http_state.DATA:
            # There's no flag for end of data
            self.http_state = http_state.TRAILERS

        if self.http_state is http_state.HEADERS:
            self.header_bytes = frame.header_block_fragment
        elif self.http_state is http_state.TRAILERS:
            self.header_bytes.extend(frame.header_block_fragment)
        else:
            self.queue_stream_error()
            self.http_state = http_state.DONE
            return frames.error.NO_ERROR

        if self.state is stream_state.IDLE:
            self.state = stream_state.OPEN

        if self.state is stream_state.RESERVED_REMOTE:
            self.close_local()

        if frame.is_flag_set(frames.headers_flags.END_STREAM):
            self.close_remote()

        if frame.is_flag_set(frames.headers_flags.END_HEADERS):
            # We process the headers lazily
            if self.remote_closed():
                self.http_state = http_state.DONE
                self.process_message()
            else:
                self.http_state = http_state.DATA

        return frames.error.NO_ERROR

    def handle_continuation(self, frame):
        if self.http_state is http_state.CONTINUATION:
            self.header_bytes.extend(frame.header_block_fragment)
        elif self.http_state is http_state.TRAILERS_CONTINUATION:
            self.header_bytes.extend(frame.header_block_fragment)
        else:
            self.queue_stream_error()
            self.http_state = http_state.DONE
            return frames.error.NO_ERROR

        if frame.is_flag_set(frames.headers_flags.END_HEADERS):
            # We process the headers lazily
            if self.remote_closed():
                self.http_state = http_state.DONE
                self.process_message()
            else:
                self.http_state = http_state.DATA

        return frames.error.NO_ERROR

    def handle_data(self, frame):
        if self.http_state is not http_state.DATA:
            self.queue_stream_error()
            self.http_state = http_state.DONE
            return frames.error.NO_ERROR

        self.data_bytes.extend(frame.data)

        if frame.is_flag_set(frames.data_flags.END_STREAM):
            self.close_remote()
            self.http_state = http_state.DONE
            self.process_message()

        return frames.error.NO_ERROR

    def handle_rst_stream(self, frame):
        self.close_remote()
        self.close_local()
        self.http_state = http_state.DONE
        return frames.error.NO_ERROR

    def handle_invalid_frame_type(self, frame):
        self.close_remote()
        self.close_local()
        self.http_state = http_state.DONE
        return frames.error.PROTOCOL_ERROR

    def handle_send_message(self, headers, data=None):
        self.close_local()

        self.hpack_ctx.start_encode()
        self.hpack_ctx.encode_header_dict(headers)
        header_block = self.hpack_ctx.end_encode()

        # Later, this may need to be fragmented according to
        # the MAX_FRAME_SIZE setting
        headers_frame = frames.headers_frame(self.identifier, header_block)
        headers_frame.set_flag(frames.headers_flags.END_HEADERS)
        if data is None or len(data) is 0:
            headers_frame.set_flag(frames.headers_flags.END_STREAM)

        self.send_queue.append(headers_frame)

        if data is None or len(data) is 0:
            return

        data_frame = frames.data_frame(data, self.identifier)
        data_frame.set_flag(frames.data_flags.END_STREAM)
        self.send_queue.append(data_frame)

    def process_message(self):
        message = http_message(self.hpack_ctx.decode_headers(self.header_bytes), self.data_bytes)
        self.header_bytes = bytearray()
        self.data_bytes = bytearray()
        self.message_queue.append(message)

    def close_local(self):
        if self.state is stream_state.HALF_CLOSED_REMOTE:
            self.state = stream_state.CLOSED
        elif self.state is stream_state.OPEN or self.state is stream_state.RESERVED_REMOTE:
            self.state = stream_state.HALF_CLOSED_LOCAL

    def close_remote(self):
        if self.state is stream_state.HALF_CLOSED_LOCAL:
            self.state = stream_state.CLOSED
        elif self.state is stream_state.OPEN or self.state is stream_state.RESERVED_REMOTE:
            self.state = stream_state.HALF_CLOSED_REMOTE

    def remote_closed(self):
        return self.state is stream_state.HALF_CLOSED_REMOTE or self.state is stream_state.CLOSED

    def local_closed(self):
        return self.state is stream_state.HALF_CLOSED_LOCAL or self.state is stream_state.CLOSED

    def flush_send_queue(self):
        send_queue = self.send_queue
        self.send_queue = []
        return send_queue

    def flush_message_queue(self):
        message_queue = self.message_queue
        self.message_queue = []
        return message_queue
