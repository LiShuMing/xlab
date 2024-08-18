include_guard(GLOBAL)

# -- Binary lookup -----------------------------------------------------------
set(_thirdparty_bin "${THIRDPARTY_ROOT}/installed/bin")
if(EXISTS "${_thirdparty_bin}")
    list(APPEND CMAKE_PROGRAM_PATH "${_thirdparty_bin}")
endif()
unset(_thirdparty_bin)

# -- Library lookup ----------------------------------------------------------
foreach(_thirdparty_lib_dir
        "${THIRDPARTY_ROOT}/installed/lib"
        "${THIRDPARTY_ROOT}/installed/lib64")
    if(EXISTS "${_thirdparty_lib_dir}")
        list(APPEND CMAKE_LIBRARY_PATH "${_thirdparty_lib_dir}")
        list(APPEND CMAKE_PREFIX_PATH "${_thirdparty_lib_dir}/cmake")
    endif()
endforeach()
unset(_thirdparty_lib_dir)

# -- Include lookup ----------------------------------------------------------
set(_thirdparty_include "${THIRDPARTY_ROOT}/installed/include")
if(EXISTS "${_thirdparty_include}")
    list(APPEND CMAKE_INCLUDE_PATH "${_thirdparty_include}")
endif()
unset(_thirdparty_include)

# -- Debug print -------------------------------------------------------------
option(SRLAB_PRINT_THIRDPARTY "Print a summary of third-party search paths" OFF)
if(SRLAB_PRINT_THIRDPARTY)
    message(STATUS "THIRDPARTY_ROOT: ${THIRDPARTY_ROOT}")
    message(STATUS "CMAKE_PREFIX_PATH: ${CMAKE_PREFIX_PATH}")
    message(STATUS "CMAKE_LIBRARY_PATH: ${CMAKE_LIBRARY_PATH}")
    message(STATUS "CMAKE_INCLUDE_PATH: ${CMAKE_INCLUDE_PATH}")
    message(STATUS "CMAKE_PROGRAM_PATH: ${CMAKE_PROGRAM_PATH}")
endif()

