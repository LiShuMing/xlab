cmake_minimum_required(VERSION 3.16)

project(wstp LANGUAGES CXX)

# C++20 standard
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Build type
if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
    set(CMAKE_BUILD_TYPE "Release" CACHE STRING "Build type" FORCE)
endif()

# Enable testing
include(CTest)
include(../../../cmake/XlabDependencies.cmake)
find_package(Threads REQUIRED)

# Add thirdparty submodules

# Library target - Phase 1: global queue implementation
add_library(wstp STATIC
    src/thread_pool.cc
    src/ws_deque.cc
)
target_include_directories(wstp PUBLIC include)
target_link_libraries(wstp PUBLIC Threads::Threads)
xlab_target_defaults(wstp)

# Unit tests
if(BUILD_TESTING)
    xlab_require_googletest()
    add_executable(test_thread_pool tests/test_thread_pool.cc)
    target_link_libraries(test_thread_pool
        wstp
        GTest::gtest_main
    )
    include(GoogleTest)
    xlab_target_defaults(test_thread_pool)
    gtest_discover_tests(test_thread_pool DISCOVERY_MODE PRE_TEST PROPERTIES TIMEOUT 60)

    add_executable(test_ws_deque tests/test_ws_deque.cc)
    target_link_libraries(test_ws_deque
        wstp
        GTest::gtest_main
    )
    xlab_target_defaults(test_ws_deque)
    gtest_discover_tests(test_ws_deque DISCOVERY_MODE PRE_TEST PROPERTIES TIMEOUT 60)
endif()

# Benchmarks
if(XLAB_BUILD_BENCHMARKS)
    xlab_require_benchmark()
    add_executable(bench_latency bench/bench_latency.cc)
    target_link_libraries(bench_latency
        wstp
        benchmark::benchmark_main
    )

    add_executable(bench_throughput bench/bench_throughput.cc)
    target_link_libraries(bench_throughput
        wstp
        benchmark::benchmark_main
    )
    xlab_target_defaults(bench_latency)
    xlab_target_defaults(bench_throughput)
endif()

# Print configuration info
message(STATUS "Build type: ${CMAKE_BUILD_TYPE}")
message(STATUS "C++ standard: ${CMAKE_CXX_STANDARD}")
