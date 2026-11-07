#!/usr/bin/env python3
"""PyTorch 安装验证脚本"""

import sys
import platform
import time

def check_basic():
    """基础信息检查"""
    print("=" * 60)
    print("PyTorch 基础信息检查")
    print("=" * 60)
    
    print(f"Python 版本: {platform.python_version()}")
    print(f"操作系统: {platform.system()} {platform.release()}")
    print(f"处理器: {platform.processor()}")
    print()

def check_pytorch():
    """PyTorch 安装检查"""
    print("=" * 60)
    print("PyTorch 安装检查")
    print("=" * 60)
    
    try:
        import torch
        print(f"✅ PyTorch 已安装")
        print(f"   版本: {torch.__version__}")
        
        # 检查 CUDA/ROCm 可用性
        if torch.cuda.is_available():
            print(f"✅ GPU 加速可用")
            print(f"   GPU 数量: {torch.cuda.device_count()}")
            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                print(f"   GPU {i}: {torch.cuda.get_device_name(i)}")
                print(f"   显存: {props.total_memory / 1e9:.2f} GB")
                print(f"   计算能力: {props.major}.{props.minor}")
        else:
            print(f"⚠️ GPU 加速不可用，将使用 CPU")
            print(f"   注意: CPU 推理速度较慢，适合学习和测试")
        
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
    print("=" * 60)
    print("张量计算测试")
    print("=" * 60)
    
    import torch
    
    # 选择设备
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"使用设备: {device}")
    
    # 创建张量
    print("\n1. 创建张量:")
    x = torch.randn(3, 3, device=device)
    print(f"   随机张量 (3x3):\n{x}")
    
    # 基本运算
    print("\n2. 基本运算:")
    y = torch.ones(3, 3, device=device)
    z = x + y
    print(f"   x + 1 = \n{z}")
    
    # 矩阵乘法测试
    print("\n3. 矩阵乘法性能测试 (1000x1000):")
    size = 1000
    a = torch.randn(size, size, device=device)
    b = torch.randn(size, size, device=device)
    
    # 预热
    for _ in range(3):
        c = torch.matmul(a, b)
    
    if device.type == "cuda":
        torch.cuda.synchronize()
    
    # 正式测试
    iterations = 10
    start = time.time()
    for _ in range(iterations):
        c = torch.matmul(a, b)
        if device.type == "cuda":
            torch.cuda.synchronize()
    
    elapsed = time.time() - start
    avg_time = elapsed / iterations
    
    print(f"   平均耗时: {avg_time*1000:.2f} ms/次")
    print(f"   结果形状: {c.shape}")
    print()

def simple_nn_test():
    """简单神经网络测试"""
    print("=" * 60)
    print("神经网络测试")
    print("=" * 60)
    
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
    
    # 计算参数量
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"总参数量: {total_params:,}")
    print(f"可训练参数量: {trainable_params:,}")
    
    # 前向传播测试
    print("\n前向传播性能测试:")
    batch_size = 64
    input_data = torch.randn(batch_size, 784, device=device)
    
    # 预热
    model.eval()
    with torch.no_grad():
        for _ in range(5):
            output = model(input_data)
    
    if device.type == "cuda":
        torch.cuda.synchronize()
    
    # 测试
    iterations = 20
    start = time.time()
    with torch.no_grad():
        for _ in range(iterations):
            output = model(input_data)
            if device.type == "cuda":
                torch.cuda.synchronize()
    
    elapsed = time.time() - start
    avg_latency = elapsed / iterations * 1000
    throughput = (batch_size * iterations) / elapsed
    
    print(f"   批量大小: {batch_size}")
    print(f"   平均延迟: {avg_latency:.2f} ms")
    print(f"   吞吐量: {throughput:.0f} samples/sec")
    print(f"   输出形状: {output.shape}")
    print()

def autograd_test():
    """自动微分测试"""
    print("=" * 60)
    print("自动微分测试")
    print("=" * 60)
    
    import torch
    
    # 创建需要梯度的张量
    x = torch.tensor([2.0, 3.0], requires_grad=True)
    
    # 定义计算图
    y = x ** 2
    z = y.sum()
    
    print(f"输入 x: {x.data}")
    print(f"y = x^2: {y.data}")
    print(f"z = sum(y): {z.data}")
    
    # 反向传播
    z.backward()
    
    print(f"dz/dx (梯度): {x.grad}")
    print(f"期望梯度: [4.0, 6.0] (因为 d(x^2)/dx = 2x)")
    print()

def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("PyTorch 安装验证报告")
    print("=" * 60 + "\n")
    
    check_basic()
    
    if not check_pytorch():
        print("\n❌ PyTorch 安装失败，请检查安装步骤")
        sys.exit(1)
    
    check_torchvision()
    check_torchaudio()
    print()
    
    simple_tensor_test()
    simple_nn_test()
    autograd_test()
    
    print("=" * 60)
    print("✅ 验证完成！PyTorch 工作正常")
    print("=" * 60)
    print("\n提示: 当前使用 CPU 模式，适合学习和小规模测试。")
    print("如需 GPU 加速，请参考 WSL2_GPU_SETUP.md 配置 ROCm。")

if __name__ == "__main__":
    main()
