# ROCm 依赖问题解决方案

## 🔍 问题分析

你的系统：Ubuntu 24.04 (noble)  
ROCm 包：为 Ubuntu 22.04 (jammy) 构建

**冲突原因：**
- `hipsolver` 依赖旧版 SuiteSparse 库
- `rocm-gdb` 依赖 Python 3.10（系统为 3.12）

---

## 解决方案 A：安装核心组件（推荐尝试）

只安装 PyTorch 必需的组件：

```bash
# 1. 安装核心 ROCm 库（跳过有问题的包）
sudo apt install -y --no-install-recommends \
    rocm-core \
    rocm-device-libs \
    rocminfo \
    hip-dev \
    hip-runtime-amd \
    rocm-llvm

# 2. 如果上面失败，尝试更精简的安装
sudo apt install -y \
    rocm-core \
    rocminfo \
    hip-dev
```

---

## 解决方案 B：使用 Docker（最可靠）

如果本地安装太麻烦，使用预配置好的 Docker 镜像：

```bash
# 1. 安装 Docker（如果还没装）
sudo apt install -y docker.io
sudo usermod -aG docker $USER

# 2. 重启 WSL2（让 docker 权限生效）
wsl --shutdown
# 重新打开 WSL2

# 3. 拉取 ROCm PyTorch 镜像
docker pull rocm/pytorch:rocm6.2_ubuntu22.04_py3.10_pytorch2.5.1

# 4. 运行容器
docker run -it --rm \
    --device=/dev/kfd \
    --device=/dev/dri \
    --group-add video \
    --group-add render \
    -v $(pwd):/workspace \
    rocm/pytorch:rocm6.2_ubuntu22.04_py3.10_pytorch2.5.1

# 5. 在容器内验证
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available())"
```

---

## 解决方案 C：使用 Conda 安装（可能更简单）

```bash
# 1. 安装 Miniconda
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh -b -p $HOME/miniconda

# 2. 初始化
source $HOME/miniconda/bin/activate
conda init bash

# 3. 创建 ROCm 环境
conda create -n rocm python=3.10 -y
conda activate rocm

# 4. 通过 conda 安装 PyTorch ROCm
conda install pytorch torchvision torchaudio pytorch-cuda=12.1 -c pytorch -c nvidia
# 或使用 pip
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm6.2
```

---

## 解决方案 D：手动安装最小 ROCm

如果只需要 PyTorch GPU 支持，可以尝试：

```bash
# 1. 创建必要的目录和链接
sudo mkdir -p /opt/rocm/lib

# 2. 下载预编译的 ROCm 库（从 GitHub 或其他源）
# 或者使用 llama.cpp 的方案（不需要完整 ROCm）
```

---

## 🚀 推荐：使用 llama.cpp 替代方案

既然 PyTorch ROCm 安装复杂，**强烈推荐使用 llama.cpp**，它对 AMD GPU 支持更好：

```bash
# 1. 安装依赖
sudo apt install -y build-essential git cmake

# 2. 克隆 llama.cpp
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp

# 3. 编译（使用 HIP 支持 AMD GPU）
make -j$(nproc) GGML_HIPBLAS=1 AMDGPU_TARGETS=gfx1100

# 4. 验证 GPU
./llama-cli --list-devices

# 5. 下载并运行模型
wget https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf

./llama-cli \
    -m qwen2.5-0.5b-instruct-q4_k_m.gguf \
    -p "你好" \
    -ngl 999  # 使用 GPU 加速
```

---

## 快速决策

| 你的情况 | 推荐方案 |
|---------|----------|
| 急需 GPU 跑 LLM | **llama.cpp**（5分钟搞定） |
| 需要 PyTorch 生态 | **Docker ROCm** |
| 想折腾到底 | **方案 A 核心组件安装** |
| 不想折腾 | **保持 CPU PyTorch** |

---

## 总结

Ubuntu 24.04 + ROCm 6.2 兼容性不好，建议：

1. **短期**：使用 llama.cpp 跑 LLM（GPU 加速完美）
2. **中期**：使用 Docker ROCm 镜像
3. **长期**：等 ROCm 官方支持 Ubuntu 24.04

你的 PyTorch CPU 版本已经完全可以用于学习和开发！

---

*要我帮你安装 llama.cpp 吗？5分钟就能用上 GPU 加速。*
