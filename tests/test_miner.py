"Unit tests for the miner module."

import unittest
import mock
import os

import minecart.miner
import minecart.color
import pdfminer.pdfdevice

TRAVIS = int(os.getenv("TRAVIS", 0))


def _patched_callable(obj):
    "Monkeypatch to allow automocking of classmethods and staticmethods."
    # See https://code.google.com/p/mock/issues/detail?id=241 and
    # http://bugs.python.org/issue23078 for the relevant bugs this
    # monkeypatch fixes
    if isinstance(obj, type):
        return True
    if getattr(obj, '__call__', None) is not None:
        return True
    if (isinstance(obj, (staticmethod, classmethod)) and
            mock._callable(obj.__func__)):
        return True
    return False


mock._callable = _patched_callable  # pylint: disable=W0212


class TestStrokeState(unittest.TestCase):

    "Testing of the StrokeState."

    def test_from_gs(self):
        "Ensure StrokeState is created properly from a graphicstate."
        gs = minecart.miner.ColoredState()  # pylint: disable=C0103
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
        "Ensure FillState is created properly from a graphicstate."
        gs = minecart.miner.ColoredState()  # pylint: disable=C0103
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
        "Ensure the ColoredInterpreter uses a ColoredState."
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
    def test_init_resources_colormaps(self, supermethod):
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

    # pylint: disable=C0103

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
        self.assertIsInstance(self.interp.graphicstate.stroke_color,
                              minecart.color.Color)
        self.assertEqual(self.interp.graphicstate.stroke_color.value,
                         (0.5,))
        pop.assert_called_once_with(self.interp, 1)
        pop.reset_mock()

        # Now we test with RGB
        pop.return_value = (0.5, .25, .125)
        self.interp.do_CS(pdfminer.pdfinterp.LITERAL_DEVICE_RGB)
        self.interp.do_SCN()
        self.assertIsInstance(self.interp.graphicstate.stroke_color,
                              minecart.color.Color)
        self.assertEqual(self.interp.graphicstate.stroke_color.value,
                         (0.5, .25, .125))
        pop.assert_called_once_with(self.interp, 3)
        pop.reset_mock()

        # Now we test with CMYK
        pop.return_value = (0.5, .25, .125, .0625)
        self.interp.do_CS(pdfminer.pdfinterp.LITERAL_DEVICE_CMYK)
        self.interp.do_SCN()
        self.assertIsInstance(self.interp.graphicstate.stroke_color,
                              minecart.color.Color)
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
        self.assertIsInstance(self.interp.graphicstate.fill_color,
                              minecart.color.Color)
        self.assertEqual(self.interp.graphicstate.fill_color.value,
                         (0.5,))
        pop.assert_called_once_with(self.interp, 1)
        pop.reset_mock()

        # Now we test with RGB
        pop.return_value = (0.5, .25, .125)
        self.interp.do_cs(pdfminer.pdfinterp.LITERAL_DEVICE_RGB)
        self.interp.do_scn()
        self.assertIsInstance(self.interp.graphicstate.fill_color,
                              minecart.color.Color)
        self.assertEqual(self.interp.graphicstate.fill_color.value,
                         (0.5, .25, .125))
        pop.assert_called_once_with(self.interp, 3)
        pop.reset_mock()

        # Now we test with CMYK
        pop.return_value = (0.5, .25, .125, .0625)
        self.interp.do_cs(pdfminer.pdfinterp.LITERAL_DEVICE_CMYK)
        self.interp.do_scn()
        self.assertIsInstance(self.interp.graphicstate.fill_color,
                              minecart.color.Color)
        self.assertEqual(self.interp.graphicstate.fill_color.value,
                         (0.5, .25, .125, .0625))
        pop.assert_called_once_with(self.interp, 4)


class TestDeviceLoader(unittest.TestCase):

    "Test the DeviceLoader class."

    def setUp(self):
        self.device = minecart.miner.DeviceLoader(object())
        self.device.page = mock.MagicMock(autospec=pdfminer.pdfpage.PDFPage)

    def test_init(self):
        "Test correct initialization of the device state."
        device = minecart.miner.DeviceLoader(object())
        self.assertIsNone(device.page)
        self.assertIsNone(device.str_container)
        self.assertEqual(device.unit, 1)

    @mock.patch("minecart.miner.Page", autospec=True)
    def test_begin_page(self, minecart_page):
        "Ensure creation of a new page and updating of `.unit`."
        page = mock.MagicMock(autospec=pdfminer.pdfpage.PDFPage)
        page.attrs = {'UserUnit': 2}
        self.device.begin_page(page, None)
        minecart_page.assert_called_once_with(page)
        self.assertEqual(self.device.unit, 2)

    def test_set_ctm(self):
        "Ensure the CTM responds to the `.unit` parameter."
        ctm = (1, 1, 1, 2, 2, 2)
        self.device.set_ctm(ctm)  # .unit is 1 from initialization
        self.assertEqual(self.device.ctm, ctm)
        self.device.unit = 2
        self.device.set_ctm(ctm)
        self.assertEqual(self.device.ctm, (2, 2, 2, 4, 4, 4))

    @mock.patch("minecart.miner.Shape", autospec=True)
    def test_paint_path_coordinates(self, minecart_shape):
        "Test the coordinate conversion when painting a path."
        user_path = [
            ('m', 0, 0),
            ('l', 5, 5),
            ('c', 10, 10, 10, 7.5, 10, 5),
            ('v', 15, 5, 20, 10),
            ('y', 10, 20, 0, 10),
            ('h',)
            # pdfminer converts 're' to mlllh for us
        ]
        # The CTM is chosen to be a 90 degree counter-clockwise rotation,
        # shifted by <5, 5>, with UserUnit set to 2
        expected_path = [
            ('m', 10, 10),
            ('l', 0, 20),
            ('c', -10, 30, -5, 30, 0, 30),
            ('v', 0, 40, -10, 50),
            ('y', -30, 30, -10, 10),
            ('h',)
        ]
        self.device.unit = 2
        self.device.set_ctm((0, 1, -1, 0, 5, 5))  # [TL, BL, TR, BR]
        self.device.paint_path(object(), False, False, False, user_path)
        minecart_shape.assert_called_once_with(None, None, False,
                                               expected_path)

    @mock.patch("minecart.miner.FillState.from_gs", autospec=True)
    @mock.patch("minecart.miner.StrokeState.from_gs", autospec=True)
    @mock.patch("minecart.miner.Shape", autospec=True)
    def test_paint_path_graphics(self, shape, stroke_from_gs, fill_from_gs):
        "Test correct passing of stroke/fill parameters to the Shape."
        gstate = minecart.miner.ColoredState()
        shape_obj = shape.return_value = object()
        path = [('m', 10, 10), ('l', 20, 20), ('l', 30, 10), ('h',)]
        self.device.ctm = (1, 0, 0, 1, 0, 0)

        self.device.paint_path(gstate, True, False, False, path)
        self.device.page.add_shape.assert_called_once_with(shape_obj)
        shape.assert_called_once_with(stroke_from_gs.return_value, None,
                                      False, path)
        shape.reset_mock()
        self.device.page.add_shape.reset_mock()
        self.device.paint_path(gstate, False, True, False, path)
        self.device.page.add_shape.assert_called_once_with(shape_obj)
        shape.assert_called_once_with(None, fill_from_gs.return_value,
                                      False, path)
        shape.reset_mock()
        self.device.page.add_shape.reset_mock()
        self.device.paint_path(gstate, False, False, True, path)
        self.device.page.add_shape.assert_called_once_with(shape_obj)
        shape.assert_called_once_with(None, None, True, path)
        shape.reset_mock()
        self.device.page.add_shape.reset_mock()
        self.device.paint_path(gstate, True, True, True, path)
        self.device.page.add_shape.assert_called_once_with(shape_obj)
        shape.assert_called_once_with(stroke_from_gs.return_value,
                                      fill_from_gs.return_value,
                                      True, path)

    def test_paint_path_int(self):
        "Test graphics params flowing through to Shape properly."
        gstate = minecart.miner.ColoredState()
        gstate.linewidth = 5
        gstate.linecap = gstate.linejoin = 2
        gstate.miterlimit = .5
        gstate.dash = ([1, 1], 0)
        gstate.stroke_color = minecart.color.DEVICE_RGB.make_color((0, 1, 1))
        gstate.fill_color = minecart.color.DEVICE_RGB.make_color((1, 0, 0))
        path = [('m', 10, 10), ('l', 20, 20), ('l', 30, 10), ('h',)]
        self.device.page = mock.MagicMock(spec_set=minecart.miner.Page)
        self.device.ctm = (1, 0, 0, 1, 0, 0)
        self.device.paint_path(gstate, True, True, False, path)
        self.device.page.add_shape.assert_called_once()
        shape = self.device.page.add_shape.call_args[0][0]
        self.assertEqual(shape.stroke.linewidth, 5)
        self.assertEqual(shape.stroke.linecap, 2)
        self.assertEqual(shape.stroke.linejoin, 2)
        self.assertEqual(shape.stroke.miterlimit, .5)
        self.assertEqual(shape.stroke.dash, ([1, 1], 0))
        self.assertEqual(shape.stroke.color.value, (0, 1, 1))
        self.assertIs(shape.stroke.color.space, minecart.color.DEVICE_RGB)
        self.assertEqual(shape.fill.color.value, (1, 0, 0))
        self.assertEqual(shape.fill.color.space, minecart.color.DEVICE_RGB)

    @mock.patch("minecart.miner.Image", autospec=True)
    def test_render_image(self, image):
        "Test the creation of an image."
        self.device.ctm = object()
        stream = object()
        self.device.render_image(object(), stream)
        image.assert_called_once_with(self.device.ctm, stream)

    @mock.patch("minecart.miner.DeviceLoader.render_string_hv",
                autospec=True)
    def test_render_string_horizontal(self, render_string_hv):
        args = ['seq', 'matrix', 'vec', 'font', 'fontsize', 'scaling',
                'charspace', 'wordspace', 'rise', 'dxscale']
        self.device.render_string_horizontal(*args)
        render_string_hv.assert_called_once_with(self.device, 'horizontal',
                                                 *args)

    @mock.patch("minecart.miner.DeviceLoader.render_string_hv",
                autospec=True)
    def test_render_string_vertical(self, render_string_hv):
        args = ['seq', 'matrix', 'vec', 'font', 'fontsize', 'scaling',
                'charspace', 'wordspace', 'rise', 'dxscale']
        self.device.render_string_vertical(*args)
        render_string_hv.assert_called_once_with(self.device, 'vertical',
                                                 *args)

    @unittest.skipIf(TRAVIS, "Skipping for Travis build")
    def test_render_char(self):
        self.fail("Not implemented")

    @unittest.skipIf(TRAVIS, "Skipping for Travis build")
    def test_render_string_hv(self):
        self.fail("Not implemented")


class TestDocument(unittest.TestCase):

    "Test the Document class."

    @mock.patch("pdfminer.pdfdocument.PDFDocument", autospec=True)
    @mock.patch("pdfminer.pdfparser.PDFParser", autospec=True)
    def test_init(self, pdfparser, pdfdocument):
        "Test correct initializing of the Document object."
        pdffile = object()
        doc = minecart.miner.Document(pdffile)
        pdfdocument.assert_called_once_with(doc.parser, caching=True)
        pdfparser.assert_called_once_with(pdffile)

    @unittest.skipIf(TRAVIS, "Skipping for Travis build")
    def test_iter_pages(self):
        "Ensure iter_pages runs through all pages."
        self.fail("Not implemented!")

    @unittest.skipIf(TRAVIS, "Skipping for Travis build")
    def test_get_page(self):
        ""
        self.fail("Not implemented!")
