from hpack.hpack import hpack_ctx
from os import urandom
import socket
import hexdump
import h2

def decode_frames(encoded):
    frames = []
    while len(encoded) > 0:
        frame,bytes_read = h2.frame.decode_static(encoded)
        frames.append(frame)
        encoded = encoded[bytes_read:]
    return frames

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(('127.0.0.1', 12345))
    sock.sendall(h2.connection_preface)
    print('SEND:')
    hexdump.hexdump(h2.connection_preface)

    f = h2.settings_frame()
    f.set_param(h2.settings_identifiers.ENABLE_PUSH, 1)
    f.set_param(h2.settings_identifiers.HEADERS_TABLE_SIZE, 4096)
    f.stream_id = 0
    encoded = f.encode()
    sock.sendall(encoded)
    print('SEND', f)
    hexdump.hexdump(encoded)

    waiting = True
    while waiting:
        msg = sock.recv(512)
        frames = decode_frames(msg)
        print('RECV:',  frames)
        hexdump.hexdump(msg)
        for frame in frames:
            if isinstance(frame, h2.settings_frame) and frame.is_flag_set(h2.settings_flags.ACK):
                waiting = False

    f = h2.settings_frame()
    f.stream_id = 0
    f.set_flag(h2.settings_flags.ACK)
    encoded = f.encode()
    sock.sendall(encoded)
    print('SEND', f)
    hexdump.hexdump(encoded)

    ctx = hpack_ctx()
    ctx.start_encode()
    ctx.encode_header(":method","GET")
    ctx.encode_header(":scheme","http")
    ctx.encode_header(":path","/")
    ctx.encode_header(":authority","localhost")
    header_block = ctx.end_encode()

    f = h2.headers_frame()
    f.header_block_fragment = header_block
    f.set_flag(h2.headers_flags.END_STREAM)
    f.set_flag(h2.headers_flags.END_HEADERS)
    f.stream_id = 3
    encoded = f.encode()
    sock.sendall(encoded)
    print('SEND', f)
    hexdump.hexdump(encoded)

    waiting = True
    while waiting:
        msg = sock.recv(512)
        frames = decode_frames(msg)
        print('RECV:', frames)
        hexdump.hexdump(msg)
        for frame in frames:
            if isinstance(frame, h2.headers_frame):
                headers = ctx.decode_headers(frame.header_block_fragment)
                print(headers)
            if isinstance(frame, h2.data_frame) and len(frame.data) > 0:
                print(frame.data.decode('ascii'))
                waiting = False

if __name__ == "__main__":
    main()
