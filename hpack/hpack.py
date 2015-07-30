import logging
from enum import Enum
from . import ed
from . import table

logger = logging.getLogger('hpack')

class index_opts(Enum):
    INCREMENTAL = 1
    WITHOUT = 2
    NEVER = 3
    ALREADY_INDEXED = 4
    MAX_SIZE_UPDATE = 5
    UNKNOWN = 6

class ctx:
    def __init__(self, max_table_size_in=4096, max_table_size_out=4096, huffman_encoding=True):
        self.table_decode = table.header_table(max_table_size_in)
        self.table_encode = table.header_table(max_table_size_out)
        self.header_bytes = None
        self.headers_out = {}
        self.use_huffman_encoding = huffman_encoding

    def start_encode(self):
        self.header_bytes = bytearray()

    def encode_header_dict(self, header_dict, index_opt=index_opts.INCREMENTAL):
        for name in header_dict:
            self.encode_header(name, header_dict[name], index_opt)

    def encode_header_list(self, header_list, index_opt=index_opts.INCREMENTAL):
        for header in header_list:
            self.encode_header(header[0], header[1], index_opt)

    def encode_header(self, name, value, index_opt=index_opts.INCREMENTAL):
        if self.header_bytes is None:
            raise Exception("Must call start_encode before encode_header")
        if len(value) == 0:
            value = None

        logger.debug("Encoding header '%s': '%s'", name, value)

        index = self.table_encode.find_index_by_field(name, value)
        # There are seven possibilities here, defined in section 6.1 & 6.2 of the
        # RFC. Basically combinations of indexing options and what is already
        # indexed.
        if index is not None:
            if value == self.table_encode.find_field_by_index(index).value:
                logger.debug("Found header name and value in table")
                # Both name and value are indexed, just pull the index and
                # encode that
                encoded = ed.encode_integer(index, 7)
                encoded[0] = (encoded[0] & 0x7f) | 0x80
            else:
                logger.debug("Found header name, but not value, in table")
                # Just the name is indexed
                if index_opt is index_opts.INCREMENTAL:
                    # Index now
                    encoded = ed.encode_integer(index, 6)
                    encoded[0] = (encoded[0] & 0x3f) | 0x40
                    logger.debug("Indexing header")
                    self.table_encode.new_header(name, value)
                elif index_opt is index_opts.WITHOUT:
                    # Don't index now
                    encoded = ed.encode_integer(index, 4)
                    encoded[0] = encoded[0] & 0x0f
                else:
                    # Never index this
                    encoded = ed.encode_integer(index, 4)
                    encoded[0] = (encoded[0] & 0x0f) | 0x10
                # Encode the value
                encoded.extend(ed.encode_string_literal(value, self.use_huffman_encoding))
        else:
            logger.debug("Did not find header in table")
            # Neither the name or value is indexed
            encoded = bytearray()
            encoded.append(0)
            if index_opt is index_opts.INCREMENTAL:
                # Index now
                encoded[0] = (encoded[0] & 0x3f) | 0x40
                # Index the header field
                logger.debug("Indexing header")
                self.table_encode.new_header(name, value)
            elif index_opt is index_opts.WITHOUT:
                # Don't index
                encoded[0] = encoded[0] & 0x0f
            else:
                # Never index
                encoded[0] = (encoded[0] & 0x0f) | 0x10
            # Encode the name and value
            encoded.extend(ed.encode_string_literal(name, self.use_huffman_encoding))
            encoded.extend(ed.encode_string_literal(value, self.use_huffman_encoding))

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
            return index_opts.MAX_SIZE_UPDATE
        elif byte & 0x10 > 0:
            return index_opts.NEVER
        elif byte & 0xf0 == 0:
            return index_opts.WITHOUT
        else:
            print("Found unknown index_opt", byte)
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
                header_field = self.table_decode.find_field_by_index(index)
                if header_field is None:
                    # Protocol error
                    logger.warning("Protocol Error: Couldn't find index %d in decode table", index)
                    logger.debug("Decode dynamic table: %s", self.table_decode.dynamic_table)
                    return None
                name,value = header_field
            else:
                # Figure out how many bits the index takes up
                if index_opt == index_opts.INCREMENTAL:
                    index_bits = 6
                elif index_opt == index_opts.WITHOUT:
                    index_bits = 4
                elif index_opt == index_opts.NEVER:
                    index_bits = 4
                elif index_opt == index_opts.MAX_SIZE_UPDATE:
                    index_bits = 5

                # Decode the header name and value
                index,bytes_read = ed.decode_integer(encoded, cur_byte, index_bits)
                cur_byte = cur_byte + bytes_read

                if index_opt == index_opts.MAX_SIZE_UPDATE:
                    # Special path - just update the max table size
                    self.table_decode.set_max_size(index)
                    logger.debug("Max decode dynamic table size updated to %d", index)
                    continue

                if index > 0:
                    # Name is contained within the table
                    header_field = self.table_decode.find_field_by_index(index)
                    name = header_field.name
                else:
                    # Name is explicit
                    name,bytes_read = ed.decode_string_literal(encoded, cur_byte)
                    cur_byte = cur_byte + bytes_read

                # Value is always explicit if not in ALREADY_INDEXED mode
                value,bytes_read = ed.decode_string_literal(encoded, cur_byte)

                if index_opt == index_opts.INCREMENTAL:
                    # Incremental; add to the table
                    self.table_decode.new_header(name, value)
                    logger.debug("New header added to the decoder dynamic table: %s", self.table_decode.dynamic_table)

            logger.debug("Read header '%s: %s' (index type: %s)", name, value, index_opt.name)

            decoded_headers[name] = value
            cur_byte = cur_byte + bytes_read

        return decoded_headers
