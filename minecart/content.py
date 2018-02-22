u"""
This module contains the representions graphics elements in a document.

The three types of graphics elements supported are `Image`, `Shape`, and
`Lettering`.

Some notes on the coordinates used here:

The PDF spec deals with many different coordinate systems and transforms, and
converting from one to another is nontrivial and involves lots of matrices
and transforms. To keep things simple, minecart defines its own coordinate
system in which all metrics are expressed. This coordinate system has as its
origin the bottom-left corner of the page, and has the positive x axis
extending to the right and the positive y axis to the top. A unit on these
axes corresponds to 1/72 of an inch.

"""

from __future__ import division

import pdfminer.pdftypes
import pdfminer.utils
import io
import itertools
import sys

import six

from pdfminer.psparser import LIT
JPEG_FILTERS = (LIT('DCTDecode'), LIT('DCT'), LIT('JPXDecode'))


class GraphicsObject(object):

    """
    An abstract base class for the graphical objects found on a page.

    `z_index` -- the object's height in the stack. (Earliest drawn objects
                 have lower z_indices).

    """

    def __init__(self, z_index=0):
        self.z_index = z_index

    def get_bbox(self):
        """
        Return the bounding box for the graphics object.

        The return value is a 4-tuple of the form (left, bottom, right, top)

        """
        raise NotImplementedError

    def check_inside_bbox(self, bbox):
        "Check whether the given shape fits inside the given bounding box."
        left, bottom, right, top = self.get_bbox()
        return (left >= bbox[0]
                and bottom >= bbox[1]
                and right <= bbox[2]
                and top <= bbox[3])

    @property
    def width(self):
        "Return the width of the bounding box of this object."
        left, right = self.get_bbox()[::2]
        return right - left

    @property
    def height(self):
        "Return the height of the bounding box of this object."
        bottom, top = self.get_bbox()[1::2]
        return top - bottom


class GraphicsCollection(list):

    """
    A collection of several graphics objects.
    """

    def iter_in_bbox(self, bbox):
        """
        Iterate over all shapes in the given bounding box.

        `bbox` -- a 4-tuple of the form (left, bottom, right, top)

        """
        for shape in self:
            if shape.check_inside_bbox(bbox):
                yield shape

    def __repr__(self):
        return "<%s: %s>" % (self.__class__.__name__,
                               ", ".join(repr(item) for item in self))


def b_spline_bbox(point_0, point_1, point_2, point_3):
    "Calculates a bounding box for the given spline segment."
    # Code translated from http://stackoverflow.com/questions/2587751/
    # It is based on calculating the first derivative of the bspline, and
    # finding all the extrema of the parametrized form, and taking the
    # bounding box of that
    #pylint: disable=C0103
    t_values = [0, 1]
    for i in (0, 1):  # Does x values first then y values
        # The following are the coefficients of the spline's derivative
        a = -3 * point_0[i] + 9 * point_1[i] - 9 * point_2[i] + 3 * point_3[i]
        b = 6 * point_0[i] - 12 * point_1[i] + 6 * point_2[i]
        c = 3 * point_1[i] - 3 * point_0[i]
        if abs(a) < sys.float_info.min:  # Numerical robustness checks
            if abs(b) < sys.float_info.min:
                # The spline is linear in this coordinate (or a single
                # point), just need to check the two endpoints
                continue
            # The spline is quadratic with a single extremum:
            t = -c / b
            if 0 < t < 1:
                t_values.append(t)
            continue
        b2ac = b ** 2 - 4 * c * a
        if b2ac < 0:
            continue
        sqrtb2ac = b2ac ** .5
        t1 = (-b + sqrtb2ac) / (2 * a)
        if 0 < t1 < 1:
            t_values.append(t1)
        t2 = (-b - sqrtb2ac) / (2 * a)
        if 0 < t2 < 1:
            t_values.append(t2)

    x0, y0 = point_0
    x1, y1 = point_1
    x2, y2 = point_2
    x3, y3 = point_3
    x_bounds = []
    y_bounds = []
    for t in t_values:
        mt = 1 - t
        x = (mt ** 3 * x0
             + 3 * mt ** 2 * t * x1
             + 3 * mt * t ** 2 * x2
             + t ** 3 * x3)
        y = (mt ** 3 * y0
             + 3 * mt ** 2 * t * y1
             + 3 * mt * t ** 2 * y2
             + t ** 3 * y3)
        x_bounds.append(x)
        y_bounds.append(y)
    return min(x_bounds), min(y_bounds), max(x_bounds), max(y_bounds)


class Shape(GraphicsObject):

    """
    A Shape on a Page. Can be a path when stroked or filled.

    `stroke` -- A StrokeState with the stroke parameters if the shape is
                stroked, otherwise None.
    `fill` -- A FillState with the fill parameters if the shape is filled,
              otherwise None.
    `evenodd` -- A boolean indicating whether to use the Even/Odd rule to
                 determine the path interior. If False, the Winding Number
                 Rule is used instead.
    `path` -- A sequence of path tuples (type, *coords), where type is one of

              - m: Moveto
              - l: Lineto
              - c: Curveto
              - h: Close subpath
              - v: Curveto (1st control point on first point)
              - y: Curveto (2nd control point on last point)

              And coords is a sequence of (flat) coordinate values describing
              the path construction operator to use.

    """

    def __init__(self, stroke, fill, evenodd, path):
        super(Shape, self).__init__()
        self.stroke = stroke
        self.fill = fill
        self.evenodd = evenodd
        self.path = path
        self._bbox = None

    def get_bbox(self):
        "Returns a minimal bounding box for the curve."
        if self._bbox is None:
            cur_path = []
            points = []
            for segment in self.path:
                kind = segment[0]
                if kind == 'm':
                    if len(cur_path) > 1: # ignore repeated movetos
                        points.extend(cur_path)
                    cur_path = list(segment[1:])
                elif kind == 'l':
                    cur_path.extend(segment[1:])
                elif kind in 'cvy':
                    if kind == 'c':
                        spline = (cur_path[-2:], segment[1:3],
                                  segment[3:5], segment[5:7])
                    elif kind == 'v':
                        spline = (cur_path[-2:], cur_path[-2:],
                                  segment[1:3], segment[3:5])
                    elif kind == 'y':
                        spline = (cur_path[-2:], segment[1:3],
                                  segment[3:5], segment[3:5])
                    # We replace the curve by a zig-zag line through the
                    # corners of the curve's bounding box
                    cur_path.extend(b_spline_bbox(*spline))
                    cur_path.extend(segment[5:7])
                elif kind == 'h':
                    points.extend(cur_path)
                    cur_path = []
            points.extend(cur_path)
            exes = points[::2]
            whys = points[1::2]
            self._bbox = (min(exes), min(whys), max(exes), max(whys))
        return self._bbox


class Image(GraphicsObject):

    """
    Represents an image on a page.

    `ctm` -- Current Transformation Matrix in the graphicstate
    `obj` -- The PDFStream object representing the image

    """

    def __init__(self, ctm, obj):
        super(Image, self).__init__()
        self.ctm = ctm
        self.obj = obj
        #pylint: disable=C0103
        self.coords = (x1, y1), (x2, y2), (x3, y3), (x4, y4) = (
            pdfminer.utils.apply_matrix_pt(self.ctm, (0, 0)),
            pdfminer.utils.apply_matrix_pt(self.ctm, (0, 1)),
            pdfminer.utils.apply_matrix_pt(self.ctm, (1, 1)),
            pdfminer.utils.apply_matrix_pt(self.ctm, (1, 0)),
        )
        self.bbox = (
            min(x1, x2, x3, x4),
            min(y1, y2, y3, y4),
            max(x1, x2, x3, x4),
            max(y1, y2, y3, y4),
        )

    def get_bbox(self):
        return self.bbox

    def as_pil(self):
        """
        Return the image data in a `PIL.Image` object.

        Requires `pillow` to be installed.

        """
        import PIL.Image
        try:
            image_data = self.obj.get_data()
        except pdfminer.pdftypes.PDFNotImplementedError:
            filters = self.obj.get_filters()
            if len(filters) == 1 and filters[0] in JPEG_FILTERS:
                # FIXME: ColorSpace in JPEG2000 should be overridden by the
                # ColorSpace in the Image dictionary
                image_data = io.BytesIO(self.obj.rawdata)
                return PIL.Image.open(image_data)
            raise  # We either can't handle the predictor or the filter

        lti = pdfminer.layout.LTImage("", self.obj, self.get_bbox())
        # The PDF spec allows non-JPEG images to have 1, 2, 4, 8 or 16 bits
        if isinstance(lti.colorspace, list):
            colorspace = str(lti.colorspace[0])[1:]  # strip leading /
        else:
            colorspace = str(lti.colorspace)[1:]  # strip leading /
        if colorspace in ('DeviceRGB', 'CalRGB', 'RGB'):
            mode = "RGB"
            samples = 3
            if lti.bits == 8:
                rawmode = "RGB"
            elif lti.bits == 16:
                rawmode = "RGB;16B"
            # elif lti.bits in (1, 2, 4):
            #     # We have to upcast our data to 8 bits from either 1, 2, or 4
            #     # bits:
            #     #  4-bit:
            #     #    RRRR GGGG BBBB -> RRRR 0000 GGGG 0000 BBBB 0000
            #     #  2-bit:
            #     #    RR GG BB -> RR 000000 GG 000000 BB 000000
            #     #  1-bit:
            #     #    RGB -> R 0000000 G 0000000 B 000000
            #     out = []
            #     if lti.bits == 4:
            #         masks = ((240, 0),
            #                  (15, 4))
            #     elif lti.bits == 2:
            #         masks = ((192, 0),
            #                  (48, 2),
            #                  (12, 4),
            #                  (3, 6))
            #     else:
            #         masks = ((128, 0),
            #                  (64, 1),
            #                  (32, 2),
            #                  (16, 3),
            #                  (8, 4),
            #                  (4, 5),
            #                  (2, 6),
            #                  (1, 7))
            #     sample_ix = 0
            #     col = 0
            #     if array.array('H', 0).itemsize != 1:
            #         out = [None] * lti.size[1]
            #     else:
            #         out = array.array('B', 0) * (lti.size[0] * lti.size[1])
            #     for byte in map(ord, image_data):
            #         for mask, shift in masks:
            #             if col < lti.size[1]:
            #                 out[sample_ix] = (byte & mask) << shift
            #                 sample_ix += 1
            #                 col += 1
            #             else:
            #                 # PDF image data must be 0-padded to be byte-aligned by row,
            #                 col = 0
            #                 break
            #     raw_mode = 8
            #     if isinstance(out, array.array)
            #         image_data = out.tostring()
            #     else:
            #         image_data = b"".join(map(chr, out))
            #     del out
            else:
                raise pdfminer.pdftypes.PDFNotImplementedError(
                    "RGB images with %d-bit samples are not supported" % lti.bits)
        elif colorspace in ('CalGray', 'DeviceGray'):
            mode = 'L'
            samples = 1
            if lti.bits == 1:
                mode = rawmode = "1"
            elif lti.bits == 2:
                rawmode = "L;2"
            elif lti.bits == 4:
                rawmode = "L;4"
            elif lti.bits == 8:
                rawmode = "L"
            elif lti.bits == 16:
                rawmode = "L;16"
        elif colorspace in ('DeviceCMYK', 'CMYK'):
            if lti.bits != 8:
                raise pdfminer.pdftypes.PDFNotImplementedError(
                    "PIL only supports 8-bit CMYK")
            # TODO: Upcast the 1/2/4 bit image to 8 bits.
            # Can PIL handle 16-bit CMYK?
            mode = "CMYK"
            rawmode = "CMYK"
            samples = 4
        else:
            raise pdfminer.pdftypes.PDFNotImplementedError(
                "Colorspace %r is not supported" % colorspace)
        # The PDF spec requires each row of data to be 0-padded to be at a
        # byte boundary. stride is the distance in bytes between consecutive
        # rows of image data.
        stride = (lti.srcsize[0] * lti.bits * samples + 7) // 8
        image = PIL.Image.open(io.BytesIO(image_data))

        return image
        # TODO: implement Decode array
        # TODO: implement image mask


class Lettering(six.text_type, GraphicsObject):

    """
    A text string on a page, including its typographic information.
    """

    def __new__(cls, data, font, bbox, horizontal=True):
        loc_str = six.text_type.__new__(cls, data)
        x1, y1, x2, y2 = bbox  #pylint: disable=C0103
        loc_str.bbox = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
        loc_str.horizontal = horizontal
        loc_str.font = font
        return loc_str

    def __init__(self, data, font, bbox, horizontal):
        super(Lettering, self).__init__()

    def get_bbox(self):
        return self.bbox

    def __repr__(self):
        return "<%s: %s %r>" % (self.__class__.__name__, self, self.bbox)


class Page(object):

    """
    A page in the document, which contains all the graphics elements.

    Has the following attributes containing the various graphics elements on
    the page:

    * `images` -- a `GraphicsCollection` with all the `Image` objects on the
                  page
    * `letterings` -- a `GraphicsCollection` containing all the text objects
                      found on the page (as `Lettering`s)
    * `shapes` -- a `GraphicsCollection` with all the `Shape` objects on the
                  page

    The coordinate system for all of these graphics elements has as its
    origin the lower-left corner of the page, and the units are DTP points
    (1/72 inch).

    The PDF standard defines several bounding boxes for each page, with a
    loose hierarchy between them:

    * MediaBox: Content outside of this box can be safely discarded. In our
                coordinate system, the media box has coordinates
                `(0, 0, page.width, page.height)`
    * CropBox:  Sets a clipping area for the page contents. Accessed through
                the `page.crop_box` attribute
    * BleedBox: Accessed through the `page.bleed_box`, it "defines the region
                to which the contents of the page should be clipped when
                output in a production environment. This may include any
                extra bleed area needed to accommodate the physical
                limitations of cutting, folding, and trimming equipment. The
                actual printed page may include printing marks that fall
                outside the bleed box. The default value is the page's crop
                box." (PDF spec 1.7 p. 963)
    * TrimBox:  Accessed through the `page.trim_box`, it "defines the intended
                dimensions of the finished page after trimming. It may be
                smaller than the media box to allow for production-related
                content, such as printing instructions, cut marks, or color
                bars. The default value is the page's crop box." (PDF spec 1.7
                p. 963)
    * ArtBox:   Accessed through the `page.art_box`, it "defines the extent of
                the page's meaningful content (including potential white space)
                as intended by the page's creator. The default value is the
                page's crop box." (PDF spec 1.7 p. 963)

    """

    def __init__(self, m_page):
        self.m_page = m_page
        self.images = GraphicsCollection()
        self.letterings = GraphicsCollection()
        self.shapes = GraphicsCollection()
        self.next_z_index = itertools.count(0)
        unit = pdfminer.pdftypes.resolve1(m_page.attrs.get('UserUnit', 1))
        self.width = (m_page.mediabox[2] - m_page.mediabox[0]) * unit
        self.height = (m_page.mediabox[3] - m_page.mediabox[1]) * unit
        if m_page.rotate in (90, 270):
            self.height, self.width = self.width, self.height
        self.crop_box = self.adjust_box(m_page.cropbox)
        try:
            self.bleed_box = self.adjust_box(
                pdfminer.pdftypes.resolve1(m_page.attrs['BleedBox']))
        except KeyError:
            self.bleed_box = self.crop_box
        try:
            self.trim_box = self.adjust_box(
                pdfminer.pdftypes.resolve1(m_page.attrs['TrimBox']))
        except KeyError:
            self.trim_box = self.crop_box
        try:
            self.art_box = self.adjust_box(
                pdfminer.pdftypes.resolve1(m_page.attrs['ArtBox']))
        except KeyError:
            self.art_box = self.crop_box

    def adjust_box(self, box):
        "Translate and rotate the given box to device coordinates."
        mb_left, mb_bot = self.m_page.mediabox[:2]
        left, bot, right, top = box
        left -= mb_left
        right -= mb_left
        bot -= mb_bot
        top -= mb_bot
        if self.m_page.rotate == 90:
            left, bot, right, top = bot, -right, top, -left
        elif self.m_page.rotate == 180:
            left, bot, right, top = -left, -bot, -right, -top
        elif self.m_page.rotate == 270:
            left, bot, right, top = -top, left, -bot, right
        return (left, bot, right, top)

    def add_shape(self, shape):
        "Add the given shape to the page."
        self.shapes.append(shape)
        shape.z_index = next(self.next_z_index)

    def add_image(self, image):
        "Add the given image to the page."
        self.images.append(image)
        image.z_index = next(self.next_z_index)

    def add_lettering(self, lettering):
        "Add the given lettering to the page."
        self.letterings.append(lettering)
        lettering.z_index = next(self.next_z_index)
