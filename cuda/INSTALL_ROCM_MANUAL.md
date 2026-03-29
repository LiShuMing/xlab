# ROCm 驱动手动安装指南

由于安装需要 sudo 权限，请按以下步骤手动执行：

---

## 步骤 1：更新系统（1-2 分钟）

```bash
sudo apt update
sudo apt install -y wget gnupg2 software-properties-common
```

---

## 步骤 2：下载 AMD GPU 安装器（1-2 分钟）

```bash
cd /tmp
wget https://repo.radeon.com/amdgpu-install/6.2/ubuntu/jammy/amdgpu-install_6.2.60200-1_all.deb
```

---

## 步骤 3：安装 AMD GPU 安装器（1 分钟）

```bash
sudo apt install -y ./amdgpu-install_6.2.60200-1_all.deb
sudo apt update
```

---

## 步骤 4：安装 ROCm 驱动（20-40 分钟）

**选项 A：使用 amdgpu-install（推荐）**

```bash
sudo amdgpu-install -y --usecase=wsl,rocm --no-dkms
```

如果失败，使用**选项 B**：

```bash
sudo apt install -y rocm-dev rocm-libs rocminfo hip-dev
```

---

## 步骤 5：配置用户权限

```bash
sudo usermod -aG video,render $USER
```

---

## 步骤 6：设置环境变量

```bash
# 添加到 ~/.bashrc
cat >> ~/.bashrc << 'EOF'

# ROCm/PyTorch GPU 配置
export HSA_OVERRIDE_GFX_VERSION=11.0.0
export PYTORCH_ROCM_ARCH=gfx1100
export PATH=$PATH:/opt/rocm/bin
export LD_LIBRARY_PATH=/opt/rocm/lib:$LD_LIBRARY_PATH
EOF
```

---

## 步骤 7：重启 WSL2

**在 Windows PowerShell 中执行：**

```powershell
wsl --shutdown
```

然后重新打开 WSL2 终端。

---

## 步骤 8：验证安装

重新打开 WSL2 后执行：

```bash
# 1. 加载环境变量
source ~/.bashrc

# 2. 检查 ROCm
rocminfo | head -30

# 3. 检查 PyTorch GPU
source ~/pytorch_env/bin/activate
python -c "
import torch
print(f'PyTorch: {torch.__version__}')
print(f'GPU 可用: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'GPU: {torch.cuda.get_device_name(0)}')
"
```

---

## 一键复制命令

如果你想一次性复制所有命令：

```bash
# === 复制以下所有命令粘贴执行 ===
sudo apt update && \
sudo apt install -y wget gnupg2 software-properties-common && \
cd /tmp && \
wget https://repo.radeon.com/amdgpu-install/6.2/ubuntu/jammy/amdgpu-install_6.2.60200-1_all.deb && \
sudo apt install -y ./amdgpu-install_6.2.60200-1_all.deb && \
sudo apt update && \
sudo amdgpu-install -y --usecase=wsl,rocm --no-dkms || sudo apt install -y rocm-dev rocm-libs rocminfo && \
sudo usermod -aG video,render $USER && \
cat >> ~/.bashrc << 'EOF'

# ROCm/PyTorch GPU 配置
export HSA_OVERRIDE_GFX_VERSION=11.0.0
export PYTORCH_ROCM_ARCH=gfx1100
export PATH=$PATH:/opt/rocm/bin
export LD_LIBRARY_PATH=/opt/rocm/lib:$LD_LIBRARY_PATH
EOF

echo "=== 安装完成！请执行: wsl --shutdown ==="
```

---

## 预期结果

重启 WSL2 后，验证应该输出：

```
PyTorch: 2.5.1+rocm6.2
GPU 可用: True
GPU: AMD Radeon Graphics
```

---

## 常见问题

### Q1: 安装过程中卡住

按 `Ctrl+C` 取消，然后重试单个步骤。

### Q2: 空间不足

ROCm 需要约 10-15GB 空间，清理磁盘：

```bash
sudo apt clean
sudo apt autoremove -y
rm -rf /tmp/amdgpu-install*
```

### Q3: 安装后 GPU 仍不可用

检查 Windows 侧 AMD 驱动：

1. 打开 Windows 设备管理器
2. 查看 "显示适配器" 是否有 AMD Radeon
3. 确保安装了 AMD 官方驱动（非微软默认驱动）

---

开始安装吧！有任何错误信息发给我。
