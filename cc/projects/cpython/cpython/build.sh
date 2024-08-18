#!/bin/bash

# This is a script to build the cpython project, it can call python
# to calculate the square root of 9.0 in c++ project.
BUILD_TYPE=Release
BUILD_DIR=build_$BUILD_TYPE
mkdir -p $BUILD_DIR
cd $BUILD_DIR
cmake -DCMAKE_BUILD_TYPE=$BUILD_TYPE \
    -DCMAKE_C_COMPILER=clang \
    -DCMAKE_CXX_COMPILER=clang++ \
    -DCMAKE_CXX_COMPILER_LAUNCHER=ccache \
    -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
    -Dgperftools_enable_libunwind=NO \
    -Dgperftools_enable_frame_pointers=ON \
    -Dgperftools_build_benchmark=OFF \
    -DBUILD_TESTING=OFF \
    -DBENCHMARK_ENABLE_TESTING=OFF \
    -DFMT_INSTALL=ON \
    -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
    .. 
make
./EmbedPython
