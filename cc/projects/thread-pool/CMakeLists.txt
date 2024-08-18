cmake_minimum_required(VERSION 3.16)

project(wstp LANGUAGES CXX)

# C++20 standard
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Build type
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE "Release" CACHE STRING "Build type" FORCE)
endif()

# Enable testing
enable_testing()

# Add thirdparty submodules
add_subdirectory(../../thirdparty/googletest googletest)
# Disable benchmark tests to avoid C++17 attribute compilation issues
set(BENCHMARK_ENABLE_TESTING OFF CACHE BOOL "" FORCE)
add_subdirectory(../../thirdparty/benchmark benchmark)

# Library target - Phase 1: global queue implementation
add_library(wstp STATIC
    src/thread_pool.cc
    src/ws_deque.cc
)
target_include_directories(wstp PUBLIC include)

# Unit tests
add_executable(test_thread_pool tests/test_thread_pool.cc)
target_link_libraries(test_thread_pool
    wstp
    GTest::gtest_main
)
include(GoogleTest)
gtest_discover_tests(test_thread_pool)

add_executable(test_ws_deque tests/test_ws_deque.cc)
target_link_libraries(test_ws_deque
    wstp
    GTest::gtest_main
)
gtest_discover_tests(test_ws_deque)

# Benchmarks
add_executable(bench_latency bench/bench_latency.cc)
target_link_libraries(bench_latency
    wstp
    benchmark_main
)

add_executable(bench_throughput bench/bench_throughput.cc)
target_link_libraries(bench_throughput
    wstp
    benchmark_main
)

# Print configuration info
message(STATUS "Build type: ${CMAKE_BUILD_TYPE}")
message(STATUS "C++ standard: ${CMAKE_CXX_STANDARD}")
