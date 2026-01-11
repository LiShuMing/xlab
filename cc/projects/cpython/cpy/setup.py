# setup.py
from setuptools import setup, Extension
from Cython.Build import cythonize

ext_modules = [
    Extension("my_c_code", sources=["my_c_code.pyx", "my_c_code.c"])
]

setup(
    name="my_c_code",
    ext_modules=cythonize(ext_modules),
)