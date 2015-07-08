from hpack.hpack import hpack_ctx
from os import urandom
import h2

def main():
    print(h2.connection_preface)

    f = h2.settings_frame()
    f.set_param(h2.settings_identifiers.ENABLE_PUSH, 1)
    f.set_param(h2.settings_identifiers.HEADERS_TABLE_SIZE, 4096)
    f.stream_id = 3
    print(f.encode())

    ctx = hpack_ctx()
    ctx.start_encode()
    ctx.encode_header(":method","GET")
    ctx.encode_header(":scheme","http")
    ctx.encode_header(":path","/")
    ctx.encode_header(":authority","localhost")
    header_block = ctx.end_encode()
    print(header_block)

    f = h2.headers_frame()
    f.header_block_fragment = header_block
    f.set_flag(h2.headers_flags.END_HEADERS)
    f.stream_id = 3
    print(f.encode())

    f = h2.data_frame()
    f.stream_id = 3
    f.data = urandom(16)
    print(f.encode())


if __name__ == "__main__":
    main()
