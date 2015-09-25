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

class request_state(IntEnum):
    HEADERS = 0
    CONTINUATION = 1
    DATA = 2
    TRAILERS = 3
    DONE = 4

class reserved(IntEnum):
    NONE = 0
    LOCAL = 1
    REMOTE = 2

# Stream essentially represents one request/response pair
class stream:
    def __init__(self, identifier, hpack_ctx, reserved_state=reserved.NONE):
        self.identifier = identifier
        self.request_state = request_state.HEADERS
        self.hpack_ctx = hpack_ctx
        if reserved_state is reserved.LOCAL:
            self.state = stream_state.RESERVED_LOCAL
        elif reserved_state is reserved.REMOTE:
            self.state = stream_state.RESERVED_REMOTE
        else:
            self.state = stream_state.IDLE

    def handle_recv_frame(self, frame):
        # Normal request processing is HEADERS, followed by CONTINUATION,
        # followed by DATA. Intermingled with these can be PRIORITY, SETTINGS,
        # WINDOW_UPDATE, and RST_STREAM.
        # PUSH_PROMISE, PING, and GOAWAY are handled by the connection.

        logger.log("Stream id %d handling %s frame", self.identifier, frame.frame_type)

        if frame.frame_type is frames.frame_type.HEADERS:
            if self.state is stream_state.IDLE:
                self.state = stream_state.OPEN
            elif self.state is stream.state.RESERVED_REMOTE:
                self.state = stream_state.HALF_CLOSED_LOCAL
            elif self.state is stream_state.OPEN:
                self.state = stream_state.HALF_CLOSED_REMOTE
            elif self.state is stream_state.HALF_CLOSED_LOCAL:
                self.state = stream_state.CLOSED
            elif self.state is stream_state.HALF_CLOSED_REMOTE or self.state is stream_state.CLOSED:
                return

            if self.request_state is request_state.DATA:
                self.request_state = request_state.TRAILERS

            if self.request_state is not request_state.HEADERS and self.request_state is not request_state.TRAILERS:
                return

            if frame.is_flag_set(frames.headers_flags.END_STREAM):
                self.state = stream_state.HALF_CLOSED_REMOTE
            else:
                if self.request_state is request_state.HEADERS:
                    self.state = stream_state.OPEN
                elif self.request_state is request_state.TRAILERS:
                    # error
                    return

            if frame.is_flag_set(frames.headers_flags.END_HEADERS):
                self.request_state = request_state.DATA
                # Store headers or, if the stream is ended, process the response
            else:
                self.request_state = request_state.CONTINUATION
        elif frame.frame_type is frames.frame_type.CONTINUATION:
            if self.state is not stream_state.OPEN and self.state is not stream_state.HALF_CLOSED_LOCAL:
                return

            if self.request_state is not request_state.CONTINUATION:
                return

            if frame.is_flag_set(frames.headers_flags.END_HEADERS):
                self.request_state = request_state.DATA
                # Store headers or, if the stream is ended, process the repsonse
        elif frame.frame_type is frames.frame_type.DATA:
            if self.state is not stream_state.OPEN and self.state is not stream_state.HALF_CLOSED_LOCAL:
                return

            if self.request_state is not request_state.DATA:
                return

            if frame.is_flag_set(frames.data_flags.END_STREAM):
                # Process the response
                return

    def handle_send_request(self, headers, data=None):
        frames_to_send = []
        self.hpack_ctx.start_encode()
        self.hpack_ctx.encode_header_dict(headers)
        header_block = self.hpack_ctx.end_encode()

        # Later, this may need to be fragmented according to
        # the MAX_FRAME_SIZE setting
        headers_frame = frames.headers_frame(self.identifier, header_block)
        if data is None or len(data) is 0:
            headers_frame.set_flag(frames.headers_flags.END_STREAM)

        frames_to_send.append(headers_frame)

        if data is None or len(data) is 0:
            return frames_to_send

        data_frame = frames.data_frame(data, self.identifier)
        frames_to_send.append(data_frame)

        return frames_to_send
