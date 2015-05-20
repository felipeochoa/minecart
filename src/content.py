u"""
This module contains the objects representing graphics elements in a document.
"""

import pdfminer.utils


class GraphicsObject(object):

    """
    An abstract base class for the graphical objects found on a page.
    """

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


class Shape(GraphicsObject):

    """
    A Shape on a Page. Can be a path when stroked or filled.

    `graphicstate` --
    `stroked` -- A boolean indicating whether the path is stroked
    `filled` -- A boolean indicating whether the path is filled
    `evenodd` -- A boolean indicating whether to use the Even/Odd rule to
                 determine the path interior. If False, the Winding Number
                 Rule is used instead.
    `path` -- A sequence of path triples (type, *coords), where type is one of

              - m: Moveto
              - l: Lineto
              - c: Curveto
              - h: Close subpath
              - v: Curveto (1st control point on first point)
              - y: Curveto (2nd control point on last point)

              And coords is a sequence of (flat) coordinate values describing
              the path construction operator to use.

    """

    def __init__(self, graphicstate, stroke, fill, evenodd, path):
        super(Shape, self).__init__()
        self.graphicstate = graphicstate.copy()
        self.stroked = stroke
        self.filled = fill
        self.evenodd = evenodd
        self.path = path
        self._bbox = None

    def get_bbox(self):
        "Returns a (not-necessarily minimal) bounding box for the curve."
        if self._bbox is None:
            cur_path = []
            points = []
            for segment in self.path:
                kind = segment[0]
                if kind == 'm':
                    if len(cur_path) > 1: # ignore repeated movetos
                        points.extend(cur_path)
                    cur_path = list(segment[1:])
                elif kind in 'lcvy':
                    # We treat curveto the same as lineto, which gives
                    # loose but correct bounds
                    # TODO: tighten bbox
                    cur_path.extend(segment[1:])
                elif kind == 'h':
                    points.extend(cur_path)
                    cur_path = []
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

class Lettering(unicode, GraphicsObject):

    """
    A text string on a page, including its typographic information.
    """

    def __new__(cls, data, bbox, horizontal=True):
        loc_str = unicode.__new__(cls, data)
        x1, y1, x2, y2 = bbox  #pylint: disable=C0103
        loc_str.bbox = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
        loc_str.horizontal = horizontal
        return loc_str

    def get_bbox(self):
        return self.bbox


class Page(object):

    """
    A page in the document, which contains all the graphics elements.

    Has the following attributes:

    * `images` -- a `GraphicsCollection` with all the `Image` objects on the
                  page
    * `letterings` -- a `GraphicsCollection` containing all the text objects
                      found on the page (as `Lettering`s)
    * `shapes` -- a `GraphicsCollection` with all the `Shape` objects on the
                  page

    """

    def __init__(self):
        self.images = GraphicsCollection()
        self.letterings = GraphicsCollection()
        self.shapes = GraphicsCollection()

    def add_shape(self, shape):
        "Add the given shape to the page."
        self.shapes.append(shape)

    def add_image(self, image):
        "Add the given image to the page."
        self.images.append(image)

    def add_lettering(self, lettering):
        "Add the given lettering to the page."
        self.letterings.append(lettering)
