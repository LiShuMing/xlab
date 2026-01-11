#!/bin/bash

# install setuptools and wheel
python3 -m pip install --user --break-system-packages setuptools wheel

# build the extension
python3 setup.py build_ext --inplace

# test in the file
python test/test_skiplist.py