# GPT Academic - AGENTS.md

> 本文档为 AI 编程助手提供项目背景、架构和开发指南。
> This document provides project background, architecture, and development guidelines for AI coding agents.

## 项目概述 (Project Overview)

**GPT Academic** (GPT 学术优化) 是一个基于 Gradio 的 LLM 交互式 Web 界面，专为学术研究场景优化。项目支持多模型并行、插件化架构、PDF/LaTeX 论文翻译、代码分析等功能。

- **主语言**: Python 3.9 - 3.11
- **UI 框架**: Gradio 3.32.15 (使用项目定制版本)
- **当前版本**: 4.00 (详见 `version` 文件)
- **开源地址**: https://github.com/binary-husky/gpt_academic

## 项目结构 (Project Structure)

```
gpt_academic/
├── main.py                      # 主入口 - Gradio UI 编排
├── config.py                    # 基础配置文件
├── config_private.py            # 用户私有配置（gitignore，优先级高于 config.py）
├── core_functional.py           # 核心功能按钮定义（润色、翻译等）
├── crazy_functional.py          # 函数插件注册中心
├── toolbox.py                   # 核心装饰器与工具函数
├── multi_language.py            # 多语言自动翻译工具
├── check_proxy.py               # 代理检测与自动更新
│
├── crazy_functions/             # 70+ 函数插件模块
│   ├── SourceCode_Analyse.py    # 代码项目分析
│   ├── Latex_Function.py        # LaTeX 论文处理
│   ├── PDF_Translate.py         # PDF 翻译
│   ├── Void_Terminal.py         # 虚空终端（自然语言调用插件）
│   └── ...                      # 其他插件
│
├── request_llms/                # LLM 桥接模块
│   ├── bridge_all.py            # LLM 统一路由/调度器
│   ├── bridge_chatgpt.py        # OpenAI API 实现
│   ├── bridge_claude.py         # Claude API 实现
│   ├── bridge_qwen.py           # 通义千问 API
│   ├── bridge_deepseek*.py      # DeepSeek API
│   ├── bridge_*.py              # 其他模型实现（40+ 模型）
│   └── embed_models/            # 嵌入模型
│
├── shared_utils/                # 共享工具模块
│   ├── config_loader.py         # 配置加载器（优先级：ENV > config_private.py > config.py）
│   ├── fastapi_server.py        # FastAPI 服务启动
│   ├── fastapi_stream_server.py # 流式响应服务器
│   ├── advanced_markdown_format.py  # Markdown 渲染增强
│   ├── context_clip_policy.py   # 上下文裁剪策略
│   ├── cookie_manager.py        # Cookie 管理
│   ├── key_pattern_manager.py   # API Key 轮换管理
│   └── handle_upload.py         # 文件上传处理
│
├── themes/                      # UI 主题系统
│   ├── theme.py                 # 主题基类
│   ├── default.py / green.py / contrast.py  # 具体主题
│   ├── common.js / common.css   # 前端通用资源
│   ├── gui_toolbar.py           # 工具栏 UI
│   ├── gui_floating_menu.py     # 浮动菜单 UI
│   └── gui_advanced_plugin_class.py  # 高级插件 UI
│
├── tests/                       # 测试目录
├── docs/                        # 文档目录
├── docker-compose.yml           # Docker 部署配置（多方案）
├── Dockerfile                   # Docker 构建文件
└── requirements.txt             # Python 依赖
```

## 技术栈 (Technology Stack)

### 核心依赖
- **Web UI**: Gradio 3.32.15 (项目定制版本)
- **Web 服务器**: FastAPI + Uvicorn
- **HTTP 客户端**: httpx, requests[socks]
- **日志**: loguru
- **配置**: 环境变量 + Python 模块

### LLM 相关
- **OpenAI**: openai, tiktoken
- ** Claude**: anthropic
- **国产模型**: dashscope(阿里), zhipuai(智谱), 各厂商 SDK
- **本地模型**: transformers, torch, llama-index

### 文档处理
- **PDF**: PyMuPDF, PyPDF2, scipdf_parser
- **Word**: python-docx, docx2pdf
- **Markdown**: Markdown, mdtex2html, pymdown-extensions
- **LaTeX**: latex2mathml (需外部 LaTeX 环境)

## 配置系统 (Configuration System)

配置优先级：**环境变量 > config_private.py > config.py**

### 关键配置项

```python
# config.py 中的核心配置
API_KEY = "sk-..."                          # OpenAI API Key（支持多个，逗号分隔）
DASHSCOPE_API_KEY = "sk-..."                # 阿里灵积云 API Key
DEEPSEEK_API_KEY = "sk-..."                 # DeepSeek API Key
USE_PROXY = False                           # 是否使用代理
proxies = {                                 # 代理配置
    "http": "socks5h://localhost:11284",
    "https": "socks5h://localhost:11284"
}
LLM_MODEL = "gpt-3.5-turbo"                 # 默认模型
AVAIL_LLM_MODELS = [...]                    # 可用模型列表
WEB_PORT = -1                               # Web 端口（-1 为随机）
DEFAULT_FN_GROUPS = ['对话', '编程', '学术', '智能体']  # 插件分组
```

### 环境变量配置
环境变量名可以是 `CONFIG` 或 `GPT_ACADEMIC_CONFIG` 格式：
```bash
export GPT_ACADEMIC_API_KEY="sk-..."
export GPT_ACADEMIC_USE_PROXY="True"
export GPT_ACADEMIC_WEB_PORT="12345"
```

## 插件系统 (Plugin System)

### 插件注册

插件在 `crazy_functional.py` 的 `get_crazy_functions()` 中注册：

```python
function_plugins = {
    "插件显示名称": {
        "Group": "对话|编程|学术|智能体",     # 插件分组，支持多分组用 | 分隔
        "Color": "stop",                      # 按钮颜色: primary/secondary/stop
        "AsButton": True,                     # 是否显示为按钮（False 则只显示在下拉菜单）
        "AdvancedArgs": False,                # 是否启用高级参数输入区
        "ArgsReminder": "提示文字",            # 高级参数区的提示
        "Info": "插件功能说明",                # 鼠标悬停提示
        "Function": HotReload(函数名),         # 插件函数（旧版接口）
        "Class": PluginClass,                  # 插件类（新版接口，推荐）
    },
    # ...
}
```

### 插件函数模板

```python
from toolbox import CatchException, update_ui

@CatchException
def my_plugin(txt, llm_kwargs, plugin_kwargs, chatbot, history, system_prompt, user_request):
    """
    插件函数标准参数：
    - txt: 用户输入或文件路径
    - llm_kwargs: LLM 参数字典（api_key, llm_model, temperature, top_p, max_length 等）
    - plugin_kwargs: 插件参数字典（advanced_arg 等）
    - chatbot: ChatBotWithCookies 实例，用于 UI 显示
    - history: 对话历史列表
    - system_prompt: 系统提示词
    - user_request: Gradio Request 对象（含用户信息）
    """
    # 1. 添加用户消息到对话
    chatbot.append(("用户问题", "正在处理..."))
    yield from update_ui(chatbot=chatbot, history=history)  # 刷新界面
    
    # 2. 调用 LLM（示例）
    from request_llms.bridge_all import predict
    # ... 调用逻辑
    
    # 3. 更新结果
    chatbot[-1] = ("用户问题", "处理结果")
    yield from update_ui(chatbot=chatbot, history=history)
```

### 核心装饰器 (toolbox.py)

| 装饰器 | 用途 |
|--------|------|
| `@CatchException` | 捕获异常并在聊天界面优雅显示 |
| `@HotReload` | 启用插件热重载（修改代码无需重启） |
| `@ArgsGeneralWrapper` | 参数包装器（内部使用） |

### 多线程 LLM 调用工具

```python
from crazy_functions.crazy_utils import (
    request_gpt_model_in_new_thread_with_ui_alive,      # 单线程，保持 UI 响应
    request_gpt_model_multi_threads_with_very_awesome_ui_and_high_efficiency,  # 多线程并行
)

# 单线程调用
result = yield from request_gpt_model_in_new_thread_with_ui_alive(
    inputs="问题",
    inputs_show_user="用户看到的提示",
    llm_kwargs=llm_kwargs,
    chatbot=chatbot,
    history=history,
    sys_prompt="系统提示词"
)

# 多线程调用
results = yield from request_gpt_model_multi_threads_with_very_awesome_ui_and_high_efficiency(
    inputs_array=["问题1", "问题2", ...],
    inputs_show_user_array=["提示1", "提示2", ...],
    history_array=[[], [], ...],
    sys_prompt_array=["系统提示1", "系统提示2", ...],
    llm_kwargs=llm_kwargs,
    chatbot=chatbot
)
```

## LLM 桥接系统 (request_llms/)

### 模型路由 (bridge_all.py)

所有模型在 `bridge_all.py` 中统一注册：

```python
model_info = {
    "gpt-3.5-turbo": {
        "fn_with_ui": chatgpt_ui,           # 带 UI 交互的函数
        "fn_without_ui": chatgpt_noui,      # 无 UI 的后台函数
        "endpoint": openai_endpoint,
        "max_token": 16385,
        "tokenizer": tokenizer_gpt35,
        "token_cnt": get_token_num_gpt35,
    },
    # ... 其他模型
}
```

### 添加新模型

1. 在 `request_llms/` 创建 `bridge_newmodel.py`
2. 实现 `predict()` 和 `predict_no_ui_long_connection()` 函数
3. 在 `bridge_all.py` 中导入并注册到 `model_info`
4. 在 `config.py` 的 `AVAIL_LLM_MODELS` 中添加模型名

## 开发规范 (Development Guidelines)

### 代码风格
- 使用 **4 空格缩进**
- 函数/变量命名：中文或英文均可（项目混合使用）
- 插件函数名建议使用中文，便于用户理解
- 日志使用 `loguru`: `from loguru import logger`

### 文件路径处理
```python
from shared_utils.fastapi_server import validate_path_safety

# 验证路径安全性（防止目录遍历）
validate_path_safety(file_path, chatbot.get_user())
```

### 用户上传文件
- 上传文件保存在 `private_upload/{username}/` 目录
- 使用 `shared_utils.handle_upload` 中的工具处理上传

### 日志与缓存
- 日志目录: `gpt_log/{username}/`
- ArXiv 缓存: `gpt_log/arxiv_cache/`

### 热重载开发
在 `config.py` 中设置 `PLUGIN_HOT_RELOAD = True`，修改插件代码后无需重启服务。

## 测试 (Testing)

### 运行测试
```bash
# 运行指定插件测试
python tests/test_plugins.py

# 运行 LLM 桥接测试
python tests/test_llms.py

# 运行工具函数测试
python tests/test_utils.py
```

### 测试模板 (tests/test_plugins.py)
```python
from test_utils import plugin_test

# 测试指定插件
plugin_test(
    plugin='crazy_functions.SourceCode_Analyse->解析一个Python项目',
    main_input="path/to/project"
)
```

## 部署 (Deployment)

### 本地运行
```bash
pip install -r requirements.txt
python main.py
```

### Docker 部署
```bash
# 选择 docker-compose.yml 中的方案，删除其他方案后：
docker-compose up
```

### 关键部署配置
- **WEB_PORT**: 服务端口（默认随机，Docker 建议指定）
- **AUTHENTICATION**: 用户名密码认证 `[("user", "pass")]`
- **SSL_KEYFILE/SSL_CERTFILE**: HTTPS 证书

## 安全注意事项 (Security Considerations)

1. **API Key 安全**: 使用 `config_private.py` 或环境变量，不要提交到 Git
2. **路径安全**: 始终使用 `validate_path_safety()` 验证用户输入路径
3. **代码执行**: 涉及代码执行的插件（如 AutoGen）默认关闭 Docker 隔离，生产环境需谨慎
4. **ALLOW_RESET_CONFIG**: 允许自然语言修改配置的功能，默认关闭，开启有安全风险

## 常用开发模式

### 1. 创建新的源码分析插件
参考 `crazy_functions/SourceCode_Analyse.py`，使用 `glob` 匹配文件，多线程分析。

### 2. 创建文件处理插件
参考 `crazy_functions/PDF_Translate.py`，处理上传文件，使用 `validate_path_safety` 验证路径。

### 3. 创建交互式插件
参考 `crazy_functions/Void_Terminal.py`，使用 `user_request` 获取请求信息，实现多轮对话。

### 4. 调用外部 API
参考 `crazy_functions/Internet_GPT.py`，使用 `httpx` 或 `requests` 进行网络请求。

## 相关文档

- **项目 Wiki**: https://github.com/binary-husky/gpt_academic/wiki
- **插件开发指南**: https://github.com/binary-husky/gpt_academic/wiki/函数插件指南
- **配置说明**: https://github.com/binary-husky/gpt_academic/wiki/项目配置说明
- **自译解报告**: `docs/self_analysis.md`

## 社区与贡献

- **开发者 QQ 群**: 610599535
- **Issue 反馈**: https://github.com/binary-husky/gpt_academic/issues
- **PR 欢迎**: https://github.com/binary-husky/gpt_academic/pulls

---

*本文档基于 GPT Academic 版本 4.00 编写*
