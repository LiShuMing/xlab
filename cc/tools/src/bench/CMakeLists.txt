set(LIBRARY_OUTPUT_PATH "${BUILD_DIR}/src/bench")

# where to put generated binaries
set(EXECUTABLE_OUTPUT_PATH "${BUILD_DIR}/src/bench")

add_library(Tools STATIC
    tool.cpp
)
