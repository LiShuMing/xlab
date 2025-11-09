# SR Lab CMake Scaffold

This repository bootstraps a simple CMake-based C++ project that leverages the shared third-party bundle hosted at `/home/disk1/sr-deps/thirdparty-latest`.

## Quick start

```bash
./build.sh
./build/srlab_app
```

## Running tests

The project includes Arrow-based tests using GoogleTest:

```bash
./build.sh
ctest --test-dir build --output-on-failure
```

Or run the test executable directly:

```bash
./build/tests/use_arrow_tests
```

## Configuration

The top-level `CMakeLists.txt` wires the shared bundle into `CMAKE_PREFIX_PATH`, `CMAKE_LIBRARY_PATH`, and `CMAKE_INCLUDE_PATH`. Toggle `SRLAB_PRINT_THIRDPARTY` to inspect the effective search paths during configuration:

```bash
./build.sh -DSRLAB_PRINT_THIRDPARTY=ON
```

## Project Structure

- `src/` - Main application source
- `tests/` - GoogleTest-based tests using Arrow
- `cmake/` - CMake helper modules
- `build.sh` - Convenience build script

