from enum import IntEnum
from os import urandom
import struct
import logging

class frame_type(IntEnum):
    UNSET = -1
    DATA = 0x0
    HEADERS = 0x1
    PRIORITY = 0x2
    RST_STREAM = 0x3
    SETTINGS = 0x4
    PUSH_PROMISE = 0x5
    PING = 0x6
    GOAWAY = 0x7
    WINDOW_UPDATE = 0x8
    CONTINUATION = 0x9

class decoding_errors(IntEnum):
    FRAME_TOO_SMALL = 1,
    INVALID_FRAME_TYPE = 2,
    TEMPORARILY_UNSUPPORTED = 3

class frame:
    frame_map = None

    def decode_static(encoded):
        if frame.frame_map is None:
            frame.frame_map = {
                    frame_type.UNSET: None,
                    frame_type.DATA: data_frame,
                    frame_type.HEADERS: headers_frame,
                    frame_type.PRIORITY: None,
                    frame_type.RST_STREAM: None,
                    frame_type.SETTINGS: settings_frame,
                    frame_type.PUSH_PROMISE: None,
                    frame_type.PING: None,
                    frame_type.GOAWAY: goaway_frame,
                    frame_type.WINDOW_UPDATE: None,
                    frame_type.CONTINUATION: None,
                }

        if len(encoded) < 4:
            return None,decoding_error.FRAME_TOO_SMALL
        elif encoded[3] in frame.frame_map:
            frame_type_bit = frame_type(encoded[3])
            new_frame_type = frame.frame_map[frame_type_bit]
            if new_frame_type is None:
                return None,decoding_error.INVALID_FRAME_TYPE
        else:
            return None,decoding_error.INVALID_FRAME_TYPE

        the_frame = new_frame_type()
        bytes_read = the_frame.decode(encoded)
        return the_frame, bytes_read

    def __init__(self, frame_type):
        self.stream_id = 0x0
        self.flags = 0x0
        self.frame_type = frame_type

    def set_flag(self, flag):
        self.flags = self.flags | flag

    def unset_flag(self, flag):
        self.flags = self.flags & (~flag)

    def is_flag_set (self, flag):
        return (self.flags & flag) > 0

    def encode_payload(self):
        raise NotImplementedError("Can't encode frame base class")

    def encode(self):
        if self.frame_type == frame_type.UNSET:
            raise Exception("Can't encode frame with frame_type unset")
        elif self.stream_id < 0 or self.stream_id > 16834:
            raise Exception("Invalid stream identifier")

        # Total length is length of frame header (9) + length of payload
        payload_encoded = self.encode_payload()
        plen = len(payload_encoded)
        encoded = bytearray(9 + plen)
        # 24-bit length
        encoded[0:3] = plen.to_bytes(3, 'big')
        # 8-bit type
        encoded[3] = (self.frame_type & 0xff)
        # 8-bit flags
        encoded[4] = self.flags & 0xff
        # 1-bit reserved flag and 31 bit stream identifier
        encoded[5:9] = self.stream_id.to_bytes(4, 'big')
        encoded[5] = encoded[5] & 0x7f

        # payload_length Payload
        encoded[9:] = payload_encoded

        return encoded

    def decode(self, encoded):
        length = int.from_bytes(encoded[0:3], 'big')
        self.frame_type = frame_type(encoded[3])
        self.flags = encoded[4]
        self.stream_identifier = int.from_bytes(encoded[5:9], 'big')
        self.decode_payload(encoded[9:], length)
        return length+9

class data_flags(IntEnum):
    END_STREAM = 0x1
    PADDED = 0x8

class headers_flags(IntEnum):
    END_STREAM = 0x1
    END_HEADERS = 0x4
    PADDED = 0x8
    PRIORITY = 0x20

class settings_flags(IntEnum):
    ACK = 0x1

class data_frame(frame):
    def __init__(self):
        frame.__init__(self, frame_type.DATA)
        self.pad_length = 0
        self.data = bytearray()

    def has_padding(self):
        return self.is_flag_set(data_flags.PADDED)

    def encode_payload(self):
        encoded = bytearray(1+len(self.data)+self.pad_length)
        cur_byte = 0

        # 8-bit Padding length field
        if self.has_padding():
            encoded[cur_byte] = self.pad_length & 0xff
            cur_byte = 1

        # Variable length data payload
        encoded[cur_byte:] = self.data
        cur_byte = cur_byte + len(self.data)

        # Variable length padding
        if self.has_padding():
            encoded[cur_byte:] = urandom(self.pad_length)
            cur_byte = cur_byte + self.pad_length

        return encoded

    def decode_payload(self, encoded, length):
        cur_byte = 0

        # 8-bit padding length
        if self.has_padding():
            self.pad_length = encoded[cur_byte]
            cur_byte = cur_byte+1

        # Variable length data payload
        self.data = encoded[cur_byte:cur_byte+length-self.pad_length]
        cur_byte = cur_byte + length - self.pad_length
        # The rest of the bytes are padding, we could verify the length but
        # we'll just ignore them

class headers_frame(frame):
    def __init__(self):
        frame.__init__(self, frame_type.HEADERS)
        self.pad_length = 0
        self.exclusive_dependency = False
        self.stream_dependency = 0x0
        self.weight = 0
        self.header_block_fragment = bytearray()

    def has_padding(self):
        return self.is_flag_set(headers_flags.PADDED)

    def has_priority(self):
        return self.is_flag_set(headers_flags.PRIORITY)

    def encode_payload(self):
        encoded = bytearray(6 + len(self.header_block_fragment) + self.pad_length)
        cur_byte = 0

        # 8-bit padding length
        if self.has_padding():
            encoded[cur_byte] = self.pad_length & 0xff
            cur_byte = cur_byte + 1

        if self.has_priority():
            # 1-bit exclusive dependency flag and 31-bit stream dependency
            encoded[cur_byte:cur_byte+4] = self.stream_dependency.to_bytes(4, 'big')
            if self.exclusive_dependency:
                encoded[cur_byte] = encoded[cur_byte] | 0x80
            else:
                encoded[cur_byte] = encoded[cur_byte] & 0x7f

            # 8-bit frame weight
            encoded[cur_byte+4] = self.weight & 0xff
            cur_byte = cur_byte + 5

        # Variable-length header block fragment
        encoded[cur_byte:] = self.header_block_fragment
        cur_byte = cur_byte + len(self.header_block_fragment)

        # Variable-length padding
        if self.has_padding():
            encoded[cur_byte:] = urandom(pad_length)
            cur_byte = cur_byte + pad_length

        return encoded

    def decode_payload(self, encoded, length):
        cur_byte = 0

        # 8-bit padding length
        if self.has_padding():
            self.pad_length = encoded[cur_byte]
            cur_byte = cur_byte + 1

        if self.has_priority():
            # 1-bit exclusive dependency flag
            self.exclusive_dependency = (encoded[cur_byte] & 0x80) > 0
            # 31-bit stream dependency
            stream_dependency_bits = encoded[cur_byte:cur_byte+4]
            stream_dependency_bits[0] = stream_dependency_bits[0] & 0x7f
            self.stream_dependency = int.from_bytes(stream_dependency_bits, 'big')
            # 8-bit weight
            self.weight = encoded[cur_byte+4]
            cur_byte = cur_byte + 5

        # Variable-length header block fragment, must be decoded by an hpack ctx
        self.header_block_fragment = encoded[cur_byte:cur_byte+length-self.pad_length]
        cur_byte = cur_byte + length - self.pad_length
        # We can ignore the padding

class settings_identifiers(IntEnum):
    HEADERS_TABLE_SIZE = 0x1
    ENABLE_PUSH = 0x2
    MAX_CONCURRENT_STREAMS = 0x3
    INITIAL_WINDOW_SIZE = 0x4
    MAX_FRAME_SIZE = 0x5
    MAX_HEADER_LIST_SIZE = 0x6

class settings_frame(frame):
    def __init__(self):
        frame.__init__(self, frame_type.SETTINGS)
        self.params = {}

    def set_param(self, identifier, value):
        if identifier not in settings_identifiers:
            raise Exception("Invalid SETTINGS identifier {:d}", idx)
        self.params[identifier] = value

    def encode_payload(self):
        # Maximum size is 36 bytes (6 different identifiers, 2 bytes to store the identifier and 4 bytes to store the value)
        encoded = bytearray(36)
        cur_byte = 0

        for idx,val in enumerate(self.params):
            encoded[cur_byte:] = struct.pack("!HI", idx, val)
            cur_byte = cur_byte + 6

        if self.is_flag_set(settings_flags.ACK) and cur_byte > 0:
            raise Exception("Settings frame must not set ACK alongside parameters")

        # Only return the bytes we used
        return encoded[0:cur_byte]

    def decode_payload(self, encoded, length):
        if self.is_flag_set(settings_flags.ACK) and length > 0:
            raise Exception("Settings frame must not set ACK alongside parameters")

        cur_byte = 0
        while cur_byte < length:
            idx,val = struct.unpack_from("!HI", encoded, cur_byte)
            self.params[idx] = val
            cur_byte = cur_byte + 6

class connection_error(IntEnum):
    NO_ERROR = 0x0
    PROTOCOL_ERROR = 0x1
    INTERNAL_ERROR = 0x2
    FLOW_CONTROL_ERROR = 0x3
    SETTINGS_TIMEOUT = 0x4
    STREAM_CLOSED = 0x5
    FRAME_SIZE_ERROR = 0x6
    REFUSED_STREAM = 0x7
    CANCEL = 0x8
    COMPRESSION_ERROR = 0x9
    CONNECT_ERROR = 0xa
    ENHANCE_YOUR_CALM = 0xb
    INADEQUATE_SECURITY = 0xc
    HTTP_1_1_REQUIRED = 0xd

class goaway_frame(frame):
    def __init__(self, error = connection_error.NO_ERROR, debug_data = None):
        frame.__init__(self, frame_type.GOAWAY)
        self.last_stream_id = 0
        self.error_code = error
        self.debug_data = debug_data

    def encode_payload(self):
        encoded = struct.pack("!HH", self.last_stream_id, self.error_code)
        # First bit is reserved
        encoded[0] = encoded[0] & 0x7f
        encoded.append(self.debug_data)
        return encoded

    def decode_payload(self, encoded, length):
        self.last_stream_id = encoded[0:4]
        self.error_code = encoded[4:8]
        self.debug_data = encoded[8:]
