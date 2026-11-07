# PyTorch ROCm 版本手动安装指南

## 📋 前置条件

- WSL2 已配置
- Python 3.12 虚拟环境
- 约 10GB 磁盘空间

---

## 第一步：准备环境

```bash
# 1. 创建并激活虚拟环境（如果还没有）
python3 -m venv ~/pytorch_rocm_env
source ~/pytorch_rocm_env/bin/activate

# 2. 升级 pip
pip install --upgrade pip

# 3. 安装基础依赖
pip install filelock typing-extensions networkx jinja2 fsspec sympy numpy
```

---

## 第二步：下载所需文件

创建下载目录：

```bash
mkdir -p ~/rocm_packages
cd ~/rocm_packages
```

### 需要下载的文件清单

| 文件名 | 大小 | 下载链接 |
|--------|------|----------|
| torch-2.5.1+rocm6.2 | ~3.8GB | [下载](https://download.pytorch.org/whl/rocm6.2/torch-2.5.1%2Brocm6.2-cp312-cp312-linux_x86_64.whl) |
| pytorch-triton-rocm-3.1.0 | ~200MB | [下载](https://download.pytorch.org/whl/rocm6.2/pytorch_triton_rocm-3.1.0-cp312-cp312-linux_x86_64.whl) |
| torchvision-0.20.1+rocm6.2 | ~50MB | [下载](https://download.pytorch.org/whl/rocm6.2/torchvision-0.20.1%2Brocm6.2-cp312-cp312-linux_x86_64.whl) |
| torchaudio-2.5.1+rocm6.2 | ~10MB | [下载](https://download.pytorch.org/whl/rocm6.2/torchaudio-2.5.1%2Brocm6.2-cp312-cp312-linux_x86_64.whl) |

### 使用 wget 下载（推荐断点续传）

```bash
cd ~/rocm_packages

# 下载 torch（已存在可跳过）
wget -c "https://download.pytorch.org/whl/rocm6.2/torch-2.5.1%2Brocm6.2-cp312-cp312-linux_x86_64.whl"

# 下载 pytorch-triton-rocm
wget -c "https://download.pytorch.org/whl/rocm6.2/pytorch_triton_rocm-3.1.0-cp312-cp312-linux_x86_64.whl"

# 下载 torchvision
wget -c "https://download.pytorch.org/whl/rocm6.2/torchvision-0.20.1%2Brocm6.2-cp312-cp312-linux_x86_64.whl"

# 下载 torchaudio
wget -c "https://download.pytorch.org/whl/rocm6.2/torchaudio-2.5.1%2Brocm6.2-cp312-cp312-linux_x86_64.whl"
```

> 💡 **提示**: 如果下载速度慢，可以：
> 1. 使用浏览器下载后上传到 `~/rocm_packages/`
> 2. 使用代理：`export https_proxy=http://your-proxy:port`

---

## 第三步：安装 whl 文件

### 方法 A：使用 pip 安装（推荐）

```bash
# 确保在虚拟环境中
source ~/pytorch_rocm_env/bin/activate
cd ~/rocm_packages

# 按顺序安装（先安装 triton，再安装 torch）
pip install pytorch_triton_rocm-3.1.0-cp312-cp312-linux_x86_64.whl
pip install torch-2.5.1+rocm6.2-cp312-cp312-linux_x86_64.whl --no-deps
pip install torchvision-0.20.1+rocm6.2-cp312-cp312-linux_x86_64.whl --no-deps
pip install torchaudio-2.5.1+rocm6.2-cp312-cp312-linux_x86_64.whl --no-deps
```

### 方法 B：如果 pip 安装失败，使用 --force-reinstall

```bash
pip install pytorch_triton_rocm-3.1.0-cp312-cp312-linux_x86_64.whl --force-reinstall
pip install torch-2.5.1+rocm6.2-cp312-cp312-linux_x86_64.whl --force-reinstall --no-deps
```

---

## 第四步：验证安装

### 4.1 基础验证

```bash
source ~/pytorch_rocm_env/bin/activate

python -c "
import torch
print(f'PyTorch 版本: {torch.__version__}')
print(f'CUDA/ROCm 可用: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'GPU 数量: {torch.cuda.device_count()}')
    print(f'GPU 名称: {torch.cuda.get_device_name(0)}')
"
```

### 4.2 完整验证脚本

创建验证脚本 `verify_rocm.py`：

```python
#!/usr/bin/env python3
import torch
import time

print("=" * 50)
print("PyTorch ROCm 验证")
print("=" * 50)

print(f"\nPyTorch 版本: {torch.__version__}")
print(f"ROCm 可用: {torch.cuda.is_available()}")

if torch.cuda.is_available():
    print(f"GPU 数量: {torch.cuda.device_count()}")
    for i in range(torch.cuda.device_count()):
        props = torch.cuda.get_device_properties(i)
        print(f"\nGPU {i}: {torch.cuda.get_device_name(i)}")
        print(f"  显存: {props.total_memory / 1e9:.2f} GB")
        print(f"  计算能力: {props.major}.{props.minor}")
    
    # 简单测试
    print("\n" + "=" * 50)
    print("运行简单测试...")
    print("=" * 50)
    
    device = torch.device("cuda")
    x = torch.randn(1000, 1000, device=device)
    y = torch.randn(1000, 1000, device=device)
    
    # 预热
    for _ in range(3):
        z = torch.matmul(x, y)
    torch.cuda.synchronize()
    
    # 测试
    start = time.time()
    for _ in range(10):
        z = torch.matmul(x, y)
    torch.cuda.synchronize()
    elapsed = time.time() - start
    
    print(f"矩阵乘法 (1000x1000) x 10: {elapsed*1000:.2f} ms")
    print(f"平均: {elapsed*100:.2f} ms/次")
    print("\n✅ ROCm GPU 工作正常！")
else:
    print("\n⚠️ GPU 不可用，将使用 CPU 模式")
```

运行：

```bash
python verify_rocm.py
```

---

## 第五步：设置环境变量

添加到 `~/.bashrc`：

```bash
cat >> ~/.bashrc << 'EOF'

# PyTorch ROCm 环境变量
export PATH=$PATH:/opt/rocm/bin
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/opt/rocm/lib
export HSA_OVERRIDE_GFX_VERSION=11.0.0  # Radeon 890M RDNA3.5
export PYTORCH_ROCM_ARCH=gfx1100
EOF

source ~/.bashrc
```

---

## 第六步：测试实际应用

### 6.1 矩阵运算对比

```python
import torch
import time

def benchmark(device, name):
    size = 2000
    a = torch.randn(size, size, device=device)
    b = torch.randn(size, device=device)
    
    # 预热
    for _ in range(5):
        c = torch.matmul(a, b)
    
    if device.type == "cuda":
        torch.cuda.synchronize()
    
    # 测试
    start = time.time()
    iterations = 20
    for _ in range(iterations):
        c = torch.matmul(a, b)
        if device.type == "cuda":
            torch.cuda.synchronize()
    
    elapsed = time.time() - start
    avg_ms = elapsed / iterations * 1000
    
    print(f"{name}: {avg_ms:.2f} ms/iter")
    return avg_ms

# CPU
cpu_time = benchmark(torch.device("cpu"), "CPU")

# GPU (如果可用)
if torch.cuda.is_available():
    gpu_time = benchmark(torch.device("cuda"), "GPU")
    print(f"\n加速比: {cpu_time/gpu_time:.1f}x")
```

### 6.2 简单神经网络

```python
import torch
import torch.nn as nn

# 定义网络
class Net(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc1 = nn.Linear(784, 256)
        self.fc2 = nn.Linear(256, 128)
        self.fc3 = nn.Linear(128, 10)
    
    def forward(self, x):
        x = torch.relu(self.fc1(x))
        x = torch.relu(self.fc2(x))
        return self.fc3(x)

# 测试
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = Net().to(device)

# 随机输入
batch_size = 64
input_data = torch.randn(batch_size, 784, device=device)

# 前向传播
output = model(input_data)
print(f"输入形状: {input_data.shape}")
print(f"输出形状: {output.shape}")
print(f"设备: {device}")
```

---

## 常见问题

### Q1: `libc++` 或 `libstdc++` 错误

```bash
# 安装兼容库
sudo apt update
sudo apt install -y libstdc++-12-dev
```

### Q2: `libamdhip64.so` 未找到

```bash
# 安装 ROCm 运行时（如果还没装）
sudo apt install -y rocm-opencl-runtime hip-runtime-amd

# 或设置库路径
export LD_LIBRARY_PATH=/opt/rocm/lib:$LD_LIBRARY_PATH
```

### Q3: `HSA_STATUS_ERROR`

```bash
# 设置 GPU 架构覆盖
export HSA_OVERRIDE_GFX_VERSION=11.0.0
export AMD_ARCH=gfx1100
```

### Q4: 权限不足

```bash
# 添加用户到 video 和 render 组
sudo usermod -aG video,render $USER

# 重新登录生效
```

---

## 快速命令清单

```bash
# 1. 创建环境
python3 -m venv ~/pytorch_rocm_env
source ~/pytorch_rocm_env/bin/activate

# 2. 下载文件（cd ~/rocm_packages）
wget -c "https://download.pytorch.org/whl/rocm6.2/torch-2.5.1%2Brocm6.2-cp312-cp312-linux_x86_64.whl"
wget -c "https://download.pytorch.org/whl/rocm6.2/pytorch_triton_rocm-3.1.0-cp312-cp312-linux_x86_64.whl"

# 3. 安装
pip install pytorch_triton_rocm-3.1.0-cp312-cp312-linux_x86_64.whl
pip install torch-2.5.1+rocm6.2-cp312-cp312-linux_x86_64.whl --no-deps

# 4. 验证
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available())"
```

---

## 文件你已经有的

```bash
# 检查已下载的文件
ls -lh /tmp/pytorch_download/

# 应该能看到:
# torch-2.5.1+rocm6.2-cp312-cp312-linux_x86_64.whl (3.8GB)
```

**你只需要再下载 pytorch-triton-rocm！**

```bash
cd /tmp/pytorch_download
wget -c "https://download.pytorch.org/whl/rocm6.2/pytorch_triton_rocm-3.1.0-cp312-cp312-linux_x86_64.whl"
```

---

祝安装顺利！如有问题，查看错误信息并参考上方 FAQ。
