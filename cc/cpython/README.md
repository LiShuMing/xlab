# Python C Extensions

This directory contains examples and implementations of Python C extensions, including both C API extensions and Cython-based extensions.

## Overview

This project demonstrates:
- Embedding Python in C++ applications
- Creating Python C extensions using the Python C API
- Creating Python extensions using Cython
- Building and packaging Python extensions

## Structure

- `main.cc` - Example of embedding Python in a C++ application
- `my_c_extension.c` - Python C extension using the C API
- `setup.py` - Setup script for building Python extensions
- `cpy/` - Cython-based extensions
  - `my_c_code.c` - C implementation
  - `my_c_code.pyx` - Cython source file
  - `setup.py` - Cython build setup
- `skiplist/` - Skip list implementation as a Python extension
  - `src/cpp/` - C++ implementation
  - `src/cpy/` - Cython bindings
  - `setup.py` - Extension build configuration

## Building

### Embedding Python in C++

```bash
./build.sh
# or
mkdir -p build
cd build
cmake ..
make
```

This builds the `EmbedPython` executable that demonstrates embedding Python.

### Building C Extensions

#### Using Python C API

```bash
python setup.py build_ext --inplace
```

#### Using Cython

```bash
cd cpy
python setup.py build_ext --inplace
```

#### Building Skip List Extension

```bash
cd skiplist
./build.sh
# or
python setup.py build_ext --inplace
```

## Usage

### Running Embedded Python Example

```bash
./build/EmbedPython
```

### Using C Extensions

After building, you can import and use the extensions in Python:

```python
import my_c_extension
# Use the extension functions
```

### Testing

```bash
python test.py
```

## Examples

### C Extension (C API)

The `my_c_extension.c` file demonstrates:
- Creating a Python module
- Defining Python functions in C
- Handling Python objects
- Error handling

### Cython Extension

The `cpy/` directory shows:
- Writing Cython code (`.pyx` files)
- Compiling Cython to C
- Building Python extensions from Cython

### Skip List Extension

The `skiplist/` directory contains a complete example:
- C++ implementation of a skip list
- Cython bindings to expose C++ classes to Python
- Proper setup and build configuration

## Requirements

- Python 3.x with development headers
- CMake 3.12+ (for embedded Python example)
- Cython (for Cython-based extensions)
- C++ compiler with C++17 support

## Notes

- Make sure Python development headers are installed (`python3-dev` on Ubuntu/Debian)
- For Cython extensions, install Cython: `pip install cython`
- The embedded Python example requires linking against Python libraries

