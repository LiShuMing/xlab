#!/bin/bash

set -e

echo "========================================"
echo "  地铁小向导 - macOS 构建脚本"
echo "========================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check prerequisites
echo "📋 检查环境..."

# Check Node.js
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js 未安装，请先安装 Node.js${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Node.js 已安装${NC}"

# Check Rust
if ! command -v cargo &> /dev/null; then
    echo -e "${YELLOW}⚠️ Rust 未安装，正在安装...${NC}"
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source $HOME/.cargo/env
fi
echo -e "${GREEN}✓ Rust 已安装${NC}"

# Install dependencies
echo ""
echo "📦 安装依赖..."
npm install
echo -e "${GREEN}✓ npm 依赖安装完成${NC}"

# Build frontend
echo ""
echo "🔨 构建前端..."
npm run build
echo -e "${GREEN}✓ 前端构建完成${NC}"

# Build Tauri
echo ""
echo "🏗️ 构建 Tauri 应用..."
cd src-tauri
cargo check
cargo update
cargo build --release
cd ..

echo ""
echo "========================================"
echo -e "${GREEN}✅ 构建成功！${NC}"
echo "========================================"
echo ""
echo "📦 打包 DMG..."
cd src-tauri
cargo tauri build
cd ..

echo ""
echo "📁 输出文件:"
echo "   - DMG: src-tauri/target/release/bundle/dmg/"
echo "   - APP: src-tauri/target/release/bundle/macos/"
echo ""
echo "🎉 下一步:"
echo "   1. 测试 DMG 安装包"
echo "   2. (可选) Apple Developer 签名"
echo "   3. 分发或提交 App Store"
echo ""
