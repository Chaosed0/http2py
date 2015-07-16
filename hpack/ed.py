import math
import binascii
import struct
import logging

logger = logging.getLogger('hpack')

huffman_encode_table = [
       (0x1ff8,13), (0x7fffd8,23), (0xfffffe2,28), (0xfffffe3,28), (0xfffffe4,28), (0xfffffe5,28), (0xfffffe6,28), (0xfffffe7,28),
       (0xfffffe8,28), (0xffffea,24), (0x3ffffffc,30), (0xfffffe9,28), (0xfffffea,28), (0x3ffffffd,30), (0xfffffeb,28), (0xfffffec,28),
       (0xfffffed,28), (0xfffffee,28), (0xfffffef,28), (0xffffff0,28), (0xffffff1,28), (0xffffff2,28), (0x3ffffffe,30), (0xffffff3,28),
       (0xffffff4,28), (0xffffff5,28), (0xffffff6,28), (0xffffff7,28), (0xffffff8,28), (0xffffff9,28), (0xffffffa,28), (0xffffffb,28),
       (0x14, 6), (0x3f8,10), (0x3f9,10), (0xffa,12), (0x1ff9,13), (0x15, 6), (0xf8, 8), (0x7fa,11),
       (0x3fa,10), (0x3fb,10), (0xf9, 8), (0x7fb,11), (0xfa, 8), (0x16, 6), (0x17, 6), (0x18, 6),
       (0x0, 5), (0x1, 5), (0x2, 5), (0x19, 6), (0x1a, 6), (0x1b, 6), (0x1c, 6), (0x1d, 6),
       (0x1e, 6), (0x1f, 6), (0x5c, 7), (0xfb, 8), (0x7ffc,15), (0x20, 6), (0xffb,12), (0x3fc,10),
       (0x1ffa,13), (0x21, 6), (0x5d, 7), (0x5e, 7), (0x5f, 7), (0x60, 7), (0x61, 7), (0x62, 7),
       (0x63, 7), (0x64, 7), (0x65, 7), (0x66, 7), (0x67, 7), (0x68, 7), (0x69, 7), (0x6a, 7),
       (0x6b, 7), (0x6c, 7), (0x6d, 7), (0x6e, 7), (0x6f, 7), (0x70, 7), (0x71, 7), (0x72, 7),
       (0xfc, 8), (0x73, 7), (0xfd, 8), (0x1ffb,13), (0x7fff0,19), (0x1ffc,13), (0x3ffc,14), (0x22, 6),
       (0x7ffd,15), (0x3, 5), (0x23, 6), (0x4, 5), (0x24, 6), (0x5, 5), (0x25, 6), (0x26, 6),
       (0x27, 6), (0x6, 5), (0x74, 7), (0x75, 7), (0x28, 6), (0x29, 6), (0x2a, 6), (0x7, 5),
       (0x2b, 6), (0x76, 7), (0x2c, 6), (0x8, 5), (0x9, 5), (0x2d, 6), (0x77, 7), (0x78, 7),
       (0x79, 7), (0x7a, 7), (0x7b, 7), (0x7ffe,15), (0x7fc,11), (0x3ffd,14), (0x1ffd,13), (0xffffffc,28),
       (0xfffe6,20), (0x3fffd2,22), (0xfffe7,20), (0xfffe8,20), (0x3fffd3,22), (0x3fffd4,22), (0x3fffd5,22), (0x7fffd9,23),
       (0x3fffd6,22), (0x7fffda,23), (0x7fffdb,23), (0x7fffdc,23), (0x7fffdd,23), (0x7fffde,23), (0xffffeb,24), (0x7fffdf,23),
       (0xffffec,24), (0xffffed,24), (0x3fffd7,22), (0x7fffe0,23), (0xffffee,24), (0x7fffe1,23), (0x7fffe2,23), (0x7fffe3,23),
       (0x7fffe4,23), (0x1fffdc,21), (0x3fffd8,22), (0x7fffe5,23), (0x3fffd9,22), (0x7fffe6,23), (0x7fffe7,23), (0xffffef,24),
       (0x3fffda,22), (0x1fffdd,21), (0xfffe9,20), (0x3fffdb,22), (0x3fffdc,22), (0x7fffe8,23), (0x7fffe9,23), (0x1fffde,21),
       (0x7fffea,23), (0x3fffdd,22), (0x3fffde,22), (0xfffff0,24), (0x1fffdf,21), (0x3fffdf,22), (0x7fffeb,23), (0x7fffec,23),
       (0x1fffe0,21), (0x1fffe1,21), (0x3fffe0,22), (0x1fffe2,21), (0x7fffed,23), (0x3fffe1,22), (0x7fffee,23), (0x7fffef,23),
       (0xfffea,20), (0x3fffe2,22), (0x3fffe3,22), (0x3fffe4,22), (0x7ffff0,23), (0x3fffe5,22), (0x3fffe6,22), (0x7ffff1,23),
       (0x3ffffe0,26), (0x3ffffe1,26), (0xfffeb,20), (0x7fff1,19), (0x3fffe7,22), (0x7ffff2,23), (0x3fffe8,22), (0x1ffffec,25),
       (0x3ffffe2,26), (0x3ffffe3,26), (0x3ffffe4,26), (0x7ffffde,27), (0x7ffffdf,27), (0x3ffffe5,26), (0xfffff1,24), (0x1ffffed,25),
       (0x7fff2,19), (0x1fffe3,21), (0x3ffffe6,26), (0x7ffffe0,27), (0x7ffffe1,27), (0x3ffffe7,26), (0x7ffffe2,27), (0xfffff2,24),
       (0x1fffe4,21), (0x1fffe5,21), (0x3ffffe8,26), (0x3ffffe9,26), (0xffffffd,28), (0x7ffffe3,27), (0x7ffffe4,27), (0x7ffffe5,27),
       (0xfffec,20), (0xfffff3,24), (0xfffed,20), (0x1fffe6,21), (0x3fffe9,22), (0x1fffe7,21), (0x1fffe8,21), (0x7ffff3,23),
       (0x3fffea,22), (0x3fffeb,22), (0x1ffffee,25), (0x1ffffef,25), (0xfffff4,24), (0xfffff5,24), (0x3ffffea,26), (0x7ffff4,23),
       (0x3ffffeb,26), (0x7ffffe6,27), (0x3ffffec,26), (0x3ffffed,26), (0x7ffffe7,27), (0x7ffffe8,27), (0x7ffffe9,27), (0x7ffffea,27),
       (0x7ffffeb,27), (0xffffffe,28), (0x7ffffec,27), (0x7ffffed,27), (0x7ffffee,27), (0x7ffffef,27), (0x7fffff0,27), (0x3ffffee,26),
       (0x3fffffff,30),
    ]
huffman_decode_table = {}
for idx,val in enumerate(huffman_encode_table):
    huffman_decode_table[val] = idx

def encode_integer(integer, prefix):
    # Make sure we don't get invalid prefix values
    assert(prefix <= 8 and prefix > 0)

    encoded = bytearray()
    prefix_max = pow(2,prefix) - 1

    # The rest of this is a translation of the pseudocode from the RFC
    if integer < prefix_max:
        encoded.append(integer & 0xFF)
        return encoded
 
    integer -= prefix_max
    encoded.append(0 | prefix_max)
    while integer >= 128:
        encoded.append(integer % 128 + 128)
        integer = integer // 128
    encoded.append(integer)
        
    return encoded

def decode_integer(encoded, start, prefix):
    # Make sure we don't get an invalid prefix value
    assert(prefix <= 8 and prefix > 0)

    prefix_max = pow(2,prefix) - 1
    integer = encoded[start] & prefix_max

    if integer < prefix_max:
        return integer,1
 
    # The rest of this is a translation of the pseudocode from the RFC
    exp = 0
    cont_bit = 1
    bytes_read = 1
    while cont_bit != 0:
        byte = encoded[start+bytes_read]
        integer = integer + (byte & 0x7f) * pow(2, exp)
        exp = exp + 7
        cont_bit = byte & 0x80
        bytes_read = bytes_read + 1
        
    return integer,bytes_read

def encode_string_literal(string, huffman=False):
    # Encode the string
    encoded_string = string.encode('ascii')
    if huffman is True:
        encoded_string = encode_huffman_string(encoded_string)

    encoded = encode_integer(len(encoded_string), 7)
    encoded.extend(encoded_string)
    # Set the "huffman encoding" bit
    encoded[0] = (encoded[0] & 0x7f) | (0x80 if huffman else 0x0)

    return encoded

def decode_string_literal(encoded, start):
    length, bytes_read = decode_integer(encoded, start, 7)
    # We currently don't support huffman encoding
    if (encoded[start] & 0x80) > 1:
        string = decode_huffman_string(encoded, start+bytes_read, length)
    else:
        string = encoded[start + bytes_read:start + bytes_read + length].decode('ascii')
    return string, bytes_read+length

def rshift(val, n):
    # Unsigned right shift
    return val>>n if val >= 0 else (val+0x100000000)>>n

def encode_huffman_string(string):
    encoded = bytearray(len(string))
    encoded_bit = 0
    idx = 0
    encoding_bit = 0

    logger.debug(" --- Huffman encoding start ---")

    while idx < len(string):
        logger.debug("Encoding byte %d (%c)", string[idx], chr(string[idx]))

        # Grab the encoding for the current character from the huffman encoding table
        char_encoding_tuple = huffman_encode_table[string[idx]]
        char_encoding = char_encoding_tuple[0]
        char_encoding_bits = char_encoding_tuple[1]

        logger.debug("Got encoding: 0x%s, %d bits, truncating at %d",
                '{:x}'.format(char_encoding), char_encoding_bits, encoding_bit)

        # Get only the bits we haven't packed yet from the encoding
        char_encoding_bits -= encoding_bit
        bitmask = (1 << char_encoding_bits) - 1
        char_encoding = char_encoding & bitmask

        logger.debug("Truncated encoding: 0x%s, %d bits", '{:x}'.format(char_encoding), char_encoding_bits)

        # Get the next byte and bit index we want to pack into
        byte_idx = encoded_bit // 8
        bit_idx = encoded_bit % 8
        bits_left = 8 - bit_idx

        pack_bits = 0
        # Move the current character encoding into the right position within
        # the byte we're packing into
        if char_encoding_bits >= bits_left:
            # We have more bits we need to pack than bits to pack into;
            # truncate the encoding
            pack_bits = rshift(char_encoding, char_encoding_bits - bits_left)
            encoded_bit = (byte_idx+1)*8
            encoding_bit += bits_left
        else:
            # We have less bits we need to pack than bits to pack into;
            # just move the bits into the right position within the byte
            pack_bits = char_encoding << bits_left - char_encoding_bits
            encoded_bit = byte_idx*8 + bit_idx + char_encoding_bits
            encoding_bit = encoding_bit + char_encoding_bits

        logger.debug("Packing 0x%s into byte %d at bit %d with %d bits left",
                '{:x}'.format(pack_bits), byte_idx, bit_idx, bits_left)

        # Add more bytes if we need to 
        if len(encoded) < byte_idx:
            encoded.append(0x0)

        # Pack the bits
        encoded[byte_idx] = encoded[byte_idx] | pack_bits

        if encoding_bit >= char_encoding_bits:
            encoding_bit = 0
            idx = idx+1

    # The last bits have to be the beginning of the EOF encoding
    if encoded_bit%8 != 0:
        logger.debug("Filling last bits with EOF")
        eof = huffman_encode_table[256]
        eof_encoding = rshift(eof[0], eof[1] - (8 - (encoded_bit % 8)))
        encoded[encoded_bit//8] |= eof_encoding

    encoded = encoded[:encoded_bit//8 + (1 if encoded_bit%8 > 0 else 0)]
    logger.debug("Got huffman encoding of bit length %d: %s", encoded_bit, encoded)
    logger.debug(" --- Huffman encoding end ---")
    return encoded

def decode_huffman_string(encoded, start, length):
    decoded = bytearray()
    decode_bytes = bytearray(8)
    decoded_bits = 0
    total_decoded_bits = 0
    for byte in encoded[start:]:
        for bit_idx in range(8):
            bit = rshift(byte & (1 << (7-bit_idx)), 7-bit_idx)
            decode_byte_idx = decoded_bits // 8
            decode_bytes[decode_byte_idx] = (decode_bytes[decode_byte_idx] << 1) | bit

            decoded_bits = decoded_bits + 1
            total_decoded_bits = total_decoded_bits + 1
            index = int.from_bytes(decode_bytes[:decode_byte_idx+1], 'little')
            byte_tuple = (index, decoded_bits)

            if byte_tuple in huffman_decode_table:
                decoded.append(huffman_decode_table[byte_tuple])
                decoded_bits = 0
                decode_bytes = bytearray(8)
            if total_decoded_bits >= length*8:
                break
        if total_decoded_bits >= length*8:
            break

    return decoded.decode('ascii')
