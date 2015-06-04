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
    if isinstance(fontpath, str):
        pathbuf = ctypes.create_string_buffer(fontpath)
        AddFontResourceEx = ctypes.windll.gdi32.AddFontResourceExA
    elif isinstance(fontpath, unicode):
        pathbuf = ctypes.create_unicode_buffer(fontpath)
        AddFontResourceEx = ctypes.windll.gdi32.AddFontResourceExW
    else:
        raise TypeError('fontpath must be of type str or unicode')
    flags = ((FR_PRIVATE if private else 0)
             | (FR_NOT_ENUM if not enumerable else 0))
    return AddFontResourceEx(ctypes.byref(pathbuf), flags, 0)


def loadfont_memory(data):
    "Load a given font stored in memory."
    num = ctypes.c_uint32()
    ctypes.windll.gdi32.AddFontMemResourceEx(data, len(data), 0,
                                             ctypes.byref(num))
    return num.value


class TkPage(ScrollingCanvas):

    """
    The canvas displays the contents from one page only.
    """

    def __init__(self, master, page, zoom=1, **kwargs):
        self.res = zoom * master.winfo_fpixels('1i') / 72.0  # pixels per point
        kwargs['width'] = page.width * self.res
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
            return self.font_cache[m_font]
        except KeyError:
            pass
        try:
            stream = m_font.descriptor['FontFile']
            subtype = ""
        except KeyError:
            try:
                stream = m_font.descriptor['FontFile2']
                subtype = ""
            except KeyError:
                stream = m_font.descriptor['FontFile3']
                subtype = m_font.descriptor['Subtype']
        data = pdfminer.pdftypes.stream_value(stream).get_data()
        family = pdfminer.pdftypes.resolve1(m_font.descriptor['FontName'])
        weight = pdfminer.pdftypes.resolve1(m_font.descriptor.get('FontWeight',
                                                                400))
        weight = 'normal' if weight < 450 else 'bold'
        slant = pdfminer.pdftypes.resolve1(m_font.descriptor['ItalicAngle'])
        slant = 'roman' if slant == 0 else 'italic'
        loadfont_memory(data)
        font = tkFont.Font(family=family, size=-int(size * self.res + .5),
                           weight=weight, slant=slant)
        self.font_cache[m_font] = font
        return font
