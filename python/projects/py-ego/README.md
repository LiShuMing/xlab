# StarRocks Materialized View Monitor + 心理陪护机器人

这是一个组合项目，包含：
1. **StarRocks 物化视图监控工具** - 用于监控 StarRocks 物化视图状态
2. **心理陪护机器人** - 基于 LLM 的智能对话机器人，具有记忆功能

## 项目结构

```
├── config.py              # LLM 配置管理（从 ~/.env 加载）
├── main.py                # 心理陪护机器人主程序
├── embeddings.py          # Embedding 向量生成
├── memory_store.py        # 记忆存储（FAISS + JSON）
├── starrocks_mv_monitor.py    # StarRocks 监控核心
├── streamlit_mv_monitor.py    # StarRocks 监控 Web 界面
├── requirements.txt       # 依赖列表
└── test_llm_config.py     # LLM 配置测试工具
```

## 配置说明

### 1. LLM 配置 (~/.env)

项目从 `~/.env` 文件加载 LLM 配置，支持任何 OpenAI 兼容的 API：

```bash
# timeout
LLM_TIMEOUT=120

# Kimi/OpenAI 配置示例
LLM_BASE_URL=https://api.kimi.com/coding/v1
LLM_API_KEY=your_api_key_here
LLM_MODEL=kimi-for-coding

# 日志级别: DEBUG | INFO | WARNING
LOG_LEVEL=INFO
```

**支持的 API 提供商：**
- **Kimi**: `https://api.kimi.com/coding/v1`
- **OpenAI**: `https://api.openai.com/v1`
- **Ollama**: `http://localhost:11434/v1`
- **DashScope**: `https://coding.dashscope.aliyuncs.com/apps/anthropic`

### 2. Embedding 配置

由于 Kimi API 暂不支持 embeddings，项目默认使用本地 embedding 模型：

```bash
# 使用本地模型（默认）
USE_LOCAL_EMBEDDING=true
EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5

# 如果没有安装 sentence-transformers，可以使用简单哈希 embedding（仅用于测试）
USE_SIMPLE_EMBEDDING=true
```

## 安装依赖

```bash
pip install -r requirements.txt
```

如果遇到 sentence-transformers 安装问题，可以：
1. 使用简单哈希 embedding 进行测试：`export USE_SIMPLE_EMBEDDING=true`
2. 或使用支持 embedding 的远程 API（如 OpenAI）

## 使用方法

### 心理陪护机器人

```bash
python main.py
```

功能特点：
- 💬 智能对话：基于配置的 LLM API 进行对话
- 🧠 记忆功能：自动保存对话历史，支持语义检索相关记忆
- 🔧 配置灵活：通过 `~/.env` 文件配置不同 LLM 提供商

### StarRocks 监控

```bash
streamlit run streamlit_mv_monitor.py
```

## 测试配置

运行测试脚本验证配置是否正确：

```bash
python test_llm_config.py
```

## 架构说明

### LLM 配置模块 (config.py)

- 从 `~/.env` 加载环境变量
- 提供 `get_openai_client()` 函数获取 OpenAI 兼容客户端
- 支持自定义环境变量路径：`ENV_PATH=/path/to/.env python main.py`

### Embedding 模块 (embeddings.py)

- 支持本地模型（sentence-transformers）
- 支持远程 API（OpenAI 兼容格式）
- 提供降级方案（简单哈希 embedding，仅用于测试）

### 记忆存储 (memory_store.py)

- 使用 FAISS 进行向量检索
- JSON 文件持久化存储
- 自动处理维度变化

## 故障排除

### 1. API 403 错误

如果使用 `kimi-for-coding` 模型返回 403，说明当前环境不在允许的 Coding Agents 列表中。可以尝试：
- 使用其他 Kimi 模型
- 使用 OpenAI API
- 使用本地 Ollama

### 2. Embedding 模型加载失败

```bash
# 方案 1: 安装 sentence-transformers
pip install sentence-transformers

# 方案 2: 使用简单哈希 embedding（仅测试）
export USE_SIMPLE_EMBEDDING=true
```

### 3. FAISS 安装失败

```bash
pip install faiss-cpu
```

## 扩展开发

### 添加新的 Monitor 类型

继承 `StarRocksBaseMonitor` 类：

```python
class CustomMonitor(StarRocksBaseMonitor):
    def get_data(self, **kwargs) -> pd.DataFrame:
        query = "SELECT * FROM information_schema.custom_table"
        return self.execute_query(query)

    def transform_data(self, df: pd.DataFrame) -> pd.DataFrame:
        return df
```

### 更换 Embedding 模型

修改 `~/.env`：

```bash
EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5  # 更大的中文模型
```

## 参考文档

- [Materialized View Metrics](https://docs.starrocks.io/docs/administration/management/monitoring/metrics-materialized_view/)
- [OpenAI API 文档](https://platform.openai.com/docs/api-reference)
