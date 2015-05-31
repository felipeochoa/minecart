"Unit testing for the color module."

import unittest
import mock

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
