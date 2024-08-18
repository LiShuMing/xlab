cmake_minimum_required(VERSION 3.20)
project(LLVMJitExprFusion LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

set(THIRDPARTY_DIR /Users/lishuming/work/xlab/cc/thirdparty)

find_package(LLVM REQUIRED CONFIG COMPONENTS Core Support ExecutionEngine IRCompiler)

message(STATUS "Found LLVM ${LLVM_PACKAGE_VERSION}")
message(STATUS "LLVM Include Dirs: ${LLVM_INCLUDE_DIRS}")
message(STATUS "LLVM Library Dirs: ${LLVM_LIBRARY_DIRS}")

include_directories(${LLVM_INCLUDE_DIRS})
include_directories(${CMAKE_SOURCE_DIR}/include)
link_directories(${LLVM_LIBRARY_DIRS})

add_definitions(${LLVM_DEFINITIONS})

option(ENABLE_BENCHMARKS "Enable benchmarks" ON)
option(ENABLE_TESTS "Enable tests" ON)

add_subdirectory(src)
if(ENABLE_TESTS)
    enable_testing()
    add_subdirectory(${THIRDPARTY_DIR}/googletest googletest-build EXCLUDE_FROM_ALL)
    add_subdirectory(test)
endif()
if(ENABLE_BENCHMARKS)
    add_subdirectory(${THIRDPARTY_DIR}/benchmark benchmark-build EXCLUDE_FROM_ALL)
    add_subdirectory(benchmarks)
endif()

install(TARGETS ${PROJECT_NAME}
    ARCHIVE DESTINATION lib
    LIBRARY DESTINATION lib
    RUNTIME DESTINATION bin)
