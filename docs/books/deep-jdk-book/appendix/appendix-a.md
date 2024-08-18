# 附录 A：JDK 27 源码构建与调试环境搭建

## A.1 获取源码

```bash
# 方式 1：从 GitHub 克隆
git clone https://github.com/openjdk/jdk27.git

# 方式 2：从 Mercurial 仓库
hg clone https://hg.openjdk.org/jdk27/jdk27

# 方式 3：下载源码包
# https://jdk.java.net/27/
```

## A.2 构建依赖

```bash
# Ubuntu/Debian
sudo apt install build-essential autoconf cmake \
    libx11-dev libxext-dev libxrender-dev libxrandr-dev \
    libxtst-dev libxt-dev libcups2-dev libfontconfig1-dev \
    libasound2-dev libfreetype6-dev libffi-dev

# CentOS/RHEL
sudo yum install gcc gcc-c++ autoconf cmake \
    libX11-devel libXext-devel libXrender-devel libXrandr-devel \
    libXtst-devel libXt-devel cups-devel fontconfig-devel \
    alsa-lib-devel freetype-devel libffi-devel

# Boot JDK（需要 JDK 26+）
sudo apt install openjdk-26-jdk
```

## A.3 配置与构建

```bash
cd jdk27

# 配置（debug 构建用于调试）
bash configure \
    --with-debug-level=slowdebug \
    --with-native-debug-symbols=internal \
    --enable-dtrace \
    --with-jvm-features=+zgc,+shenandoahgc,+jvmci

# 构建
make images JOBS=$(nproc)

# 验证
build/linux-x86_64-server-slowdebug/jdk/bin/java -version
```

## A.4 常用构建目标

```bash
make images          # 完整 JDK 镜像
make hotspot         # 仅构建 HotSpot
make jdk             # 构建 JDK 类库
make docs            # 构建文档
make clean           # 清理
make CONF=...        # 指定配置
```

## A.5 调试环境

```bash
# 使用 GDB 调试 JVM
gdb --args build/.../jdk/bin/java -XX:+UseG1GC -cp app.jar Main

# GDB 常用断点
break JNI_CreateJavaVM
break Threads::create_vm
break Universe::initialize_heap
break SafepointSynchronize::begin

# 使用 LLDB 调试（macOS）
lldb -- build/.../jdk/bin/java --patch-module ...
```

## A.6 IDE 配置

```
CLion：
  1. File → Open → 选择 jdk27 目录
  2. 选择 CMakeLists.txt 或 compile_commands.json
  3. 配置构建目标：build/linux-x86_64-server-slowdebug

VS Code：
  1. 安装 C/C++ 扩展
  2. 打开 jdk27 目录
  3. 配置 c_cpp_properties.json：
     "compileCommands": "build/.../compile_commands.json"
```

## A.7 远程调试

```bash
# 启动 JVM 时开启 JDWP
java -agentlib:jdwp=transport=dt_socket,server=y,suspend=n,address=5005 \
     -cp app.jar Main

# 在 IDE 中连接远程调试端口 5005
```
