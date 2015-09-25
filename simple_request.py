from hpack import hpack
import h2.connection
import asyncio
import socket
import logging
import hexdump
import functools
import ssl

def decode_frames(encoded):
    frames = []
    while len(encoded) > 0:
        frame,bytes_read = h2.frame.decode_static(encoded)
        frames.append(frame)
        encoded = encoded[bytes_read:]
    return frames

class h2_protocol_events(asyncio.Protocol):
    def __init__(self, connection, loop, sock):
        self.connection = connection
        self.loop = loop
        self.sock = sock

    def connection_made(self, transport):
        logging.debug("Made connection: %s", transport)
        if self.sock.selected_alpn_protocol() != 'h2':
            logging.warn("Server did not negotiate h2 (alpn)")
            self.terminate()
            return

    def data_received(self, data):
        logging.debug("RECV: ")
        hexdump.hexdump(data)
        self.connection.process_bytes(data)

    def connection_lost(self, exc):
        logging.debug("Connection lost: %s", exc)
        self.terminate()

    def terminate(self):
        logging.debug("Cancelling all leftover tasks")
        tasks = asyncio.Task.all_tasks(self.loop)
        for task in tasks:
            task.cancel()
        logging.debug("Stopping event loop")
        self.loop.stop()

class h2_comms():
    def __init__(self, url, port):
        self.url = url
        self.port = port
        self.loop = asyncio.SelectorEventLoop()
        self.sock = None
        callbacks = {
            "send": self.send_callback,
            "close": self.close_callback
        }
        self.connection = h2.connection.connection(callbacks)
        self.connected = False
        self.connection_future = None

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sslcontext = ssl.create_default_context()
        sslcontext.check_hostname = False
        sslcontext.verify_mode = ssl.CERT_NONE
        sslcontext.set_alpn_protocols(['http/1.1','h2'])
        self.sock = sslcontext.wrap_socket(self.sock)
        self.sock.connect((self.url, self.port))

        coro= self.loop.create_connection(
                lambda: h2_protocol_events(self.connection, self.loop, self.sock),
                sock=self.sock)

        self.connection_future = self.loop.create_task(coro)
        self.connection_future.add_done_callback(self.on_connect)

    def on_connect(self, future):
        exc = future.exception()
        if exc is not None:
            logging.warn("Got exception when connecting: %s", exc)
            self.loop.stop()
        else:
            self.connection.initiate()
            self.connected = True

    def send_request(self, headers, data=None):
        if not self.connected:
            if self.connection_future is None:
                logging.warn("Tried to send a request when not connected")
            else:
                self.connection_future.add_done_callback(lambda future:
                        self.loop.create_task(self.send_request_coro(headers, data, future)))
        else:
            self.loop.create_task(self.send_request_coro(headers, data))

    async def send_request_coro(self, headers, data, future=None):
        if future is None or future.exception() is None:
            logging.debug("Sending request")
            self.connection.send_request(headers, data)
        else:
            logging.debug("Aborting request send because we didn't connect successfully")

    def send_callback(self, data):
        logging.debug("SEND: ")
        hexdump.hexdump(data)
        self.sock.sendall(data)
        return 0

    def close_callback(self):
        self.loop.stop()
        return 0

def main():
    logging.info("Started test program for h2")
    comms = h2_comms('127.0.0.1', 10431) 

    logging.debug("Connecting socket")
    comms.connect()
    comms.send_request({
        ":method": "GET",
        ":scheme": "http",
        ":path": "/",
        ":authority": "localhost"
    })

    comms.loop.run_forever()
    comms.loop.close()

if __name__ == '__main__':
    logging.basicConfig(format="[%(levelname)s] %(filename)s:%(lineno)d %(funcName)s(): %(message)s", level=logging.DEBUG)
    logging.getLogger('hpack').setLevel(logging.INFO)
    main()
