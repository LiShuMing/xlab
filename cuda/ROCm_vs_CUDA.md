# ROCm vs CUDA GPU 开发对比

> 深入对比 AMD ROCm 和 NVIDIA CUDA 两大 GPU 计算平台的开发差异

---

## 📊 快速对比概览

| 特性 | NVIDIA CUDA | AMD ROCm |
|------|-------------|----------|
| **所属公司** | NVIDIA | AMD |
| **推出时间** | 2007 年 | 2016 年 |
| **生态系统成熟度** | ⭐⭐⭐⭐⭐ 非常成熟 | ⭐⭐⭐☆☆ 快速发展中 |
| **市场占有率** | ~90% (数据中心/AI) | ~10% (快速增长) |
| **开源程度** | 闭源（部分开源） | 完全开源 |
| **硬件支持** | 仅限 NVIDIA GPU | AMD GPU + 部分 NVIDIA (通过 HIP) |
| **跨平台支持** | NVIDIA only | AMD + 移植到 CUDA |

---

## 1. 架构与编程模型

### 1.1 CUDA 架构

```cpp
// CUDA 核函数示例
__global__ void vectorAdd(float* a, float* b, float* c, int n) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i < n) {
        c[i] = a[i] + b[i];
    }
}

// 主机代码
int main() {
    float *d_a, *d_b, *d_c;
    cudaMalloc(&d_a, size);
    cudaMemcpy(d_a, h_a, size, cudaMemcpyHostToDevice);
    
    vectorAdd<<<numBlocks, threadsPerBlock>>>(d_a, d_b, d_c, n);
    
    cudaMemcpy(h_c, d_c, size, cudaMemcpyDeviceToHost);
    cudaFree(d_a);
}
```

**特点：**
- 专有语言扩展（`__global__`, `__device__`, `<<< >>>`）
- 紧密集成到 C/C++
- 编译器：`nvcc`

### 1.2 ROCm/HIP 架构

```cpp
// HIP 核函数示例（与 CUDA 几乎相同）
__global__ void vectorAdd(float* a, float* b, float* c, int n) {
    int i = hipBlockIdx_x * hipBlockDim_x + hipThreadIdx_x;
    if (i < n) {
        c[i] = a[i] + b[i];
    }
}

// 主机代码
int main() {
    float *d_a, *d_b, *d_c;
    hipMalloc(&d_a, size);
    hipMemcpy(d_a, h_a, size, hipMemcpyHostToDevice);
    
    hipLaunchKernelGGL(vectorAdd, numBlocks, threadsPerBlock, 0, 0, 
                       d_a, d_b, d_c, n);
    
    hipMemcpy(h_c, d_c, size, hipMemcpyDeviceToHost);
    hipFree(d_a);
}
```

**特点：**
- HIP（Heterogeneous-compute Interface for Portability）是 ROCm 的核心
- 代码几乎与 CUDA 相同，只是关键字替换
- 编译器：`hipcc`

---

## 2. 代码迁移：CUDA → HIP

### 2.1 自动迁移工具

```bash
# 使用 hipify-perl 自动转换
/opt/rocm/bin/hipify-perl cuda_code.cu > hip_code.cpp

# 或使用 hipify-clang（更精确）
/opt/rocm/bin/hipify-clang cuda_code.cu --o hip_code.cpp
```

### 2.2 主要 API 对照表

| CUDA API | HIP API | 说明 |
|----------|---------|------|
| `cudaMalloc` | `hipMalloc` | 内存分配 |
| `cudaFree` | `hipFree` | 内存释放 |
| `cudaMemcpy` | `hipMemcpy` | 内存拷贝 |
| `cudaMemset` | `hipMemset` | 内存设置 |
| `<<< >>>` | `hipLaunchKernelGGL` | 核函数启动 |
| `blockIdx.x` | `hipBlockIdx_x` | 块索引 |
| `threadIdx.x` | `hipThreadIdx_x` | 线程索引 |
| `cudaStream_t` | `hipStream_t` | 流 |
| `cudaEvent_t` | `hipEvent_t` | 事件 |
| `cudaError_t` | `hipError_t` | 错误类型 |
| `cudaDeviceSynchronize` | `hipDeviceSynchronize` | 设备同步 |
| `__shared__` | `__shared__` | 共享内存（相同） |
| `__syncthreads()` | `__syncthreads()` | 线程同步（相同） |

### 2.3 头文件对照

```cpp
// CUDA
#include <cuda_runtime.h>
#include <cuda.h>

// HIP
#include <hip/hip_runtime.h>
#include <hip/hip_runtime_api.h>
```

---

## 3. 生态系统与库支持

### 3.1 深度学习框架

| 框架 | CUDA 支持 | ROCm 支持 | 说明 |
|------|-----------|-----------|------|
| **PyTorch** | ✅ 原生 | ✅ 官方 | `pip install torch --index-url https://download.pytorch.org/whl/rocm6.2` |
| **TensorFlow** | ✅ 原生 | ✅ 社区 | `tensorflow-rocm` 包 |
| **JAX** | ✅ 原生 | ⚠️ 实验性 | 通过 OpenXLA |
| **ONNX Runtime** | ✅ 原生 | ✅ 官方 | ROCm Execution Provider |

```python
# PyTorch - CUDA vs ROCm

# CUDA 版本
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

# ROCm 版本（API 完全相同！）
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm6.2

# 代码层面无需修改
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = model.to(device)
```

### 3.2 数学库对比

| 功能 | CUDA (cuXXX) | ROCm (rocXXX/hipXXX) |
|------|--------------|----------------------|
| BLAS | cuBLAS | rocBLAS / hipBLAS |
| FFT | cuFFT | rocFFT / hipFFT |
| 随机数 | cuRAND | rocRAND / hipRAND |
| 稀疏矩阵 | cuSPARSE | rocSPARSE / hipSPARSE |
| 深度学习 | cuDNN | MIOpen |
| 线性代数 | cuSOLVER | rocSOLVER / hipSOLVER |
| Thrust | thrust | rocThrust / hipThrust |

### 3.3 通信库（多 GPU）

| CUDA | ROCm | 说明 |
|------|------|------|
| **NCCL** | **RCCL** | 集合通信库，API 几乎相同 |

```cpp
// NCCL (CUDA)
ncclAllReduce(sendbuff, recvbuff, count, ncclFloat, ncclSum, comm, stream);

// RCCL (ROCm) - 完全相同！
ncclAllReduce(sendbuff, recvbuff, count, ncclFloat, ncclSum, comm, stream);
```

---

## 4. 性能对比

### 4.1 计算性能（以 MI300X vs H100 为例）

| 指标 | AMD MI300X | NVIDIA H100 | 差距 |
|------|------------|-------------|------|
| FP64 (TFLOPS) | 2.6 | 0.99 | AMD 领先 2.6x |
| FP32 (TFLOPS) | 1.3 | 67 | NVIDIA 领先 51x |
| FP16/BF16 (TFLOPS) | 2.6 | 989 | NVIDIA 领先 38x |
| FP8 (TFLOPS) | 5.2 | 1,979 | NVIDIA 领先 38x |
| 显存容量 | 192 GB | 80 GB | AMD 领先 2.4x |
| 显存带宽 (TB/s) | 5.3 | 3.35 | AMD 领先 1.6x |

> ⚠️ 注意：不同架构难以直接比较，实际性能取决于具体工作负载

### 4.2 实际 LLM 推理性能

以 **Llama 2 70B** 为例：

| 配置 | 性能 (tokens/s) | 备注 |
|------|-----------------|------|
| H100 SXM5 | ~80-100 | vLLM + Tensor Parallel=4 |
| MI300X | ~70-90 | vLLM + Tensor Parallel=4 |
| RTX 4090 x2 | ~30-40 | 显存限制需要量化 |

### 4.3 开发优化难度

| 方面 | CUDA | ROCm |
|------|------|------|
|  profiling 工具 | Nsight (功能强大) | rocprof / Omniperf (发展中) |
| 调试工具 | cuda-gdb | rocgdb |
| 优化文档 | 非常详细 | 较完善，但不如 CUDA |
| 社区支持 | 庞大 | 较小但活跃 |

---

## 5. 开发与部署

### 5.1 开发环境

**CUDA：**
```bash
# Ubuntu 安装
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.0-1_all.deb
sudo dpkg -i cuda-keyring_1.0-1_all.deb
sudo apt update
sudo apt install cuda-toolkit-12-4
```

**ROCm：**
```bash
# Ubuntu 安装
sudo apt install "linux-headers-$(uname -r)" "linux-modules-extra-$(uname -r)"
sudo apt install amdgpu-dkms rocm-dev
```

### 5.2 Docker 支持

**CUDA：**
```bash
docker run --gpus all -it nvidia/cuda:12.4.0-devel-ubuntu22.04
```

**ROCm：**
```bash
docker run --device=/dev/kfd --device=/dev/dri \
    --group-add video --group-add render \
    -it rocm/dev-ubuntu-22.04:6.2-complete
```

### 5.3 Kubernetes 支持

**CUDA：**
```yaml
# 使用 NVIDIA Device Plugin
resources:
  limits:
    nvidia.com/gpu: 1
```

**ROCm：**
```yaml
# 使用 AMD GPU Device Plugin
resources:
  limits:
    amd.com/gpu: 1
```

---

## 6. 实际开发差异示例

### 6.1 矩阵乘法

```cpp
// ========== CUDA (cuBLAS) ==========
#include <cublas_v2.h>

cublasHandle_t handle;
cublasCreate(&handle);

float alpha = 1.0f, beta = 0.0f;
cublasSgemm(handle, CUBLAS_OP_N, CUBLAS_OP_N, 
            m, n, k, &alpha, 
            d_A, lda, d_B, ldb, 
            &beta, d_C, ldc);
```

```cpp
// ========== ROCm (hipBLAS) ==========
#include <hipblas/hipblas.h>

hipblasHandle_t handle;
hipblasCreate(&handle);

float alpha = 1.0f, beta = 0.0f;
hipblasSgemm(handle, HIPBLAS_OP_N, HIPBLAS_OP_N, 
             m, n, k, &alpha, 
             d_A, lda, d_B, ldb, 
             &beta, d_C, ldc);
```

### 6.2 卷积神经网络

```cpp
// ========== CUDA (cuDNN) ==========
#include <cudnn.h>

cudnnHandle_t cudnn;
cudnnCreate(&cudnn);

cudnnTensorDescriptor_t inputDesc, outputDesc;
cudnnFilterDescriptor_t filterDesc;
cudnnConvolutionDescriptor_t convDesc;

// 设置描述符...
cudnnSetTensor4dDescriptor(inputDesc, CUDNN_TENSOR_NCHW, ...);

// 前向卷积
cudnnConvolutionForward(cudnn, &alpha, inputDesc, input,
                        filterDesc, filter, convDesc, algo,
                        workspace, workspaceSize, &beta,
                        outputDesc, output);
```

```cpp
// ========== ROCm (MIOpen) ==========
#include <miopen/miopen.h>

miopenHandle_t miopen;
miopenCreate(&miopen);

miopenTensorDescriptor_t inputDesc, outputDesc;
miopenTensorDescriptor_t filterDesc;
miopenConvolutionDescriptor_t convDesc;

// 设置描述符（API 类似但略有不同）
miopenSet4dTensorDescriptor(inputDesc, miopenFloat, n, c, h, w);

// 前向卷积
miopenConvolutionForward(miopen, &alpha, inputDesc, input,
                         filterDesc, filter, convDesc, algo,
                         &beta, outputDesc, output,
                         workspace, workspaceSize);
```

> ⚠️ MIOpen 与 cuDNN 的 API 有差异，需要适配代码

---

## 7. 平台特有功能

### 7.1 NVIDIA 特有

| 技术 | 说明 | 用途 |
|------|------|------|
| **Tensor Cores** | 专用矩阵计算单元 | FP16/BF16/FP8/INT8 加速 |
| **DLSS** | 深度学习超采样 | 图形渲染 |
| **NVLink** | 高速 GPU 互联 | 多 GPU 通信 |
| **CUDA Graphs** | 预定义执行流 | 降低 CPU 开销 |
| **Unified Memory** | 自动内存管理 | 简化编程 |

### 7.2 AMD 特有

| 技术 | 说明 | 用途 |
|------|------|------|
| **CDNA Architecture** | 计算优化架构 | 数据中心 GPU |
| **RDNA Architecture** | 图形优化架构 | 游戏/工作站 GPU |
| **Infinity Fabric** | AMD 互联技术 | CPU-GPU、GPU-GPU 通信 |
| **XDNA (Ryzen AI)** | AI 加速引擎 | 低功耗 AI 推理 |
| **Large VRAM** | 更大显存 | 大模型推理 |

---

## 8. 选择建议

### 选择 CUDA 如果：

- ✅ 你已经有大量 CUDA 代码需要维护
- ✅ 使用最新 NVIDIA 特性（如 FP8、Transformer Engine）
- ✅ 需要最佳的 LLM 训练性能
- ✅ 团队熟悉 CUDA 生态
- ✅ 预算充足购买 NVIDIA GPU

### 选择 ROCm 如果：

- ✅ 你使用 AMD GPU（如本机的 Radeon 890M）
- ✅ 需要大显存进行大模型推理（MI300X 192GB）
- ✅ 偏好开源软件栈
- ✅ 预算有限（AMD GPU 通常性价比更高）
- ✅ 需要避免 vendor lock-in

---

## 9. 未来趋势

### 行业动向

| 趋势 | 影响 |
|------|------|
| **PyTorch 2.0/Inductor** | 减少 CUDA 依赖，更容易支持 ROCm |
| **OpenAI Triton** | 高级 GPU 编程，支持 CUDA 和 ROCm |
| **Mojo** | 新兴 AI 编程语言，多后端支持 |
| **统一标准** | SYCL、oneAPI 等跨平台方案发展 |

### 市场份额预测

- **短期（1-2 年）**：CUDA 仍占主导（~85%）
- **中期（3-5 年）**：ROCm 份额增长（可能达 20-30%）
- **长期**：可能形成双头垄断，或出现统一标准

---

## 📚 参考资源

| 资源 | 链接 |
|------|------|
| CUDA 文档 | https://docs.nvidia.com/cuda/ |
| ROCm 文档 | https://rocm.docs.amd.com/ |
| HIP 编程指南 | https://rocm.docs.amd.com/projects/HIP/ |
| PyTorch ROCm | https://pytorch.org/docs/stable/notes/hip.html |
| GPU Benchmarks | https://www.techpowerup.com/gpu-specs/ |

---

## 📝 总结

| 维度 | 优势方 | 差距 |
|------|--------|------|
| 生态成熟度 | CUDA | ROCm 落后 5-10 年 |
| 代码可移植性 | ROCm | HIP 可编译到 CUDA |
| 开源程度 | ROCm | 完全开源 |
| 性能 | 持平 | 取决于具体工作负载 |
| 大模型推理 | ROCm | 更大显存优势 |
| 学习资源 | CUDA | 更丰富 |
| 硬件成本 | ROCm | 通常更便宜 |

> 💡 **核心建议**：如果你是开发者，学习 CUDA 仍然有更高性价比，因为 ROCm 代码几乎与 CUDA 相同，而掌握 CUDA 后转向 ROCm 非常容易。

---

*最后更新: 2026-03-28*
