import unittest
from hpack import ed

class TestEncodeDecode(unittest.TestCase):

    def test_encode_integer(self):
        encoded = ed.encode_integer(20, 5)
        self.assertEqual(len(encoded), 1)
        self.assertEqual(encoded[0], 0x14)

        encoded = ed.encode_integer(20, 4)
        self.assertEqual(len(encoded), 2)
        self.assertEqual(encoded[0], 0x0f)
        self.assertEqual(encoded[1], 0x05)

        encoded = ed.encode_integer(15, 4)
        self.assertEqual(len(encoded), 2)
        self.assertEqual(encoded[0], 0x0f)
        self.assertEqual(encoded[1], 0x00)

        encoded = ed.encode_integer(4096, 5)
        self.assertEqual(len(encoded), 3)
        self.assertEqual(encoded[0], 0x1f)
        self.assertEqual(encoded[1], 0xe1)
        self.assertEqual(encoded[2], 0x1f)

    def test_decode_integer(self):
        decoded = ed.decode_integer(b'\x14', 0, 5)
        self.assertEqual(decoded, (20, 1))

        decoded = ed.decode_integer(b'\x0f\x05', 0, 4)
        self.assertEqual(decoded, (20, 2))

        decoded = ed.decode_integer(b'\x0f\x00', 0, 4)
        self.assertEqual(decoded, (15, 2))

        decoded = ed.decode_integer(b'\x1f\xe1\x1f', 0, 5)
        self.assertEqual(decoded, (4096, 3))

        decoded = ed.decode_integer(b'\x00\x00\x0f\x05\x00\x00', 2, 4)
        self.assertEqual(decoded, (20, 2))

        decoded = ed.decode_integer(b'\x00\x0f\x00\xff\xf0', 1, 4)
        self.assertEqual(decoded, (15, 2))

    def test_encode_string_literal(self):
        encoded = ed.encode_string_literal("test")
        self.assertEqual(encoded, b'\x04test')

        longstring = 'a'*4096
        encoded = ed.encode_string_literal(longstring)
        self.assertEqual(encoded, b'\x7f\x81\x1f' + longstring.encode('ascii'))


    def test_encode_string_literal_huffman(self):
        encoded = ed.encode_string_literal("test", True)
        self.assertEqual(encoded, b'\x83\x49\x50\x9f')

        longstring = 'a'*4096
        longstring_encoded = b'\x18\xc6\x31\x8c\x63' * (4096//8)
        encoded = ed.encode_string_literal(longstring, True)
        self.assertEqual(encoded, b'\xff\x81\x13' + longstring_encoded)

    def test_decode_string_literal(self):
        longstring = 'a'*4096

        encoded = b'\x04test'
        self.assertEqual(ed.decode_string_literal(encoded, 0), ('test', 5))

        encoded = b'\x7f\x81\x1f' + longstring.encode('ascii')
        self.assertEqual(ed.decode_string_literal(encoded, 0), (longstring, len(encoded)))

        encoded = b'\x00\x00\x00\x83\x49\x50\x9f\x00\x00\x00'
        self.assertEqual(ed.decode_string_literal(encoded, 3), ('test', 4))

    def test_decode_string_literal_huffman(self):
        longstring = 'a'*4096

        encoded = b'\x83\x49\x50\x9f'
        self.assertEqual(ed.decode_string_literal(encoded, 0), ('test', 4))

        encoded = b'\xff\x81\x13' + (b'\x18\xc6\x31\x8c\x63' * (4096//8))
        self.assertEqual(ed.decode_string_literal(encoded, 0), (longstring, len(encoded)))

        encoded = b'\xff\xff\xff\xff\xf0' + b'\xff\x81\x13' + (b'\x18\xc6\x31\x8c\x63' * (4096//8)) + b'\x0f\xff'
        self.assertEqual(ed.decode_string_literal(encoded, 5), (longstring, 3 + 5 * (4096//8)))

if __name__ == '__main__':
    unittest.main()
