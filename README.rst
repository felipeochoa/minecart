minecart: A Pythonic interface to PDF documents
===============================================

|Travis CI build status (Linux)| |Coverage Status|

``minecart`` is a Python package that simplifies the extraction of text,
images, and shapes from a PDF document. It provides a very Pythonic
interface to extract positioning, color, and font metadata for all of
the objects in the PDF. It is a pure-Python package (it depends on
|pdfminer|_ for the low-level parsing). ``minecart`` takes
inspiration from Tim McNamara’s |slate|_, but aims to provide more
detailed information:

.. code:: python

    >>> pdffile = open('example.pdf', 'rb')
    >>> doc = minecart.Document(pdffile)
    >>> page = doc.get_page(3)
    >>> for shape in page.shapes.iter_in_bbox((0, 0, 100, 200)):
    ...     print shape.path, shape.fill.color.as_rgb()
    >>> im = page.images[0].as_pil()  # requires pillow
    >>> im.show()

Installation
------------

Currently only Python 2.7 is supported. Plans for supporting 3.4+ (using
|pdfminer.six|_) is planned.

1. The easy way: ``pip instal minecart``
2. The hard way: download the source code, change into the working
   directory, and run ``python setup.py install``

**For CJK languages**: Supporting the CJK languages requires an
addtional step, as detailed_ in |pdfminer|.

Features
--------

-  **Shapes**: You can extract path information, bounding box, stroke
   parameters, and stroke/fill colors. Color support is fairly robust,
   allowing the simple ``.as_rgb()`` in most cases. (To be concrete,
   ``minecart`` supports the ``DeviceRGB``, ``DeviceCMYK``,
   ``DeviceGray``, and ``CIE-based`` color spaces. ``Indexed`` colors
   are supported if they index into one of the above.)
-  **Images**: ``minecart`` can easily extract images to ``PIL.Image``
   objects.
-  **Text**: (Called ``Lettering`` in the source) In addition to
   extracting plain text from the PDF, you can access the
   position/bounding box information and the font used.

If there’s a feature you’d like to extract from a PDF that’s not
currently supported, open up an issue or submit a pull request! I’m
especially interested in hearing whether there are many PDFs using color
spaces outside of the ones currently supported.

Documentation
-------------

The main entry point will always be ``minecart.Document``, which accepts
a single parameter, an open file-like object which will be read to
create the document. The ``Document`` has two primary methods for
accessing its contents: ``.get_page(num)`` and ``iter_pages()``. Both
methods return ``minecart.Page`` objects, which provide access to the
graphical elements found on the page. ``Page`` objects have three main
attributes:

-  ``.images``: A list of all the ``minecart.Image`` objects found on
   the page.

-  ``.letterings``: A list of all the text objects found on the page, as
   ``Lettering`` objects. ``Lettering`` is a ``unicode`` subclass which
   adds bounding box and font information (using ``.get_bbox()`` or
   ``.font``).

-  ``.shapes``: A list of all the squares, circles, lines, etc. found on
   the page as ``Shape`` objects. ``Shape`` objects have three main
   attributes of interest:

   - ``stroke``: An object containing the stroke parameters used to
     draw the shape. ``.stroke`` has ``.color``, ``.linewidth``,
     ``.linecap``, ``.linejoin``, ``.miterlimit``, and ``.dash``
     attributes. If the shape was not stroked, ``.stroke`` will be
     ``None``.

   - ``.fill``: An object containing the fill parameters used to draw
     the shape. Right now, ``.fill`` only has a ``.color``\ parameter.

   - ``.path``: A list with the coordinates used to defined the shape,
     as well as the type of line segment each set of coordinates
     defines.  Refer to the ``minecart.Shape`` documentation for more
     details

I try to keep docstrings complete and up to date, so you can read
through the source or use ``dir`` and ``help`` to see what methods are
available. Most of the public interface is implemented in the
``content`` class, and ``miner`` has more of the PDF nitty-gritty stuff.

Support
-------

If you are having trouble working with ``minecart``, let us know. We
have a Google group located at:
https://groups.google.com/forum/#!forum/minecart, or you can email
|contact email|_ directly.

Contributing
------------

Bug reports are always welcome (using the GitHub tracker) as are feature
requests. The PDF spec has so many corners, it is hard for me to
prioritize implementing access to its various features. If there’s
something you’d like to extract from a document but isn’t currently
supported, please `create a new issue`_.

If you’d like to contribute code, you can either create an issue and
include a patch (if the changes are small) or fork the project and
create a pull request.

License
-------

This project is licensed under the MIT license.

.. _create a new issue: https://github.com/felipeochoa/minecart/issues/new
.. _pdfminer: https://github.com/euske/pdfminer
.. _slate: https://github.com/timClicks/slate
.. _pdfminer.six: https://github.com/goulu/pdfminer
.. _detailed: https://github.com/euske/pdfminer#for-cjk-languages
.. _contact email: mailto:minecart@googlegroups.com
.. |Travis CI build status (Linux)| image:: https://travis-ci.org/felipeochoa/minecart.svg?branch=master
   :target: https://travis-ci.org/felipeochoa/minecart
.. |Coverage Status| image:: https://coveralls.io/repos/felipeochoa/minecart/badge.svg
   :target: https://coveralls.io/r/felipeochoa/minecart
.. |pdfminer| replace:: ``pdfminer``
.. |slate| replace:: ``slate``
.. |pdfminer.six| replace:: ``pdfminer.six``
.. |contact email| replace:: minecart@googlegroups.com
