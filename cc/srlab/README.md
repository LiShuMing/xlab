# SR Lab CMake Scaffold

This repository bootstraps a simple CMake-based C++ project that leverages the shared third-party bundle hosted at `/home/disk1/sr-deps/thirdparty-latest`.

## Quick start

```bash
cmake -S . -B build -DSRLAB_PRINT_THIRDPARTY=ON
cmake --build build
./build/srlab_app
```

The top-level `CMakeLists.txt` wires the shared bundle into `CMAKE_PREFIX_PATH`, `CMAKE_LIBRARY_PATH`, and `CMAKE_INCLUDE_PATH`. Toggle `SRLAB_PRINT_THIRDPARTY` to inspect the effective search paths during configuration.

