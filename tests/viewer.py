"""
Provides a class to render a PDF (incompletely) using tkinter.

This is for testing only! The PDF spec has many, many corner cases that this
viewer does not handle separately. The purpose of this module is to allow
seeing PDFs as minecart sees them.

***DO NOT USE THIS MODULE FOR PRODUCTION CODE. IT IS ENTIRELY UNTESTED.***

"""

import ctypes
import Tkinter as tkinter
import tkFont
import ttk
import six
import minecart.content
import pdfminer.pdftypes

# Constants for AddFontResource in windll:
FR_PRIVATE = 0x10
FR_NOT_ENUM = 0x20


class AutoScrollbar(ttk.Scrollbar):  #pylint: disable=R0901

    """
    A scrollbar that hides itself if it's not needed.

    Only works if you use the grid geometry manager.
    """

    def set(self, lo_val, hi_val):  #pylint: disable=W0221
        if float(lo_val) <= 0.0 and float(hi_val) >= 1.0:
            self.grid_remove()
        else:
            self.grid()
        ttk.Scrollbar.set(self, lo_val, hi_val)

    def pack(self, **kw):
        raise tkinter.TclError("Cannot use pack with AutoScrollbar")

    def place(self, **kw):
        raise tkinter.TclError("Cannot use place with AutoScrollbar")


class ScrollingCanvas(tkinter.Canvas, object):  #pylint: disable=R0904,R0901

    """
    A canvas packed in a frame with scrollbars that appear when needed.
    """

    def __init__(self, master=None, cnf=None, **kwargs):
        self.frame = ttk.Frame(master)
        self.frame.grid_rowconfigure(0, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)
        self.xbar = AutoScrollbar(self.frame, orient=tkinter.HORIZONTAL)
        self.xbar.grid(row=1, column=0,
                       sticky=tkinter.E + tkinter.W)
        self.ybar = AutoScrollbar(self.frame)
        self.ybar.grid(row=0, column=1,
                       sticky=tkinter.S + tkinter.N)
        tkinter.Canvas.__init__(self, self.frame, cnf or {},
                                xscrollcommand=self.xbar.set,
                                yscrollcommand=self.ybar.set,
                                **kwargs)
        tkinter.Canvas.grid(self, row=0, column=0,
                            sticky=tkinter.E + tkinter.W + tkinter.N + tkinter.S)
        self.xbar.config(command=self.xview)
        self.ybar.config(command=self.yview)
        self.bind("<MouseWheel>", self.on_mousewheel)

    def pack(self, cnf=None, **kw):
        """Pack the parent frame."""
        self.frame.pack(cnf or {}, **kw)

    def grid(self, cnf=None, **kw):
        """Grid the parent frame."""
        self.frame.grid(cnf or {}, **kw)

    def on_mousewheel(self, event):
        "Called when the user tries to scroll with the mousewheel."
        self.yview_scroll(-1 * (event.delta / 120) ** 3, "units")

    def create_window(self, *args, **kw):
        "Make sure the mouse wheel is bound in children windows."
        widget = kw['window']
        widget.bind("<MouseWheel>", self.on_mousewheel)
        return tkinter.Canvas.create_window(self, *args, **kw)


def loadfont(fontpath, private=True, enumerable=False):
    '''
    Makes fonts located in file `fontpath` available to the font system.

    `private`     if True, other processes cannot see this font, and this
                  font will be unloaded when the process dies
    `enumerable`  if True, this font will appear when enumerating fonts

    See https://msdn.microsoft.com/en-us/library/dd183327(VS.85).aspx

    '''
    # This function was taken from digsby:
    # https://github.com/ifwe/digsby/blob/f5fe00244744aa131e07f09348d10563f3d8fa99/digsby/src/gui/native/win/winfonts.py#L15
    if isinstance(fontpath, six.binary_type):
        pathbuf = ctypes.create_string_buffer(fontpath)
        AddFontResourceEx = ctypes.windll.gdi32.AddFontResourceExA
    elif isinstance(fontpath, six.text_type):
        pathbuf = ctypes.create_unicode_buffer(fontpath)
        AddFontResourceEx = ctypes.windll.gdi32.AddFontResourceExW
    else:
        raise TypeError('fontpath must be of type {} or {}'.format(six.binary_type, six.text_type))
    flags = ((FR_PRIVATE if private else 0)
             | (FR_NOT_ENUM if not enumerable else 0))
    return AddFontResourceEx(ctypes.byref(pathbuf), flags, 0)


def loadfont_memory(data):
    "Load a given font stored in memory."
    num = ctypes.c_uint32()
    ctypes.windll.gdi32.AddFontMemResourceEx(data, len(data), 0,
                                             ctypes.byref(num))
    return num.value

def get_font_program(font_dict):
    """
    Extracts the font program from a PDF font dictionary.

    Returns a tuple (family_name, font_program_data, attrs), where
    family_name is the unicode name of the family that can be passed to
    `tkFont.Font` to create the font. `font_program_data` is the raw binary
    data of the embedded font, if any, that can be passed to
    `loadfont_memory` to load the font into the central repository, or `None`
    if the font isn't emebedded. `attrs` is a dictionary of kwargs that can
    be passed to `tkFont.Font`.

    """
    subtype = str(pdfminer.pdftypes.resolve1(font_dict['Subtype']))
    if subtype == '/Type1':
        return get_type1_font(font_dict)
    elif subtype == '/TrueType':
        return get_truetype_font(font_dict)
    elif subtype == '/Type0':
        return get_type0_font(font_dict)
    elif subtype == '/Type3':
        raise pdfminer.pdftypes.PDFNotImplementedError(
            "Type 3 Fonts are not supported by this viewer")
    elif subtype == '/MMType1':
        raise pdfminer.pdftypes.PDFNotImplementedError(
            "Multiple Master Fonts are not supported by this viewer")
    raise pdfminer.pdftypes.PDFValueError(
        "Unknown font subtype: '%s'" % subtype)

def extract_font_stream(font_dict, file_names):
    """
    Try to extract the embedded font program data from a font_dict.

    Returns (stream, data) or (None, None) if there is no embedded font.

    file_names is a sequence of keys to try looking in under the font
    descriptor. (E.g., ('/FontFile2', '/FontFile3') for TrueType fonts)

    """
    desc = pdfminer.pdftypes.resolve1(font_dict['FontDescriptor'])
    for name in file_names:
        try:
            stream = desc[name]
        except KeyError:
            pass
        else:
            stream = pdfminer.pdftypes.resolve1(stream)
            return stream, stream.get_data()
    return None, None

def get_type1_font(font_dict):
    # Convert base name to regular string without the leading backslash
    base_name = str(pdfminer.pdftypes.resolve1(font_dict.get('BaseFont')))[1:]
    if base_name in ('Times-Roman', 'Times-Bold', 'Times-Italic',
                     'Times-BoldItalic', 'Helvetica', 'Helvetica-Bold',
                     'Helvetica-Oblique', 'Helvetica-BoldOblique',
                     'Courier', 'Courier-Bold', 'Courier-Oblique',
                     'Courier-BoldOblique'):
        root_name = base_name.split("-", 1)[0]
        args = {}
        if 'Bold' in base_name:
            args['weight'] = 'bold'
        if 'Italic' in base_name or 'Oblique' in base_name:
            args['slant'] = 'italic'
        return root_name, None, args
    elif base_name in ('Symbol', 'ZapfDingbats'):
        raise pdfminer.pdftypes.PDFNotImplementedError(
            "The '%s' builtin font is not supported by this viewer." %
            base_name)
    if (base_name[6] == '+'
        and set(base_name[:6]) < set('ABCDEFGHIJKLMNOPQRSTUVWXYZ')):
        base_name = base_name[7:]
    data = extract_font_stream(font_dict, ('FontFile', 'FontFile3'))[1]
    return base_name, data, {}

def get_truetype_font(font_dict):
    base_name = str(pdfminer.pdftypes.resolve1(font_dict.get('BaseFont')))[1:]
    if (base_name[6] == '+'
        and set(base_name[:6]) < set('ABCDEFGHIJKLMNOPQRSTUVWXYZ')):
        base_name = base_name[7:]
    args = {}
    if ',' in base_name:
        base_name, attrs = base_name.split(',', 1)
        if 'Bold' in attrs:
            args['weight'] = 'bold'
        if 'Italic' in attrs:
            args['slant'] = 'italic'
    data = extract_font_stream(font_dict, ('FontFile2', 'FontFile3'))[1]
    return base_name, data, args

def get_type0_font(font_dict):
    subfont = pdfminer.pdftypes.resolve1(font_dict['DescendantFonts'])[0]
    subfont = pdfminer.pdftypes.resolve1(subfont)
    subtype = str(pdfminer.pdftypes.resolve1(subfont['Subtype']))
    if subtype == '/CIDFontType0':
        name, data, args = get_type1_font(subfont)

    elif subtype == '/CIDFontType2':
        return get_truetype_font(subfont)
    else:
        raise pdfminer.pdftypes.PDFValueError(
            "Unknown subtype of CID font: '%s'" % subtype)



class TkPage(ScrollingCanvas):

    """
    The canvas displays the contents from one page only.
    """

    def __init__(self, master, page, zoom=1, **kwargs):
        self.res = zoom * master.winfo_fpixels('1i') / 72.0  # pixels per point
        if 'width' not in kwargs:
            kwargs['width'] = page.width * self.res
        if 'height' not in kwargs:
            kwargs['height'] = page.height * self.res
        kwargs['scrollregion'] = (0, 0, kwargs['width'], kwargs['height'])
        super(TkPage, self).__init__(master, **kwargs)
        self.page = page  # A minecart.Page object
        self.postscript_names = {}  # A mapping of PDF font names to PS names
        self.font_cache = {}  # To prevent loading duplicate fonts

    def render(self):
        "Render all shapes and text onto the canvas"
        elems = sorted(self.page.shapes + self.page.letterings
                       + self.page.images,
                       key=lambda obj: obj.z_index)
        for elem in elems:
            if isinstance(elem, minecart.content.Shape):
                self.render_shape(elem)
            elif isinstance(elem, minecart.content.Image):
                self.render_image(elem)
            else:
                self.render_lettering(elem)

    def render_shape(self, shape):
        "Render the given shape onto the canvas."
        subpaths = []
        filled = shape.fill is not None
        closed_path = True
        curpath = None
        for segment in shape.path:
            kind = segment[0]
            if kind == 'm':
                if filled and not closed_path:
                    curpath.extend(curpath[:2] * 3)
                curpath = list(segment[1:])
                subpaths.append(curpath)
            elif kind == 'l':
                curpath.extend(curpath[-2:])
                curpath.extend(segment[1:] * 2)
            elif kind == 'c':
                curpath.extend(segment[1:])
            elif kind == 'h':
                curpath.extend(curpath[:2] * 3)
            elif kind == 'v':
                curpath.extend(curpath[-2:])
                curpath.extend(segment[1:])
            elif kind == 'y':
                curpath.extend(segment[1:])
                curpath.extend(curpath[-2:])
            else:
                raise ValueError("Invalid path operator '%s'" % kind)
        if filled:
            drawer = self.create_polygon
            args = {'fill': "#%02X%02X%02X" %
                        tuple(int(255 * c + .5) for c in
                              shape.fill.color.as_rgb())}
        else:
            drawer = self.create_line
            args = {}
        if shape.stroke is None:
            args['width'] = 0
        else:
            args['width'] = shape.stroke.linewidth or 2
            args['joinstyle'] = \
              ('miter', 'round', 'bevel')[shape.stroke.linejoin or 0]
            if shape.stroke.dash and shape.stroke.dash[0]:
                args['dash'] = shape.stroke.dash[0]  # ignore the phase
        args['smooth'] = 'raw'
        for subpath in subpaths:
            xvals = [xval * self.res for xval in subpath[::2]]
            yvals = [(self.page.height - yval) * self.res
                     for yval in subpath[1::2]]
            subpath = sum(zip(xvals, yvals), tuple())
            drawer(subpath, **args)

    def render_image(self, image):
        "Render the given image onto the canvas."
        from PIL import ImageTk
        size = (image.bbox[2] - image.bbox[0], image.bbox[3] - image.bbox[1])
        size = tuple(int(c * self.res + .5) for c in size)
        tkim = ImageTk.PhotoImage(image.as_pil().resize(size))
        pos = (image.bbox[0] * self.res,
               (self.page.height - image.bbox[3]) * self.res)
        image.tkim = tkim
        self.create_image(pos, anchor='nw', image=tkim)

    def render_lettering(self, lettering):
        "Render the given lettering onto the canvas."
        font = self.get_font(lettering.font,
                             lettering.bbox[3] - lettering.bbox[1])
        top = (self.page.height - lettering.bbox[3]) * self.res
        left = lettering.bbox[0] * self.res
        self.create_text((left, top), anchor='nw', text=lettering, font=font)

    def get_font(self, m_font, size):
        "Return a font matching the given specs, loading it if necessary."
        try:
            family, attrs = self.font_cache[m_font]
        except KeyError:
            family, data, attrs = get_font_program(m_font)
            self.font_cache[m_font] = family, attrs
            loadfont_memory(data)
        desc = pdfminer.pdftypes.resolve1(m_font.descriptor)
        if 'FontWeight' in desc:
            attrs['weight'] = 'normal' if desc['FontWeight'] < 450 else 'bold'
        if 'ItalicAngle' in desc:
            attrs['slant'] = 'roman' if desc['ItalicAngle'] ==0 else 'italic'
        return tkFont.Font(family=family, size=-int(size * self.res), **attrs)
