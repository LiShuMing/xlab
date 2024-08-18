#!/usr/bin/env python3
"""
简单的 LLM 推理演示（纯 PyTorch 实现）
不依赖 transformers 库，使用 PyTorch 原生功能
"""

import torch
import torch.nn as nn
import time

class SimpleTransformerBlock(nn.Module):
    """简化的 Transformer Block"""
    def __init__(self, d_model=512, nhead=8, dim_feedforward=2048, dropout=0.1):
        super().__init__()
        self.self_attn = nn.MultiheadAttention(d_model, nhead, dropout=dropout, batch_first=True)
        self.linear1 = nn.Linear(d_model, dim_feedforward)
        self.linear2 = nn.Linear(dim_feedforward, d_model)
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)
        self.activation = nn.GELU()
    
    def forward(self, src, src_mask=None):
        # 自注意力
        src2 = self.self_attn(src, src, src, attn_mask=src_mask)[0]
        src = src + self.dropout(src2)
        src = self.norm1(src)
        
        # 前馈网络
        src2 = self.linear2(self.dropout(self.activation(self.linear1(src))))
        src = src + self.dropout(src2)
        src = self.norm2(src)
        
        return src

class SimpleLLM(nn.Module):
    """简化版大语言模型"""
    def __init__(self, vocab_size=5000, d_model=512, nhead=8, num_layers=6, max_seq_len=512):
        super().__init__()
        self.d_model = d_model
        self.max_seq_len = max_seq_len
        
        # 词嵌入
        self.embedding = nn.Embedding(vocab_size, d_model)
        self.pos_embedding = nn.Embedding(max_seq_len, d_model)
        
        # Transformer 层
        self.layers = nn.ModuleList([
            SimpleTransformerBlock(d_model, nhead)
            for _ in range(num_layers)
        ])
        
        # 输出层
        self.norm = nn.LayerNorm(d_model)
        self.fc_out = nn.Linear(d_model, vocab_size)
        
        self.dropout = nn.Dropout(0.1)
        
        # 初始化参数
        self._init_parameters()
    
    def _init_parameters(self):
        for p in self.parameters():
            if p.dim() > 1:
                nn.init.xavier_uniform_(p)
    
    def forward(self, x):
        batch_size, seq_len = x.shape
        
        # 位置编码
        positions = torch.arange(0, seq_len, device=x.device).unsqueeze(0).expand(batch_size, -1)
        
        # 嵌入 + 位置编码
        x = self.dropout(self.embedding(x) + self.pos_embedding(positions))
        
        # Transformer 层
        for layer in self.layers:
            x = layer(x)
        
        # 输出
        x = self.norm(x)
        logits = self.fc_out(x)
        
        return logits
    
    @torch.no_grad()
    def generate(self, input_ids, max_new_tokens=50, temperature=1.0, top_k=50):
        """生成文本"""
        self.eval()
        generated = input_ids.clone()
        
        for _ in range(max_new_tokens):
            # 截断到最大长度
            if generated.size(1) > self.max_seq_len:
                generated = generated[:, -self.max_seq_len:]
            
            # 前向传播
            logits = self(generated)
            logits = logits[:, -1, :] / temperature
            
            # Top-k 采样
            if top_k > 0:
                indices_to_remove = logits < torch.topk(logits, top_k)[0][..., -1, None]
                logits[indices_to_remove] = float('-inf')
            
            # Softmax 采样
            probs = torch.softmax(logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)
            
            generated = torch.cat([generated, next_token], dim=1)
        
        return generated

def demo_training():
    """演示训练过程"""
    print("=" * 60)
    print("LLM 训练演示")
    print("=" * 60)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"使用设备: {device}\n")
    
    # 创建模型
    vocab_size = 1000
    model = SimpleLLM(vocab_size=vocab_size, d_model=256, nhead=8, num_layers=4).to(device)
    
    total_params = sum(p.numel() for p in model.parameters())
    print(f"模型参数量: {total_params:,} ({total_params/1e6:.2f}M)")
    print(f"模型大小: {total_params * 4 / 1024 / 1024:.2f} MB (float32)\n")
    
    # 模拟数据
    batch_size = 8
    seq_len = 128
    
    # 创建优化器和损失函数
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4, weight_decay=0.01)
    criterion = nn.CrossEntropyLoss()
    
    print("模拟训练 10 个 step:")
    model.train()
    
    for step in range(10):
        # 生成随机输入
        input_ids = torch.randint(0, vocab_size, (batch_size, seq_len), device=device)
        labels = torch.randint(0, vocab_size, (batch_size, seq_len), device=device)
        
        # 前向传播
        start = time.time()
        logits = model(input_ids)
        
        # 计算损失
        loss = criterion(logits.view(-1, vocab_size), labels.view(-1))
        
        # 反向传播
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        
        elapsed = time.time() - start
        
        if step % 3 == 0:
            print(f"  Step {step}: Loss = {loss.item():.4f}, Time = {elapsed*1000:.1f}ms")
    
    print("✅ 训练演示完成\n")

def demo_inference():
    """演示推理过程"""
    print("=" * 60)
    print("LLM 推理演示")
    print("=" * 60)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"使用设备: {device}\n")
    
    # 创建较小的模型用于快速推理演示
    vocab_size = 500
    model = SimpleLLM(vocab_size=vocab_size, d_model=128, nhead=4, num_layers=2, max_seq_len=128).to(device)
    model.eval()
    
    print(f"模型参数量: {sum(p.numel() for p in model.parameters()):,}\n")
    
    # 模拟输入
    prompt_length = 10
    input_ids = torch.randint(0, vocab_size, (1, prompt_length), device=device)
    
    print(f"输入 token 长度: {prompt_length}")
    print("开始生成...")
    
    # 生成
    start = time.time()
    with torch.no_grad():
        output = model.generate(
            input_ids,
            max_new_tokens=30,
            temperature=0.8,
            top_k=40
        )
    elapsed = time.time() - start
    
    generated_length = output.size(1) - prompt_length
    tokens_per_sec = generated_length / elapsed
    
    print(f"生成 token 数: {generated_length}")
    print(f"耗时: {elapsed:.2f}s")
    print(f"速度: {tokens_per_sec:.2f} tokens/sec")
    print(f"输出形状: {output.shape}")
    print(f"\n✅ 推理演示完成\n")

def benchmark_matrix_sizes():
    """不同矩阵大小的性能测试"""
    print("=" * 60)
    print("矩阵乘法性能基准测试")
    print("=" * 60)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"使用设备: {device}\n")
    
    sizes = [512, 1024, 2048, 4096]
    
    print(f"{'Size':>10} {'Time (ms)':>12} {'GFLOPS':>12}")
    print("-" * 40)
    
    for size in sizes:
        a = torch.randn(size, size, device=device)
        b = torch.randn(size, size, device=device)
        
        # 预热
        for _ in range(3):
            c = torch.matmul(a, b)
        
        if device.type == "cuda":
            torch.cuda.synchronize()
        
        # 测试
        iterations = 10 if size >= 2048 else 20
        start = time.time()
        for _ in range(iterations):
            c = torch.matmul(a, b)
            if device.type == "cuda":
                torch.cuda.synchronize()
        
        elapsed = time.time() - start / iterations
        avg_time_ms = elapsed * 1000 / iterations
        
        # 计算 GFLOPS: 2 * N^3 / time / 1e9
        flops = 2 * size ** 3
        gflops = flops / (avg_time_ms / 1000) / 1e9
        
        print(f"{size:>10} {avg_time_ms:>12.2f} {gflops:>12.1f}")
    
    print()

def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("PyTorch LLM 演示程序")
    print("=" * 60)
    print(f"\nPyTorch 版本: {torch.__version__}")
    print(f"CUDA 可用: {torch.cuda.is_available()}")
    print()
    
    try:
        # 运行基准测试
        benchmark_matrix_sizes()
        
        # 运行训练演示
        demo_training()
        
        # 运行推理演示
        demo_inference()
        
        print("=" * 60)
        print("✅ 所有演示完成！")
        print("=" * 60)
        print("\n说明:")
        print("- 这是一个简化的 LLM 实现，用于演示 PyTorch 功能")
        print("- 真实 LLM 需要使用 transformers 库加载预训练模型")
        print("- 当前在 CPU 上运行，GPU 加速可提升 5-50 倍性能")
        
    except Exception as e:
        print(f"\n❌ 运行出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
