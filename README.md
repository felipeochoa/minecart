
minecart: A Pythonic interface to PDF documents
===============================================

![Travis CI build status (Linux)](https://travis-ci.org/felipeochoa/minecart.svg?branch=master)
![Coverage Status](https://coveralls.io/repos/felipeochoa/minecart/badge.svg)(https://coveralls.io/r/felipeochoa/minecart)

`minecart` is a Python package that simplifies the extraction of text,
images, and shapes from a PDF document. It depends on
[`pdfminer`](https://github.com/euske/pdfminer). `minecart` takes
inspiration from Tim McNamara's
[`slate`](https://github.com/timClicks/slate), but aims to also
provide access to the images and shapes found in the document, in a
very simple, Pythonic way. E.g.:

```python
>>> pdffile = open('example.pdf', 'rb')
>>> doc = minecart.Document(pdffile)
>>> page = doc.get_page(3)
>>> for shape in page.shapes:
...     if shape.check_inside_bbox((0, 0, 100, 200)):
...         print shape.path, shape.fill.color.as_rgb()
```

Development status
---------------------

`minecart` is under active development, with support for images and
shapes improving daily. The interface is still in flux as I uncover
what the most natural form is, but will stabilize soon.

Currently supported features
------------------------------

* *Shapes*: You can extract path information, bounding box, stroke
  paramters, and stroke/fill colors. Color support covers `DeviceRGB`,
  `DeviceCMYK`, `DeviceGray`, and `CIE-based` (though this last one
  cannot yet be converted to `RGB`). `Indexed` colors are supported if
  they index into one of the above.
* *Images*: In theory, you can now easily extract images and
  manipulate/save them as `PIL.Image` objects. The implementation is
  pretty hackish and untested, so will likely require an overhaul
  before being production-ready.
* *Text*: (Called `Lettering` in the source) In addition to extracting
  plain text from the PDF, you have access to position/bounding box
  information.

If there's a feature you'd like to extract from a PDF that's not
currently supported, open up an issue or submit a pull request! I'm
especially interested in hearing whether there are many PDFs using
color spaces outside of the ones currently supported.


Documentation
-----------------

I try to keep docstrings complete and up to date, so you can read
through the source or use `dir` and `help` to see what methods are
available. Most of the public interface is implemented in the
`content` class, and `miner` has more of the PDF nitty-gritty stuff
(though the division isn't perfect). The main entry point will always
be `minecart.Document` and then either `Document.get_page` or
`Document.iter_pages`.
