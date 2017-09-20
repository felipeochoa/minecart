"Unit testing for the color module."

import unittest
import mock
import pdfminer
import os

import minecart
import minecart.color


class TestColor(unittest.TestCase):

    "Test the base color class."

    def test_creation(self):
        space = object()
        value = object()
        color = minecart.color.Color(space, value)
        self.assertIs(space, color.space)
        self.assertIs(value, color.value)
        self.assertIsNone(color.index_val)

    def test_creation_with_default(self):
        space = mock.MagicMock(spec_set=minecart.color.ColorSpace)
        space.get_default.return_value = default = object()
        color = minecart.color.Color(space)
        self.assertIs(color.value, default)
        self.assertIs(color.space, space)
        self.assertIsNone(color.index_val)
        space.get_default.assert_called_once_with()

    def test_as_rgb(self):
        space = mock.MagicMock(spec_set=minecart.color.ColorSpace)
        value = object()
        color = minecart.color.Color(space, value)
        space.as_rgb.return_value = rgb = object()
        self.assertIs(rgb, color.as_rgb())
        space.as_rgb.assert_called_once_with(value)


class TestColorSpace(unittest.TestCase):

    "Test the base ColorSpace class."

    def test_creation(self):
        family = object()
        default = object()
        ncomps = object()
        space = minecart.color.ColorSpace(family, ncomps, default)
        self.assertIs(family, space.family)
        self.assertIs(default, space.default)
        self.assertIs(ncomps, space.ncomponents)

    def test_get_default(self):
        family = object()
        default = object()
        ncomps = object()
        space = minecart.color.ColorSpace(family, ncomps, default)
        self.assertIs(default, space.get_default())

    def test_get_ranges(self):
        family = object()
        default = object()
        ncomps = 3
        space = minecart.color.ColorSpace(family, ncomps, default)
        self.assertEqual((0, 1, 0, 1, 0, 1), space.get_ranges())

    def test_as_rgb(self):
        family = object()
        default = object()
        ncomps = object()
        space = minecart.color.ColorSpace(family, ncomps, default)
        self.assertRaises(NotImplementedError, space.as_rgb, object())

    def test_make_color(self):
        family = object()
        default = object()
        ncomps = object()
        space = minecart.color.ColorSpace(family, ncomps, default)
        value = object()
        color = space.make_color(value)
        self.assertIs(space, color.space)
        self.assertIs(value, color.value)
        self.assertIsInstance(color, minecart.color.Color)


class TestColorSpaceFamily(unittest.TestCase):

    "Test the default ColorSpaceFamily."

    def test_creation(self):
        name = object()
        cs_class = object()
        family = minecart.color.ColorSpaceFamily(name, cs_class)
        self.assertIs(name, family.name)
        self.assertIs(cs_class, family.color_space_class)

    def test_make_space(self):
        name = object()
        cs_class = mock.MagicMock(spec_set=minecart.color.ColorSpace)
        family = minecart.color.ColorSpaceFamily(name, cs_class)
        params = object()
        space = family.make_space(params)
        cs_class.assert_called_once_with(family, params)
        self.assertIs(space, cs_class.return_value)

@mock.patch('minecart.color.DeviceSpace', autospec=True)
class TestDeviceFamily(unittest.TestCase):

    "Test the DeviceFamily color space family."

    def test_creation(self, dev_space):
        name = object()
        default = object()
        family = minecart.color.DeviceFamily(name, default)
        self.assertIs(family.name, name)
        dev_space.assert_called_once_with(family=family, default=default)
        self.assertIsInstance(family.color_space, minecart.color.ColorSpace)
        self.assertIsNone(family.color_space_class)

    def test_make_space(self, dev_space):
        name = object()
        default = object()
        family = minecart.color.DeviceFamily(name, default)
        space = family.make_space()
        space2 = family.make_space()
        self.assertIs(space, space2)
        dev_space.assert_called_once_with(family=family, default=default)


class TestDeviceSpace(unittest.TestCase):

    "Common code for the 3 device spaces."

    DEFAULT = None
    NAME = None
    VALUE = None
    RESULT = (.5, .5, .5)

    def setUp(self):
        if self.NAME is not None:
            self.family = minecart.color.DeviceFamily(self.NAME, self.DEFAULT)
            self.space = minecart.color.DeviceSpace(self.family, self.DEFAULT)

    def test_creation(self):
        if self.NAME is not None:
            self.assertIs(self.space.family, self.family)
            self.assertEqual(self.space.ncomponents, len(self.DEFAULT))
        else:
            # test invalid cration
            self.assertRaises(ValueError, minecart.color.DeviceFamily,
                              '<Invalid>', (0,))

    def test_as_rgb(self):
        if self.NAME is not None:
            self.assertEqual(self.RESULT, self.space.as_rgb(self.VALUE))


class TestDeviceSpaceGray(TestDeviceSpace):

    "Test the DeviceGray color space."

    DEFAULT = (0,)
    NAME = 'DeviceGray'
    VALUE = (.5,)


class TestDeviceSpaceRGB(TestDeviceSpace):

    "Test the DeviceRGB color space."

    DEFAULT = (0, 0, 0)
    NAME = 'DeviceRGB'
    VALUE = (.5, .5, .5)


class TestDeviceSpaceCMYK(TestDeviceSpace):

    "Test the DeviceCMYK color space."

    DEFAULT = (0, 0, 0, 1)
    NAME = 'DeviceCMYK'
    VALUE = (.5, .5, .5, 0)

    def test_as_rgb_2(self):
        self.assertEqual(self.RESULT, self.space.as_rgb((.25, .25, .25, .25)))
        self.assertEqual(self.RESULT, self.space.as_rgb((0, 0, 0, .5)))

    def test_as_rgb_subtractive(self):
        self.assertEqual((.25, .25, .25),
                         self.space.as_rgb((.75, .75, .75, 0)))


class TestCIEColor(unittest.TestCase):

    "Testing of the CIEColor class"

    def test_as_xyz(self):
        "Ensure the CIEColor as_xyz() calls the color space's method."
        space = mock.MagicMock(spec_set=minecart.color.CIESpace)
        color = minecart.color.CIEColor(space, object())
        self.assertEqual(color.as_xyz(), space.as_xyz.return_value)
        space.as_xyz.assert_called_once_with(color.value)


class TestCIESpace(unittest.TestCase):

    "Testing of the abstract CIESpace class."

    def test_init_params(self):
        "Ensure the initializing parameters are properly checked."
        family = mock.MagicMock(spec_set=minecart.color.ColorSpaceFamily)
        self.assertRaises(TypeError, minecart.color.CIESpace, family, [])
        self.assertRaises(TypeError, minecart.color.CIESpace, family,
                          ['a', 'b'])
        self.assertRaises(TypeError, minecart.color.CIESpace, family,
                          ['WhitePoint'])

    def test_init_attrs(self):
        "Ensure the initializer sets the white and black point attributes."
        family = mock.MagicMock(spec_set=minecart.color.ColorSpaceFamily)
        # First only white is specified, black should default to (0, 0, 0)
        white = (.25, 1, .125)
        space = minecart.color.CIESpace(family, [{'WhitePoint': white}])
        self.assertEqual(white, space.white_point)
        self.assertEqual((0, 0, 0), space.black_point)
        # Now we specify both
        white = (.125, 1, .25)
        black = (0, .25, .125)
        space = minecart.color.CIESpace(family, [{'WhitePoint': white,
                                                  'BlackPoint': black}])
        self.assertEqual(white, space.white_point)
        self.assertEqual(black, space.black_point)
        # Now we pass invalid values of white point
        white = (-.25, 1, .125)
        self.assertRaises(ValueError, minecart.color.CIESpace, family,
                          [{'WhitePoint': white}])
        white = (.25, 1, -.125)
        self.assertRaises(ValueError, minecart.color.CIESpace, family,
                          [{'WhitePoint': white}])
        white = (.25, .95, .125)
        self.assertRaises(ValueError, minecart.color.CIESpace, family,
                          [{'WhitePoint': white}])
        # And finally invalid values of black point
        white = (.25, 1, .125)
        black = (-1, 0, 0)
        self.assertRaises(ValueError, minecart.color.CIESpace, family,
                          [{'WhitePoint': white, 'BlackPoint': black}])
        black = (0, -1, 0)
        self.assertRaises(ValueError, minecart.color.CIESpace, family,
                          [{'WhitePoint': white, 'BlackPoint': black}])
        black = (0, 0, -1)
        self.assertRaises(ValueError, minecart.color.CIESpace, family,
                          [{'WhitePoint': white, 'BlackPoint': black}])

    def test_as_rgb(self):
        "Test the conversion of XYZ values into sRGB values."
        # These test values were obtained randomly from
        # https://www.colorcodehex.com//
        test_values = (
            #    X       Y       Z         R       G      B
            [(.19244, .10728, 0.04927), (.6902, .1373, .2235)],
            [(.01171, .00922, 0.03731), (.0627, .0824, .2157)],
            [(.62216, .72826, 1.05385), (.6431, .9098, 1)],
            [(.04631, .07551, 0.01972), (.1686, .3451, .0863)],
        )
        minecart.color.CIESpace.as_xyz = lambda self, value: value
        family = mock.MagicMock(spec_set=minecart.color.ColorSpaceFamily)
        space = minecart.color.CIESpace(family,
                                        [{'WhitePoint': (.01, 1, .01)}])
        for xyz, rgb in test_values:
            rgb_test = space.as_rgb(xyz)
            for comp_a, comp_b in zip(rgb_test, rgb):
                self.assertLessEqual(abs(comp_a - comp_b), .00006)

    def test_make_color(self):
        "Ensure make color uses CIEColor."
        family = mock.MagicMock(spec_set=minecart.color.ColorSpaceFamily)
        space = minecart.color.CIESpace(family,
                                        [{'WhitePoint': (.01, 1, .01)}])
        self.assertIsInstance(space.make_color([1]), minecart.color.CIEColor)


class TestICCSpace(unittest.TestCase):

    def test_no_alternate_n1(self):
        family = minecart.color.ColorSpaceFamily(
            'ICCBased', minecart.color.ICCSpace
        )
        attrs = {'N': 1}
        stream = pdfminer.pdftypes.PDFStream(attrs, b'')
        space = family.make_space([stream])
        self.assertIs(space.alternate, minecart.color.DEVICE_GRAY)
        color = space.make_color((.25,))
        self.assertEqual(color.as_rgb(), (.25, .25, .25))

    def test_no_alternate_n3(self):
        family = minecart.color.ColorSpaceFamily(
            'ICCBased', minecart.color.ICCSpace
        )
        attrs = {'N': 3}
        stream = pdfminer.pdftypes.PDFStream(attrs, b'')
        space = family.make_space([stream])
        self.assertIs(space.alternate, minecart.color.DEVICE_RGB)
        color = space.make_color((.25, .25, .25))
        self.assertEqual(color.as_rgb(), (.25, .25, .25))

    def test_no_alternate_n4(self):
        family = minecart.color.ColorSpaceFamily(
            'ICCBased', minecart.color.ICCSpace
        )
        attrs = {'N': 4}
        stream = pdfminer.pdftypes.PDFStream(attrs, b'')
        space = family.make_space([stream])
        self.assertIs(space.alternate, minecart.color.DEVICE_CMYK)
        color = space.make_color((.25, .25, .25, 0))
        self.assertEqual(color.as_rgb(), (.75, .75, .75))

    def test_alternate_n1(self):
        family = minecart.color.ColorSpaceFamily(
            'ICCBased', minecart.color.ICCSpace
        )
        attrs = {
            'N': 1,
            'Alternate': ['CalGray', {'WhitePoint': (.5, 1, .5)}]
        }
        stream = pdfminer.pdftypes.PDFStream(attrs, b'')
        space = family.make_space([stream])
        self.assertEqual(space.alternate.family.name, 'CalGray')
        color = space.make_color((.25,))
        self.assertIsInstance(color, minecart.color.CIEColor)

    def test_alternate_n3(self):
        family = minecart.color.ColorSpaceFamily(
            'ICCBased', minecart.color.ICCSpace
        )
        attrs = {
            'N': 3,
            'Alternate': ['CalRGB', {'WhitePoint': (.5, 1, .5)}]
        }
        stream = pdfminer.pdftypes.PDFStream(attrs, b'')
        space = family.make_space([stream])
        self.assertEqual(space.alternate.family.name, 'CalRGB')
        color = space.make_color((.25,))
        self.assertIsInstance(color, minecart.color.CIEColor)

    def test_ai_file_as_pdf(self):
        "Test real-world parsing of ICCBased colors."
        # Test file from snoyer/minecart
        pdfpath = os.path.join(os.path.dirname(__file__),
                               'testdocs', 'ai-files-are-pdfs.pdf')
        doc = minecart.Document(open(pdfpath, 'rb'))
        page = doc.get_page(0)
        red = (0.929, 0.11, 0.141)
        black = (0.137, 0.122, 0.125)
        blue = (0.18, 0.192, 0.573)
        self.assertEqual(
            set(tuple(shape.fill.color.as_rgb()) for shape in page.shapes),
            {red, black, blue}
        )
