message(STATUS "link_libs=${link_libs}")

add_subdirectory(common)
# add_subdirectory(experiment)

# only build benchmark in release mode
if (${CMAKE_BUILD_TYPE} STREQUAL "RELEASE")
    add_subdirectory(../../thirdparty/benchmark benchmark)
    add_subdirectory(bench)
endif()

# Create the executable
add_executable(${PROJECT_NAME} main.cc)

