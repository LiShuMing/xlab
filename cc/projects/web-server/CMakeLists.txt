cmake_minimum_required(VERSION 3.16)
project(RingServer VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Default build type to Release
if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
    set(CMAKE_BUILD_TYPE "Release" CACHE STRING "Build type" FORCE)
    set_property(CACHE CMAKE_BUILD_TYPE PROPERTY STRINGS "Debug" "Release" "RelWithDebInfo")
endif()

# Find system libraries
find_package(Threads REQUIRED)

# Optional io_uring (Linux only)
option(RINGSERVER_ENABLE_URING "Enable io_uring backend (Linux only)" OFF)
if(RINGSERVER_ENABLE_URING AND NOT APPLE)
    find_package(PkgConfig REQUIRED)
    pkg_check_modules(liburing IMPORTED_TARGET liburing)
    if(NOT liburing_FOUND)
        message(FATAL_ERROR "liburing not found. Install liburing-dev or set RINGSERVER_ENABLE_URING=OFF")
    endif()
endif()

# Google Test for unit tests
include(FetchContent)
FetchContent_Declare(
    googletest
    GIT_REPOSITORY https://github.com/google/googletest.git
    GIT_TAG v1.14.0
)
set(gtest_build_tests ON)
FetchContent_MakeAvailable(googletest)

# Google Benchmark for benchmarks
FetchContent_Declare(
    benchmark
    GIT_REPOSITORY https://github.com/google/benchmark.git
    GIT_TAG v1.9.0
)
set(BENCHMARK_ENABLE_TESTING OFF)
FetchContent_MakeAvailable(benchmark)

# Main library (renamed to avoid conflict with include/ringserver directory)
add_library(ringserver_lib
    ${CMAKE_SOURCE_DIR}/src/common/status.cpp
    ${CMAKE_SOURCE_DIR}/src/io/io_backend.cpp
    ${CMAKE_SOURCE_DIR}/src/io/kqueue_backend.cpp
    ${CMAKE_SOURCE_DIR}/src/server/connection.cpp
    ${CMAKE_SOURCE_DIR}/src/server/server.cpp
)
target_include_directories(ringserver_lib PUBLIC
    $<BUILD_INTERFACE:${CMAKE_SOURCE_DIR}/include>
)
if(APPLE)
    target_compile_definitions(ringserver_lib PUBLIC RINGSERVER_PLATFORM_APPLE)
elseif(RINGSERVER_ENABLE_URING)
    target_link_libraries(ringserver_lib PUBLIC PkgConfig::liburing)
    target_compile_definitions(ringserver_lib PUBLIC RINGSERVER_ENABLE_URING=1)
endif()

# Main executable
add_executable(ringserver ${CMAKE_SOURCE_DIR}/src/main.cpp)
target_link_libraries(ringserver PRIVATE ringserver_lib Threads::Threads)

# Unit tests (placeholder)
add_executable(ringserver_test ${CMAKE_SOURCE_DIR}/tests/http/http_parser_test.cpp)
target_link_libraries(ringserver_test PRIVATE ringserver_lib gtest gtest_main)

# Enable testing
enable_testing()
add_test(NAME ringserver_test COMMAND ringserver_test)

# Benchmarks (placeholder)
add_executable(ringserver_bench ${CMAKE_SOURCE_DIR}/bench/http/http_bench.cpp)
target_link_libraries(ringserver_bench PRIVATE ringserver_lib benchmark::benchmark)

# Print configuration summary
message(STATUS "RingServer Configuration:")
message(STATUS "  Platform: ${CMAKE_SYSTEM_NAME}")
message(STATUS "  Build type: ${CMAKE_BUILD_TYPE}")
message(STATUS "  C++ standard: ${CMAKE_CXX_STANDARD}")
message(STATUS "  io_uring support: ${RINGSERVER_ENABLE_URING}")
