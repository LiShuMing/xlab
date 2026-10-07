cmake_minimum_required(VERSION 3.16)
project(vagg LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type")
endif()

include(CTest)
include(../../../cmake/XlabDependencies.cmake)

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
xlab_target_defaults(vagg)

if(BUILD_TESTING)
    xlab_require_googletest()
    include(GoogleTest)
    file(GLOB test_sources CONFIGURE_DEPENDS "tests/*.cc")
    if(NOT test_sources)
        message(FATAL_ERROR "BUILD_TESTING is ON, but query-engine has no test sources")
    endif()
    foreach(source IN LISTS test_sources)
        get_filename_component(test_name "${source}" NAME_WE)
        add_executable(${test_name} "${source}")
        target_link_libraries(${test_name} PRIVATE vagg GTest::gtest_main)
        xlab_target_defaults(${test_name})
        gtest_discover_tests(${test_name} DISCOVERY_MODE PRE_TEST PROPERTIES TIMEOUT 60)
    endforeach()
endif()

if(XLAB_BUILD_BENCHMARKS)
    if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/bench/bench_aggregation.cc")
        xlab_require_benchmark()
        add_executable(bench_aggregation bench/bench_aggregation.cc)
        target_link_libraries(bench_aggregation PRIVATE vagg benchmark::benchmark_main)
        xlab_target_defaults(bench_aggregation)
    else()
        message(STATUS "query-engine benchmark source is absent; skipping bench_aggregation")
    endif()
endif()
