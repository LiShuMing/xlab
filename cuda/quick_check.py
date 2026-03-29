#!/usr/bin/env python3
"""快速检查 PyTorch ROCm 安装"""

import torch

print("=" * 50)
print("PyTorch ROCm 快速检查")
print("=" * 50)

print(f"\nPyTorch 版本: {torch.__version__}")
print(f"ROCm 可用: {torch.cuda.is_available()}")

if torch.cuda.is_available():
    print(f"\nGPU 数量: {torch.cuda.device_count()}")
    for i in range(torch.cuda.device_count()):
        print(f"GPU {i}: {torch.cuda.get_device_name(i)}")
        props = torch.cuda.get_device_properties(i)
        print(f"  显存: {props.total_memory / 1e9:.2f} GB")
    
    # 简单测试
    print("\n运行简单测试...")
    x = torch.randn(1000, 1000, device="cuda")
    y = torch.randn(1000, 1000, device="cuda")
    z = torch.matmul(x, y)
    print(f"矩阵乘法结果: {z.shape}")
    print("\n✅ GPU 加速正常工作！")
else:
    print("\n⚠️ GPU 不可用，使用 CPU 模式")

print("=" * 50)
