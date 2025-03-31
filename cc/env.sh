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

# check XLAB_HOME
export LC_ALL=C

XLAB_HOME="../"

# check OS type
if [[ -n "${OSTYPE}" ]]; then
    if [[ "${OSTYPE}" != "linux-gnu" ]] && [[ "${OSTYPE:0:6}" != "darwin" ]]; then
        echo "Error: Unsupported OS type: ${OSTYPE}"
        exit 1
    fi
fi

# if [[ "$(uname -s)" == 'Darwin' ]]; then
#     if ! command -v brew &>/dev/null; then
#         echo "Error: Homebrew is missing. Please install it first due to we use Homebrew to manage the tools which are needed to build the project."
#         exit 1
#     fi

#     cat >"${XLAB_HOME}/custom_env_mac.sh" <<EOF
# # This file is generated automatically. PLEASE DO NOT MODIFY IT.

# HOMEBREW_REPO_PREFIX="$(brew --prefix)"
# CELLARS=(
#     automake
#     autoconf
#     libtool
#     pkg-config
#     texinfo
#     coreutils
#     gnu-getopt
#     python@3
#     cmake
#     ninja
#     ccache
#     bison
#     byacc
#     gettext
#     wget
#     pcre
#     maven
#     llvm@16
#     m4
# )
# for cellar in "\${CELLARS[@]}"; do
#     EXPORT_CELLARS="\${HOMEBREW_REPO_PREFIX}/opt/\${cellar}/bin:\${EXPORT_CELLARS}"
# done
# export PATH="\${EXPORT_CELLARS}:/usr/bin:\${PATH}"

# export XLAB_BUILD_PYTHON_VERSION='python3'

# export NODE_OPTIONS='--openssl-legacy-provider'
# EOF

#     XLAB_HOME_ABSOLUATE_PATH="$(
#         set -e
#         cd "${XLAB_HOME}"
#         pwd
#     )"
#     SOURCE_MAC_ENV_CONTENT="source '${XLAB_HOME_ABSOLUATE_PATH}/custom_env_mac.sh'"
#     if [[ ! -f "${XLAB_HOME}/custom_env.sh" ]] ||
#         ! grep "${SOURCE_MAC_ENV_CONTENT}" "${XLAB_HOME}/custom_env.sh" &>/dev/null; then
#         echo "${SOURCE_MAC_ENV_CONTENT}" >>"${XLAB_HOME}/custom_env.sh"
#     fi
# fi

# # include custom environment variables
# if [[ -f "${XLAB_HOME}/custom_env.sh" ]]; then
#     # shellcheck disable=1091
#     . "${XLAB_HOME}/custom_env.sh"
# fi

# # set XLAB_THIRDPARTY
# if [[ -z "${XLAB_THIRDPARTY}" ]]; then
#     export XLAB_THIRDPARTY="${XLAB_HOME}/thirdparty"
# fi

# # check python
# if [[ -z "${XLAB_BUILD_PYTHON_VERSION}" ]]; then
#     XLAB_BUILD_PYTHON_VERSION="python"
# fi

# export PYTHON="${XLAB_BUILD_PYTHON_VERSION}"

# if ! ${PYTHON} --version; then
#     echo "Error: ${PYTHON} is not found, maybe you should set XLAB_BUILD_PYTHON_VERSION."
#     exit 1
# fi

# if [[ -z "${XLAB_TOOLCHAIN}" ]]; then
#     if [[ "$(uname -s)" == 'Darwin' ]]; then
#         XLAB_TOOLCHAIN=clang
#     else
#         XLAB_TOOLCHAIN=clang
#     fi
# fi

# if [[ "${XLAB_TOOLCHAIN}" == "gcc" ]]; then
#     # set GCC HOME
#     if [[ -z "${XLAB_GCC_HOME}" ]]; then
#         XLAB_GCC_HOME="$(dirname "$(command -v gcc)")"/..
#         export XLAB_GCC_HOME
#     fi

#     export CC="${XLAB_GCC_HOME}/bin/gcc"
#     export CXX="${XLAB_GCC_HOME}/bin/g++"
#     if test -x "${XLAB_GCC_HOME}/bin/ld"; then
#         export XLAB_BIN_UTILS="${XLAB_GCC_HOME}/bin/"
#     fi
#     ENABLE_PCH='OFF'
# elif [[ "${XLAB_TOOLCHAIN}" == "clang" ]]; then
#     # set CLANG HOME
#     if [[ -z "${XLAB_CLANG_HOME}" ]]; then
#         XLAB_CLANG_HOME="$(dirname "$(command -v clang)")"/..
#         export XLAB_CLANG_HOME
#     fi

#     export CC="${XLAB_CLANG_HOME}/bin/clang"
#     export CXX="${XLAB_CLANG_HOME}/bin/clang++"
#     if test -x "${XLAB_CLANG_HOME}/bin/ld.lld"; then
#         export XLAB_BIN_UTILS="${XLAB_CLANG_HOME}/bin/"
#     fi
#     if [[ -f "${XLAB_CLANG_HOME}/bin/llvm-symbolizer" ]]; then
#         export ASAN_SYMBOLIZER_PATH="${XLAB_CLANG_HOME}/bin/llvm-symbolizer"
#     fi

#     covs=()
#     while IFS='' read -r line; do covs+=("${line}"); done <<<"$(find "${XLAB_CLANG_HOME}" -name "llvm-cov*")"
#     if [[ ${#covs[@]} -ge 1 ]]; then
#         LLVM_COV="${covs[0]}"
#     else
#         LLVM_COV="$(command -v llvm-cov)"
#     fi
#     export LLVM_COV

#     profdatas=()
#     while IFS='' read -r line; do profdatas+=("${line}"); done <<<"$(find "${XLAB_CLANG_HOME}" -name "llvm-profdata*")"
#     if [[ ${#profdatas[@]} -ge 1 ]]; then
#         LLVM_PROFDATA="${profdatas[0]}"
#     else
#         LLVM_PROFDATA="$(command -v llvm-profdata)"
#     fi
#     export LLVM_PROFDATA

#     if [[ -z "${ENABLE_PCH}" ]]; then
#         ENABLE_PCH='ON'
#     fi
# else
#     echo "Error: unknown XLAB_TOOLCHAIN=${XLAB_TOOLCHAIN}, currently only 'gcc' and 'clang' are supported"
#     exit 1
# fi

export CCACHE_COMPILERCHECK=content
if [[ "${ENABLE_PCH}" == "ON" ]]; then
    export CCACHE_PCH_EXTSUM=true
    export CCACHE_SLOPPINESS="pch_defines,time_macros"
else
    export CCACHE_NOPCH_EXTSUM=true
    export CCACHE_SLOPPINESS="default"
fi

if [[ -z "${XLAB_BIN_UTILS}" ]]; then
    export XLAB_BIN_UTILS='/usr/bin/'
fi

XLAB_GCC_HOME='/opt/rh/gcc-toolset-10/root/usr/'
if [[ -z "${XLAB_GCC_HOME}" ]]; then
    XLAB_GCC_HOME="$(dirname "$(command -v gcc)")/.."
    export XLAB_GCC_HOME
fi
echo "XLAB_GCC_HOME=${XLAB_GCC_HOME}"
if [[ ! -f "${XLAB_GCC_HOME}/bin/gcc" ]]; then
    echo "Error: wrong directory XLAB_GCC_HOME=${XLAB_GCC_HOME}"
    exit 1
fi

# export CLANG COMPATIBLE FLAGS
CLANG_COMPATIBLE_FLAGS="$(echo | "${XLAB_GCC_HOME}/bin/gcc" -Wp,-v -xc++ - -fsyntax-only 2>&1 |
    grep -E '^\s+/' | awk '{print "-I" $1}' | tr '\n' ' ')"
export CLANG_COMPATIBLE_FLAGS

echo "1"
CMAKE_CMD='cmake'
if [[ -n "${CUSTOM_CMAKE}" ]]; then
    CMAKE_CMD="${CUSTOM_CMAKE}"
fi
if ! "${CMAKE_CMD}" --version; then
    echo "Error: cmake is not found"
    exit 1
fi
export CMAKE_CMD
echo "${CMAKE_CMD}"

GENERATOR="Unix Makefiles"
BUILD_SYSTEM="make"
if NINJA_VERSION="$(ninja --version 2>/dev/null)"; then
    echo "ninja ${NINJA_VERSION}"
    GENERATOR="Ninja"
    BUILD_SYSTEM="ninja"
fi

if CCACHE_VERSION="$(ccache --version 2>/dev/null)"; then
    echo "${CCACHE_VERSION}" | head -n 1
    # shellcheck disable=2034
    CMAKE_USE_CCACHE="-DCMAKE_CXX_COMPILER_LAUNCHER=ccache"
fi

export GENERATOR
export BUILD_SYSTEM

export PKG_CONFIG_PATH="${XLAB_HOME}/thirdparty/installed/lib64/pkgconfig:${PKG_CONFIG_PATH}"