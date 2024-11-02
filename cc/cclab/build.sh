#!/usr/bin/env bash
if [ ! $GCC_HOME ];then
    echo "Not Found GCC_HOME using default GCC"
else
    export CC=$GCC_HOME/bin/gcc
    export CXX=$GCC_HOME/bin/g++
    export PATH=$GCC_HOME/bin:$PATH
fi

#CC=clang 
#CXX=clang++

BUILD_THREAD=12
#BUILD_TYPE=ASAN
BUILD_TYPE=Release
BUILD_DIR=build_$BUILD_TYPE
DIR=$(cd $(dirname $0) && pwd )

# export CMAKE_GENERATOR="Ninja"
# export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64/
# export LD_LIBRARY_PATH=$JAVA_HOME/jre/lib/amd64/server/

# rm -rf $BUILD_DIR
mkdir -p $BUILD_DIR
cd $BUILD_DIR &&
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
        .. && cmake --build . --parallel $BUILD_THREAD
