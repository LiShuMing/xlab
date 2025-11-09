cmake_minimum_required(VERSION 3.16)

project(srlab
    VERSION 0.1.0
    DESCRIPTION "Sample CMake project configured with a shared third-party toolchain"
    LANGUAGES CXX)

set(THIRDPARTY_ROOT "/home/disk1/sr-deps/thirdparty-latest" CACHE PATH "Root directory of SR Lab's shared third-party dependencies")

if(NOT EXISTS "${THIRDPARTY_ROOT}")
    message(FATAL_ERROR "Configured THIRDPARTY_ROOT='${THIRDPARTY_ROOT}' does not exist."
        " Adjust THIRDPARTY_ROOT or mount the shared third-party bundle.")
endif()

list(PREPEND CMAKE_PREFIX_PATH
    "${THIRDPARTY_ROOT}/installed"
    "${THIRDPARTY_ROOT}/installed/lib/cmake"
    "${THIRDPARTY_ROOT}/installed/lib64/cmake")

list(REMOVE_DUPLICATES CMAKE_PREFIX_PATH)

set(CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake" ${CMAKE_MODULE_PATH})

include(ThirdpartyConfig)

add_executable(srlab_app src/main.cpp)

set_target_properties(srlab_app PROPERTIES
    CXX_STANDARD 17
    CXX_STANDARD_REQUIRED ON
    CXX_EXTENSIONS OFF)

target_include_directories(srlab_app PRIVATE
    "${THIRDPARTY_ROOT}/installed/include")

find_package(fmt QUIET)
if(fmt_FOUND)
    target_link_libraries(srlab_app PRIVATE fmt::fmt)
    target_compile_definitions(srlab_app PRIVATE SRLAB_USE_FMT=1)
endif()

find_package(absl QUIET COMPONENTS strings)
if(absl_FOUND)
    target_link_libraries(srlab_app PRIVATE absl::strings)
    target_compile_definitions(srlab_app PRIVATE SRLAB_USE_ABSL_STRINGS=1)
endif()

set(Boost_USE_STATIC_LIBS ON)
set(Boost_USE_STATIC_RUNTIME ON)
set(Boost_NO_WARN_NEW_VERSIONS ON)
set(Boost_DIR "${THIRDPARTY_ROOT}/installed/lib/cmake/Boost-1.80.0")
find_package(Boost 1.80 QUIET COMPONENTS system filesystem)
if(Boost_FOUND)
    target_link_libraries(srlab_app PRIVATE Boost::system Boost::filesystem)
    target_compile_definitions(srlab_app PRIVATE SRLAB_USE_BOOST=1)
    message(STATUS "Boost found: ${Boost_VERSION}")
endif()

enable_testing()
add_subdirectory(tests)

include(GNUInstallDirs)
install(TARGETS srlab_app
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})

