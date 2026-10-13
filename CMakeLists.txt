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
