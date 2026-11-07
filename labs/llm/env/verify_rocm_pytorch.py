#!/usr/bin/env python3
"""
PyTorch ROCm 完整验证脚本
验证 GPU 是否可用、性能测试、简单神经网络测试
"""

import torch
import torch.nn as nn
import time
import sys

def print_header(title):
    """打印标题"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def check_basic_info():
    """检查基础信息"""
    print_header("基础信息")
    
    print(f"Python 版本: {sys.version.split()[0]}")
    print(f"PyTorch 版本: {torch.__version__}")
    print(f"PyTorch 路径: {torch.__file__}")
    
    # 检查是否为 ROCm 版本
    if 'rocm' in torch.__version__.lower():
        print("✅ 检测到 ROCm 版本 PyTorch")
    elif 'cpu' in torch.__version__.lower():
        print("⚠️ 检测到 CPU 版本 PyTorch")
    else:
        print(f"ℹ️ PyTorch 版本: {torch.__version__}")
    
    print()

def check_gpu_available():
    """检查 GPU 可用性"""
    print_header("GPU 可用性检查")
    
    cuda_available = torch.cuda.is_available()
    print(f"torch.cuda.is_available(): {cuda_available}")
    
    if cuda_available:
        print("\n✅ GPU 加速可用！")
        
        device_count = torch.cuda.device_count()
        print(f"\n检测到 {device_count} 个 GPU 设备:")
        
        for i in range(device_count):
            props = torch.cuda.get_device_properties(i)
            print(f"\n  GPU {i}: {torch.cuda.get_device_name(i)}")
            print(f"    总显存: {props.total_memory / 1024**3:.2f} GB")
            print(f"    计算能力: {props.major}.{props.minor}")
            print(f"    多处理器数量: {props.multi_processor_count}")
            
            # 显存使用情况
            allocated = torch.cuda.memory_allocated(i) / 1024**3
            reserved = torch.cuda.memory_reserved(i) / 1024**3
            print(f"    已分配显存: {allocated:.2f} GB")
            print(f"    预留显存: {reserved:.2f} GB")
        
        return True
    else:
        print("\n❌ GPU 不可用")
        print("   将使用 CPU 模式运行")
        print("\n可能原因:")
        print("  1. ROCm 驱动未正确安装")
        print("  2. 缺少环境变量 (HSA_OVERRIDE_GFX_VERSION)")
        print("  3. 当前 PyTorch 版本与 GPU 不兼容")
        print("  4. WSL2 GPU 支持配置问题")
        return False

def tensor_operations_test(device):
    """张量运算测试"""
    print_header(f"张量运算测试 ({device.type.upper()})")
    
    # 创建张量
    print("1. 创建张量:")
    x = torch.randn(3, 3, device=device)
    print(f"   随机张量 (3x3):\n{x}")
    
    # 基本运算
    print("\n2. 基本运算:")
    y = torch.ones(3, 3, device=device)
    z = x + y
    print(f"   x + 1 = \n{z}")
    
    print(f"\n3. 矩阵乘法测试:")
    
    # 不同大小的矩阵测试
    sizes = [512, 1024, 2048]
    
    for size in sizes:
        a = torch.randn(size, size, device=device)
        b = torch.randn(size, size, device=device)
        
        # 预热
        for _ in range(3):
            c = torch.matmul(a, b)
        
        if device.type == "cuda":
            torch.cuda.synchronize()
        
        # 正式测试
        iterations = 10 if size >= 2048 else 20
        start = time.time()
        for _ in range(iterations):
            c = torch.matmul(a, b)
            if device.type == "cuda":
                torch.cuda.synchronize()
        
        elapsed = time.time() - start
        avg_time = elapsed / iterations * 1000
        
        # 计算 GFLOPS: 2 * N^3 / time / 1e9
        flops = 2 * size ** 3
        gflops = flops / (avg_time / 1000) / 1e9
        
        print(f"   {size}x{size}: {avg_time:.2f} ms ({gflops:.1f} GFLOPS)")

def neural_network_test(device):
    """神经网络测试"""
    print_header(f"神经网络测试 ({device.type.upper()})")
    
    # 定义简单网络
    class SimpleNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.fc1 = nn.Linear(784, 256)
            self.fc2 = nn.Linear(256, 128)
            self.fc3 = nn.Linear(128, 10)
            self.relu = nn.ReLU()
            self.dropout = nn.Dropout(0.2)
        
        def forward(self, x):
            x = self.relu(self.fc1(x))
            x = self.dropout(x)
            x = self.relu(self.fc2(x))
            x = self.fc3(x)
            return x
    
    model = SimpleNet().to(device)
    
    # 计算参数量
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    
    print(f"模型: SimpleNet (3层全连接)")
    print(f"总参数量: {total_params:,} ({total_params/1e6:.2f}M)")
    print(f"设备: {device}")
    
    # 训练模式测试
    print("\n1. 训练模式 (Forward + Backward):")
    model.train()
    
    batch_size = 64
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.SGD(model.parameters(), lr=0.01)
    
    # 模拟数据
    input_data = torch.randn(batch_size, 784, device=device)
    labels = torch.randint(0, 10, (batch_size,), device=device)
    
    # 预热
    for _ in range(3):
        optimizer.zero_grad()
        output = model(input_data)
        loss = criterion(output, labels)
        loss.backward()
        optimizer.step()
    
    if device.type == "cuda":
        torch.cuda.synchronize()
    
    # 测试
    iterations = 10
    start = time.time()
    for _ in range(iterations):
        optimizer.zero_grad()
        output = model(input_data)
        loss = criterion(output, labels)
        loss.backward()
        optimizer.step()
        if device.type == "cuda":
            torch.cuda.synchronize()
    
    elapsed = time.time() - start
    avg_time = elapsed / iterations * 1000
    throughput = (batch_size * iterations) / elapsed
    
    print(f"   批量大小: {batch_size}")
    print(f"   平均时间: {avg_time:.2f} ms/iter")
    print(f"   吞吐量: {throughput:.0f} samples/sec")
    
    # 推理模式测试
    print("\n2. 推理模式 (Forward only):")
    model.eval()
    
    with torch.no_grad():
        # 预热
        for _ in range(5):
            output = model(input_data)
        
        if device.type == "cuda":
            torch.cuda.synchronize()
        
        # 测试
        iterations = 20
        start = time.time()
        for _ in range(iterations):
            output = model(input_data)
            if device.type == "cuda":
                torch.cuda.synchronize()
        
        elapsed = time.time() - start
        avg_time = elapsed / iterations * 1000
        throughput = (batch_size * iterations) / elapsed
        
        print(f"   平均时间: {avg_time:.2f} ms/iter")
        print(f"   吞吐量: {throughput:.0f} samples/sec")

def compare_cpu_gpu():
    """对比 CPU 和 GPU 性能"""
    print_header("CPU vs GPU 性能对比")
    
    if not torch.cuda.is_available():
        print("GPU 不可用，跳过对比测试")
        return
    
    cpu_device = torch.device("cpu")
    gpu_device = torch.device("cuda")
    
    # 矩阵乘法对比
    print("矩阵乘法 (2048x2048) 对比:\n")
    
    size = 2048
    
    # CPU 测试
    print("CPU:")
    a_cpu = torch.randn(size, size, device=cpu_device)
    b_cpu = torch.randn(size, size, device=cpu_device)
    
    # 预热
    for _ in range(3):
        c_cpu = torch.matmul(a_cpu, b_cpu)
    
    start = time.time()
    iterations = 5
    for _ in range(iterations):
        c_cpu = torch.matmul(a_cpu, b_cpu)
    cpu_time = (time.time() - start) / iterations * 1000
    print(f"   平均时间: {cpu_time:.2f} ms")
    
    # GPU 测试
    print("\nGPU:")
    a_gpu = a_cpu.to(gpu_device)
    b_gpu = b_cpu.to(gpu_device)
    
    # 预热
    for _ in range(10):
        c_gpu = torch.matmul(a_gpu, b_gpu)
    torch.cuda.synchronize()
    
    start = time.time()
    iterations = 20
    for _ in range(iterations):
        c_gpu = torch.matmul(a_gpu, b_gpu)
        torch.cuda.synchronize()
    gpu_time = (time.time() - start) / iterations * 1000
    print(f"   平均时间: {gpu_time:.2f} ms")
    
    # 加速比
    speedup = cpu_time / gpu_time
    print(f"\n🚀 GPU 加速比: {speedup:.1f}x")

def memory_test():
    """显存测试"""
    if not torch.cuda.is_available():
        return
    
    print_header("显存测试")
    
    # 清空缓存
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    
    initial_memory = torch.cuda.memory_allocated() / 1024**3
    print(f"初始显存使用: {initial_memory:.2f} GB")
    
    # 创建大张量
    sizes = [1000, 2000, 4000, 8000]
    
    for size in sizes:
        try:
            x = torch.randn(size, size, device="cuda")
            memory = torch.cuda.memory_allocated() / 1024**3
            print(f"创建 {size}x{size} 张量: 显存使用 {memory:.2f} GB")
            del x
            torch.cuda.empty_cache()
        except RuntimeError as e:
            print(f"创建 {size}x{size} 张量失败: {e}")
            break
    
    peak_memory = torch.cuda.max_memory_allocated() / 1024**3
    print(f"\n峰值显存使用: {peak_memory:.2f} GB")

def simple_training_demo():
    """简单训练演示"""
    print_header("简单训练演示")
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"使用设备: {device}\n")
    
    # 生成模拟数据: y = 2x + 1 + 噪声
    torch.manual_seed(42)
    X = torch.randn(1000, 1, device=device)
    y = 2 * X + 1 + 0.1 * torch.randn(1000, 1, device=device)
    
    # 定义模型
    model = nn.Linear(1, 1).to(device)
    criterion = nn.MSELoss()
    optimizer = torch.optim.SGD(model.parameters(), lr=0.01)
    
    print("训练线性回归模型: y = 2x + 1")
    print(f"初始参数: w={model.weight.item():.4f}, b={model.bias.item():.4f}")
    
    # 训练
    start = time.time()
    epochs = 1000
    
    for epoch in range(epochs):
        # 前向传播
        predictions = model(X)
        loss = criterion(predictions, y)
        
        # 反向传播
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        
        if (epoch + 1) % 200 == 0:
            print(f"Epoch [{epoch+1}/{epochs}], Loss: {loss.item():.4f}")
    
    elapsed = time.time() - start
    
    print(f"\n训练完成! 耗时: {elapsed:.2f}s")
    print(f"最终参数: w={model.weight.item():.4f}, b={model.bias.item():.4f}")
    print(f"目标参数: w=2.0000, b=1.0000")

def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("  PyTorch ROCm 完整验证")
    print("=" * 60)
    
    try:
        # 1. 基础信息
        check_basic_info()
        
        # 2. GPU 可用性
        gpu_available = check_gpu_available()
        
        # 3. 选择设备
        device = torch.device("cuda" if gpu_available else "cpu")
        
        # 4. 张量运算测试
        tensor_operations_test(device)
        
        # 5. 神经网络测试
        neural_network_test(device)
        
        # 6. CPU vs GPU 对比
        if gpu_available:
            compare_cpu_gpu()
        
        # 7. 显存测试
        if gpu_available:
            memory_test()
        
        # 8. 简单训练演示
        simple_training_demo()
        
        # 总结
        print_header("验证完成")
        if gpu_available:
            print("✅ PyTorch ROCm GPU 版本工作正常！")
        else:
            print("⚠️ PyTorch 运行正常，但 GPU 未启用")
            print("   可以使用 CPU 模式进行开发和测试")
        
    except Exception as e:
        print(f"\n❌ 验证过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
