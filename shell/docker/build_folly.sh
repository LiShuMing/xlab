apt-get update
apt-get install -y \
  g++ cmake pkg-config \
  libfmt-dev libdouble-conversion-dev libevent-dev \
  libgoogle-glog-dev libgflags-dev \
  zlib1g-dev liblz4-dev libzstd-dev libsnappy-dev liblzma-dev \
  libunwind-dev binutils-dev libdw-dev \
  libssl-dev libjemalloc-dev

apt-get install -y \
  libboost-context-dev \
  libboost-filesystem-dev \
  libboost-program-options-dev \
  libboost-regex-dev \
  libboost-thread-dev
#（可选）兜底整个 Boost 开发包
apt-get install -y libboost-all-dev
apt-get install -y libfast-float-dev

# copy fast_float to /opt/fast_float/include
git submodule add git@github.com:fastfloat/fast_float.git cc/thirdparty/fast_float
mkdir -p /opt/fast_float/include
cp -r fast_float/include/fast_float /opt/fast_float/include/

# build folly
cmake .. \
  -DBUILD_SHARED_LIBS=ON \
  -DCMAKE_BUILD_TYPE=Release \
  -DFOLLY_USE_JEMALLOC=ON \
  -DFASTFLOAT_INCLUDE_DIR=/opt/fast_float/include
cmake --build . -j$(nproc)