
minecart: A Pythonic interface to PDF documents
===============================================


`minecart` is a Python package that simplifies the extraction of text,
images, and shapes from a PDF document. It depends on Yusuke
Shinyama's [`pdfminer`](https://github.com/euske/pdfminer).

`minecart` takes inspiration from Tim McNamara's
[`slate`](https://github.com/timClicks/slate), but aims to also
provide access to the images and shapes found in the document, in a
very Pythonic way. E.g.:

    >>> pdffile = open('example.pdf', 'rb')
    >>> doc = minecart.Document(pdffile)
    >>> page = doc.get_page(3)
    >>> for shape in page.shapes.iter_in_bbox(0, 0, 100, 200):
    ...     if shape.stroked:
    ...         print shape.path


Development status
---------------------

`minecart` is under active development, with improved support for
images, shapes, and fonts coming up. If there's a feature you'd like
to extract from a PDF that's not currently supported, open up an issue
or submit a pull request!

**Note**: I expect that as this package evolves, the `Shape` and
`Image` classes will expand their API and expose less of the
`pdfminer` internals, but for now extracting detailed information or
image data requires going down to the `pdfminer` API.
