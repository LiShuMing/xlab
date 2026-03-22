# Refactoring Changes

This document records the major changes made during the refactoring of py-academic,
as required by `ISSUES.md`.

---

## 1. LLM API Configuration — Moved to `~/.env`

**Before:** LLM API keys (`API_KEY`, `ANTHROPIC_API_KEY`, `DASHSCOPE_API_KEY`, etc.) were
set directly inside `config.py` or `config_private.py`.

**After:** All LLM API keys are loaded **exclusively** from `~/.env` (or environment variables).
They are no longer present in `config.py`.

### How to configure

Create or edit `~/.env`:

```dotenv
# OpenAI
API_KEY=sk-...

# Anthropic / Claude
ANTHROPIC_API_KEY=sk-ant-...

# Qwen / DashScope
QWEN_API_KEY=sk-...
# or
DASHSCOPE_API_KEY=sk-...

# DeepSeek
DEEPSEEK_API_KEY=sk-...

# Azure OpenAI
AZURE_API_KEY=...

# Other optional keys
GEMINI_API_KEY=...
ZHIPUAI_API_KEY=...
MOONSHOT_API_KEY=...
ARK_API_KEY=...
GROK_API_KEY=...
MINIMAX_API_KEY=...
MATHPIX_APPID=...
MATHPIX_APPKEY=...
DOC2X_API_KEY=...
JINA_API_KEY=...
SEMANTIC_SCHOLAR_KEY=...
```

The `~/.env` file is parsed at startup by `shared_utils/config_loader.py`.
Keys already present in the shell environment take precedence over `~/.env`.

### Changed files

- `shared_utils/config_loader.py` — added `_load_dotenv()` that reads `~/.env` at import time;
  added `_LLM_API_KEY_NAMES` set; LLM keys now bypass `config.py`/`config_private.py`.
- `config.py` — all LLM API key fields removed; only non-secret settings remain.

---

## 2. `config.py` Simplified

- Removed all LLM API key fields (see section 1).
- Reduced `AVAIL_LLM_MODELS` to the three first-class providers (OpenAI, Anthropic, Qwen/DashScope, DeepSeek).
- Removed Chinese font options from `AVAIL_FONTS`; kept only generic web-safe fonts.
- Replaced Chinese comments with English throughout.
- Updated `DEFAULT_FN_GROUPS` from `['对话', '编程', '学术', '智能体']`
  to `['chat', 'coding', 'academic', 'agent']`.

---

## 3. Plugin Display Names — Chinese → English

All plugin display names (dictionary keys in `crazy_functional.py`) have been renamed to English.

| Old name (Chinese) | New name (English) |
|---|---|
| 虚空终端 | Void Terminal |
| 解析整个Python项目 | Analyse Python Project |
| 注释Python项目 | Add Docstrings to Python Project |
| 载入对话历史存档… | Load Conversation Archive … |
| 删除所有本地对话历史记录… | Delete All Local Conversation History … |
| 清除所有缓存文件… | Clear All Cache Files … |
| 生成多种Mermaid图表… | Generate Mermaid Diagrams … |
| Arxiv论文翻译 | Translate ArXiv Paper |
| 批量总结Word文档 | Summarise Word Documents (batch) |
| 解析整个Matlab项目 | Analyse Matlab Project |
| 解析整个C++项目头文件 | Analyse C++ Project Headers |
| 解析整个C++项目 | Analyse C++ Project |
| 解析整个Go项目 | Analyse Go Project |
| 解析整个Rust项目 | Analyse Rust Project |
| 解析整个Java项目 | Analyse Java Project |
| 解析整个前端项目… | Analyse Frontend Project (js/ts/css) |
| 解析整个Lua项目 | Analyse Lua Project |
| 解析整个CSharp项目 | Analyse CSharp Project |
| 解析Jupyter Notebook文件 | Analyse Jupyter Notebook |
| 读Tex论文写摘要 | Write Abstract from LaTeX Paper |
| 翻译README或MD | Translate README / Markdown |
| 翻译Markdown或README… | Translate Markdown (GitHub link supported) |
| 批量生成函数注释 | Generate Function Comments (batch) |
| 保存当前的对话 | Save Current Conversation |
| [多线程Demo]解析此项目本身… | [Multi-thread Demo] Analyse This Project … |
| 查互联网后回答 | Web Search then Answer |
| 历史上的今天 | Today in History |
| PDF论文翻译 | Translate PDF Paper |
| 询问多个GPT模型 | Query Multiple LLM Models |
| 批量总结PDF文档 | Summarise PDF Documents (batch) |
| 谷歌学术检索助手… | Google Scholar Assistant … |
| 理解PDF文档内容… | Chat with PDF Document (ChatPDF style) |
| 英文Latex项目全文润色… | Polish English LaTeX Project |
| 中文Latex项目全文润色… | Polish Chinese LaTeX Project |
| 批量Markdown中译英… | Translate Markdown ZH→EN (batch) |
| Latex英文纠错+高亮修正位置… | LaTeX English Proofreading + Diff Highlight … |
| 📚Arxiv论文精细翻译… | 📚 Precise ArXiv Paper Translation … |
| 📚本地Latex论文精细翻译… | 📚 Translate Local LaTeX Paper … |
| PDF翻译中文并重新编译PDF… | Translate PDF and Recompile … |
| 批量文件询问… | Batch Document Q&A … |
| 🎨图片生成… | 🎨 Image Generation … |
| 🎨图片修改_DALLE2… | 🎨 Edit Image with DALLE2 … |
| 一键下载arxiv论文并翻译摘要… | Download ArXiv Paper and Translate Abstract … |
| 解析项目源代码… | Analyse Project (custom file type filter) |
| 询问多个GPT模型（手动指定…） | Query Multiple LLM Models (specify models manually) |
| 批量总结音视频… | Summarise Audio / Video (batch) |
| 数学动画生成… | Math Animation Generator (Manim) |
| Markdown翻译（指定翻译成何种语言） | Translate Markdown (specify target language) |
| 构建知识库… | Build Knowledge Base … |
| 知识库文件注入… | Query Knowledge Base … |
| 实时语音对话 | Real-time Voice Chat |
| 精准翻译PDF文档（NOUGAT） | Translate PDF Document (NOUGAT) |
| 动态代码解释器（CodeInterpreter） | Dynamic Code Interpreter (CodeInterpreter) |
| Rag智能召回 | RAG Smart Recall |
| 速读论文 | Quick Paper Reading |
| 多媒体智能体 | Multimedia Agent |

---

## 4. Plugin Group Names — Chinese → English

| Old | New |
|---|---|
| 对话 | chat |
| 编程 | coding |
| 学术 | academic |
| 智能体 | agent |

---

## 5. Core Function Button Names — Chinese → English

In `core_functional.py`:

| Old key | New key |
|---|---|
| 学术语料润色 | Academic Polish |
| 总结绘制脑图 | Summarize as Mind Map |
| 查找语法错误 | Grammar Check |
| 中译英 | Chinese to English |
| 学术英中互译 | Academic EN<->ZH Translation |
| 英译中 | English to Chinese |
| 找图片 | Find Image |
| 解释代码 | Explain Code |
| 参考文献转Bib | References to BibTeX |

---

## 6. Removed Unused Files

| File | Reason |
|---|---|
| `config_new.py` | Duplicate/unused alternative config — never referenced |

Commented-out legacy plugin blocks in `crazy_functional.py` have also been removed:
- `AutoGenMulti_Agent_Legacy` terminal
- `一键处理文档` document optimizer
- `绘制逻辑关系` diagram renderer

---

## 7. Comments and Strings

All Chinese comments, docstrings, log messages, and inline strings in the following
files have been replaced with English equivalents:

- `shared_utils/config_loader.py`
- `config.py`
- `core_functional.py`
- `crazy_functional.py`

**Note:** Internal Python function names inside `crazy_functions/` plugins (e.g.
`解析一个Python项目`, `批量翻译PDF文档`) are not renamed in this pass because they are
referenced across many files and the plugin logic is unchanged. A follow-up pass can
rename these using Python aliases.

---

## Upgrade Path for Existing Users

1. Move your API keys out of `config_private.py` into `~/.env`.
2. Delete or archive `config_private.py` (it is still loaded for non-secret settings).
3. Restart the application — keys are read from `~/.env` at startup.
