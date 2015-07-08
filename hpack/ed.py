
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

def encode_string_literal(string):
    encoded = encode_integer(len(string), 7)
    # Set the "huffman encoding" bit to 0
    encoded[0] = encoded[0] & 0x7f
    # Encode the string
    encoded.extend(string.encode('ascii'))
    return encoded

def decode_string_literal(encoded, start):
    length, bytes_read = decode_integer(encoded, start, 7)
    # We currently don't support huffman encoding
    if (encoded[0] & 0x80) > 1:
        raise Exception("Huffman encoding found, but it is currently unsupported")
    string = encoded[start + bytes_read:start + bytes_read + length].decode('ascii')
    return string, bytes_read+length
