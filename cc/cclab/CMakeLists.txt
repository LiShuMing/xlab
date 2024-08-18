cmake_minimum_required(VERSION 3.12.0)
project(vec)

set(CMAKE_CXX_STANDARD 17)

set(CXX_GCC_FLAGS "${CXX_GCC_FLAGS} -fno-omit-frame-pointer")

set(CXX_FLAGS_DEBUG "${CXX_GCC_FLAGS} -Werror -ggdb3 -O0 -gdwarf-2")
#set(CXX_FLAGS_RELEASE "${CXX_GCC_FLAGS} -O3 -gdwarf-2 -DNDEBUG -fopt-info-vec-optimized -fopt-info-vec-missed")
set(CXX_FLAGS_RELEASE "${CXX_GCC_FLAGS} -O3 -fPIC -gdwarf-2 -DNDEBUG")
SET(CXX_FLAGS_ASAN "${CXX_GCC_FLAGS} -ggdb3 -O0 -gdwarf-2 -fsanitize=address -DADDRESS_SANITIZER")
SET(CXX_FLAGS_LSAN "${CXX_GCC_FLAGS} -ggdb3 -O0 -gdwarf-2 -fsanitize=leak -DLEAK_SANITIZER")
SET(CXX_FLAGS_UBSAN "${CXX_GCC_FLAGS} -ggdb3 -O0 -gdwarf-2 -fno-wrapv -fsanitize=undefined")
#SET(CXX_FLAGS_UBSAN "${CXX_FLAGS_UBSAN} -fno-sanitize=alignment,function,vptr,float-divide-by-zero,float-cast-overflow")
string(TOUPPER ${CMAKE_BUILD_TYPE} CMAKE_BUILD_TYPE)

if ("${CMAKE_BUILD_TYPE}" STREQUAL "DEBUG")
    SET(CMAKE_CXX_FLAGS ${CXX_FLAGS_DEBUG})
elseif ("${CMAKE_BUILD_TYPE}" STREQUAL "RELEASE")
    SET(CMAKE_CXX_FLAGS ${CXX_FLAGS_RELEASE})
elseif ("${CMAKE_BUILD_TYPE}" STREQUAL "ASAN")
    SET(CMAKE_CXX_FLAGS "${CXX_FLAGS_ASAN}")
elseif ("${CMAKE_BUILD_TYPE}" STREQUAL "LSAN")
    SET(CMAKE_CXX_FLAGS "${CXX_FLAGS_LSAN}")
else()
    message(FATAL_ERROR "Unknown build type: ${CMAKE_BUILD_TYPE}")
endif()

#include
include_directories(main)
# include_directories(SYSTEM ${PROJECT_SOURCE_DIR}/third-party/gtest-1.7.0/fused-cpp)

# pthread, required by absl see https://github.com/abseil/abseil-cpp/issues/183#issuecomment-458453010
set(CMAKE_THREAD_PREFER_PTHREAD TRUE)
set(THREADS_PREFER_PTHREAD_FLAG TRUE)
find_package(Threads REQUIRED)

# thirdparty
add_subdirectory(../thirdparty/googletest googletest)
add_subdirectory(../thirdparty/benchmark benchmark)
add_subdirectory(../thirdparty/robin-hood-hashing robin-hood-hashing)
add_subdirectory(../thirdparty/abseil-cpp abseil-cpp)
#add_subdirectory(../thirdparty/brpc brpc)
#add_subdirectory(thirdparty/gperftools)
#add_subdirectory(../thirdparty/fmt fmt)
#add_subdirectory(thirdparty/glog)
#add_subdirectory(thirdparty/boost)
#add_subdirectory(thirdparty/folly)

# cpp
add_subdirectory(bench)
add_subdirectory(test)
add_subdirectory(main)

# use ccache
find_program(CCACHE_PROGRAM ccache)
if(CCACHE_PROGRAM)
    set_property(GLOBAL PROPERTY RULE_LAUNCH_COMPILE "${CCACHE_PROGRAM}")
endif(CCACHE_PROGRAM)

# I like colors, even with ninja build
if ("${CMAKE_CXX_COMPILER_ID}" STREQUAL "GNU")
    add_compile_options (-fdiagnostics-color=always)
elseif ("${CMAKE_CXX_COMPILER_ID}" STREQUAL "Clang")
    add_compile_options (-fcolor-diagnostics)
endif ()
