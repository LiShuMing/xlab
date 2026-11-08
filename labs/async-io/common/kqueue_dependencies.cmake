# Linux compatibility only; native Apple builds use the system kqueue API.
find_path(KQUEUE_INCLUDE_DIR sys/event.h
    HINTS "${LIBKQUEUE_ROOT}/include" PATH_SUFFIXES kqueue)
find_library(KQUEUE_LIBRARY NAMES libkqueue.a kqueue
    HINTS "${LIBKQUEUE_ROOT}/lib")
if(NOT KQUEUE_INCLUDE_DIR OR NOT KQUEUE_LIBRARY)
    message(FATAL_ERROR "libkqueue is required: set LIBKQUEUE_ROOT to an installed prefix")
endif()
find_package(Threads REQUIRED)
add_library(async_libkqueue INTERFACE)
target_include_directories(async_libkqueue SYSTEM INTERFACE "${KQUEUE_INCLUDE_DIR}")
target_link_libraries(async_libkqueue INTERFACE "${KQUEUE_LIBRARY}" Threads::Threads)
