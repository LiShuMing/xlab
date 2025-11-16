FROM ubuntu:24.04
# FROM docker.mirrors.ustc.edu.cn/library/ubuntu:25.04

# 环境设置
ENV DEBIAN_FRONTEND=noninteractive

# 安装必要工具
RUN apt update && apt install -y \
    software-properties-common \
    build-essential \
    wget \
    curl \
    git \
    gnupg \
#    cmake \
#    gdb \
#    lldb \
#    vim \
#    ninja-build \
    python3 \
    python3-pip 
#    ca-certificates \
#    && rm -rf /var/lib/apt/lists/*

# 安装 GCC 14（Ubuntu 24.04 默认已经带 GCC 14）
RUN wget -O - https://apt.llvm.org/llvm-snapshot.gpg.key | apt-key add -
RUN echo "deb http://apt.llvm.org/$(lsb_release -cs)/ llvm-toolchain-$(lsb_release -cs)-20 main" >> /etc/apt/sources.list.d/llvm.list

# Update and install Clang 20 and other desired tools
RUN apt-get update && apt-get install -y \
    clang-20 \
    clang-format-20 \
    clang-tidy-20 \
    # Add any other tools you need, e.g., lld-20, libc++-20-dev
    build-essential # For general compilation tools

RUN gcc --version && g++ --version

# 创建工作目录
WORKDIR /workspace

CMD [ "bash" ]
