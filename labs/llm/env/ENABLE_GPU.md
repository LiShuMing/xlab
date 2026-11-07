# 启用 PyTorch ROCm GPU 加速

## 📊 当前状态

```
PyTorch 版本: 2.5.1+rocm6.2 ✅ 已安装
ROCm 可用: False ❌ GPU 未启用
```

---

## 步骤 1：设置环境变量

在终端运行：

```bash
# 设置 GPU 架构（Radeon 890M 是 RDNA3.5 / gfx1100）
export HSA_OVERRIDE_GFX_VERSION=11.0.0
export PYTORCH_ROCM_ARCH=gfx1100

# 添加到 ~/.bashrc 永久生效
echo 'export HSA_OVERRIDE_GFX_VERSION=11.0.0' >> ~/.bashrc
echo 'export PYTORCH_ROCM_ARCH=gfx1100' >> ~/.bashrc
```

然后重新验证：

```bash
source ~/.bashrc
source ~/pytorch_env/bin/activate
python -c "import torch; print(torch.cuda.is_available())"
```

---

## 步骤 2：检查 ROCm 运行时

```bash
# 检查 ROCm 是否安装
which rocminfo
rocminfo 2>/dev/null | head -50

# 检查 HIP
which hipcc
hipcc --version 2>/dev/null

# 检查设备
ls -la /dev/kfd 2>/dev/null
ls -la /dev/dri/ 2>/dev/null
```

---

## 步骤 3：安装 ROCm 驱动（如未安装）

```bash
# 下载并安装 AMD GPU 驱动（ROCm）
wget https://repo.radeon.com/amdgpu-install/6.2/ubuntu/jammy/amdgpu-install_6.2.60200-1_all.deb
sudo apt install ./amdgpu-install_6.2.60200-1_all.deb
sudo apt update

# 安装 ROCm
sudo apt install -y amdgpu-dkms rocm-dev

# 添加用户到相关组
sudo usermod -aG render,video $USER

# 重启 WSL2
wsl --shutdown
```

> ⚠️ **注意**: 安装驱动后需要**重新启动 WSL2** 才能生效！

---

## 步骤 4：验证 WSL2 GPU 支持

在 Windows PowerShell 中检查：

```powershell
# 检查 WSL 版本
wsl --version

# 检查 WSL 配置
cat $env:USERPROFILE\.wslconfig

# 确保配置包含 GPU 支持
[wsl2]
gpuSupport=true
```

---

## 步骤 5：完整验证命令

```bash
# 1. 激活环境
source ~/pytorch_env/bin/activate

# 2. 设置环境变量
export HSA_OVERRIDE_GFX_VERSION=11.0.0
export PYTORCH_ROCM_ARCH=gfx1100

# 3. 验证 GPU
python -c "
import torch
print(f'PyTorch: {torch.__version__}')
print(f'GPU 可用: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'GPU: {torch.cuda.get_device_name(0)}')
    x = torch.randn(1000, 1000, device='cuda')
    y = torch.randn(1000, 1000, device='cuda')
    z = torch.matmul(x, y)
    print(f'矩阵乘法测试: {z.shape} ✅')
"
```

---

## 常见问题

### Q1: `rocminfo` 命令不存在

```bash
# 安装 ROCm 工具
sudo apt install -y rocm-dev rocminfo
```

### Q2: `HSA_STATUS_ERROR` 错误

```bash
# 检查权限
sudo usermod -aG render,video $USER

# 检查设备
ls -la /dev/kfd
# 应该显示当前用户在 render 或 video 组
```

### Q3: Windows 侧驱动问题

在 Windows 上安装 AMD GPU 驱动：
1. 访问 https://www.amd.com/support
2. 下载 **Ryzen AI 9 HX 370** 的最新驱动
3. 确保安装 **AMD HIP SDK**

### Q4: PyTorch 报告 "No HIP GPUs are available"

```bash
# 可能是 GPU 架构不匹配
# 尝试其他架构版本
export HSA_OVERRIDE_GFX_VERSION=10.3.0  # 尝试 RDNA2 架构
# 或
export HSA_OVERRIDE_GFX_VERSION=11.0.1  # 尝试其他 RDNA3 版本
```

---

## 快速诊断脚本

创建 `diagnose_gpu.sh`：

```bash
#!/bin/bash

echo "===== ROCm GPU 诊断 ====="

echo -e "\n1. 环境变量:"
echo "HSA_OVERRIDE_GFX_VERSION=$HSA_OVERRIDE_GFX_VERSION"
echo "PYTORCH_ROCM_ARCH=$PYTORCH_ROCM_ARCH"

echo -e "\n2. ROCm 工具:"
which rocminfo && echo "✅ rocminfo 存在" || echo "❌ rocminfo 不存在"
which hipcc && echo "✅ hipcc 存在" || echo "❌ hipcc 不存在"

echo -e "\n3. 设备文件:"
ls -la /dev/kfd 2>/dev/null && echo "✅ /dev/kfd 存在" || echo "❌ /dev/kfd 不存在"
ls -la /dev/dri/ 2>/dev/null && echo "✅ /dev/dri 存在" || echo "❌ /dev/dri 不存在"

echo -e "\n4. PyTorch GPU 检查:"
source ~/pytorch_env/bin/activate
python -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'GPU: {torch.cuda.is_available()}')"

echo -e "\n诊断完成!"
```

运行：

```bash
chmod +x diagnose_gpu.sh
./diagnose_gpu.sh
```

---

## 总结

| 步骤 | 命令 | 目的 |
|------|------|------|
| 1 | `export HSA_OVERRIDE_GFX_VERSION=11.0.0` | 设置 GPU 架构 |
| 2 | `sudo apt install rocm-dev` | 安装 ROCm 驱动 |
| 3 | `sudo usermod -aG render,video $USER` | 添加权限 |
| 4 | `wsl --shutdown` | 重启 WSL2 |
| 5 | `python -c "import torch; print(torch.cuda.is_available())"` | 验证 |

**预期结果：**
```
PyTorch 版本: 2.5.1+rocm6.2
GPU 可用: True
GPU: AMD Radeon Graphics
```

---

*如果仍然无法启用 GPU，请运行诊断脚本并将输出发给我！*
