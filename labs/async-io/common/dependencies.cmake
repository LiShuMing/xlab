# Configuration never downloads. Each experiment can be configured independently.
find_path(URING_INCLUDE_DIR liburing.h HINTS "${LIBURING_ROOT}/include")
find_library(URING_LIBRARY NAMES liburing.a uring HINTS "${LIBURING_ROOT}/lib")
if(NOT URING_INCLUDE_DIR OR NOT URING_LIBRARY)
    message(FATAL_ERROR "liburing is required: set LIBURING_ROOT to an installed prefix")
endif()
add_library(async_liburing INTERFACE)
target_include_directories(async_liburing SYSTEM INTERFACE "${URING_INCLUDE_DIR}")
target_link_libraries(async_liburing INTERFACE "${URING_LIBRARY}")
