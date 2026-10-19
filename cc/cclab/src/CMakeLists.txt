message(STATUS "link_libs=${link_libs}")

add_subdirectory(common)
# add_subdirectory(experiment)

# only build benchmark in release mode
if (${CMAKE_BUILD_TYPE} STREQUAL "RELEASE")
    xlab_require_benchmark()
    if(NOT TARGET benchmark)
        add_library(benchmark ALIAS benchmark::benchmark)
    endif()
    add_subdirectory(bench)
endif()

# Create the executable
add_executable(${PROJECT_NAME} main.cc)

