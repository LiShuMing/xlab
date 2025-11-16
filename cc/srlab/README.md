# SR Lab CMake Scaffold

This repository bootstraps a CMake-based C++ project that leverages the shared third-party bundle hosted at `/home/disk1/sr-deps/thirdparty-latest`.

## Quick start

```bash
./build.sh
./build/srlab_app
```

## Running tests

The project includes comprehensive tests using GoogleTest:

```bash
./build.sh
ctest --test-dir build --output-on-failure
```

Or run test executables directly:

```bash
./build/tests/use_arrow_tests    # Arrow tests
./build/tests/use_boost_tests    # Boost tests
```

## Integrated Libraries

### From Third-Party Bundle
- **Apache Arrow** - Columnar in-memory analytics (static linking)
- **Boost 1.80.0** - System, Filesystem, Algorithm libraries
- **GoogleTest** - Unit testing framework
- **fmt** - Modern formatting library (optional)
- **Abseil** - Google's C++ library collection (optional)

### From Source (Optional)
- **Folly** - Facebook's C++ library (disabled by default)
  - **Status**: Requires `double-conversion` library which is not available in the thirdparty bundle
  - **Dependencies needed**: 
    - ✅ glog (available)
    - ✅ gflags (available)
    - ❌ double-conversion (missing - only vendored in Arrow)
    - ✅ Boost (available)
  - **To enable**: Install double-conversion, then `./build.sh -DSRLAB_BUILD_FOLLY=ON`
  - Source location: `/home/disk1/lishuming/work/xlab/cc/thirdparty/folly`

## Configuration Options

```bash
# Print third-party search paths
./build.sh -DSRLAB_PRINT_THIRDPARTY=ON

# Enable Folly build from source (requires double-conversion)
./build.sh -DSRLAB_BUILD_FOLLY=ON

# Custom third-party root
./build.sh -DTHIRDPARTY_ROOT=/path/to/thirdparty
```

## Project Structure

- `src/` - Main application source
- `tests/` - GoogleTest-based tests
  - `test_arrow.cpp` - Arrow array operations ✅
  - `test_boost.cpp` - Boost algorithm and filesystem ✅
  - `test_folly.cpp` - Folly string and container tests (requires Folly)
- `cmake/` - CMake helper modules
  - `ThirdpartyConfig.cmake` - Third-party path configuration
- `build.sh` - Convenience build script with PKG_CONFIG_PATH setup

## Installing Missing Dependencies

To enable Folly support, install double-conversion:

```bash
# Option 1: System package (Ubuntu/Debian)
sudo apt-get install libdouble-conversion-dev

# Option 2: Build from source
git clone https://github.com/google/double-conversion.git
cd double-conversion
cmake -S . -B build -DCMAKE_INSTALL_PREFIX=/home/disk1/sr-deps/thirdparty-latest/installed
cmake --build build
cmake --install build
```
