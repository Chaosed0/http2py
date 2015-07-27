from hpack.hpack import hpack_ctx
from hpack import ed
from os import urandom
import socket
import logging
import hexdump
import ssl
import h2

def decode_frames(encoded):
    frames = []
    while len(encoded) > 0:
        frame,bytes_read = h2.frame.decode_static(encoded)
        frames.append(frame)
        encoded = encoded[bytes_read:]
    return frames


def test_huffman_encode():
    encoded_string = ed.encode_huffman_string("lolwut".encode('ascii'))
    decoded_string = ed.decode_huffman_string(encoded_string, 0, len(encoded_string))
    logging.debug(decoded_string)

def test_request():
    logging.info("Started test program for h2")

    logging.debug("Connecting socket")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sslcontext = ssl.create_default_context()
    sslcontext.check_hostname = False
    sslcontext.verify_mode = ssl.CERT_NONE
    sslcontext.set_alpn_protocols(['h2'])
    sock = sslcontext.wrap_socket(sock)

    sock.connect(('127.0.0.1', 443))

    if sock.selected_alpn_protocol() != 'h2':
        logging.warn("Server did not negotiate h2 (alpn)")
        return

    sock.sendall(h2.connection_preface)
    logging.debug("SEND:")
    hexdump.hexdump(h2.connection_preface)
    ctx = hpack_ctx()

    f = h2.settings_frame()
    f.set_param(h2.settings_identifiers.ENABLE_PUSH, 1)
    f.set_param(h2.settings_identifiers.HEADERS_TABLE_SIZE, 4096)
    f.stream_id = 0
    encoded = f.encode()
    sock.sendall(encoded)
    logging.debug("SEND: %s",f)
    hexdump.hexdump(encoded)

    waiting = True
    while waiting:
        msg = sock.recv(512)
        logging.debug('RECV:')
        hexdump.hexdump(msg)
        frames = decode_frames(msg)
        logging.debug('%s', frames)
        for frame in frames:
            if isinstance(frame, h2.settings_frame) and frame.is_flag_set(h2.settings_flags.ACK):
                waiting = False

    f = h2.settings_frame()
    f.stream_id = 0
    f.set_flag(h2.settings_flags.ACK)
    encoded = f.encode()
    sock.sendall(encoded)
    logging.debug("SEND: %s",f)
    hexdump.hexdump(encoded)

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
    logging.debug("SEND: %s",f)
    hexdump.hexdump(encoded)

    waiting = True
    while waiting:
        msg = sock.recv(512)
        logging.debug('RECV:')
        hexdump.hexdump(msg)
        frames = decode_frames(msg)
        logging.debug('%s', frames)
        for frame in frames:
            if isinstance(frame, h2.headers_frame):
                headers = ctx.decode_headers(frame.header_block_fragment)
                logging.debug("Headers: %s",headers)
            if isinstance(frame, h2.data_frame) and len(frame.data) > 0:
                logging.debug("Data: %s",frame.data.decode('ascii'))
                waiting = False
            if isinstance(frame, h2.goaway_frame) or len(msg) == 0:
                waiting = False
                return

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
    f.stream_id = 5
    encoded = f.encode()
    sock.sendall(encoded)
    logging.debug("SEND: %s",f)
    hexdump.hexdump(encoded)

    waiting = True
    while waiting:
        msg = sock.recv(512)
        logging.debug('RECV:')
        hexdump.hexdump(msg)
        frames = decode_frames(msg)
        logging.debug('%s', frames)
        for frame in frames:
            if isinstance(frame, h2.headers_frame):
                headers = ctx.decode_headers(frame.header_block_fragment)
                print(headers)
                logging.debug("Headers: %s",headers)
            if isinstance(frame, h2.data_frame) and len(frame.data) > 0:
                logging.debug("Data: %s",frame.data.decode('ascii'))
                waiting = False
            if isinstance(frame, h2.goaway_frame) or len(msg) == 0:
                waiting = False
                return

logging.basicConfig(format="[%(levelname)s] %(filename)s:%(lineno)d %(funcName)s(): %(message)s", level=logging.DEBUG)
logging.getLogger('hpack').setLevel(logging.INFO)
