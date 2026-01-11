cmake_minimum_required(VERSION 3.16)
project(TinyKV VERSION 0.1.0 LANGUAGES CXX)

# C++ standard
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Build type
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE "Debug" CACHE STRING "Build type" FORCE)
endif()

# Enable tests and benchmarks
include(CTest)
enable_testing()

# Use local thirdparty dependencies
set(THIRDPARTY_DIR /Users/lishuming/work/xlab/cc/thirdparty)

# Core library
add_library(tinykv STATIC
    src/memtable/arena.cpp
    src/memtable/skiplist.cpp
    src/memtable/memtable.cpp
)
target_include_directories(tinykv PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)
target_compile_options(tinykv PRIVATE
    -Wall -Wextra -Wpedantic
    -Werror=return-type
    -Werror=uninitialized
)

# GoogleTest from local submodule (out-of-tree requires binary dir)
add_subdirectory(${THIRDPARTY_DIR}/googletest googletest-build EXCLUDE_FROM_ALL)
add_subdirectory(${THIRDPARTY_DIR}/benchmark benchmark-build EXCLUDE_FROM_ALL)

# Unit tests
add_executable(tinykv_memtable_test
    tests/memtable/skiplist_test.cpp
    tests/memtable/memtable_test.cpp
)
target_link_libraries(tinykv_memtable_test
    tinykv
    gtest_main
)
add_test(NAME tinykv_memtable_test COMMAND tinykv_memtable_test)

# Benchmarks
add_executable(tinykv_memtable_bench
    bench/memtable/memtable_bench.cpp
)
target_link_libraries(tinykv_memtable_bench
    tinykv
    benchmark::benchmark
)
set_target_properties(tinykv_memtable_bench PROPERTIES
    EXCLUDE_FROM_ALL TRUE
    EXCLUDE_FROM_DEFAULT_BUILD TRUE
)

# Code style check (optional)
add_custom_target(format
    COMMAND clang-format -i
        ${CMAKE_CURRENT_SOURCE_DIR}/include/tinykv/**/*.hpp
        ${CMAKE_CURRENT_SOURCE_DIR}/src/**/*.cpp
        ${CMAKE_CURRENT_SOURCE_DIR}/tests/**/*.cpp
        ${CMAKE_CURRENT_SOURCE_DIR}/bench/**/*.cpp
    COMMENT "Formatting code with clang-format"
)

# Install rules
install(DIRECTORY include/tinykv DESTINATION include)
install(TARGETS tinykv ARCHIVE DESTINATION lib)

message(STATUS "TinyKV Configuration:")
message(STATUS "  Build type: ${CMAKE_BUILD_TYPE}")
message(STATUS "  C++ standard: ${CMAKE_CXX_STANDARD}")
message(STATUS "  Tests: tinykv_memtable_test")
message(STATUS "  Benchmarks: tinykv_memtable_bench")
message(STATUS "  Using local thirdparty from: ${THIRDPARTY_DIR}")
