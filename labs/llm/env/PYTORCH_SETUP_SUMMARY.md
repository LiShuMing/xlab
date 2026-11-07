# PyTorch 配置总结与替代方案

## 📊 当前状态

### ✅ 已完成：CPU 版本 PyTorch

```bash
source ~/pytorch_env/bin/activate
python -c "import torch; print(torch.__version__)"
# 输出: 2.11.0+cpu
```

**已验证功能：**
- ✅ PyTorch 基础张量运算
- ✅ 神经网络模块 (nn.Module)
- ✅ 自动微分 (autograd)
- ✅ 模型训练/推理流程

**性能测试结果：**
- 矩阵乘法 (1000x1000): ~10ms
- 神经网络前向传播: ~0.6ms/batch

---

## ⚠️ ROCm GPU 版本安装问题

### 遇到的困难

| 问题 | 原因 |
|------|------|
| 下载超时 | PyTorch ROCm 包约 4GB，网络下载缓慢 |
| 依赖缺失 | 需要 `pytorch-triton-rocm` 等特定版本依赖 |
| 硬件兼容性 | Radeon 890M 核显的 ROCm 支持有限 |

### 已下载文件

```
/tmp/pytorch_download/torch-2.5.1+rocm6.2-cp312-cp312-linux_x86_64.whl (3.8GB)
```

**如需继续安装**，可在网络条件好时手动执行：

```bash
source ~/pytorch_env/bin/activate

# 1. 安装 triton（先下载）
wget https://download.pytorch.org/whl/rocm6.2/pytorch_triton_rocm-3.1.0-cp312-cp312-linux_x86_64.whl
pip install pytorch_triton_rocm-3.1.0-cp312-cp312-linux_x86_64.whl

# 2. 安装 torch
pip install /tmp/pytorch_download/torch-2.5.1+rocm6.2-cp312-cp312-linux_x86_64.whl --no-deps

# 3. 安装其他依赖
pip install filelock typing-extensions networkx jinja2 fsspec sympy
```

---

## 🚀 推荐的替代方案

### 方案 1：使用 llama.cpp（GPU 加速 LLM 推理）

**优势：**
- 对 AMD GPU 支持更好
- 不需要完整的 ROCm PyTorch
- 专门针对 LLM 推理优化

**安装步骤：**

```bash
# 1. 安装依赖
sudo apt update
sudo apt install -y build-essential git cmake

# 2. 克隆仓库
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp

# 3. 使用 HIP 编译（AMD GPU）
make -j$(nproc) GGML_HIPBLAS=1 AMDGPU_TARGETS=gfx1100

# 4. 验证
./llama-cli --list-devices
```

**使用示例：**

```bash
# 下载模型（以 Qwen2.5-0.5B 为例）
wget https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf

# GPU 推理
./llama-cli \
    -m qwen2.5-0.5b-instruct-q4_k_m.gguf \
    -p "你好，请介绍一下自己" \
    -ngl 999  \
    -n 256
```

### 方案 2：使用 Ollama（最简单的 LLM 方案）

```bash
# 安装 Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 设置 AMD GPU 环境变量
export HSA_OVERRIDE_GFX_VERSION=11.0.0

# 运行服务
ollama serve &

# 拉取并运行模型
ollama pull qwen2.5:0.5b
ollama run qwen2.5:0.5b
```

### 方案 3：使用 Docker ROCm 镜像

```bash
# 拉取 ROCm PyTorch Docker 镜像
docker pull rocm/pytorch:rocm6.2_ubuntu22.04_py3.10_pytorch2.5.1

# 运行容器
docker run -it --rm \
    --device=/dev/kfd \
    --device=/dev/dri \
    --group-add video \
    --group-add render \
    -v $(pwd):/workspace \
    rocm/pytorch:rocm6.2_ubuntu22.04_py3.10_pytorch2.5.1

# 在容器内验证
python -c "import torch; print(torch.cuda.is_available())"
```

### 方案 4：云端 GPU（开发/训练）

| 平台 | 特点 | 适用场景 |
|------|------|----------|
| **Google Colab** | 免费 T4 GPU | 学习、测试 |
| **AutoDL** | 国内，按时计费 | 训练模型 |
| **Lambda Cloud** | 专业 GPU 云 | 大规模训练 |

---

## 📝 后续建议

### 短期（现在可以做的）

1. **使用 CPU PyTorch 学习开发**
   ```bash
   source ~/pytorch_env/bin/activate
   python verify_pytorch.py
   python simple_llm_demo.py
   ```

2. **安装 llama.cpp 进行 GPU 推理**
   - 参考上方安装步骤
   - 适合运行 GGUF 格式的模型

3. **尝试 Docker ROCm 方案**
   - 无需本地配置
   - 开箱即用

### 中期（网络条件好时）

1. **完成 ROCm PyTorch 本地安装**
   - 使用已下载的 3.8GB whl 文件
   - 手动安装缺失依赖

2. **安装 ROCm 驱动**
   ```bash
   sudo apt install amdgpu-dkms rocm-dev
   ```

### 长期（如需更高性能）

1. **考虑外接 NVIDIA eGPU**
   - 如果你的笔记本支持 Thunderbolt/USB4
   - 可获得完整 CUDA 支持

2. **使用云端 GPU 进行训练**
   - 本地开发 + 云端训练
   - 性价比更高

---

## 📚 相关文件

| 文件 | 说明 |
|------|------|
| `~/pytorch_env/` | PyTorch CPU 虚拟环境 |
| `verify_pytorch.py` | PyTorch 验证脚本 |
| `simple_llm_demo.py` | LLM 演示代码 |
| `WSL2_GPU_SETUP.md` | GPU 配置完整教程 |
| `ROCm_vs_CUDA.md` | ROCm/CUDA 对比 |

---

## 🔧 快速命令参考

```bash
# 激活环境
source ~/pytorch_env/bin/activate

# 验证 PyTorch
python -c "import torch; print(torch.__version__)"

# 运行验证
python verify_pytorch.py

# 运行 LLM 演示
python simple_llm_demo.py

# 退出环境
deactivate
```

---

## 💡 总结

| 需求 | 推荐方案 |
|------|----------|
| 学习 PyTorch | ✅ 已安装的 CPU 版本 |
| LLM 推理（GPU 加速） | llama.cpp / Ollama |
| 模型训练 | 云端 GPU (Colab/AutoDL) |
| 生产部署 | Docker ROCm 镜像 |

**当前 CPU PyTorch 已完全可以用于：**
- 学习和理解深度学习原理
- 开发和测试模型代码
- 小规模数据实验
- 模型结构设计和调试

GPU 加速主要用于大规模训练和推理，对于学习和开发阶段，CPU 版本已经足够。

---

*最后更新: 2026-03-28*
