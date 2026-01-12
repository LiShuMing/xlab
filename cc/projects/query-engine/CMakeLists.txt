cmake_minimum_required(VERSION 3.16)

project(vagg LANGUAGES CXX)

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
include(GoogleTest)

# Add thirdparty submodules
add_subdirectory(../../thirdparty/googletest googletest)
set(BENCHMARK_ENABLE_TESTING OFF CACHE BOOL "" FORCE)
add_subdirectory(../../thirdparty/benchmark benchmark)

# Library target
add_library(vagg STATIC
    src/common/status.cc
    src/vector/vector.cc
    src/ht/hash_table.cc
    src/ht/hash.cc
    src/ops/scan_op.cc
    src/ops/aggregate_op.cc
    src/ops/sink_op.cc
)
target_include_directories(vagg PUBLIC include)

# Unit tests
add_executable(test_hash_table tests/test_hash_table.cc)
target_link_libraries(test_hash_table
    vagg
    GTest::gtest_main
)
gtest_discover_tests(test_hash_table)

add_executable(test_aggregation tests/test_aggregation.cc)
target_link_libraries(test_aggregation
    vagg
    GTest::gtest_main
)
gtest_discover_tests(test_aggregation)

add_executable(test_vector tests/test_vector.cc)
target_link_libraries(test_vector
    vagg
    GTest::gtest_main
)
gtest_discover_tests(test_vector)

add_executable(test_hash_join tests/test_hash_join.cc)
target_link_libraries(test_hash_join
    vagg
    GTest::gtest_main
)
gtest_discover_tests(test_hash_join)

add_executable(test_sort tests/test_sort.cc)
target_link_libraries(test_sort
    vagg
    GTest::gtest_main
)
gtest_discover_tests(test_sort)

# Benchmarks
add_executable(bench_aggregation bench/bench_aggregation.cc)
target_link_libraries(bench_aggregation
    vagg
    benchmark_main
)

# Print configuration info
message(STATUS "Build type: ${CMAKE_BUILD_TYPE}")
message(STATUS "C++ standard: ${CMAKE_CXX_STANDARD}")
