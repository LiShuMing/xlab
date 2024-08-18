# 每日精进 Agent

基于 Python + Telegram Bot + SQLite 的全自动每日学习 Agent。
覆盖6个知识领域：语言精通、算法解题、Linux 精通、OLAP/数据库、大规模架构、前沿追踪。

## 快速开始

### 1. 环境准备

确保使用指定的 venv 环境：

```bash
source /home/lism/.venv/general-3.12/bin/activate
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

在 `~/.env` 文件中配置以下变量：

```bash
# LLM 配置 (使用 OpenAI 兼容接口)
LLM_BASE_URL=https://your-api-endpoint.com/v1
LLM_API_KEY=your-api-key

# Telegram Bot 配置
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id
```

### 4. 运行

**定时调度模式（默认）：**
```bash
cd src
python main.py --mode scheduler
```

**手动触发一次：**
```bash
cd src
python main.py --mode once
```

**强制指定领域：**
```bash
python main.py --mode once --domain db
```

## 项目结构

```
├── config.yaml          # 主配置文件
├── topics.yaml          # 知识图谱配置
├── requirements.txt     # 依赖
├── CHANGES_LOG.md       # 变更日志
├── src/
│   ├── main.py          # 主入口
│   ├── config.py        # 配置加载
│   ├── db.py            # 数据库封装
│   ├── plan.py          # 出题规划器
│   ├── generate.py      # 题目生成
│   ├── reflect.py       # 评估引擎
│   ├── bot.py           # Telegram Bot
│   ├── scheduler.py     # 定时调度
│   └── tools/
│       ├── knowledge.py # 知识图谱工具
│       ├── memory.py    # 记忆读取工具
│       └── crawler.py   # 热点爬虫
├── data/
│   └── memory.db        # SQLite 数据库
└── logs/
    └── agent.jsonl      # 运行日志
```

## Telegram 命令

| 命令 | 功能 |
|------|------|
| `/tm_hint` | 获取一次提示（-1分） |
| `/tm_skip` | 跳过今日题目 |
| `/tm_status` | 查看本周进度 |
| `/tm_history [n]` | 查看最近 n 条记录 |
| `/tm_weak` | 列出薄弱点 |
| `/tm_topic <名称>` | 指定下次主题 |
| `/tm_level <L2/L3/L4>` | 临时覆盖难度 |

## 配置说明

### config.yaml

```yaml
schedule:
  timezone: "Asia/Tokyo"
  push_time: "08:00"      # 每日推送时间
  reminder_time: "20:00"  # 提醒时间
  timeout_hours: 24       # 超时时间

telegram:
  bot_token: "${TELEGRAM_BOT_TOKEN}"
  chat_id: "${TELEGRAM_CHAT_ID}"

llm:
  provider: "openai"
  model: "qwen-coding-plan"
  base_url: "${LLM_BASE_URL}"
  api_key: "${LLM_API_KEY}"
  question_max_tokens: 1200
  reflect_max_tokens: 800

learning:
  default_level: 3
  level_up_threshold: 9.0      # 升级阈值
  level_down_threshold: 4.0    # 降级阈值
  weak_threshold: 6.0          # 薄弱点阈值
```

### topics.yaml

定义6个知识领域及其主题：
- **lang** (周一): 语言精通 (C++/Java)
- **algo** (周二): 算法解题
- **os** (周三): Linux 精通
- **db** (周四): OLAP/数据库
- **arch** (周五): 大规模架构
- **frontier** (周六): 前沿追踪
- **review** (周日): 综合复盘

## 核心特性

1. **领域轮转**: 按星期自动切换不同知识领域
2. **Topic 选择**: 基于历史表现的加权随机选择
3. **难度自适应**: 根据答题表现自动调整难度 (L2-L4)
4. **LLM 出题**: 使用大模型生成高质量面试级题目
5. **多维度评分**: 概念/深度/边界三个维度评估
6. **薄弱点追踪**: 自动识别并强化薄弱知识
7. **定时调度**: 支持每日自动推送、提醒、超时处理

## 实现状态

- [x] v0.1 MVP: 核心功能完整
- [ ] v0.2 记忆: 薄弱点权重优化
- [ ] v0.3 自适应: 难度自动调整增强
- [ ] v0.4 热点: 爬虫热点素材注入
- [ ] v0.5 报告: 每周学习报告

## 依赖

- Python 3.12+
- APScheduler (定时任务)
- python-telegram-bot (Bot 交互)
- OpenAI SDK (LLM 调用)
- PyYAML (配置解析)

## 许可证

MIT
