#!/bin/bash

# install setuptools and wheel
python3 -m pip install --user --break-system-packages setuptools wheel

# build the extension
python3 setup.py build_ext --inplace

python -c "import my_c_extension; print(my_c_extension.c_sum(1, 2))"

# test in the file
python test.py