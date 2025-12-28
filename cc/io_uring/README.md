# io_uring Library

A C++20 library wrapper for Linux io_uring, providing async I/O capabilities with coroutines support.

## Overview

This project provides a modern C++ interface to Linux io_uring, featuring:
- C++20 coroutines support
- Type-safe async I/O operations
- Header-only interface library
- Test suite demonstrating usage

## Structure

- `include/liburing/` - Header-only library interface
  - `io_service.hpp` - Main io_uring service
  - `sqe_awaitable.hpp` - Coroutine awaitables for submission queue entries
  - `task.hpp` - Task types for coroutines
  - `utils.hpp` - Utility functions
- `tests/` - Test examples
  - `basic_test.cpp` - Basic io_uring operations
  - `delay_and_print.cpp` - Async delay example
  - `ping_pong.cpp` - Ping-pong communication example
- `functions.cmake` - CMake helper functions
- `CMakeLists.txt` - Build configuration

## Building

The project uses CMake and automatically fetches dependencies:

```bash
./build.sh
```

Or manually:

```bash
mkdir -p build
cd build
cmake ..
make -j$(nproc)
```

### Prerequisites

- Linux kernel 5.1+ (for io_uring support)
- liburing library (system package or built from source)
- CMake 3.14+
- C++20 compiler with coroutines support
  - GCC 10+ with `-fcoroutines` flag
  - Clang 14+ with coroutines support

### Installing liburing

On Ubuntu/Debian:
```bash
sudo apt-get install liburing-dev
```

Or build from source:
```bash
git clone https://github.com/axboe/liburing.git
cd liburing
./configure
make
sudo make install
```

## Running Tests

After building:

```bash
cd build
ctest --output-on-failure

# Or run tests directly
./tests/basic_test
./tests/delay_and_print
./tests/ping_pong
```

## Usage

This is an interface library. To use it in your project:

```cmake
# In your CMakeLists.txt
add_subdirectory(io_uring)
target_link_libraries(your_target io_uring)
```

Then in your C++ code:

```cpp
#include <liburing/io_service.hpp>
#include <liburing/sqe_awaitable.hpp>

// Use io_uring with coroutines
```

## Features

### Coroutines Support

The library provides C++20 coroutine awaitables for async I/O operations:

```cpp
auto result = co_await io_service.read(fd, buffer, size);
```

### Type Safety

All operations are type-safe with compile-time checks.

### Header-Only Interface

The library is designed as a header-only interface, making it easy to integrate.

## Dependencies

- **liburing**: Linux io_uring library (automatically detected or fetched)
- **fmt**: Formatting library (automatically fetched via FetchContent)
- **pthread**: Thread support

## Examples

### Basic Test
Demonstrates basic read/write operations with io_uring.

### Delay and Print
Shows async delay operations using io_uring timers.

### Ping Pong
Demonstrates bidirectional communication patterns.

## Notes

- Requires Linux kernel 5.1+ for io_uring support
- Coroutines require C++20 and appropriate compiler flags
- The library is designed for high-performance async I/O
- All dependencies are automatically managed via CMake FetchContent

