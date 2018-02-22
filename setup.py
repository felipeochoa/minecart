from os import path
from setuptools import setup

README = path.join(path.dirname(path.abspath(__file__)), "README.rst")

setup(
    name="minecart",
    version="0.3.0",
    description=("Simple, Pythonic extraction of images, text, and shapes "
                 "from PDFs"),
    long_description=open(README).read(),
    author="Felipe Ochoa",
    author_email="find me through Github",
    url="https://github.com/felipeochoa/minecart",
    download_url='https://github.com/felipeochoa/minecart/tarball/0.3.0',
    license="MIT",
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3 :: Only',
        'License :: OSI Approved :: MIT License',
    ],
    keywords='pdf pdfminer extract mining images',
    install_requires=['pdfminer3k', 'six'],
    extras_require={
        'PIL': ['Pillow'],
    },
    packages=["minecart"],
)
