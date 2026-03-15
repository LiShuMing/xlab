# Invest-AI 股票分析报告平台

基于 LLM 的智能股票投资分析系统，生成专业级的投资分析报告。

## 特性

- 📊 **多市场支持** - A 股、港股、美股全覆盖
- 🤖 **AI 驱动** - 基于 LangChain + LangGraph 的多 Agent 编排
- 📰 **实时资讯** - 整合最新新闻、财报、宏观经济数据
- 📝 **精美报告** - 结构化 Markdown 报告，支持导出
- 🎯 **专业分析** - 8 大投资视角，包括价值投资、技术分析、量化风控

## 技术栈

**后端**
- FastAPI + Python 3.11+
- LangChain + LangGraph
- PostgreSQL + Redis
- yfinance, AKShare

**前端**
- React + TypeScript
- Ant Design
- ECharts

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- Redis
- PostgreSQL

### 安装

```bash
# 克隆项目
git clone <repository-url>
cd invest-ai

# 安装 Python 依赖
pip install -e ".[dev]"

# 安装前端依赖
cd apps/web
npm install

# 配置环境变量
cp .env.example .env
# 编辑 .env 配置 LLM API Key 等
```

### 启动服务

```bash
# 启动 Redis
redis-server

# 启动后端
cd apps/api
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 启动前端（新终端）
cd apps/web
npm run dev
```

访问 http://localhost:5173 开始使用。

## 项目结构

```
invest-ai/
├── apps/
│   ├── web/           # React 前端
│   └── api/           # FastAPI 后端
├── modules/           # 业务模块
│   ├── stock_analyzer/
│   ├── data_collector/
│   └── report_generator/
├── agents/            # Agent 系统
├── core/              # 核心基础设施
├── storage/           # 数据存储
└── tests/             # 测试
```

## API 文档

启动后端后访问 http://localhost:8000/docs 查看 OpenAPI 文档。

## 配置

在 `.env` 文件中配置：

```env
# LLM 配置
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1
MODEL_NAME=gpt-4o

# 数据库
DATABASE_URL=postgresql://user:pass@localhost:5432/invest_ai
REDIS_URL=redis://localhost:6379/0

# 应用
LOG_LEVEL=info
```

## License

MIT
