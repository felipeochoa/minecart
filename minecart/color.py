u"""
This module provides support for managing PDF colorspaces and colors.

Color spaces in PDF are organized as two factory functions:

1. `COLOR SPACE FAMILIES` create `COLOR SPACES` based on certain parameters
2. `COLOR SPACES` create `COLORS` based on certain numerical values

minecart's approach to handling these color spaces is to model everything as
a Python object. Thus COLORS are instances of `Color` (or one of its
subclasses), COLOR SPACES are instances of `ColorSpace` (or one of its
subclasses), and COLOR SPACE FAMILIES are instances of `ColorSpaceFamily` (or
one of its subclasses).

When creating a new COLOR SPACE, minecart identifies the `ColorSpaceFamily`
in the `FAMILIES` dict, and calls `make_space` with the parameters specified
in the document (as a Python list).

When using a COLOR SPACE to create a color, minecart uses the (previously
created) `ColorSpace` instance and calls `make_color` with a single value
argument, returning an instance of `Color`.

Colors provide a single method, `.as_rgb()`, which converts the color to the
Device RGB color space.

TODO:
* CIE to DeviceRGB conversion
* Gamma-correction (transfer functions)
* Custom devices to allow conversion of colors into arbitrary color
  spaces. Colors would provide a `.render()` method with a `Device` parameter
  to convert the color into the `Device`'s color space. (`Device` would
  control gamma-correction). `.as_rgb()` would use a default RGB-device to
  convert the color into 'DeviceRGB' space
* Pattern, Separation, DeviceN colorspaces

"""
#pylint: disable=R0903

import pdfminer.pdftypes

FAMILIES = {}  # The dict is built up througout the module


############################################################################
#        The base classes, Color, ColorSpace, and ColorSpaceFamily         #
############################################################################

class Color(object):

    """
    A fully-specified color.

    `space` -- the ColorSpace this color belongs to
    `value` -- the value (interpreted according to the ColorSpace) of this
               color. If `value` is None, the color is initialized to the
               color space default.

    Colors have 2 attributes that specify them completely:

    * `space` -- points to the color space in which this color is defined
    * `value` -- is a color space-dependent value that identifies the color
                 within it.

    If the color came from an index space, `space` will point to the
    reference (i.e., non-index) color space, and `value` will contain the
    identifier in that space. In this case, `index_val` will be a tuple
    (`index_space`, `index`), identifying the index space in which the color
    was originally defined, and its index in that space. If the color did not
    come from an index space, `index_val` is `None`

    """

    __slots__ = ['space', 'value', 'index_val']

    def __init__(self, space, value=None):
        self.space = space
        if value is None:
            self.value = space.get_default()
        else:
            self.value = value
        self.index_val = None

    def as_rgb(self):
        """
        Convert the color into the device RGB colorspace.

        Returns a 3-tuple of values in the range [0, 1] representing the red,
        green, and blue component values, respectively.

        """
        return self.space.as_rgb(self.value)


class ColorSpace(object):

    """
    A specific (parametrized) color space.

    `family` -- the ColorSpaceFamily this color space belongs to.
    `default` -- the default value of colors in this color space.
    `ncomponents` -- the number of components in the color space.

    Note that the abstract base class does not take a `params` argument,
    unlike many of the other ones.

    """

    def __init__(self, family, ncomponents, default=None):
        self.family = family
        self.default = default
        self.ncomponents = ncomponents

    def make_color(self, value=None):
        "Return a Color instance representing this particular color."
        return Color(self, value)

    def as_rgb(self, value):
        "Convert the given color value into device RGB."
        raise NotImplementedError

    def get_default(self):
        "Returns the default value for colors in this family."
        return self.default

    def get_ranges(self):
        """
        Returns a tuple (min_0, max_0, ..., min_n, max_n) of component ranges.

        The default implementation assumes minima of 0 and maxima of 1 for
        all components.

        """
        return (0, 1) * self.ncomponents


class ColorSpaceFamily(object):

    """
    Represents a color space family.

    `color_space_class` -- the class to use to create a specific color space
    """

    def __init__(self, name, color_space_class):
        self.name = name
        self.color_space_class = color_space_class

    def make_space(self, params=None):
        """
        Create a particular instance of the color space.

        `params` -- a sequence containing the parameters used to build the
                    specific ColorSpace instance.
        """
        return self.color_space_class(self, params)


NO_COLOR = Color(ColorSpace(ColorSpaceFamily('NoneFamily', None), tuple()))


############################################################################
#                    The device families and colorspaces                   #
############################################################################

class DeviceFamily(ColorSpaceFamily):

    """
    Device color spaces only have one color space.

    `default` -- the default value of the color value in the family

    """

    def __init__(self, name, default):
        super(DeviceFamily, self).__init__(name, color_space_class=None)
        self.color_space = DeviceSpace(family=self, default=default)

    def make_space(self, params=None):
        "Overrides the supermethod to return the singleton ColorSpace"
        if params:
            raise TypeError("Device families are unparametrized!")
        return self.color_space


class DeviceSpace(ColorSpace):

    """
    One of the 3 device spaces (DeviceGray, DeviceRGB, DeviceCMYK).
    """

    def __init__(self, family, default):
        super(DeviceSpace, self).__init__(family, len(default), default)
        if family.name == 'DeviceGray':
            self.as_rgb = lambda value: value * 3  # tuple mult.
        elif family.name == 'DeviceRGB':
            self.as_rgb = lambda value: value
        elif family.name == 'DeviceCMYK':
            self.as_rgb = lambda value: self.cmyk_to_rgb(value)
        else:
            raise ValueError("Invalid device family name: %s", family.name)

    @staticmethod
    def cmyk_to_rgb(cmyk_value):
        """
        Converts a color value of DeviceCMYK to DeviceRGB (returns a tuple).
        """
        cyan, magenta, yellow, black = cmyk_value
        return (
            1.0 - min(1, cyan + black),
            1.0 - min(1, magenta + black),
            1.0 - min(1, yellow + black)
        )


DEVICE_GRAY = DeviceFamily('DeviceGray', (0,)).make_space()
DEVICE_RGB = DeviceFamily('DeviceRGB', (0, 0, 0)).make_space()
DEVICE_CMYK = DeviceFamily('DeviceCMYK', (0, 0, 0, 1)).make_space()
FAMILIES.update({
    'DeviceGray': DEVICE_GRAY.family,
    'DeviceRGB': DEVICE_RGB.family,
    'DeviceCMYK': DEVICE_CMYK.family
})


############################################################################
#                     The CIE families and colorspaces                     #
############################################################################

class CIEColor(Color):

    """
    A Color in a CIE-based color space.

    It has an additional method `as_xyz()` that returns the XYZ values of the
    color, in the range [0, 1].

    """

    __slots__ = []

    def as_xyz(self):
        "Returns the XYZ components of this color."
        return self.space.as_xyz(self.value)


class CIESpace(ColorSpace):

    """
    An abstract base clas for the CalGray, CalRGB, and Lab spaces.
    """

    DEFAULT_COLOR_VALUE = None  # (0,) for CalGray and (0, 0, 0) for CalRGB
                                # Lab is (0, 0, 0), but clipped to its range
    NCOMPONENTS = None  # 1 for CalGray, 3 for CalRGB, 3 for RGB

    def __init__(self, family, params):
        if len(params) != 1:
            raise TypeError("%s takes exactly one dict parameter",
                            self.__class__.__name__)
        params = params[0]
        self.check_params(params)
        super(CIESpace, self).__init__(family,
                                       default=self.DEFAULT_COLOR_VALUE,
                                       ncomponents=self.NCOMPONENTS)
        self.white_point = tuple(params['WhitePoint'])
        if self.white_point[0] <= 0 or self.white_point[2] <= 0:
            raise ValueError(
                "The X and Z values of WhitePoint must be postive")
        if self.white_point[1] != 1:
            raise ValueError("The Y value of WhitePoint must be 1")
        self.black_point = tuple(params.get('BlackPoint', (0, 0, 0)))
        if min(self.black_point) < 0:
            raise ValueError("All components of BlackPoint must be >= 0")

    @staticmethod
    def check_params(params):
        """
        Raises TypeError if there are extra or missing keys in the dict.

        `params` is the dict that makes up the second element of the array
        defining the color space.

        """
        tester = lambda WhitePoint, **kwargs: None
        tester(**params)

    def as_xyz(self, value):
        "Convert a given value into XYZ components."
        raise NotImplementedError

    def as_rgb(self, value):
        "Converts the given value into sRGB components."
        # See http://www.color.org/srgb.pdf for the transformation details
        x, y, z = self.as_xyz(value)  #pylint: disable=C0103
        linear = (
            +3.2406 * x - 1.5372 * y - 0.4986 * z,
            -0.9689 * x + 1.8758 * y + 0.0415 * z,
            +0.0557 * x - 0.2040 * y + 1.0570 * z
        )
        return tuple(
            comp * 12.92 if comp <= 0.0031308 else
            1.055 * pow(comp, 1.0 / 2.4) - 0.055
            for comp in (max(0, min(1, comp)) for comp in linear)
        )


    def make_color(self, value=None):
        "Overrides parent method to use a CIEColor instead."
        return CIEColor(self, value)

    def __eq__(self, other):
        "Compare two spaces based on their parametrization."
        default = object()
        return (
            self.family == other.family
            and self.ncomponents == other.ncomponents
            and self.default == other.default
            and self.white_point == other.white_point
            and self.black_point == other.black_point
            and (getattr(self, 'gamma', default)
                 == getattr(other, 'gamma', default))
            and (getattr(self, 'matrix', default)
                 == getattr(other, 'matrix', default))
            and (getattr(self, 'a_range', default)
                 == getattr(other, 'a_range', default))
            and (getattr(self, 'b_range', default)
                 == getattr(other, 'b_range', default))
        )


class CalGraySpace(CIESpace):

    """
    A CalGray color space.
    """

    DEFAULT_COLOR_VALUE = (0,)
    NCOMPONENTS = 1

    def __init__(self, family, params):
        super(CalGraySpace, self).__init__(family, params)
        self.gamma = params[0].get('gamma', 1)

    @staticmethod
    def check_params(params):
        def _test(WhitePoint, BlackPoint=None, Gamma=None):
            #pylint: disable=W0613,C0103,C0111
            # run params through this to force TypeErrors
            pass
        _test(**params)

    def as_xyz(self, value):
        a_to_the_g = pow(value[0], self.gamma)
        return tuple(c * a_to_the_g for c in self.white_point)


FAMILIES['CalGray'] = ColorSpaceFamily('CalGray', CalGraySpace)


class CalRGBSpace(CIESpace):

    """
    A CalRGB color space.
    """

    DEFAULT_COLOR_VALUE = (0, 0, 0)
    NCOMPONENTS = 3

    def __init__(self, family, params):
        super(CalRGBSpace, self).__init__(family, params)
        params = params[0]  # The supermethod ensures this is safe/correct
        self.gamma = params.get('Gamma', (1, 1, 1))
        self.matrix = params.get('Matrix', (1, 0, 0, 0, 1, 0, 0, 0, 1))

    @staticmethod
    def check_params(params):
        def _test(WhitePoint, BlackPoint=None, Gamma=None, Matrix=None):
            #pylint: disable=W0613,C0103,C0111
            # run params through this to force TypeErrors
            pass
        _test(**params)

    def as_xyz(self, value):
        a_g, b_g, c_g = (pow(val, gamma)
                         for val, gamma in zip(value, self.gamma))
        x_a, y_a, z_a, x_b, y_b, z_b, x_c, y_c, z_c = self.matrix
        return (
            x_a * a_g + x_b * b_g + x_c * c_g,
            y_a * a_g + y_b * b_g + y_c * c_g,
            z_a * a_g + z_b * b_g + z_c * c_g,
        )


FAMILIES['CalRGB'] = ColorSpaceFamily('CalRGB', CalRGBSpace)


class LabSpace(CIESpace):

    """
    A Lab color space.
    """

    NCOMPONENTS = 3

    def __init__(self, family, params):
        super(LabSpace, self).__init__(family, params)
        ranges = params[0].get('Range', (-100, 100, -100, 100))
        self.a_range = tuple(ranges[:2])
        self.b_range = tuple(ranges[2:4])
        self.default = (
            0,  # L always has range 0 to 100
            max(self.a_range[0], min(self.a_range[1], 0)),
            max(self.b_range[0], min(self.b_range[1], 0))
        )

    @staticmethod
    def check_params(params):
        def _test(WhitePoint, BlackPoint=None, Range=None):
            #pylint: disable=W0613,C0103,C0111
            # run params through this to force TypeErrors
            pass
        _test(**params)

    def as_xyz(self, value):
        #pylint: disable=C0103
        l_star, a_star, b_star = value
        m = (l_star + 16) / 116.0
        l = m + a_star / 500.0
        n = m - b_star / 200.0
        return (
            self.white_point[0] * self.g_transform(l),
            self.white_point[1] * self.g_transform(m),
            self.white_point[2] * self.g_transform(n),
        )

    @staticmethod
    def g_transform(x):  #pylint: disable=C0103
        "The function used in the second transformation stage."
        # Taken from the PDF spec 1.7, p. 252xs
        if 29 * x > 6:
            return x ** 3
        return 108.0 / 841.0 * (x - 4 / 29.0)

    def get_ranges(self):
        return (0, 100) + self.a_range + self.b_range


FAMILIES['Lab'] = ColorSpaceFamily('Lab', LabSpace)


class IndexedSpace(ColorSpace):

    """
    An indexed color space.

    From the spec: (1.7, p. 262): "An Indexed color space allows a PDF
    content stream to use small integers as indices into a color map or color
    table of arbitrary colors in some other space. A PDF consumer application
    treats each sample value as an index into the color table and uses the
    color value it finds there."

    """

    def __init__(self, family, params):
        super(IndexedSpace, self).__init__(family, default=0, ncomponents=1)
        def setup(base, hival, lookup):
            #pylint: disable=W0201,C0111
            self.base = base
            self.hival = hival
            lookup = pdfminer.pdftypes.resolve1(lookup)
            if isinstance(lookup, pdfminer.pdftypes.PDFStream):
                lookup = lookup.get_data()
            self.lookup = lookup
        setup(*params)

    def make_color(self, value=None):
        "Overrides supermethod to call its base profile's method."
        if value is None:
            value = self.default  # Typically 0, but can be overridden
        color = self.base.make_color(self.get_value(value))
        color.index_val = (self, value)

    def get_value(self, value):
        "Return the value corresponding to the color in the base space."
        comp_bytes = (self.lookup[value + self.hival * n]
                      for n in xrange(self.base.ncomponents))
        base_range = self.base.get_ranges()
        mins = base_range[::2]
        maxes = base_range[1::2]
        return (
            max(min_val, min(max_val, ord(comp_byte)))
            for comp_byte, max_val, min_val in zip(comp_bytes, maxes, mins)
        )

FAMILIES['Indexed'] = ColorSpaceFamily('Indexed', IndexedSpace)


class ICCSpace(ColorSpace):

    "A simple implementation of ICC colors using the alternate color space."

    # From the spec (v1.7; Section 4.5 p.253):
    # > An alternate color space to be used in case the one specified
    # > in the stream data is not supported (for example, by
    # > applications designed for earlier versions of PDF). The
    # > alternate space may be any valid color space (except a Pattern
    # > color space) that has the number of components specified by
    # > N. If this entry is omitted and the application does not
    # > understand the ICC profile data, the color space used is
    # > DeviceGray, DeviceRGB, or DeviceCMYK, depending on whether
    # > the value of N is 1, 3, or 4, respectively

    def __init__(self, family, params):
        stream = params[0]
        self.n = stream['N']
        alternate = stream.get('Alternate')
        if alternate is None:
            if self.n == 1:
                self.alternate = DEVICE_GRAY
            elif self.n == 3:
                self.alternate = DEVICE_RGB
            elif self.n == 4:
                self.alternate = DEVICE_CMYK
            else:
                raise ValueError('ICC space must have 1, 3 or 4 componnents')
        else:
            self.alternate = make_color_space(alternate)
        super(ICCSpace, self).__init__(family, self.n)

    def make_color(self, value=None):
        "Use the alternate color's implementation."
        return self.alternate.make_color(value)


FAMILIES['ICCBased'] = ColorSpaceFamily('ICCBased', ICCSpace)

############################################################################
#             Stub implementations Pattern, Separation                     #
############################################################################


class StubColorSpaceFamily(ColorSpaceFamily):

    "A stub implementation with only a number of components."

    def __init__(self, name, ncomponents):
        super(StubColorSpaceFamily, self).__init__(name, None)
        self.ncomponents = ncomponents

    def make_space(self, params=None):
        # Overrides supermethod to discard params and create generic
        # colorspace
        return ColorSpace(self, self.ncomponents, (0,) * self.ncomponents)


for name, ncomps in [('Pattern', 1), ('Separation', 1)]:
    FAMILIES[name] = StubColorSpaceFamily(name, ncomps)


def make_color_space(spec):
    "Translate a string or list into a ColorSpace class."
    spec = pdfminer.pdftypes.resolve_all(spec)
    if isinstance(spec, list):
        name = pdfminer.psparser.literal_name(spec[0])
        params = spec[1:]
    else:
        name = pdfminer.psparser.literal_name(spec)
        params = []
    return FAMILIES[name].make_space(params)
