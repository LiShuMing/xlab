# llama.cpp GPU 加速安装指南

## 🚀 快速安装（5分钟）

### 步骤 1：安装依赖（1分钟）

在你的 WSL2 终端执行：

```bash
sudo apt update
sudo apt install -y build-essential git cmake
```

### 步骤 2：克隆仓库（30秒）

```bash
cd ~
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp
```

### 步骤 3：编译 GPU 版本（3分钟）

```bash
# 使用 AMD GPU (HIP) 编译
make -j$(nproc) GGML_HIPBLAS=1 AMDGPU_TARGETS=gfx1100
```

**如果上面失败，尝试 CMake 方式：**

```bash
mkdir build && cd build
cmake .. -DGGML_HIPBLAS=ON -DAMDGPU_TARGETS=gfx1100
make -j$(nproc)
```

### 步骤 4：验证 GPU（30秒）

```bash
# 在 llama.cpp 目录
./llama-cli --list-devices
```

**预期输出：**
```
Available devices:
  - device 0: AMD Radeon Graphics (AMD)
```

### 步骤 5：下载模型并运行（1分钟）

```bash
# 下载 Qwen2.5-0.5B 模型（小模型，适合测试）
wget https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf

# GPU 运行（-ngl 999 表示加载所有层到 GPU）
./llama-cli \
    -m qwen2.5-0.5b-instruct-q4_k_m.gguf \
    -p "你好，请介绍一下自己" \
    -ngl 999 \
    -n 256
```

---

## 📋 一键复制命令

```bash
# 复制以下所有命令粘贴执行
sudo apt update && \
sudo apt install -y build-essential git cmake && \
cd ~ && \
git clone https://github.com/ggerganov/llama.cpp.git && \
cd llama.cpp && \
make -j$(nproc) GGML_HIPBLAS=1 AMDGPU_TARGETS=gfx1100 && \
echo "=== 编译完成！验证 GPU ===" && \
./llama-cli --list-devices
```

---

## 🎯 运行更多模型

### 下载其他模型

| 模型 | 大小 | 下载命令 |
|------|------|----------|
| Qwen2.5-0.5B | 400MB | `wget https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf` |
| Qwen2.5-1.5B | 1GB | `wget https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf` |
| Llama-3.2-1B | 700MB | `wget https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf` |

### 常用运行参数

```bash
# 基础对话
./llama-cli \
    -m model.gguf \
    -p "你的提示词" \
    -ngl 999 \
    -n 512

# 参数说明：
# -m: 模型文件路径
# -p: 提示词 (prompt)
# -ngl: 加载到 GPU 的层数 (999 = 全部)
# -n: 生成最大 token 数
# -t: 使用线程数 (默认 CPU 核心数)
# --temp: 温度参数 (默认 0.8)
# --top-p: Top-p 采样 (默认 0.9)
```

### 交互式对话模式

```bash
./llama-cli \
    -m qwen2.5-0.5b-instruct-q4_k_m.gguf \
    -ngl 999 \
    --interactive \
    --chatml
```

---

## 🔧 高级用法

### 创建启动脚本

创建 `run_chat.sh`：

```bash
#!/bin/bash
cd ~/llama.cpp
./llama-cli \
    -m qwen2.5-0.5b-instruct-q4_k_m.gguf \
    -ngl 999 \
    --interactive \
    --chatml \
    --color
```

使用：

```bash
chmod +x run_chat.sh
./run_chat.sh
```

### 使用 llama-server（API 服务）

```bash
# 编译 server
make -j$(nproc) GGML_HIPBLAS=1 AMDGPU_TARGETS=gfx1100 llama-server

# 启动服务
./llama-server \
    -m qwen2.5-0.5b-instruct-q4_k_m.gguf \
    -ngl 999 \
    --host 0.0.0.0 \
    --port 8080

# 在浏览器打开 http://localhost:8080
```

---

## 🐛 常见问题

### Q1: 编译报错 "hipcc not found"

```bash
# 安装 HIP 编译器
sudo apt install -y hip-dev

# 或者使用 clang
export CC=clang
export CXX=clang++
make -j$(nproc) GGML_HIPBLAS=1
```

### Q2: GPU 未检测到

```bash
# 设置环境变量
export HSA_OVERRIDE_GFX_VERSION=11.0.0

# 重新运行
./llama-cli --list-devices
```

### Q3: 显存不足

```bash
# 减少 GPU 层数（只加载部分层到 GPU）
./llama-cli -m model.gguf -ngl 20  # 只加载 20 层
```

### Q4: 模型下载慢

```bash
# 使用镜像加速
wget -c --tries=0 --read-timeout=60 \
    "https://hf-mirror.com/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf" \
    -O qwen2.5-0.5b-instruct-q4_k_m.gguf
```

---

## ✅ 验证成功标志

运行 `./llama-cli --list-devices` 应输出：

```
Available devices:
  - device 0: AMD Radeon Graphics (AMD)
```

运行模型时应看到：

```
offload 25/25 layers to GPU
```

这表示所有层都已加载到 GPU！

---

## 📊 性能参考

在 AMD Radeon 890M 上预期性能：

| 模型 | 量化 | 速度 |
|------|------|------|
| Qwen2.5-0.5B | Q4_K_M | ~50-100 tokens/sec |
| Qwen2.5-1.5B | Q4_K_M | ~20-40 tokens/sec |
| Llama-3.2-1B | Q4_K_M | ~30-60 tokens/sec |

---

## 🎉 完成！

现在你可以：
1. ✅ 使用 GPU 加速运行 LLM
2. ✅ 本地离线运行，无需联网
3. ✅ 比 PyTorch 更快的推理速度

**开始你的第一次对话吧！** 🚀
