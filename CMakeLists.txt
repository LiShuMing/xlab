cmake_minimum_required(VERSION 3.22)
project(xlab LANGUAGES C CXX)

include(CTest)
include(cmake/XlabDependencies.cmake)

option(XLAB_BUILD_CCLAB "Build the portable cclab subset" ON)
option(XLAB_BUILD_THREAD_POOL "Build the work-stealing thread pool" ON)

if(XLAB_BUILD_CCLAB)
    set(CCLAB_PORTABLE_ONLY ON CACHE BOOL "Build the portable cclab subset" FORCE)
    add_subdirectory(cc/cclab)
endif()
if(XLAB_BUILD_THREAD_POOL)
    add_subdirectory(cc/projects/thread-pool)
endif()

if(BUILD_TESTING AND XLAB_BUILD_CCLAB AND XLAB_BUILD_THREAD_POOL)
    add_executable(xlab_core_smoke tools/cpp_smoke.cc)
    target_link_libraries(xlab_core_smoke PRIVATE cclab_portable wstp)
    xlab_target_defaults(xlab_core_smoke)
    add_test(NAME xlab_core_smoke COMMAND xlab_core_smoke)
    set_tests_properties(xlab_core_smoke PROPERTIES TIMEOUT 60)
endif()
