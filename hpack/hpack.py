from enum import Enum
from . import ed
from . import st

class index_opts(Enum):
    INCREMENTAL = 1
    WITHOUT = 2
    NEVER = 3
    ALREADY_INDEXED = 4
    UNKNOWN = 5

class hpack_ctx:
    def __init__(self, max_table_size_in=256, max_table_size_out=256):
        self.table_in = st.header_table(max_table_size_in)
        self.table_out = st.header_table(max_table_size_out)
        self.header_bytes = None
        self.headers_out = {}

    def start_encode(self):
        self.header_bytes = bytearray()

    def encode_header(self, name, value, index_opt=index_opts.INCREMENTAL):
        if self.header_bytes is None:
            raise Exception("Must call start_encode before encode_header")
        if len(value) == 0:
            value = None

        index = self.table_out.find_index_by_field(name, value)
        # There are seven possibilities here, defined in section 6.1 & 6.2 of the
        # RFC. Basically combinations of indexing options and what is already
        # indexed.
        if index is not None:
            if value == self.table_out.find_field_by_index(index).value:
                # Both name and value are indexed
                encoded = ed.encode_integer(index, 7)
                encoded[0] = (encoded[0] & 0x7f) | 0x80
            else:
                if index_opt is index_opts.INCREMENTAL:
                    # Just name is indexed and we want incremental indexing
                    encoded = ed.encode_integer(index, 6)
                    # Set the incremental indexing bits
                    encoded[0] = (encoded[0] & 0x3f) | 0x40
                    # Index the entire header field
                    self.table_out.new_header(name, value)
                elif index_opt is index_opts.WITHOUT:
                    # Just name is indexed and we don't want indexing
                    encoded = ed.encode_integer(index, 4)
                    # Set the bits
                    encoded[0] = encoded[0] & 0x0f
                else:
                    # Just name is indexed and we don't want indexing
                    encoded = ed.encode_integer(index, 4)
                    # Set the bits
                    encoded[0] = (encoded[0] & 0x0f) | 0x10
                # Encode the value
                encoded.extend(ed.encode_string_literal(value))
        else:
            encoded = bytearray()
            encoded.append(0)
            if index_opt is index_opts.INCREMENTAL:
                # Neither name nor value is indexed and we want incremental indexing
                encoded[0] = (encoded[0] & 0x3f) | 0x40
                # Index the entire header field
                self.table_out.new_header(name, value)
            elif index_opt is index_opts.WITHOUT:
                # Just name is indexed and we don't want indexing
                encoded[0] = encoded[0] & 0x0f
            else:
                # Just name is indexed and we don't want indexing
                encoded[0] = (encoded[0] & 0x0f) | 0x10
            # Encode the name and value
            encoded.extend(ed.encode_string_literal(name))
            encoded.extend(ed.encode_string_literal(value))

        self.header_bytes.extend(encoded)

    def end_encode(self):
        header_bytes = self.header_bytes
        self.header_bytes = None
        return header_bytes

    def get_index_opt_from_byte(self, byte):
        if byte & 0x80 > 0:
            return index_opts.ALREADY_INDEXED
        elif byte & 0x40 > 0:
            return index_opts.INCREMENTAL
        elif byte & 0x20 > 0:
            return index_opts.UNKNOWN
        elif byte & 0x10 > 0:
            return index_opts.NEVER
        elif byte & 0xf0 == 0:
            return index_opts.WITHOUT
        else:
            return index_opts.UNKNOWN

    def decode_headers(self, encoded):
        decoded_headers = {}
        cur_byte = 0
        bytes_read = 0

        while cur_byte < len(encoded):
            # Look at the next header type
            index_opt = self.get_index_opt_from_byte(encoded[cur_byte])
            if index_opt == index_opts.ALREADY_INDEXED:
                # This header is indexed and we should just find it in the
                # table
                index, bytes_read = ed.decode_integer(encoded, cur_byte, 7)
                header_field = self.table_in.find_field_by_index(index)
                if header_field is None:
                    # Protocol error
                    return
                name,value = header_field
            else:
                # Figure out how many bits the index takes up
                if index_opt == index_opts.INCREMENTAL:
                    index_bits = 6
                elif index_opt == index_opts.WITHOUT:
                    index_bits = 4
                elif index_opt == index_opts.NEVER:
                    index_bits = 4

                # Decode the header name and value
                index,bytes_read = ed.decode_integer(encoded, cur_byte, index_bits)
                cur_byte = cur_byte + bytes_read
                if index > 0:
                    # Name is contained within the table
                    header_field = self.table_in.find_field_by_index(index)
                    name = header_field.name
                else:
                    # Name is explicit
                    name,bytes_read = ed.decode_string_literal(encoded, cur_byte)
                    cur_byte = cur_byte + bytes_read

                # Value is always explicit if not in ALREADY_INDEXED mode
                value,bytes_read = ed.decode_string_literal(encoded, cur_byte)

                if index_opt == index_opts.INCREMENTAL:
                    # Incremental; add to the table
                    self.table_in.new_header(name, value)

            decoded_headers[name] = value
            cur_byte = cur_byte + bytes_read

        return decoded_headers
