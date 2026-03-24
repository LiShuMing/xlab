#!/bin/bash
# GPT Academic 启动脚本
# 自动从 ~/.env 读取 LLM 配置

cd "$(dirname "$0")"

echo "🚀 启动 GPT Academic..."
echo "📋 当前 LLM 配置:"
echo "   模型: $(grep '^LLM_MODEL=' ~/.env 2>/dev/null | cut -d'=' -f2 || echo '未设置')"
echo "   端点: $(grep '^LLM_BASE_URL=' ~/.env 2>/dev/null | cut -d'=' -f2 || echo '未设置')"
echo ""

python main.py
