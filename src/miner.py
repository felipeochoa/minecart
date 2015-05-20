"""
This module contains all the classes that interface with pfdminer directly.
"""

import pdfminer.layout
import pdfminer.pdfdevice
import pdfminer.pdfdocument
import pdfminer.pdfinterp
import pdfminer.pdfpage
import pdfminer.pdfparser
import pdfminer.utils

from . import content


class DeviceLoader(pdfminer.pdfdevice.PDFTextDevice):

    """
    An interpreter that creates `Page` objects.
    """

    def __init__(self, *args, **kwargs):
        super(DeviceLoader, self).__init__(*args, **kwargs)
        self.page = None
        self.str_container = None

    def __repr__(self):
        return object.__repr__(self)

    def begin_page(self, page, ctm):
        self.page = content.Page()

    def paint_path(self, graphicstate, stroke, fill, evenodd, path):
        self.page.add_shape(content.Shape(graphicstate, stroke,
                                          fill, evenodd, path))

    def render_image(self, name, stream):
        self.page.add_image(content.Image(self.ctm, stream))

    def render_string_horizontal(self, *args):
        return self.render_string_hv('horizontal', *args)

    def render_string_vertical(self, *args):
        return self.render_string_hv('vertical', *args)

    def render_char(self, matrix, font, fontsize, scaling, rise, cid):
        # Essentially copied from
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
            if pdfminer.utils.isnumber(obj):
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
                self.page.add_lettering(content.Lettering(
                    u''.join(string), self.str_container.bbox, hv == 0))
                self.str_container = None
        return tuple(vec)


class Document(object):

    """
    An in-memory PDF document.
    """

    def __init__(self, pdffile):
        res_mgr = pdfminer.pdfinterp.PDFResourceManager()
        self.device = DeviceLoader(res_mgr)
        self.interpreter = pdfminer.pdfinterp.PDFPageInterpreter(
            res_mgr, self.device)
        self.parser = pdfminer.pdfparser.PDFParser(pdffile)
        self.doc = pdfminer.pdfdocument.PDFDocument(self.parser, caching=True)

    def iter_pages(self):
        "Iterate through all the pages in a document."
        for page in pdfminer.pdfpage.PDFPage.create_pages(self.doc):
            self.interpreter.process_page(page)
            yield self.device.page

    def get_page(self, num):
        """
        Get a specific page in the document.

        The number refers to the 0-based index of the page in the document
        display order, not the numbering system used in the document.

        """
        for i, page in enumerate(
                pdfminer.pdfpage.PDFPage.create_pages(self.doc)):
            if i == num:
                self.interpreter.process_page(page)
                return self.device.page
