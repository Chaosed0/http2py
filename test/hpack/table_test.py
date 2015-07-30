import unittest
from hpack import table

class TestHpackTable(unittest.TestCase):

    def assertHeaderEquals(self, header, name, value):
        self.assertEquals(header.name, name)
        self.assertEquals(header.value, value)

    def test_dynamic_table_add(self):
        hpack_table = table.header_table(4096)
        hpack_table.new_header("name", "value")
        self.assertEquals(hpack_table.length(), 63)
        self.assertEquals(hpack_table.dynamic_size(), 41)
        self.assertEquals(hpack_table.find_index_by_field("name", None), hpack_table.length()-1)

        hpack_table.new_header("name2", "value2")
        self.assertEquals(hpack_table.length(), 64)
        self.assertEquals(hpack_table.dynamic_size(), 84)
        self.assertEquals(hpack_table.find_index_by_field("name2", None), hpack_table.length()-2)
        self.assertEquals(hpack_table.find_index_by_field("name", None), hpack_table.length()-1)

    def test_dynamic_table_evict(self):
        hpack_table = table.header_table(128)

        hpack_table.new_header("a", "aaaaaaa")
        self.assertEquals(hpack_table.dynamic_size(), 40)
        hpack_table.new_header("b", "aaaaaaa")
        self.assertEquals(hpack_table.dynamic_size(), 80)
        hpack_table.new_header("c", "aaaaaaa")
        self.assertEquals(hpack_table.dynamic_size(), 120)
        hpack_table.new_header("d", "aaaaaaa")
        self.assertEquals(hpack_table.dynamic_size(), 120)
        self.assertEquals(hpack_table.find_index_by_field("a", "aaaaaaa"), None)
        hpack_table.new_header("e", "aaaaaaa")
        self.assertEquals(hpack_table.dynamic_size(), 120)
        self.assertEquals(hpack_table.find_index_by_field("b", "aaaaaaa"), None)

    def test_table_find_by_field(self):
        hpack_table = table.header_table(4096)

        hpack_table.new_header(":status", "503")
        hpack_table.new_header(":path", "/about.html")
        hpack_table.new_header("name", "value")
        hpack_table.new_header("cookie", "JSESSIONID")

        self.assertEquals(hpack_table.find_index_by_field(":status", "123"), 8)
        self.assertEquals(hpack_table.find_index_by_field(":path", "/blog.html"), 4)
        self.assertEquals(hpack_table.find_index_by_field("name", "notvalue"), hpack_table.length()-3)
        self.assertEquals(hpack_table.find_index_by_field("cookie", "monster"), 32)

        self.assertEquals(hpack_table.find_index_by_field(":status", "503"), hpack_table.length()-1)
        self.assertEquals(hpack_table.find_index_by_field(":path", "/about.html"), hpack_table.length()-2)
        self.assertEquals(hpack_table.find_index_by_field("name", "value"), hpack_table.length()-3)
        self.assertEquals(hpack_table.find_index_by_field("cookie", "JSESSIONID"), hpack_table.length()-4)

    def test_table_find_by_index(self):
        hpack_table = table.header_table(4096)
        hpack_table.new_header("name", "value")
        hpack_table.new_header("name2", "value2")

        self.assertHeaderEquals(hpack_table.find_field_by_index(1), ":authority", None)
        self.assertHeaderEquals(hpack_table.find_field_by_index(12), ":status", "400")
        self.assertHeaderEquals(hpack_table.find_field_by_index(61), "www-authenticate", None)
        self.assertHeaderEquals(hpack_table.find_field_by_index(62), "name2", "value2")
        self.assertHeaderEquals(hpack_table.find_field_by_index(63), "name", "value")
