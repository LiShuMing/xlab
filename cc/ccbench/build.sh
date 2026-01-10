#!/usr/bin/env bash
if [ ! $GCC_HOME ];then
    echo "Not Found GCC_HOME using default GCC"
    if command -v clang-19 >/dev/null 2>&1; then
        CC="clang-19"
        CXX="clang++-19"
        echo "Using clang for compilation."
    elif command -v clang >/dev/null 2>&1; then
        CC="clang"
        CXX="clang++"
        echo "Using clang for compilation."
    elif command -v gcc >/dev/null 2>&1; then
        CC="gcc"
        CXX="g++"
        echo "Clang not found. Using gcc instead."
        GCC_VERSION=$(gcc --version | grep -oP '\d+\.\d+\.\d+')
        GCC_HOME=$(dirname $(dirname $(which gcc)))
        echo "GCC_HOME: $GCC_HOME"
        echo "GCC_VERSION: $GCC_VERSION"
        echo "Using GCC_HOME: $GCC_HOME"
    else
        echo "Error: Neither clang nor gcc is available on this system."
        exit 1
    fi
else
    export CC=$GCC_HOME/bin/gcc
    export CXX=$GCC_HOME/bin/g++
    export PATH=$GCC_HOME/bin:$PATH
    GCC_VERSION=$(cc --version | grep -oP '\d+\.\d+\.\d+')
fi

echo "Compiler: $CC"
echo "C++ Compiler: $CXX"
echo "GCC_HOME: $GCC_HOME"
echo "GCC_VERSION: $GCC_VERSION"

BUILD_THREAD=12
if [ ! $BUILD_TYPE ];then
    BUILD_TYPE=RELEASE
fi
echo "BUILD_TYPE: $BUILD_TYPE"
# BUILD_TYPE=RELEASE
BUILD_DIR=build_$BUILD_TYPE

REQUIRED_CMAKE_VERSION="3.22.0"
version_ge() {
    [ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -n1)" = "$2" ]
}

resolve_cmake() {
    local candidate=$1
    if [ -x "$candidate" ]; then
        echo "$candidate"
        return 0
    fi
    if command -v "$candidate" >/dev/null 2>&1; then
        command -v "$candidate"
        return 0
    fi
    return 1
}

CMAKE_BIN=${CMAKE_BIN:-cmake}
if ! CMAKE_BIN=$(resolve_cmake "$CMAKE_BIN"); then
    echo "Error: cmake executable not found (looked for '${CMAKE_BIN}')." >&2
    exit 1
fi

CURRENT_CMAKE_VERSION=$($CMAKE_BIN --version | head -n1 | awk '{print $3}')
if ! version_ge "$CURRENT_CMAKE_VERSION" "$REQUIRED_CMAKE_VERSION"; then
    if [ "$CMAKE_BIN" != "/usr/bin/cmake" ] && [ -x /usr/bin/cmake ]; then
        ALT_CMAKE_VERSION=$(/usr/bin/cmake --version | head -n1 | awk '{print $3}')
        if version_ge "$ALT_CMAKE_VERSION" "$REQUIRED_CMAKE_VERSION"; then
            CMAKE_BIN="/usr/bin/cmake"
            CURRENT_CMAKE_VERSION="$ALT_CMAKE_VERSION"
        fi
    fi
fi

if ! version_ge "$CURRENT_CMAKE_VERSION" "$REQUIRED_CMAKE_VERSION"; then
    echo "Error: CMake >= ${REQUIRED_CMAKE_VERSION} is required but found ${CURRENT_CMAKE_VERSION} at ${CMAKE_BIN}." >&2
    echo "Please install a newer CMake or set CMAKE_BIN to the appropriate executable." >&2
    exit 1
fi

echo "CMake: $CMAKE_BIN (version $CURRENT_CMAKE_VERSION)"
DIR=$(cd $(dirname $0) && pwd )

# export CMAKE_GENERATOR="Ninja"
# export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64/
# export LD_LIBRARY_PATH=$JAVA_HOME/jre/lib/amd64/server/

# rm -rf $BUILD_DIR
mkdir -p $BUILD_DIR
cd $BUILD_DIR &&
    "$CMAKE_BIN" -DCMAKE_BUILD_TYPE=$BUILD_TYPE \
        -DCMAKE_C_COMPILER=${CC} \
        -DCMAKE_CXX_COMPILER=${CXX} \
        -DCMAKE_CXX_COMPILER_LAUNCHER=ccache \
        -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
        -Dgperftools_enable_libunwind=NO \
        -Dgperftools_enable_frame_pointers=ON \
        -Dgperftools_build_benchmark=OFF \
        -DFMT_INSTALL=ON \
        -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
        .. && "$CMAKE_BIN" --build . --parallel $BUILD_THREAD
