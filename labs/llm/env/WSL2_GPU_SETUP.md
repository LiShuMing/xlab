# WSL2 GPU 加速配置教程

> 📌 本教程适用于在 WSL2 环境下配置 GPU 加速，用于 AI/LLM 推理和训练任务。
>
> 🔧 当前硬件: **AMD Ryzen AI 9 HX 370** + **AMD Radeon 890M** (核显)

---

## 📋 目录

1. [环境确认](#1-环境确认)
2. [Windows 端配置](#2-windows-端配置)
3. [WSL2 端 GPU 驱动配置](#3-wsl2-端-gpu-驱动配置)
4. [AMD ROCm 配置（本文重点）](#4-amd-rocm-配置本文重点)
5. [NVIDIA CUDA 配置（参考）](#5-nvidia-cuda-配置参考)
6. [AI/LLM 框架 GPU 加速配置](#6-aillm-框架-gpu-加速配置)
7. [故障排查](#7-故障排查)

---

## 1. 环境确认

### 1.1 确认 WSL 版本

```bash
# 检查 WSL 版本（需要 WSL2）
wsl --version

# 输出示例：
# WSL 版本： 2.3.26.0
# 内核版本： 5.15.167.4-1
```

**必须确保是 WSL2**，WSL1 不支持 GPU 直通。

### 1.2 确认 Windows 版本

```powershell
# 在 PowerShell 中运行
winver
```

**要求**: Windows 11 或 Windows 10 版本 21H2（内部版本 19044+）

### 1.3 检查当前 GPU 状态

```bash
# 在 WSL2 中运行
cat /proc/version
lspci 2>/dev/null | grep -i vga
dmesg | grep -i vga
```

---

## 2. Windows 端配置

### 2.1 更新 Windows

确保 Windows 已安装最新更新，特别是以下组件：
- **WSL2 内核更新**
- **GPU 驱动程序**

### 2.2 安装 GPU 驱动（Windows 端）

#### AMD GPU 用户

1. 访问 [AMD 驱动下载页面](https://www.amd.com/en/support/download/drivers.html)
2. 下载并安装 **Ryzen AI 9 HX 370** 的最新驱动
3. 确保安装 **AMD HIP SDK**（用于 ROCm 支持）

或者通过 Windows Update 自动安装：
```powershell
# 在管理员 PowerShell 中
winget upgrade --all
```

#### NVIDIA GPU 用户

1. 访问 [NVIDIA 驱动下载](https://www.nvidia.com/drivers)
2. 安装最新 Game Ready 或 Studio 驱动
3. 确保勾选 **"CUDA"** 组件

### 2.3 启用 WSL2 GPU 支持

```powershell
# 在管理员 PowerShell 中执行

# 1. 确保 WSL2 为默认版本
wsl --set-default-version 2

# 2. 更新 WSL（获取最新 GPU 支持）
wsl --update

# 3. 重启 WSL
wsl --shutdown
```

---

## 3. WSL2 端 GPU 驱动配置

### 3.1 进入 WSL2

```bash
wsl
```

### 3.2 安装基础依赖

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装必要工具
sudo apt install -y \
    build-essential \
    cmake \
    git \
    wget \
    curl \
    python3 \
    python3-pip \
    python3-venv \
    mesa-utils \
    pciutils
```

### 3.3 验证 GPU 是否被识别

```bash
# 方法 1: 查看 PCI 设备
lspci | grep -i vga

# 方法 2: 查看 DirectX 内核驱动
dmesg | grep dxgkrnl

# 方法 3: 查看 /dev/dri 设备
ls -la /dev/dri/

# 方法 4: 对于 AMD GPU，查看渲染设备
ls -la /dev/kfd 2>/dev/null || echo "KFD 设备未找到"
```

---

## 4. AMD ROCm 配置（本文重点）

由于当前系统是 **AMD Radeon 890M**，我们需要配置 **ROCm** 来实现 GPU 加速。

### 4.1 检查 ROCm 兼容性

⚠️ **重要提示**: 
- Radeon 890M (RDNA3.5 架构) 官方 ROCm 支持正在不断完善
- Windows WSL2 下的 ROCm 支持相对较新，可能需要特定版本

### 4.2 安装 ROCm（方法一：官方仓库）

```bash
# 1. 添加 ROCm 仓库
sudo mkdir -p --mode=0755 /etc/apt/keyrings
wget -q -O - https://repo.radeon.com/rocm/rocm.gpg.key | sudo gpg --dearmor -o /etc/apt/keyrings/rocm.gpg

# 2. 添加源（根据 Ubuntu 版本选择）
# Ubuntu 22.04
sudo tee /etc/apt/sources.list.d/rocm.list <<EOF
deb [arch=amd64 signed-by=/etc/apt/keyrings/rocm.gpg] https://repo.radeon.com/rocm/apt/6.2 jammy main
EOF

# Ubuntu 24.04
# deb [arch=amd64 signed-by=/etc/apt/keyrings/rocm.gpg] https://repo.radeon.com/rocm/apt/6.2 noble main

# 3. 更新并安装 ROCm
sudo apt update
sudo apt install -y rocm-dev rocm-libs

# 4. 添加用户到 render 和 video 组
sudo usermod -aG render,video $USER

# 5. 重新登录或重启 WSL
wsl --shutdown
```

### 4.3 安装 ROCm（方法二：Docker 推荐）

由于 WSL2 下的原生 ROCm 可能有兼容性问题，**推荐使用 Docker**：

```bash
# 1. 安装 Docker
sudo apt install -y docker.io docker-compose
sudo usermod -aG docker $USER

# 2. 重启 WSL
wsl --shutdown

# 3. 重新进入 WSL 后，测试 ROCm Docker
docker run -it --rm \
    --device=/dev/kfd \
    --device=/dev/dri \
    --group-add video \
    --group-add render \
    rocm/rocm-terminal:latest

# 在容器内验证
rocminfo
/opt/rocm/bin/rocminfo
```

### 4.4 验证 ROCm 安装

```bash
# 查看 ROCm 信息
rocminfo

# 查看 HIP 设备
rocminfo | grep -E "(Name|Device|Arch)"

# 运行简单测试
/opt/rocm/bin/rocminfo

# 检查库文件
ls /opt/rocm/lib/ | grep hip
```

### 4.5 配置环境变量

```bash
# 添加到 ~/.bashrc 或 ~/.zshrc
cat >> ~/.bashrc << 'EOF'

# ROCm 环境变量
export PATH=$PATH:/opt/rocm/bin:/opt/rocm/hip/bin
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/opt/rocm/lib
export HIP_VISIBLE_DEVICES=0
EOF

source ~/.bashrc
```

---

## 5. NVIDIA CUDA 配置（参考）

如果使用 NVIDIA GPU，配置会更简单：

### 5.1 安装 CUDA Toolkit

```bash
# 1. 下载并安装 CUDA
wget https://developer.download.nvidia.com/compute/cuda/repos/wsl-ubuntu2204/x86_64/cuda-wsl-ubuntu2204.pin
sudo mv cuda-wsl-ubuntu2204.pin /etc/apt/preferences.d/cuda-repository-pin-600

wget https://developer.download.nvidia.com/compute/cuda/12.4.1/local_installers/cuda-repo-wsl-ubuntu-2204-12-4-local_12.4.1-1_amd64.deb
sudo dpkg -i cuda-repo-wsl-ubuntu-2204-12-4-local_12.4.1-1_amd64.deb
sudo cp /var/cuda-repo-wsl-ubuntu-2204-12-4-local/cuda-*-keyring.gpg /usr/share/keyrings/

sudo apt update
sudo apt install -y cuda-toolkit-12-4

# 2. 配置环境变量
echo 'export PATH=/usr/local/cuda/bin:$PATH' >> ~/.bashrc
echo 'export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$PATH' >> ~/.bashrc
source ~/.bashrc
```

### 5.2 验证 CUDA

```bash
nvidia-smi
nvcc --version
```

---

## 6. AI/LLM 框架 GPU 加速配置

### 6.1 PyTorch (ROCm 版本)

```bash
# 创建虚拟环境
python3 -m venv ~/pytorch_env
source ~/pytorch_env/bin/activate

# 安装 ROCm 版本的 PyTorch
pip install torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/rocm6.2

# 或者使用特定版本
pip install torch==2.5.0+rocm6.2 torchvision torchaudio \
    --extra-index-url https://download.pytorch.org/whl/rocm6.2
```

**验证 PyTorch GPU**：

```python
python3 << 'EOF'
import torch

print(f"PyTorch 版本: {torch.__version__}")
print(f"HIP 可用: {torch.cuda.is_available()}")

if torch.cuda.is_available():
    print(f"GPU 数量: {torch.cuda.device_count()}")
    print(f"当前 GPU: {torch.cuda.current_device()}")
    print(f"GPU 名称: {torch.cuda.get_device_name(0)}")
    
    # 简单测试
    x = torch.rand(1000, 1000).cuda()
    y = torch.rand(1000, 1000).cuda()
    z = torch.matmul(x, y)
    print(f"矩阵乘法结果形状: {z.shape}")
    print("✅ GPU 加速正常工作！")
else:
    print("❌ GPU 不可用")
EOF
```

### 6.2 PyTorch (CUDA 版本 - NVIDIA GPU)

```bash
# NVIDIA GPU 用户
pip install torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/cu124
```

### 6.3 llama.cpp (LLM 推理推荐)

llama.cpp 对 AMD GPU 支持良好：

```bash
# 克隆仓库
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp

# 使用 HIP 编译（AMD GPU）
make clean
make -j$(nproc) GGML_HIPBLAS=1 AMDGPU_TARGETS=gfx1100

# 或者 CMake 方式
mkdir build && cd build
cmake .. -DGGML_HIPBLAS=ON -DAMDGPU_TARGETS=gfx1100
make -j$(nproc)

# 验证
./bin/llama-cli --list-devices
```

**常用 llama.cpp 参数**：

```bash
# 运行模型（GPU 推理）
./bin/llama-cli \
    -m /path/to/model.gguf \
    -p "你好" \
    -ngl 999  \  # 加载所有层到 GPU
    -n 512

# 批量推理
./bin/llama-cli \
    -m model.gguf \
    -f input.txt \
    -ngl 999 \
    -o output.txt
```

### 6.4 Ollama（简单 LLM 部署）

```bash
# 安装 Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 对于 AMD GPU，需要设置环境变量
export OLLAMA_HOST=0.0.0.0
export HSA_OVERRIDE_GFX_VERSION=11.0.0  # 对于 RDNA3 架构

# 运行 Ollama
ollama serve &

# 拉取并运行模型
ollama pull qwen2.5:7b
ollama run qwen2.5:7b
```

### 6.5 vLLM（高性能推理）

```bash
# 安装 vLLM（ROCm 版本）
pip install vllm --extra-index-url https://download.pytorch.org/whl/rocm6.2

# 或者从源码安装（推荐）
git clone https://github.com/vllm-project/vllm.git
cd vllm
pip install -e . --extra-index-url https://download.pytorch.org/whl/rocm6.2
```

**运行 vLLM**：

```python
from vllm import LLM, SamplingParams

# 加载模型
llm = LLM(
    model="Qwen/Qwen2.5-7B-Instruct",
    tensor_parallel_size=1,
    gpu_memory_utilization=0.9
)

# 推理
prompts = ["你好，请介绍一下自己"]
sampling_params = SamplingParams(temperature=0.7, max_tokens=512)
outputs = llm.generate(prompts, sampling_params)

for output in outputs:
    print(output.outputs[0].text)
```

### 6.6 Transformers + Accelerate

```bash
pip install transformers accelerate
```

**使用示例**：

```python
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
import torch

model_name = "Qwen/Qwen2.5-7B-Instruct"

# 自动检测 GPU
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"使用设备: {device}")

# 加载模型（自动分配到 GPU）
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype=torch.float16 if device == "cuda" else torch.float32,
    device_map="auto"
)
tokenizer = AutoTokenizer.from_pretrained(model_name)

# 创建 pipeline
pipe = pipeline(
    "text-generation",
    model=model,
    tokenizer=tokenizer,
    torch_dtype=torch.float16,
    device_map="auto"
)

# 推理
result = pipe("你好，请介绍一下自己", max_new_tokens=256)
print(result[0]['generated_text'])
```

---

## 7. 故障排查

### 7.1 常见问题

#### Q1: `rocminfo` 显示 "No devices found"

```bash
# 解决方案 1: 检查设备权限
ls -la /dev/kfd /dev/dri/
sudo usermod -aG render,video $USER

# 解决方案 2: 设置 HSA_OVERRIDE_GFX_VERSION
export HSA_OVERRIDE_GFX_VERSION=11.0.0  # RDNA3/3.5 架构

# 解决方案 3: 检查 Windows 驱动
# 确保 Windows 侧安装了最新的 AMD Adrenalin 驱动
```

#### Q2: PyTorch 显示 `cuda.is_available() = False`

```bash
# 对于 ROCm，需要安装 rocm 版本的 torch
pip uninstall torch torchvision torchaudio
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm6.2

# 验证
python3 -c "import torch; print(torch.__version__); print(torch.cuda.is_available())"
```

#### Q3: llama.cpp 编译失败

```bash
# 确保安装了 hip 开发库
sudo apt install -y hip-dev rocm-llvm

# 检查 hipcc
which hipcc
hipcc --version

# 重新编译
cd llama.cpp
make clean
make -j$(nproc) GGML_HIPBLAS=1
```

#### Q4: WSL2 无法识别 GPU

```powershell
# 在 Windows PowerShell 中检查
# 1. 确保 GPU 驱动已安装
Get-ComputerInfo | findstr "HyperV"

# 2. 检查 WSL 配置
cat $env:USERPROFILE\.wslconfig

# 3. 创建/编辑 .wslconfig 启用 GPU
@"
[wsl2]
gpuSupport=true
memory=16GB
processors=8
"@ | Out-File -FilePath $env:USERPROFILE\.wslconfig -Encoding utf8

# 4. 重启 WSL
wsl --shutdown
```

### 7.2 性能优化建议

```bash
# 1. 限制 WSL2 内存（避免 Windows 卡顿）
# 编辑 C:\Users\<用户名>\.wslconfig
[wsl2]
memory=12GB
processors=8
swap=4GB

# 2. 使用共享内存（提高 GPU-CPU 传输效率）
sudo mount -t tmpfs -o size=4G tmpfs /dev/shm

# 3. 设置环境变量优化性能
export HIP_VISIBLE_DEVICES=0
export HSA_ENABLE_SDMA=0  # 某些情况下禁用 SDMA 更稳定
```

### 7.3 获取帮助

| 资源 | 链接 |
|------|------|
| ROCm 文档 | https://rocm.docs.amd.com/ |
| PyTorch ROCm | https://pytorch.org/docs/stable/notes/hip.html |
| llama.cpp | https://github.com/ggerganov/llama.cpp |
| AMD 社区 | https://community.amd.com/ |

---

## 📝 快速检查清单

完成配置后，运行以下命令验证：

```bash
# 1. 系统信息
echo "=== 系统信息 ==="
uname -a
cat /etc/os-release | grep PRETTY_NAME

# 2. GPU 信息
echo "=== GPU 信息 ==="
lspci 2>/dev/null | grep -i vga || echo "lspci 不可用"
dmesg 2>/dev/null | grep -i "dxgkrnl" | head -3

# 3. ROCm/CUDA 信息
echo "=== ROCm/CUDA 信息 ==="
which rocminfo && rocminfo 2>/dev/null | head -20
which nvidia-smi && nvidia-smi 2>/dev/null

# 4. Python GPU 检查
echo "=== Python GPU 检查 ==="
python3 << 'PYEOF'
import sys
try:
    import torch
    print(f"PyTorch: {torch.__version__}")
    print(f"CUDA/ROCm 可用: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
except ImportError:
    print("PyTorch 未安装")
PYEOF

echo "=== 检查完成 ==="
```

---

## ✅ 总结

| 步骤 | 状态 | 命令 |
|------|------|------|
| WSL2 版本检查 | ⬜ | `wsl --version` |
| Windows GPU 驱动 | ⬜ | 设备管理器检查 |
| ROCm/CUDA 安装 | ⬜ | 见章节 4/5 |
| PyTorch 安装 | ⬜ | `pip install torch --index-url ...` |
| llama.cpp 编译 | ⬜ | `make GGML_HIPBLAS=1` |
| 模型推理测试 | ⬜ | 见章节 6 |

> 💡 **提示**: 对于 AMD Radeon 890M，推荐使用 **llama.cpp** 或 **Ollama** 进行 LLM 推理，它们对 AMD GPU 的支持相对成熟。

---

*最后更新: 2026-03-28*
