message(STATUS "link_libs=${link_libs}")

add_subdirectory(common)
# add_subdirectory(experiment)

# Create the executable
add_executable(${PROJECT_NAME} main.cc)

