"""
This module contains code to build simple PDFs for testing.

This is for testing only! The generated PDF files are checked for conformance
individually.

***DO NOT USE THIS MODULE FOR PRODUCTION CODE. IT IS ENTIRELY UNTESTED.***

"""



class Stream(object):

    "A PDF stream."

    def __init__(self, data=b""):
        self.info = {
            'Length': len(data),
        }
        self.data = data

    def append(self, new_data):
        "Add more data to the stream, updating the info dict."
        self.data += new_data
        self.info['Length'] = len(self.data)


class Writer(object):

    """
    Class to help write a PDF object to a file.

    `outfile` should have a `.write` method accepting a single `bytes` object
    as an argument. `root` should be a `dict` representing the PDF root
    object.

    """

    HEADER = b"%PDF-1.7\n"

    def __init__(self, outfile, root):
        self.outfile = outfile
        self.obj_stack = [(1, root)]
        self.offsets = {1: len(self.HEADER)}
        self.next_free_id = 2
        self.pdf_ids = {}  # maps id(dict_obj) to their PDF id numbers

    def write_pdf(self):
        self.outfile.write(self.HEADER)
        while self.obj_stack:
            obj_id, obj = self.obj_stack.pop()
            obj_bytes = self.convert_obj(obj, obj_id)
            self.offsets[obj_id] = self.outfile.tell()
            self.outfile.write(obj_bytes)
        xref_offset = self.outfile.tell()
        xref = self.make_xref()
        self.outfile.write(xref)
        trailer = self.make_trailer(xref_offset)
        self.outfile.write(trailer)

    def convert_obj(self, obj, obj_id):
        """
        Converts a dict into a PDF object byte sequence.

        `obj` -- a `dict` or `Stream` to be converted into a bytestream in
                 PDF bytes format.
        `obj_id` -- the numeric ID of the object.

        Returns `obj_bytes`, where `obj_bytes` are the `bytes` representing
        `obj` in PDF format. Extends `self.obj_stack` with any objects it
        finds that need converting.

        """
        ret = [b"%d 0 obj\n" % obj_id]
        if isinstance(obj, Stream):
            ret.append(self.convert_literal(obj.info, force_inline=True))
            ret.append(b"\nstream\n")
            ret.append(obj.data)
            ret.append(b"\nendstream\n")
        else:
            ret.append(self.convert_literal(obj, force_inline=True))
        ret.append(b"endobj\n")
        self.pdf_ids[id(obj)] = obj_id
        return b"".join(ret)

    def convert_literal(self, val, force_inline=False):
        """
        Convert a Python literal into its literal PDF representation.

        If `force_inline` is True and val is a dictionary, it is rendered to
        bytes directly. Otherwise it is added to the object stack and
        rendered as an indirect object. `Stream` objects are always rendered
        indirectly, and other objects are always rendered directly.

        """
        if isinstance(val, bytes):
            if val.startswith(b'/'):  # it's a name
                return val
            elif val.startswith(b'\\'):  # ignore starting slashes [to escape
                                         # leading backslashes in a string]
                val = val[1:]
            ret = [b"<"]
            for char in val:
                hex_val = hex(ord(char))[2:]  # strip leading '0x'
                if len(hex_val) == 1:
                    ret.append(b'0')
                ret.append(hex_val)
            ret.append(b">")
            return b"".join(ret)
        elif val is None:
            return b"null"
        elif isinstance(val, list):
            return b"[%s]" % " ".join(map(self.convert_literal, val))
        elif isinstance(val, (int, long, float)):
            return str(val)
        elif force_inline and isinstance(val, dict):
            ret = [b"<<"]
            for key, val2 in val.items():
                if val2 is not None:
                    ret.append(b"\n   /%s %s" % (key,
                                                 self.convert_literal(val2)))
            ret.append(b"\n>>\n")
            return b"".join(ret)
        elif isinstance(val, (dict, Stream)):
            try:
                sub_id = self.pdf_ids[id(val)]
            except KeyError:
                sub_id = self.next_free_id
                self.next_free_id += 1
                self.obj_stack.append((sub_id, val))
            return b"%d 0 R" % sub_id
        elif isinstance(val, Stream):
            try:
                sub_id = self.pdf_ids[id(val)]
            except KeyError:
                sub_id = self.next_free_id
                self.next_free_id += 1
                self.obj_stack.append((sub_id, val))

        else:
            raise ValueError("%s is not a valid PDF literal!" % val)

    def make_xref(self):
        "Make the xref table."
        num_objs = len(self.offsets) + 1
        ret = [b"xref\n0 %d\n0000000000 65535 f \n" % num_objs]
        for obj_id in xrange(1, num_objs):
            ret.append(b"%010d 00000 n \n" % self.offsets[obj_id])
        return b"".join(ret)

    def make_trailer(self, xref_offset):
        """Make the trailer object."""
        return (b"trailer\n" +
                b"<< /Size %d\n" % self.next_free_id +
                b"   /Root 1 0 R>>\n" +
                b"startxref\n{}\n%%EOF".format(xref_offset))


class Document(dict):

    "The PDF root object (AKA Catlaog)."

    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self['Type'] = '/Catalog'
        self['Pages'] = {
            'Type': '/Pages',
            'Count': 0,
            'Kids': [],
            # Parent is not required for the root pages node
        }

    def add_page(self, page):
        "Add a page to the document. Page should be a dict."
        page['Parent'] = self['Pages']
        self['Pages']['Count'] += 1
        self['Pages']['Kids'].append(page)

    def write_to_file(self, outfile):
        "Write the document to the given file object."
        writer = Writer(outfile, self)
        writer.write_pdf()


class Page(dict):

    "A page in a PDF document."

    def __init__(self, mediabox=None, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self['Type'] = '/Page'
        self['Parent'] = None
        self['Resources'] = {}
        if mediabox is  None:
            mediabox = [0, 0, 612, 792]
        self['MediaBox'] = mediabox
        self['Contents'] = None

    def add_content(self, graphics_cmd):
        "Adds the `graphics_cmd` bytes to the page's content stream."
        if self['Contents'] is None:
            self['Contents'] = Stream()
        self['Contents'].append(graphics_cmd)
