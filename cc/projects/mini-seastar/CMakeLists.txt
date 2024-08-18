cmake_minimum_required(VERSION 3.16)
project(MiniSeastar VERSION 0.1.0 LANGUAGES CXX)

# C++23 standard (working draft c++2b) for full coroutine support
set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Find clang for coroutine support
include(CheckCXXCompilerFlag)
check_cxx_compiler_flag("-fcoroutines-ts" CXX_HAS_FCOROUTINES_TS)
if(NOT CXX_HAS_FCOROUTINES_TS)
    message(FATAL_ERROR "Compiler does not support C++20 coroutines")
endif()

# Enable coroutines on Apple Clang
add_compile_options(-fcoroutines-ts)
add_link_options(-fcoroutines-ts)

# Default to Release build with symbols for debugging
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE "RelWithDebInfo")
endif()

# Enable address sanitizer for development
option(MS_USE_ASAN "Enable AddressSanitizer" OFF)
if(MS_USE_ASAN)
    add_compile_options(-fsanitize=address -fno-omit-frame-pointer)
    add_link_options(-fsanitize=address)
endif()

# -------------------------------------------------------------------
# Library target
# -------------------------------------------------------------------
add_library(miniseastar_lib STATIC
    src/scheduler.cpp
)

target_include_directories(miniseastar_lib
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/include
)

# GoogleTest from local submodule
add_subdirectory(${CMAKE_CURRENT_SOURCE_DIR}/../../../cc/thirdparty/googletest googletest-build EXCLUDE_FROM_ALL)

# Unit tests
enable_testing()
add_executable(miniseastar_tests
    tests/main.cpp
    tests/test_task.cpp
    tests/test_scheduler.cpp
    tests/test_awaitables.cpp
)
target_link_libraries(miniseastar_tests
    PRIVATE
        miniseastar_lib
        gtest_main
)
target_include_directories(miniseastar_tests PRIVATE include)

include(GoogleTest)
gtest_discover_tests(miniseastar_tests)

# Demo: coroutine demo
add_executable(coro_demo
    examples/01_coro_demo.cpp
)
target_link_libraries(coro_demo PRIVATE miniseastar_lib)

# Demo: sleep demo
add_executable(sleep_demo
    examples/02_sleep_demo.cpp
)
target_link_libraries(sleep_demo PRIVATE miniseastar_lib)

# Demo: task chain demo
add_executable(task_chain_demo
    examples/03_task_chain.cpp
)
target_link_libraries(task_chain_demo PRIVATE miniseastar_lib)

# Demo: ping-pong benchmark
add_executable(pingpong_bench
    examples/04_pingpong_bench.cpp
)
target_link_libraries(pingpong_bench PRIVATE miniseastar_lib)

# -------------------------------------------------------------------
# Installation (optional)
# -------------------------------------------------------------------
install(TARGETS miniseastar_lib coro_demo sleep_demo task_chain_demo pingpong_bench
    EXPORT miniseastar_targets
)

install(DIRECTORY include/miniseastar
    DESTINATION include
)

install(EXPORT miniseastar_targets
    FILE miniseastar_targets.cmake
    NAMESPACE miniseastar::
    DESTINATION lib/cmake/miniseastar
)

# Print configuration
message(STATUS "MiniSeastar Configuration:")
message(STATUS "  C++ Standard: ${CMAKE_CXX_STANDARD}")
message(STATUS "  Build Type: ${CMAKE_BUILD_TYPE}")
message(STATUS "  ASAN: ${MS_USE_ASAN}")
