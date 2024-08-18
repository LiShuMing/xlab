#!/bin/bash
# GPT Academic 启动脚本（后台运行）
# 自动从 ~/.env 读取 LLM 配置

cd "$(dirname "$0")"

echo "🚀 启动 GPT Academic..."
echo "📋 当前 LLM 配置:"
echo "   模型: $(grep '^LLM_MODEL=' ~/.env 2>/dev/null | cut -d'=' -f2 || echo '未设置')"
echo "   端点: $(grep '^LLM_BASE_URL=' ~/.env 2>/dev/null | cut -d'=' -f2 || echo '未设置')"
echo ""

# 后台启动，日志输出到 gpt_academic.log
nohup python main.py > gpt_academic.log 2>&1 &
PID=$!

echo "✅ 服务已后台启动 (PID: $PID)"
echo "📝 日志文件: $(pwd)/gpt_academic.log"
echo ""
echo "查看日志: tail -f gpt_academic.log"
echo "停止服务: kill $PID"

# 保存 PID 到文件
echo $PID > .gpt_academic.pid
