#!/bin/bash
# 停止 GPT Academic 服务

cd "$(dirname "$0")"

if [ -f .gpt_academic.pid ]; then
    PID=$(cat .gpt_academic.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "🛑 正在停止 GPT Academic (PID: $PID)..."
        kill $PID
        sleep 2
        if ps -p $PID > /dev/null 2>&1; then
            echo "⚠️ 进程仍在运行，强制终止..."
            kill -9 $PID
        fi
        echo "✅ 服务已停止"
    else
        echo "ℹ️ 服务未运行"
    fi
    rm -f .gpt_academic.pid
else
    # 尝试查找并停止
    PID=$(pgrep -f "python main.py" | head -1)
    if [ -n "$PID" ]; then
        echo "🛑 正在停止 GPT Academic (PID: $PID)..."
        kill $PID
        echo "✅ 服务已停止"
    else
        echo "ℹ️ 未找到运行中的服务"
    fi
fi
