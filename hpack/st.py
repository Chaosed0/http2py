from collections import namedtuple

class header_table:
    header_field = namedtuple("header_field", ["name", "value"])
    static_table = [
                header_field(None, None),
                header_field(":authority",None),
                header_field(":method","GET"),
                header_field(":method","POST"),
                header_field(":path","/"),
                header_field(":path","/index.html"),
                header_field(":scheme","http"),
                header_field(":scheme","https"),
                header_field(":status","200"),
                header_field(":status","204"),
                header_field(":status","206"),
                header_field(":status","304"),
                header_field(":status","400"),
                header_field(":status","404"),
                header_field(":status","500"),
                header_field("accept-charset",None),
                header_field("accept-encoding","gzip, deflate"),
                header_field("accept-language",None),
                header_field("accept-ranges",None),
                header_field("accept",None),
                header_field("access-control-allow-origin",None),
                header_field("age",None),
                header_field("allow",None),
                header_field("authorization",None),
                header_field("cache-control",None),
                header_field("content-disposition",None),
                header_field("content-encoding",None),
                header_field("content-language",None),
                header_field("content-length",None),
                header_field("content-location",None),
                header_field("content-range",None),
                header_field("content-type",None),
                header_field("cookie",None),
                header_field("date",None),
                header_field("etag",None),
                header_field("expect",None),
                header_field("expires",None),
                header_field("from",None),
                header_field("host",None),
                header_field("if-match",None),
                header_field("if-modified-since",None),
                header_field("if-none-match",None),
                header_field("if-range",None),
                header_field("if-unmodified-since",None),
                header_field("last-modified",None),
                header_field("link",None),
                header_field("location",None),
                header_field("max-forwards",None),
                header_field("proxy-authenticate",None),
                header_field("proxy-authorization",None),
                header_field("range",None),
                header_field("referer",None),
                header_field("refresh",None),
                header_field("retry-after",None),
                header_field("server",None),
                header_field("set-cookie",None),
                header_field("strict-transport-security",None),
                header_field("transfer-encoding",None),
                header_field("user-agent",None),
                header_field("vary",None),
                header_field("via",None),
                header_field("www-authenticate",None),
            ]
    st_len = len(static_table)
    static_table_rev = {}
    for index,field in enumerate(static_table):
        static_table_rev[field] = index

    def __init__(self, max_size):
        self.cur_size = 0
        self.max_size = max_size
        self.dynamic_table = []

    def length(self):
        return header_table.st_len + len(self.dynamic_table)

    def find_field_by_index(self, index):
        if index < header_table.st_len:
            return header_table.static_table[index]
        elif index < header_table.st_len + len(self.dynamic_table):
            return self.dynamic_table[index - self.st_len]
        else:
            return None

    def find_index_by_field(self, name, value):
        hfield = header_table.header_field(name, value)
        prelim_idx = None
        # Find the entire field if possible; otherwise, just find the name
        if hfield in header_table.static_table_rev:
            return header_table.static_table_rev[hfield]
        else:
            prelim_idx = next((idx for idx,header in enumerate(header_table.static_table) if header.name == name), None)

        for idx,val in enumerate(self.dynamic_table):
            if val == hfield:
                return idx + header_table.st_len
            elif val.name == name:
                prelim_idx = idx + header_table.st_len
        return prelim_idx

    def new_header(self, name, value):
        self.dynamic_table.insert(0, header_table.header_field(name, value))
        self.cur_size = self.cur_size + len(name) + len(value) + 32
        while self.cur_size > self.max_size:
            elem = self.dynamic_table.pop()
            self.cur_size = self.cur_size - (len(elem.name) + len(elem.value) + 32)
