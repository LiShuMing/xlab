# PyTorch 配置与使用教程（WSL2 + AMD GPU）

> 针对 AMD Radeon 890M 的 PyTorch 安装、配置与验证指南

---

## 📋 目录

1. [环境检查](#1-环境检查)
2. [安装方案选择](#2-安装方案选择)
3. [方案 A：ROCm GPU 版本（推荐尝试）](#3-方案-arocm-gpu-版本推荐尝试)
4. [方案 B：CPU 版本（保底方案）](#4-方案-bcpu-版本保底方案)
5. [验证安装](#5-验证安装)
6. [简单 LLM 推理示例](#6-简单-llm-推理示例)
7. [故障排查](#7-故障排查)

---

## 1. 环境检查

### 1.1 检查当前系统

```bash
# 检查操作系统
uname -a
cat /etc/os-release

# 检查 Python 版本（需要 3.8+）
python3 --version

# 检查是否有 GPU
lspci 2>/dev/null | grep -i vga
dmesg 2>/dev/null | grep -i "dxgkrnl"
```

### 1.2 检查硬件信息

```bash
# CPU 信息
lscpu | grep "Model name"

# 内存ﬀ信息
free -h

# 磁盘空间
df -h /
```

---

## 2. 安装方案选择

| 方案 | 适用场景 | 性能 | 难度 |
|------|----------|------|------|
| **A. ROCm GPU** | 有 AMD GPU，想尝试 GPU 加速 | 高 | 中 |
| **B. CPU** | 无 GPU 或 ROCm 不支持 | 低 | 低 |

**建议：** 先尝试方案 A，如遇到问题再使用方案 B。

---

## 3. 方案 A：ROCm GPU 版本（推荐尝试）

### 3.1 安装依赖

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装必要依赖
sudo apt install -y \
    python3-pip \
    python3-venv \
    libjpeg-dev \
    zlib1g-dev \
    libomp-dev \
    mesa-common-dev
```

### 3.2 创建虚拟环境

```bash
# 创建虚拟环境
python3 -m venv ~/pytorch_env

# 激活环境
source ~/pytorch_env/bin/activate

# 升级 pip
pip install --upgrade pip wheel setuptools
```

### 3.3 安装 ROCm PyTorch

```bash
# 安装 ROCm 版本的 PyTorch
# 注意：根据 PyTorch 官网最新版本调整
pip install torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/rocm6.2

# 或者指定版本
# pip install torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 \
#     --index-url https://download.pytorch.org/whl/rocm6.2
```

### 3.4 设置环境变量

```bash
# 添加到 ~/.bashrc
cat >> ~/.bashrc << 'EOF'

# PyTorch ROCm 环境变量
export PATH=$PATH:/opt/rocm/bin
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/opt/rocm/lib
export HSA_OVERRIDE_GFX_VERSION=11.0.0  # RDNA3/3.5 架构
export PYTORCH_ROCM_ARCH=gfx1100
EOF

source ~/.bashrc
```

---

## 4. 方案 B：CPU 版本（保底方案）

如果 ROCm 版本遇到问题，使用 CPU 版本：

```bash
# 创建新的虚拟环境
python3 -m venv ~/pytorch_cpu_env
source ~/pytorch_cpu_env/bin/activate

# 安装 CPU 版本
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
```

---

## 5. 验证安装

### 5.1 基础验证脚本

创建验证脚本 `verify_pytorch.py`：

```python
#!/usr/bin/env python3
"""PyTorch 安装验证脚本"""

import sys
import platform

def check_basic():
    """基础信息检查"""
    print("=" * 50)
    print("PyTorch 基础信息检查")
    print("=" * 50)
    
    print(f"Python 版本: {platform.python_version()}")
    print(f"操作系统: {platform.system()} {platform.release()}")
    print()

def check_pytorch():
    """PyTorch 安装检查"""
    print("=" * 50)
    print("PyTorch 安装检查")
    print("=" * 50)
    
    try:
        import torch
        print(f"✅ PyTorch 已安装")
        print(f"   版本: {torch.__version__}")
        print(f"   编译器: {torch.__config__.show() if hasattr(torch.__config__, 'show') else 'N/A'}")
        
        # 检查 CUDA/ROCm 可用性
        if torch.cuda.is_available():
            print(f"✅ GPU 加速可用")
            print(f"   GPU 数量: {torch.cuda.device_count()}")
            for i in range(torch.cuda.device_count()):
                print(f"   GPU {i}: {torch.cuda.get_device_name(i)}")
                print(f"   显存: {torch.cuda.get_device_properties(i).total_memory / 1e9:.2f} GB")
        else:
            print(f"⚠️ GPU 加速不可用，将使用 CPU")
            print(f"   注意: CPU 推理速度较慢")
        
        print()
        return True
        
    except ImportError as e:
        print(f"❌ PyTorch 未安装: {e}")
        return False

def check_torchvision():
    """TorchVision 检查"""
    try:
        import torchvision
        print(f"✅ TorchVision 已安装: {torchvision.__version__}")
    except ImportError:
        print(f"⚠️ TorchVision 未安装")

def check_torchaudio():
    """TorchAudio 检查"""
    try:
        import torchaudio
        print(f"✅ TorchAudio 已安装: {torchaudio.__version__}")
    except ImportError:
        print(f"⚠️ TorchAudio 未安装")

def simple_tensor_test():
    """简单张量测试"""
    print("=" * 50)
    print("简单张量测试")
    print("=" * 50)
    
    import torch
    
    # 选择设备
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"使用设备: {device}")
    
    # 创建张量
    x = torch.randn(1000, 1000, device=device)
    y = torch.randn(1000, 1000, device=device)
    
    # 矩阵乘法测试
    import time
    
    # 预热
    for _ in range(3):
        z = torch.matmul(x, y)
    
    if device.type == "cuda":
        torch.cuda.synchronize()
    
    # 正式测试
    start = time.time()
    iterations = 10
    for _ in range(iterations):
        z = torch.matmul(x, y)
    
    if device.type == "cuda":
        torch.cuda.synchronize()
    
    elapsed = time.time() - start
    avg_time = elapsed / iterations
    
    print(f"矩阵乘法 (1000x1000): {avg_time*1000:.2f} ms/次")
    print(f"结果形状: {z.shape}")
    print()

def simple_nn_test():
    """简单神经网络测试"""
    print("=" * 50)
    print("简单神经网络测试")
    print("=" * 50)
    
    import torch
    import torch.nn as nn
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    # 定义简单网络
    class SimpleNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.fc1 = nn.Linear(784, 256)
            self.fc2 = nn.Linear(256, 128)
            self.fc3 = nn.Linear(128, 10)
            self.relu = nn.ReLU()
        
        def forward(self, x):
            x = self.relu(self.fc1(x))
            x = self.relu(self.fc2(x))
            x = self.fc3(x)
            return x
    
    model = SimpleNet().to(device)
    print(f"模型已加载到: {device}")
    print(f"模型参数数量: {sum(p.numel() for p in model.parameters()):,}")
    
    # 前向传播测试
    batch_size = 64
    input_data = torch.randn(batch_size, 784, device=device)
    
    import time
    # 预热
    for _ in range(5):
        output = model(input_data)
    
    if device.type == "cuda":
        torch.cuda.synchronize()
    
    # 测试
    start = time.time()
    iterations = 20
    for _ in range(iterations):
        output = model(input_data)
    
    if device.type == "cuda":
        torch.cuda.synchronize()
    
    elapsed = time.time() - start
    throughput = (batch_size * iterations) / elapsed
    
    print(f"批量大小: {batch_size}")
    print(f"平均延迟: {elapsed/iterations*1000:.2f} ms")
    print(f"吞吐量: {throughput:.0f} samples/sec")
    print()

def main():
    """主函数"""
    print("\n" + "=" * 50)
    print("PyTorch 安装验证报告")
    print("=" * 50 + "\n")
    
    check_basic()
    
    if not check_pytorch():
        print("\n❌ PyTorch 安装失败，请检查安装步骤")
        sys.exit(1)
    
    check_torchvision()
    check_torchaudio()
    print()
    
    simple_tensor_test()
    simple_nn_test()
    
    print("=" * 50)
    print("✅ 验证完成！")
    print("=" * 50)

if __name__ == "__main__":
    main()
```

运行验证：

```bash
# 激活环境后运行
source ~/pytorch_env/bin/activate
python verify_pytorch.py
```

---

## 6. 简单 LLM 推理示例

### 6.1 使用 Transformers 进行文本生成

```python
#!/usr/bin/env python3
"""使用 PyTorch + Transformers 进行 LLM 推理"""

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

def setup_model(model_name="Qwen/Qwen2.5-0.5B-Instruct"):
    """加载模型"""
    print(f"正在加载模型: {model_name}")
    
    # 确定设备
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"使用设备: {device}")
    
    # 加载 tokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    
    # 加载模型
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.float16 if device == "cuda" else torch.float32,
        device_map="auto" if device == "cuda" else None,
        trust_remote_code=True
    )
    
    if device == "cpu":
        model = model.to(device)
    
    return model, tokenizer, device

def generate_text(model, tokenizer, prompt, device, max_length=200):
    """生成文本"""
    # 编码输入
    inputs = tokenizer(prompt, return_tensors="pt").to(device)
    
    # 生成
    import time
    start = time.time()
    
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_length,
            temperature=0.7,
            top_p=0.9,
            do_sample=True
        )
    
    elapsed = time.time() - start
    
    # 解码输出
    generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
    
    # 计算 token 速度
    num_tokens = outputs.shape[1] - inputs.shape[1]
    tokens_per_sec = num_tokens / elapsed
    
    return generated_text, elapsed, tokens_per_sec

def main():
    # 使用小模型测试（0.5B 参数）
    model_name = "Qwen/Qwen2.5-0.5B-Instruct"
    
    model, tokenizer, device = setup_model(model_name)
    
    # 测试提示
    prompts = [
        "你好，请介绍一下自己。",
        "什么是人工智能？",
        "用 Python 写一个简单的 hello world 程序。"
    ]
    
    print("\n" + "=" * 50)
    print("开始推理测试")
    print("=" * 50 + "\n")
    
    for i, prompt in enumerate(prompts, 1):
        print(f"\n--- 测试 {i} ---")
        print(f"提示: {prompt}")
        print("生成中...")
        
        output, elapsed, tps = generate_text(model, tokenizer, prompt, device)
        
        # 提取生成的部分（去掉提示）
        generated = output[len(prompt):].strip()
        
        print(f"生成结果: {generated[:200]}...")
        print(f"耗时: {elapsed:.2f}s")
        print(f"速度: {tps:.2f} tokens/sec")
    
    print("\n" + "=" * 50)
    print("测试完成！")
    print("=" * 50)

if __name__ == "__main__":
    main()
```

安装依赖并运行：

```bash
pip install transformers accelerate
python llm_inference.py
```

---

## 7. 故障排查

### 7.1 常见问题

#### Q1: `RuntimeError: CUDA error: invalid device ordinal`

```bash
# 解决：检查环境变量
export HIP_VISIBLE_DEVICES=0
export CUDA_VISIBLE_DEVICES=0
```

#### Q2: `hipErrorNoBinaryForGpu: Could not find kernel`

```bash
# 解决：设置 GPU 架构版本
export HSA_OVERRIDE_GFX_VERSION=11.0.0
export PYTORCH_ROCM_ARCH=gfx1100
```

#### Q3: 安装后 import torch 报错

```bash
# 解决：检查依赖
pip install --upgrade numpy
pip install --force-reinstall torch
```

#### Q4: GPU 内存不足

```python
# 代码中设置内存限制
import torch
torch.cuda.set_per_process_memory_fraction(0.8)  # 使用 80% 显存
```

### 7.2 性能优化建议

```python
# 1. 使用混合精度训练
from torch.cuda.amp import autocast, GradScaler

scaler = GradScaler()
with autocast():
    output = model(input)
    loss = criterion(output, target)

# 2. 使用 DataLoader 多进程
from torch.utils.data import DataLoader
dataloader = DataLoader(dataset, batch_size=32, num_workers=4, pin_memory=True)

# 3. 模型编译（PyTorch 2.0+）
model = torch.compile(model)  # 加速推理
```

---

## 📋 快速命令清单

```bash
# 1. 创建环境
python3 -m venv ~/pytorch_env
source ~/pytorch_env/bin/activate

# 2. 安装 PyTorch (ROCm)
pip install torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/rocm6.2

# 3. 安装 PyTorch (CPU)
pip install torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/cpu

# 4. 验证安装
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available())"

# 5. 运行验证脚本
python verify_pytorch.py
```

---

*最后更新: 2026-03-28*
