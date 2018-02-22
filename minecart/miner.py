"""
This module contains all the classes that interface with pfdminer directly.
"""

import numbers

import pdfminer.layout
import pdfminer.pdfdevice
import pdfminer.pdfinterp
import pdfminer.pdfparser
import pdfminer.pdftypes
import pdfminer.utils
import pdfminer.pdfcolor

from .content import Page, Shape, Image, Lettering
from . import color

class ColoredState(pdfminer.pdfinterp.PDFGraphicState):

    """
    Expands the graphic state with fill and stroke color parameters.
    """

    def __init__(self):
        super(ColoredState, self).__init__()
        self.fill_color = color.NO_COLOR    # Is there a better way to advise
        self.stroke_color = color.NO_COLOR  # pylint that these are Colors?

    def copy(self):
        obj = self.__class__()
        obj.linewidth = self.linewidth
        obj.linecap = self.linecap
        obj.linejoin = self.linejoin
        obj.miterlimit = self.miterlimit
        obj.dash = self.dash
        obj.intent = self.intent
        obj.flatness = self.flatness
        obj.fill_color = self.fill_color
        obj.stroke_color = self.stroke_color
        return obj


class StrokeState(object):

    """
    An object that encapsulates the stroking parameters.
    """

    def __init__(self):
        self.color = None
        self.linewidth = 2
        self.linecap = 0
        self.linejoin = 0
        self.miterlimit = 10
        self.dash = ([], 0)
        self.stroke_adjustment = False

    @classmethod
    def from_gs(cls, graphics):
        "Creates a new StrokeState from a ColoredState object."
        ret = cls()
        ret.color = graphics.stroke_color
        ret.linewidth = graphics.linewidth
        ret.linecap = graphics.linecap
        ret.linejoin = graphics.linejoin
        ret.miterlimit = graphics.miterlimit
        ret.dash = graphics.dash
        return ret

    def __repr__(self):
        return ("<%s: color=%r, line-width=%r, line-cap=%r "
                + "line-join=%r miter-limit=%r dash-pattern=%r>") %(
                    self.__class__.__name__, self.color, self.linewidth,
                    self.linecap, self.linejoin, self.miterlimit,
                    self.dash)


class FillState(object):

    """
    An object that encapsulates the fill parameters.
    """

    def __init__(self):
        self.color = None

    @classmethod
    def from_gs(cls, graphics):
        "Creates a new FillState from a ColoredState object."
        ret = cls()
        ret.color = graphics.fill_color
        return ret

    def __repr__(self):
        return ("<%s: color=%r>") % (self.__class__.__name__, self.color)


class ColoredInterpreter(pdfminer.pdfinterp.PDFPageInterpreter):

    """
    A PDF interpreter that can handle color commands.
    """

    # The ColoredInterpreter extends the PDFPageInterpreter found in pdfminer
    # by keeping track of the stroke and fill colors. It keeps a `ColorSpace`
    # for both stroke and fill operations, and uses it to create `Color`
    # objects for each of stroke and fill.
    #
    # The ColoredInterpreter manages the current color spaces the same way
    # that the PDFPageInterpreter does (pdfminer needs to care about the
    # number of components in the color space, so it has a thin version of
    # color spaces already). To plug into this machinery, it overrides the
    # setting of `self.csmap` in `self.init_resources()`. csmap is a
    # dictionary mapping names as found in the /Resources dict of a page to
    # instances of the colorspaces, initialized according to the parameters
    # found in /Resources.

    def __init__(self, *args, **kwargs):
        super(ColoredInterpreter, self).__init__(*args, **kwargs)
        # This is here to allow for independent testing of init_state and
        # init_resources, as well as to avoid pylint warnings ;)
        self.csmap = {}
        self.graphicstate = None

    def init_state(self, ctm):
        # Extends the parent method to install our custom graphic state
        super(ColoredInterpreter, self).init_state(ctm)
        self.graphicstate = ColoredState()

    def init_resources(self, resources):
        # Extends the parent method to install our custom color spaces
        if resources:
            resources = pdfminer.pdftypes.dict_value(resources)
            spaces = resources.pop('ColorSpace', {})
        else:
            spaces = {}
        super(ColoredInterpreter, self).init_resources(resources)
        self.csmap.clear()
        # Per the PDF spec, (p. 287), "The names DeviceGray, DeviceRGB,
        # DeviceCMYK, and Pattern always identify the corresponding color
        # spaces directly; they never refer to resources in the ColorSpace
        # subdictionary." We implement this behavior by overriding any
        # entries in the csmap with this name with the original color spaces.
        for csname, spec in pdfminer.pdftypes.dict_value(spaces).items():
            self.csmap[csname] = color.make_color_space(spec)
        self.csmap.update(
            (name, color.FAMILIES[name].make_space())
            for name in ('DeviceGray', 'DeviceRGB', 'DeviceCMYK')
        )
        # The next loop ensures that device color spaces are overriden by
        # their defaults, if any
        for csname in ('DefaultGray', 'DefaultRGB', 'DefaultCMYK'):
            try:
                space = self.csmap[csname]
            except KeyError:
                pass
            else:
                self.csmap[csname.replace('Default', 'Device')] = space

    # setgray-stroking
    def do_G(self, gray):
        self.do_CS(pdfminer.pdfcolor.LITERAL_DEVICE_GRAY)
        self.graphicstate.stroke_color = self.scs.make_color((gray,))

    # setgray-non-stroking
    def do_g(self, gray):
        self.do_cs(pdfminer.pdfcolor.LITERAL_DEVICE_GRAY)
        self.graphicstate.fill_color = self.ncs.make_color((gray,))

    # setrgb-stroking
    def do_RG(self, r, g, b):
        self.do_CS(pdfminer.pdfcolor.LITERAL_DEVICE_RGB)
        self.graphicstate.stroke_color = self.scs.make_color((r, g, b))

    # setrgb-non-stroking
    def do_rg(self, r, g, b):
        self.do_cs(pdfminer.pdfcolor.LITERAL_DEVICE_RGB)
        self.graphicstate.fill_color = self.ncs.make_color((r, g, b))

    # setcmyk-stroking
    def do_K(self, c, m, y, k):
        self.do_CS(pdfminer.pdfcolor.LITERAL_DEVICE_CMYK)
        self.graphicstate.stroke_color = self.scs.make_color((c, m, y, k))

    # setcmyk-non-stroking
    def do_k(self, c, m, y, k):
        self.do_cs(pdfminer.pdfcolor.LITERAL_DEVICE_CMYK)
        self.graphicstate.fill_color = self.ncs.make_color((c, m, y, k))

    # setcolor-stroking
    def do_SCN(self):
        if self.scs:
            samples = self.scs.ncomponents
        else:
            raise pdfminer.pdfinterp.PDFInterpreterError(
                'No colorspace specified!')
        self.graphicstate.stroke_color = self.scs.make_color(
            self.pop(samples))

    # setcolor-non-stroking
    def do_scn(self):
        if self.ncs:
            samples = self.ncs.ncomponents
        else:
            raise pdfminer.pdfinterp.PDFInterpreterError(
                'No colorspace specified!')
        self.graphicstate.fill_color = self.ncs.make_color(self.pop(samples))


class DeviceLoader(pdfminer.pdfdevice.PDFTextDevice):

    """
    An interpreter that creates `Page` objects.
    """

    def __init__(self, rsrcmgr):
        super(DeviceLoader, self).__init__(rsrcmgr)
        self.page = None
        self.str_container = None
        self.unit = 1

    def __repr__(self):
        return object.__repr__(self)

    def begin_page(self, page, ctm):
        self.page = Page(page)
        self.unit = pdfminer.pdftypes.resolve1(page.attrs.get('UserUnit', 1))

    def set_ctm(self, ctm):
        # pdfminer adjusts the ctm for the page rotation and MediaBox,
        # so we just need to adjust for the UserUnit
        self.ctm = tuple(c * self.unit for c in ctm)

    def paint_path(self, graphicstate, stroked, filled, evenodd, path):
        # Converts path to device coordinates and adds the path to the page
        device_path = []
        for segment in path:
            coords = iter(segment[1:])
            new_seg = [segment[0]]
            for x in coords:  #pylint: disable=C0103
                y = next(coords)  #pylint: disable=C0103
                new_seg.extend(pdfminer.utils.apply_matrix_pt(self.ctm,
                                                              (x, y)))
            device_path.append(tuple(new_seg))
        stroke = StrokeState.from_gs(graphicstate) if stroked else None
        fill = FillState.from_gs(graphicstate) if filled else None
        self.page.add_shape(Shape(stroke, fill, evenodd, device_path))

    def render_image(self, name, stream):
        self.page.add_image(Image(self.ctm, stream))

    def render_string_horizontal(self, *args):
        return self.render_string_hv('horizontal', *args)

    def render_string_vertical(self, *args):
        return self.render_string_hv('vertical', *args)

    def render_char(self, matrix, font, fontsize, scaling, rise, cid):
        # Essentials copied from
        # pdfminer.converter.PDFLayoutAnalyzer.render_char
        text = font.to_unichr(cid)
        textwidth = font.char_width(cid)
        textdisp = font.char_disp(cid)
        item = pdfminer.layout.LTChar(matrix, font, fontsize, scaling, rise,
                                      text, textwidth, textdisp)
        self.str_container.add(item)
        return item.adv

    def render_string_hv(self, hv, seq, matrix, vec, font, fontsize,
                         scaling, charspace, wordspace, rise,
                         dxscale):
        """
        Calculate the bounding box in user coordinates for a string.

        `hv` -- one of 'horizontal' or 'vertical', for the type of string to
                render
        `seq` -- The array of strings/numbers to render
        `matrix` -- The matrix mapping text coordinates to user coordinates,
                    (T_m x CTM, part of T_rm)
        `vec` -- the user coordinates of the text origin
        `font` -- the font to use for rendering the string
        `fontsize` -- the fontsize in the text state
        `scaling` -- the horizontal scaling factor (Tz * .01)
        `charspace` -- additional space to insert b/ween characters, scaled
                       (Tc * Tz * .01) in text coordinates
        `wordspace` -- additional space to insert b/ween words, scaled
                       (Tw * Tz * .01) in text coordinates
        `rise` -- the text rise parameter, scaled (Ts * Tz * .01) in text
                  coordinates
        `dxscale` -- the size in user coordinates to skip when rendering `1`.

        """
        vec = list(vec)
        hv = ('horizontal', 'vertical').index(hv)
        needcharspace = False
        for obj in seq:
            if isinstance(obj, numbers.Number):
                vec[hv] -= obj * dxscale
                needcharspace = True
            else:
                string = []
                self.str_container = pdfminer.layout.LTExpandableContainer()
                for cid in font.decode(obj):
                    if needcharspace:
                        vec[hv] += charspace
                    vec[hv] += self.render_char(
                        pdfminer.utils.translate_matrix(matrix, vec),
                        font, fontsize, scaling, rise, cid)
                    if cid == 32 and wordspace:
                        vec[hv] += wordspace
                    needcharspace = True
                    string.append(font.to_unichr(cid))
                self.page.add_lettering(Lettering(
                    u''.join(string), font, self.str_container.bbox, hv == 0))
                self.str_container = None
        return tuple(vec)


class Document(object):

    """
    An in-memory PDF document.
    """

    def __init__(self, pdffile):
        res_mgr = pdfminer.pdfinterp.PDFResourceManager()
        self.device = DeviceLoader(res_mgr)
        self.interpreter = ColoredInterpreter(res_mgr, self.device)
        self.parser = pdfminer.pdfparser.PDFParser(pdffile)
        self.doc = pdfminer.pdfparser.PDFDocument(caching=True)
        self.parser.set_document(self.doc)
        self.doc.set_parser(self.parser)

    def iter_pages(self):
        "Iterate through all the pages in a document."
        for page in self.doc.get_pages():
            self.interpreter.process_page(page)
            yield self.device.page

    def get_page(self, num):
        """
        Get a specific page in the document.

        The number refers to the 0-based index of the page in the document
        display order, not the numbering system used in the document.

        """
        for i, page in enumerate(self.doc.get_pages()):
            if i == num:
                self.interpreter.process_page(page)
                return self.device.page
