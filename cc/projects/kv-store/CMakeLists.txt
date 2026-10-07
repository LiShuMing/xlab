cmake_minimum_required(VERSION 3.16)
project(TinyKV VERSION 0.1.0 LANGUAGES CXX)

# C++ standard
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Build type
if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
    set(CMAKE_BUILD_TYPE "Debug" CACHE STRING "Build type" FORCE)
endif()

# Enable tests and benchmarks
include(CTest)
include(../../../cmake/XlabDependencies.cmake)

# Use local thirdparty dependencies
set(THIRDPARTY_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../../thirdparty)

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
xlab_target_defaults(tinykv)

# GoogleTest from local submodule (out-of-tree requires binary dir)
if(BUILD_TESTING)
    xlab_require_googletest()

    # Unit tests
    add_executable(tinykv_memtable_test
        tests/memtable/arena_test.cpp
        tests/memtable/skiplist_test.cpp
        tests/memtable/memtable_test.cpp
    )
    target_link_libraries(tinykv_memtable_test
        tinykv
        GTest::gtest_main
    )
    add_test(NAME tinykv_memtable_test COMMAND tinykv_memtable_test)
    set_tests_properties(tinykv_memtable_test PROPERTIES TIMEOUT 60)
    xlab_target_defaults(tinykv_memtable_test)
endif()

# Benchmarks
if(XLAB_BUILD_BENCHMARKS)
    xlab_require_benchmark()
    add_executable(tinykv_memtable_bench
        bench/memtable/memtable_bench.cpp
    )
    target_link_libraries(tinykv_memtable_bench
        tinykv
        benchmark::benchmark
    )
    xlab_target_defaults(tinykv_memtable_bench)
endif()

# Code style check (optional)
find_program(XLAB_CLANG_FORMAT clang-format)
if(XLAB_CLANG_FORMAT)
    file(GLOB_RECURSE format_sources CONFIGURE_DEPENDS
        "include/tinykv/*.hpp" "src/*.cpp" "tests/*.cpp" "bench/*.cpp")
    add_custom_target(format
        COMMAND "${XLAB_CLANG_FORMAT}" -i ${format_sources}
        COMMENT "Formatting code with clang-format"
        VERBATIM)
endif()

# Install rules
install(DIRECTORY include/tinykv DESTINATION include)
install(TARGETS tinykv ARCHIVE DESTINATION lib)

message(STATUS "TinyKV Configuration:")
message(STATUS "  Build type: ${CMAKE_BUILD_TYPE}")
message(STATUS "  C++ standard: ${CMAKE_CXX_STANDARD}")
message(STATUS "  Tests: tinykv_memtable_test")
message(STATUS "  Benchmarks: tinykv_memtable_bench")
message(STATUS "  Using local thirdparty from: ${THIRDPARTY_DIR}")
