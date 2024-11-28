#!/usr/bin/env bash
if [ ! $GCC_HOME ];then
    echo "Not Found GCC_HOME using default GCC"
else
    export CC=$GCC_HOME/bin/gcc
    export CXX=$GCC_HOME/bin/g++
    export PATH=$GCC_HOME/bin:$PATH
fi

if command -v clang >/dev/null 2>&1; then
    CC="clang"
    CXX="clang++"
    echo "Using clang for compilation."
elif command -v gcc >/dev/null 2>&1; then
    CC="gcc"
    CXX="g++"
    echo "Clang not found. Using gcc instead."
else
    echo "Error: Neither clang nor gcc is available on this system."
    exit 1
fi

BUILD_THREAD=12
BUILD_TYPE=ASAN
# BUILD_TYPE=RELEASE
BUILD_DIR=build_$BUILD_TYPE
DIR=$(cd $(dirname $0) && pwd )

# export CMAKE_GENERATOR="Ninja"
# export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64/
# export LD_LIBRARY_PATH=$JAVA_HOME/jre/lib/amd64/server/

# rm -rf $BUILD_DIR
mkdir -p $BUILD_DIR
cd $BUILD_DIR &&
    cmake -DCMAKE_BUILD_TYPE=$BUILD_TYPE \
        -DCMAKE_C_COMPILER=${CC} \
        -DCMAKE_CXX_COMPILER=${CXX} \
        -DCMAKE_CXX_COMPILER_LAUNCHER=ccache \
        -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
        -Dgperftools_enable_libunwind=NO \
        -Dgperftools_enable_frame_pointers=ON \
        -Dgperftools_build_benchmark=OFF \
        -DFMT_INSTALL=ON \
        -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
        .. && cmake --build . --parallel $BUILD_THREAD
