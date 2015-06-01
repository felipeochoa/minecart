from setuptools import setup

setup(
    name="minecart",
    version="0.1",
    description=("Simple, Pythonic extraction of text, shapes, and images "
                 "from PDFs"),
    author="Felipe Ochoa",
    author_email="find me through Github",
    url="https://github.com/felipeochoa/minecart",
    license="MIT",
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 2 :: Only',
        'License :: OSI Approved :: MIT License',
    ],
    keywords='pdf pdfminer extract mining images',
    install_requires=['pdfminer'],
    extras_require={
        'PIL': ['Pillow'],
    },
    packages=["minecart"],
    package_dir={'minecart': 'src'}
)
