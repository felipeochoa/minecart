"Unit tests for the miner module."

import unittest
import mock

import minecart.miner
import minecart.color
import pdfminer.pdfdevice

class TestStrokeState(unittest.TestCase):

    "Testing of the StrokeState."

    def test_from_gs(self):
        gs = minecart.miner.ColoredState()  #pylint: disable=C0103
        gs.linewidth = 3
        gs.linecap = 1
        gs.linejoin = 2
        gs.miterlimit = 1.5
        gs.dash = ([2, 1], 0)
        gs.stroke_color = color = object()
        stroke = minecart.miner.StrokeState.from_gs(gs)
        self.assertIsInstance(stroke, minecart.miner.StrokeState)
        self.assertEqual(stroke.linewidth, 3)
        self.assertEqual(stroke.linecap, 1)
        self.assertEqual(stroke.linejoin, 2)
        self.assertEqual(stroke.miterlimit, 1.5)
        self.assertEqual(stroke.dash, ([2, 1], 0))
        self.assertEqual(stroke.color, color)


class TestFillState(unittest.TestCase):

    "Testing of the FillState"

    def test_from_gs(self):
        gs = minecart.miner.ColoredState()  #pylint: disable=C0103
        gs.fill_color = color = object()
        fill = minecart.miner.FillState.from_gs(gs)
        self.assertIsInstance(fill, minecart.miner.FillState)
        self.assertIs(fill.color, color)


class TestColoredInterpreter(unittest.TestCase):

    "Testing of the expanded interpreter."

    def setUp(self):
        rsrcmgr = object()
        device = pdfminer.pdfdevice.PDFDevice(rsrcmgr)
        self.interp = minecart.miner.ColoredInterpreter(rsrcmgr, device)

    @mock.patch('pdfminer.pdfinterp.PDFPageInterpreter.init_state',
                autospec=True)
    def test_init_state(self, supermethod):
        ctm = (1, 0, 0, 1, 0, 0)
        self.interp.init_state(ctm)
        supermethod.assert_called_once_with(self.interp, ctm)
        self.assertIsInstance(self.interp.graphicstate,
                              minecart.miner.ColoredState)

    @mock.patch('pdfminer.pdfinterp.PDFPageInterpreter.init_resources',
                autospec=True)
    def test_init_resources(self, supermethod):
        "Test init_resources with no color maps"
        self.interp.init_resources(None)
        supermethod.assert_called_once_with(self.interp, None)
        self.assertEqual(
            self.interp.csmap,
            {name: minecart.color.FAMILIES[name].make_space()
             for name in ('DeviceRGB', 'DeviceCMYK', 'DeviceGray')})

    @mock.patch('pdfminer.pdfinterp.PDFPageInterpreter.init_resources',
                autospec=True)
    def test_init_resources_with_colormaps(self, supermethod):
        "Test init_resources when there are color maps given."
        self.interp.init_resources({'ColorSpace': {
            'space1': ['DeviceRGB'],
            'DefaultGray': ['CalGray', {'WhitePoint': (1, 1, 1)}]
        }})
        supermethod.assert_called_once_with(self.interp, {})
        target_map = {name: minecart.color.FAMILIES[name].make_space()
                      for name in ('DeviceRGB', 'DeviceCMYK', 'DeviceGray')}
        target_map['space1'] = target_map['DeviceRGB']
        target_map['DefaultGray'] = minecart.color.FAMILIES[
            'CalGray'].make_space([{'WhitePoint': (1, 1, 1)}])
        target_map['DeviceGray'] = target_map['DefaultGray']
        self.assertEqual(self.interp.csmap, target_map)


class TestColoredInterpreterGraphics(unittest.TestCase):

    "Test the graphics commands on the ColoredInterpreter."

    def setUp(self):
        rsrcmgr = object()
        device = pdfminer.pdfdevice.PDFDevice(rsrcmgr)
        self.interp = minecart.miner.ColoredInterpreter(rsrcmgr, device)
        self.interp.init_state((1, 0, 0, 1, 0, 0))
        self.interp.init_resources(None)

    def test_do_G(self):
        "Test setting the stroking colorspace to gray."
        self.interp.do_G(0.25)
        self.assertEqual(self.interp.scs,
                         minecart.color.FAMILIES['DeviceGray'].make_space())
        self.assertEqual(self.interp.graphicstate.stroke_color.value, (0.25,))

    def test_do_g(self):
        "Test setting the fill colorspace to gray."
        self.interp.do_g(0.25)
        self.assertEqual(self.interp.ncs,
                         minecart.color.FAMILIES['DeviceGray'].make_space())
        self.assertEqual(self.interp.graphicstate.fill_color.value, (0.25,))

    def test_do_RG(self):
        "Test setting the stroke colorspace to RGB."
        self.interp.do_RG(.125, .5, .25)
        self.assertEqual(self.interp.scs,
                         minecart.color.FAMILIES['DeviceRGB'].make_space())
        self.assertEqual(self.interp.graphicstate.stroke_color.value,
                         (.125, .5, .25))

    def test_do_rg(self):
        "Test setting the fill colorspace to RGB."
        self.interp.do_rg(.5, .25, .125)
        self.assertEqual(self.interp.ncs,
                         minecart.color.FAMILIES['DeviceRGB'].make_space())
        self.assertEqual(self.interp.graphicstate.fill_color.value,
                         (.5, .25, .125))

    def test_do_K(self):
        "Test setting the stroke colorspace to CMYK."
        self.interp.do_K(.125, .5, .25, .0625)
        self.assertEqual(self.interp.scs,
                         minecart.color.FAMILIES['DeviceCMYK'].make_space())
        self.assertEqual(self.interp.graphicstate.stroke_color.value,
                         (.125, .5, .25, .0625))

    def test_do_k(self):
        "Test setting the fill colorspace to RGB."
        self.interp.do_k(.0625, .5, .25, .125)
        self.assertEqual(self.interp.ncs,
                         minecart.color.FAMILIES['DeviceCMYK'].make_space())
        self.assertEqual(self.interp.graphicstate.fill_color.value,
                         (.0625, .5, .25, .125))

    @mock.patch('pdfminer.pdfinterp.PDFPageInterpreter.pop', autospec=True)
    def test_do_SCN(self, pop):
        "Test setting the stroking color."
        # First we test Gray
        pop.return_value = (0.5,)
        self.interp.do_CS(pdfminer.pdfinterp.LITERAL_DEVICE_GRAY)
        self.interp.do_SCN()
        self.assertEqual(self.interp.graphicstate.stroke_color.value,
                         (0.5,))
        pop.assert_called_once_with(self.interp, 1)
        pop.reset_mock()

        # Now we test with RGB
        pop.return_value = (0.5, .25, .125)
        self.interp.do_CS(pdfminer.pdfinterp.LITERAL_DEVICE_RGB)
        self.interp.do_SCN()
        self.assertEqual(self.interp.graphicstate.stroke_color.value,
                         (0.5, .25, .125))
        pop.assert_called_once_with(self.interp, 3)
        pop.reset_mock()

        # Now we test with CMYK
        pop.return_value = (0.5, .25, .125, .0625)
        self.interp.do_CS(pdfminer.pdfinterp.LITERAL_DEVICE_CMYK)
        self.interp.do_SCN()
        self.assertEqual(self.interp.graphicstate.stroke_color.value,
                         (0.5, .25, .125, .0625))
        pop.assert_called_once_with(self.interp, 4)

    @mock.patch('pdfminer.pdfinterp.PDFPageInterpreter.pop', autospec=True)
    def test_do_scn(self, pop):
        "Test setting the fill color."
        # First we test Gray
        pop.return_value = (0.5,)
        self.interp.do_cs(pdfminer.pdfinterp.LITERAL_DEVICE_GRAY)
        self.interp.do_scn()
        self.assertEqual(self.interp.graphicstate.fill_color.value,
                         (0.5,))
        pop.assert_called_once_with(self.interp, 1)
        pop.reset_mock()

        # Now we test with RGB
        pop.return_value = (0.5, .25, .125)
        self.interp.do_cs(pdfminer.pdfinterp.LITERAL_DEVICE_RGB)
        self.interp.do_scn()
        self.assertEqual(self.interp.graphicstate.fill_color.value,
                         (0.5, .25, .125))
        pop.assert_called_once_with(self.interp, 3)
        pop.reset_mock()

        # Now we test with CMYK
        pop.return_value = (0.5, .25, .125, .0625)
        self.interp.do_cs(pdfminer.pdfinterp.LITERAL_DEVICE_CMYK)
        self.interp.do_scn()
        self.assertEqual(self.interp.graphicstate.fill_color.value,
                         (0.5, .25, .125, .0625))
        pop.assert_called_once_with(self.interp, 4)


class TestDeviceLoader(unittest.TestCase):

    "Test the DeviceLoader class."

    def test_x(self):
        self.fail("No test coverage of the DeviceLoader class!")


class TestDocument(unittest.TestCase):

    "Test the Document class."

    def test_x(self):
        self.fail("No test coverage of the Document class!")
