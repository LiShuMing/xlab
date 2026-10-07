include_guard(GLOBAL)
include(FetchContent)

if(MSVC AND DEFINED XLAB_MSVC_SHOWINCLUDES_PREFIX)
    set(CMAKE_CL_SHOWINCLUDES_PREFIX "${XLAB_MSVC_SHOWINCLUDES_PREFIX}")
endif()

option(XLAB_FETCH_DEPENDENCIES "Download missing C++ test/benchmark dependencies" OFF)
option(XLAB_BUILD_BENCHMARKS "Build C++ benchmarks" OFF)
get_filename_component(XLAB_THIRDPARTY_DIR "${CMAKE_CURRENT_LIST_DIR}/../cc/thirdparty" ABSOLUTE)

function(xlab_require_dependency name target revision)
    if(TARGET ${target})
        return()
    endif()
    if(EXISTS "${XLAB_THIRDPARTY_DIR}/${name}/CMakeLists.txt")
        add_subdirectory("${XLAB_THIRDPARTY_DIR}/${name}"
            "${CMAKE_BINARY_DIR}/thirdparty/${name}" EXCLUDE_FROM_ALL)
    elseif(XLAB_FETCH_DEPENDENCIES OR EXISTS "${FETCHCONTENT_BASE_DIR}/${name}-src/CMakeLists.txt")
        FetchContent_Declare(${name}
            GIT_REPOSITORY "https://github.com/google/${name}.git"
            GIT_TAG "${revision}"
            UPDATE_DISCONNECTED TRUE)
        FetchContent_MakeAvailable(${name})
    else()
        find_package(${name} CONFIG QUIET)
        if(NOT TARGET ${target})
            message(FATAL_ERROR "Missing ${name}. Initialize cc/thirdparty/${name}, install its CMake package, or use -DXLAB_FETCH_DEPENDENCIES=ON.")
        endif()
    endif()
endfunction()

function(xlab_require_googletest)
    # Match the consuming MSVC targets' dynamic runtime, including Debug builds.
    set(gtest_force_shared_crt ON CACHE BOOL "Use shared MSVC runtime" FORCE)
    set(INSTALL_GTEST OFF CACHE BOOL "Disable dependency installation" FORCE)
    if(NOT TARGET GTest::gtest_main)
        find_package(GTest CONFIG QUIET)
    endif()
    xlab_require_dependency(googletest GTest::gtest_main
        b514bdc898e2951020cbdca1304b75f5950d1f59)
endfunction()

function(xlab_require_benchmark)
    set(BENCHMARK_ENABLE_TESTING OFF CACHE BOOL "Disable benchmark's own tests" FORCE)
    set(BENCHMARK_ENABLE_INSTALL OFF CACHE BOOL "Disable dependency installation" FORCE)
    xlab_require_dependency(benchmark benchmark::benchmark
        96afad55c79e02f5dfca1374e772c2be72ba631b)
endfunction()

function(xlab_target_defaults target)
    target_compile_features(${target} PUBLIC cxx_std_20)
    if(MSVC)
        target_compile_options(${target} PRIVATE /W4 /permissive- /utf-8 /Zc:__cplusplus)
        target_compile_definitions(${target} PUBLIC NOMINMAX WIN32_LEAN_AND_MEAN)
    else()
        target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic
            -Werror=return-type -Werror=uninitialized)
    endif()
endfunction()
