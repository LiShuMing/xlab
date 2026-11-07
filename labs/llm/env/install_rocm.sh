#!/bin/bash
set -e

echo "=========================================="
echo "      ROCm 驱动安装脚本"
echo "=========================================="

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 1. 安装依赖
log_info "步骤 1/6: 安装基础依赖..."
sudo apt update
sudo apt install -y wget gnupg2 software-properties-common

# 2. 下载 AMD GPU 安装器
log_info "步骤 2/6: 下载 AMD GPU 安装器..."
cd /tmp
if [ ! -f amdgpu-install_6.2.60200-1_all.deb ]; then
    wget -q --show-progress https://repo.radeon.com/amdgpu-install/6.2/ubuntu/jammy/amdgpu-install_6.2.60200-1_all.deb
fi
log_info "安装包下载完成"

# 3. 安装 AMD GPU 安装器
log_info "步骤 3/6: 安装 AMD GPU 安装器..."
sudo apt install -y ./amdgpu-install_6.2.60200-1_all.deb
sudo apt update

# 4. 安装 ROCm（WSL 版本）
log_info "步骤 4/6: 安装 ROCm 驱动（这可能需要 20-40 分钟）..."
sudo amdgpu-install -y --usecase=wsl,rocm --no-dkms 2>&1 || {
    log_warn "amdgpu-install 失败，尝试直接安装 rocm-dev..."
    sudo apt install -y rocm-dev rocm-libs rocminfo
}

# 5. 添加用户到组
log_info "步骤 5/6: 配置用户权限..."
sudo usermod -aG video,render $USER
log_info "用户已添加到 video 和 render 组"

# 6. 设置环境变量
log_info "步骤 6/6: 配置环境变量..."

# 检查是否已存在
if ! grep -q "HSA_OVERRIDE_GFX_VERSION" ~/.bashrc; then
    echo "" >> ~/.bashrc
    echo "# ROCm/PyTorch GPU 配置" >> ~/.bashrc
    echo 'export HSA_OVERRIDE_GFX_VERSION=11.0.0' >> ~/.bashrc
    echo 'export PYTORCH_ROCM_ARCH=gfx1100' >> ~/.bashrc
    echo 'export PATH=$PATH:/opt/rocm/bin' >> ~/.bashrc
    echo 'export LD_LIBRARY_PATH=/opt/rocm/lib:$LD_LIBRARY_PATH' >> ~/.bashrc
    log_info "环境变量已添加到 ~/.bashrc"
else
    log_warn "环境变量已存在，跳过"
fi

echo ""
echo "=========================================="
echo "      安装完成！"
echo "=========================================="
echo ""
log_info "请执行以下命令重启 WSL2:"
echo ""
echo "  wsl --shutdown"
echo ""
echo "然后重新打开 WSL2 终端，运行:"
echo ""
echo "  source ~/.bashrc"
echo "  source ~/pytorch_env/bin/activate"
echo "  python -c \"import torch; print(torch.cuda.is_available())\""
echo ""
echo "预期输出: True"
echo ""
