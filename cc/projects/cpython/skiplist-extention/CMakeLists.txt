cmake_minimum_required(VERSION 3.13)
project(SkipList)

set(CMAKE_CXX_STANDARD 17)
#set(CMAKE_C_FLAGS "-std=c99")

add_compile_definitions(SKIPLIST_THREAD_SUPPORT)

IF(CMAKE_BUILD_TYPE MATCHES Debug)
    message("debug build")
    add_compile_definitions(DEBUG)
ELSE()
    message("release build")
ENDIF(CMAKE_BUILD_TYPE MATCHES Debug)

# Use system architecture (arm64 on Apple Silicon, x86_64 on Intel)
# Don't force a specific architecture - let CMake detect it

add_compile_options(
        "-Wall" "-Wpedantic" "-Wextra" "-fexceptions"
        "$<$<CONFIG:DEBUG>:-O0;-g3;-ggdb>"
)
add_definitions(-DSKIPLIST_THREAD_SUPPORT_TRACE)

add_executable(
        SkipList

        src/cpp/HeadNode.h
        src/cpp/IntegrityEnums.h
        src/cpp/main.cpp
        src/cpp/Node.h
        src/cpp/NodeRefs.h
        src/cpp/RollingMedian.h
        src/cpp/SkipList.cpp
        src/cpp/SkipList.h

        # Python interface
        src/cpy/cmpPyObject.cpp
        src/cpy/cmpPyObject.h
        src/cpy/cOrderedStructs.cpp
        src/cpy/cOrderedStructs.h
        src/cpy/cSkipList.cpp
        src/cpy/cSkipList.h
        src/cpy/OrderedStructs.cpp
        src/cpy/OrderedStructs.h
)

include_directories(
        src/cpp
        src/cpy
)

# Use Python 3 (any version) instead of forcing 3.10
FIND_PACKAGE (Python3 3.10 REQUIRED COMPONENTS Interpreter Development)
IF (Python3_FOUND)
    INCLUDE_DIRECTORIES("${Python3_INCLUDE_DIRS}")
    message("Python3_VERSION:           ${Python3_VERSION}")
    message("Python3_EXECUTABLE:        ${Python3_EXECUTABLE}")
    message("Python3_INTERPRETER_ID:    ${Python3_INTERPRETER_ID}")
    message("Python3_INCLUDE_DIRS:      ${Python3_INCLUDE_DIRS}")
    message("Python3_STDLIB:            ${Python3_STDLIB}")
    message("Python3_STDARCH:           ${Python3_STDARCH}")
    message("Python3_LINK_OPTIONS:      ${Python3_LINK_OPTIONS}")
    message("Python3_LIBRARIES:         ${Python3_LIBRARIES}")
ELSE ()
    MESSAGE(FATAL_ERROR "Unable to find Python libraries.")
ENDIF ()

target_link_libraries(SkipList ${Python3_LIBRARIES})

target_compile_options(SkipList PRIVATE -Wall -Wextra -Wno-c99-extensions -pedantic)# -Werror)
