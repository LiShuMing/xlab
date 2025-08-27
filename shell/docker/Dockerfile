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
RUN gcc --version && g++ --version

# 创建工作目录
WORKDIR /workspace

CMD [ "bash" ]
