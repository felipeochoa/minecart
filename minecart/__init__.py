u"""
minecart provides a Pythonic interface for extracting content from PDF files.

`minecart` depends on `pdfminer` (a pure Python package) for parsing of the pdf
file; `minecart` simply provides a Pythonic interface around `pdfminer`.

The most important classes in `minecart` are:

* `Document`: the main entry point for calling code; takes a file object with
              PDF data and provides access to its structure and content.
* `Page`: PDF is at its core a collection of pages with content. The `Page`
          class provides access to the different graphical elements on each
          page of the underlying document.
* `Shape`: PDF operates mainly on vector paths, painting and stroking them
           appropriately. (There's more you can do with paths, but this is
           all that `pdfminer` supports). `minecart` translates these
           commands into `Shape` objects.
* `Image`: PDF allows documents to embed images, and this class is how
           `minecart` lets you interface with them. Currently limited, but
           the plan is to eventually interface with `PIL`
* `Lettering`: Text in PDF documents is more than just a sequence of
               characters. `Lettering` subclasses `str` to allow storing
               font, size, placement, etc.

"""

from .content import Page, Shape, Image, Lettering
from .miner import Document
