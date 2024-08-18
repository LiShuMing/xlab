#!/bin/bash

echo "=========================================="
echo "      ROCm GPU 诊断脚本"
echo "=========================================="

echo -e "\n【1】环境变量检查:"
echo "HSA_OVERRIDE_GFX_VERSION=${HSA_OVERRIDE_GFX_VERSION:-未设置}"
echo "PYTORCH_ROCM_ARCH=${PYTORCH_ROCM_ARCH:-未设置}"
echo "LD_LIBRARY_PATH=${LD_LIBRARY_PATH:-未设置}"
echo "PATH 包含 rocm: $(echo $PATH | grep -o 'rocm' || echo '否')"

echo -e "\n【2】ROCm 工具检查:"
which rocminfo 2>/dev/null && echo "✅ rocminfo: $(which rocminfo)" || echo "❌ rocminfo 未安装"
which hipcc 2>/dev/null && echo "✅ hipcc: $(which hipcc)" || echo "❌ hipcc 未安装"
which rocm-smi 2>/dev/null && echo "✅ rocm-smi: $(which rocm-smi)" || echo "❌ rocm-smi 未安装"

echo -e "\n【3】设备文件检查:"
if [ -e /dev/kfd ]; then
    echo "✅ /dev/kfd 存在"
    ls -la /dev/kfd
else
    echo "❌ /dev/kfd 不存在"
fi

if [ -d /dev/dri ]; then
    echo "✅ /dev/dri 存在"
    ls -la /dev/dri/
else
    echo "❌ /dev/dri 不存在"
fi

echo -e "\n【4】用户组检查:"
echo "当前用户: $(whoami)"
echo "用户组: $(groups)"
if groups | grep -qE '(video|render)'; then
    echo "✅ 用户在 video/render 组"
else
    echo "❌ 用户不在 video/render 组"
fi

echo -e "\n【5】ROCm 安装路径检查:"
if [ -d /opt/rocm ]; then
    echo "✅ /opt/rocm 存在"
    ls -la /opt/rocm/bin/ 2>/dev/null | head -10
else
    echo "❌ /opt/rocm 不存在"
fi

echo -e "\n【6】PyTorch GPU 检查:"
source ~/pytorch_env/bin/activate 2>/dev/null || echo "⚠️ 无法激活虚拟环境"
python3 << 'PYEOF'
import sys
try:
    import torch
    print(f"PyTorch 版本: {torch.__version__}")
    print(f"CUDA/ROCm 可用: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU 数量: {torch.cuda.device_count()}")
        for i in range(torch.cuda.device_count()):
            print(f"  GPU {i}: {torch.cuda.get_device_name(i)}")
    else:
        print("\n可能原因:")
        print("  - ROCm 驱动未安装")
        print("  - 缺少环境变量 HSA_OVERRIDE_GFX_VERSION")
        print("  - GPU 架构不匹配")
        print("  - 用户权限不足")
except ImportError:
    print("❌ PyTorch 未安装")
    sys.exit(1)
PYEOF

echo -e "\n【7】WSL2 信息:"
if [ -f /proc/version ]; then
    grep -i microsoft /proc/version && echo "✅ 检测到 WSL2" || echo "ℹ️ 非 WSL 环境"
fi

echo -e "\n=========================================="
echo "      诊断完成"
echo "=========================================="
