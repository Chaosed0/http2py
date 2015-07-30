import unittest
from hpack import hpack

class Example():
    def __init__(self, decoded, encoded, huffman_encoded):
        self.decoded = decoded
        self.encoded = encoded
        self.huffman_encoded = huffman_encoded

class TestHpack(unittest.TestCase):
    # RFC7541 examples
    examples = [
            Example([
                    (':method', 'GET'),
                    (':scheme', 'http'),
                    (':path', '/'),
                    (':authority', 'www.example.com')
                ],
                b'\x82\x86\x84\x41\x0f\x77\x77\x77\x2e\x65\x78\x61\x6d\x70\x6c\x65\x2e\x63\x6f\x6d',
                b'\x82\x86\x84\x41\x8c\xf1\xe3\xc2\xe5\xf2\x3a\x6b\xa0\xab\x90\xf4\xff'
            ),
            Example([
                    (':method', 'GET'),
                    (':scheme', 'http'),
                    (':path', '/'),
                    (':authority', 'www.example.com'),
                    ('cache-control', 'no-cache')
                ],
                b'\x82\x86\x84\xbe\x58\x08\x6e\x6f\x2d\x63\x61\x63\x68\x65',
                b'\x82\x86\x84\xbe\x58\x86\xa8\xeb\x10\x64\x9c\xbf'
            ),
            Example([
                    (':method', 'GET'),
                    (':scheme', 'https'),
                    (':path', '/index.html'),
                    (':authority', 'www.example.com'),
                    ('custom-key', 'custom-value')
                ],
                b'\x82\x87\x85\xbf\x40\x0a\x63\x75\x73\x74\x6f\x6d\x2d\x6b\x65\x79\x0c\x63\x75\x73\x74\x6f\x6d\x2d\x76\x61\x6c\x75\x65',
                b'\x82\x87\x85\xbf\x40\x88\x25\xa8\x49\xe9\x5b\xa9\x7d\x7f\x89\x25\xa8\x49\xe9\x5b\xb8\xe8\xb4\xbf'
             )
        ]

    def assertHeaderListMatchesDict(self, header_list, header_dict):
        num_headers = 0
        for header in header_list:
            name, value = header
            self.assertIn(name, header_dict)
            self.assertEqual(header_dict[name], value)
            num_headers += 1
        self.assertEqual(num_headers, len(header_dict))

    def test_encode_without_huffman_encoding(self):
        ctx = hpack.ctx(huffman_encoding=False)

        for example in TestHpack.examples:
            ctx.start_encode()
            ctx.encode_header_list(example.decoded)
            encoded = ctx.end_encode()
            self.assertEqual(encoded, example.encoded)

    def test_encode_with_huffman_encoding(self):
        ctx = hpack.ctx(huffman_encoding=True)

        for example in TestHpack.examples:
            ctx.start_encode()
            ctx.encode_header_list(example.decoded)
            encoded = ctx.end_encode()
            self.assertEqual(encoded, example.huffman_encoded)

    def test_decode(self):
        ctx = hpack.ctx()
        for example in TestHpack.examples:
            decoded = ctx.decode_headers(example.encoded)
            self.assertHeaderListMatchesDict(example.decoded, decoded)

        ctx = hpack.ctx()
        for example in TestHpack.examples:
            decoded = ctx.decode_headers(example.huffman_encoded)
            self.assertHeaderListMatchesDict(example.decoded, decoded)
