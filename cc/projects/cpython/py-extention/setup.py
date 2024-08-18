# setup.py
from setuptools import setup, Extension

module = Extension("my_c_extension", sources=["my_c_extension.c"])

setup(
    name="my_c_extension",
    version="1.0",
    description="A simple C extension",
    ext_modules=[module]
)