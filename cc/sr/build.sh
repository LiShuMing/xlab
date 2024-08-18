#!/usr/bin/env bash
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

##############################################################
# This script is used to compile StarRocks
# Usage: 
#    sh build.sh --help
# Eg:
#    sh build.sh                                      build all
#    sh build.sh  --be                                build Backend without clean
#    sh build.sh  --fe --clean                        clean and build Frontend and Spark Dpp application
#    sh build.sh  --fe --be --clean                   clean and build Frontend, Spark Dpp application and Backend
#    sh build.sh  --spark-dpp                         build Spark DPP application alone
#    BUILD_TYPE=build_type ./build.sh --be            build Backend is different mode (build_type could be Release, Debug, or Asan. Default value is Release. To build Backend in Debug mode, you can execute: BUILD_TYPE=Debug ./build.sh --be)
#
# You need to make sure all thirdparty libraries have been
# compiled and installed correctly.
##############################################################

set -eo pipefail

ROOT=`dirname "$0"`
ROOT=`cd "$ROOT"; pwd`
MACHINE_TYPE=$(uname -m)

export STARROCKS_HOME=${ROOT}

. ${STARROCKS_HOME}/env.sh



if [[ ! -f ${STARROCKS_THIRDPARTY}/installed/include/fast_float/fast_float.h ]]; then
    echo "Thirdparty libraries need to be build ..."
    ${STARROCKS_THIRDPARTY}/build-thirdparty.sh
fi
PARALLEL=$[$(nproc)/4+1]



if [[ -z ${USE_AVX2} ]]; then
    USE_AVX2=ON
fi
if [[ -z ${USE_AVX512} ]]; then
    ## Disable it by default
    USE_AVX512=OFF
fi
if [[ -z ${USE_SSE4_2} ]]; then
    USE_SSE4_2=ON
fi

if [ -e /proc/cpuinfo ] ; then
    # detect cpuinfo
    if [[ -z $(grep -o 'avx[^ ]*' /proc/cpuinfo) ]]; then
        USE_AVX2=OFF
    fi
    if [[ -z $(grep -o 'avx512' /proc/cpuinfo) ]]; then
        USE_AVX512=OFF
    fi
    if [[ -z $(grep -o 'sse[^ ]*' /proc/cpuinfo) ]]; then
        USE_SSE4_2=OFF
    fi
fi

check_tool()
{
    local toolname=$1
    if [ -e $STARROCKS_THIRDPARTY/installed/bin/$toolname ] ; then
        return 0
    fi
    if which $toolname &>/dev/null ; then
        return 0
    fi
    return 1
}

# check protoc and thrift
for tool in protoc thrift
do
    if ! check_tool $tool ; then
        echo "Can't find command tool '$tool'!"
        exit 1
    fi
done


cd ${STARROCKS_HOME}


if [[ "${MACHINE_TYPE}" == "aarch64" ]]; then
    export LIBRARY_PATH=${JAVA_HOME}/jre/lib/aarch64/server/
else
    export LIBRARY_PATH=${JAVA_HOME}/jre/lib/amd64/server/
fi


if ! ${CMAKE_CMD} --version; then
    echo "Error: cmake is not found"
    exit 1
fi

CMAKE_BUILD_TYPE=${BUILD_TYPE:-Release}
echo "Build Backend: ${CMAKE_BUILD_TYPE}"
CMAKE_BUILD_DIR=${STARROCKS_HOME}/be/build_${CMAKE_BUILD_TYPE}
if [ "${WITH_GCOV}" = "ON" ]; then
    CMAKE_BUILD_DIR=${STARROCKS_HOME}/be/build_${CMAKE_BUILD_TYPE}_gcov
fi
export PATH=$PATH:$STARROCKS_THIRDPARTY/installed/bin/
which protoc

mkdir -p ${CMAKE_BUILD_DIR}
cd ${CMAKE_BUILD_DIR}
${CMAKE_CMD} -G "${CMAKE_GENERATOR}" \
            -DSTARROCKS_THIRDPARTY=${STARROCKS_THIRDPARTY} \
            -DSTARROCKS_HOME=${STARROCKS_HOME} \
            -DCMAKE_CXX_COMPILER_LAUNCHER=ccache \
            -DCMAKE_BUILD_TYPE=${CMAKE_BUILD_TYPE} \
            -DMAKE_TEST=OFF -DWITH_GCOV=${WITH_GCOV}\
            -DUSE_AVX2=$USE_AVX2 -DUSE_AVX512=$USE_AVX512 -DUSE_SSE4_2=$USE_SSE4_2 \
            -DENABLE_QUERY_DEBUG_TRACE=$ENABLE_QUERY_DEBUG_TRACE \
            -DUSE_JEMALLOC=$USE_JEMALLOC \
            -DWITH_BENCH=${WITH_BENCH} \
            -DWITH_BLOCK_CACHE=${WITH_BLOCK_CACHE} \
            -DCMAKE_EXPORT_COMPILE_COMMANDS=ON  ..
time ${BUILD_SYSTEM} -j${PARALLEL}
${BUILD_SYSTEM} install

echo "***************************************"
echo "Successfully build StarRocks ${MSG}"
echo "***************************************"

exit 0
