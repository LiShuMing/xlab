
# TO-FIX
- 除了各个web指定的url之外，可以丰富调用news/google其他api获取更多的关于产品/keywords更多的信息，保障输出内容的高质量及价值。实现方式：
  - 新增 `enhanced_sources.py` 模块，支持 Google Custom Search API 和 NewsAPI
  - `GoogleSearchSource`: 使用 Google Custom Search 搜索产品相关新闻
  - `NewsAPISource`: 使用 NewsAPI 获取产品相关新闻
  - `EnhancedSourceManager`: 统一管理增强数据源
  - 在 CLI 的 `run` 和 `fetch` 命令中自动检测并使用配置好的增强数据源
  - 环境变量配置: `GOOGLE_API_KEY` + `GOOGLE_CX` 或 `NEWSAPI_KEY`


# FIXED
- ✅ 确认 ~/.env 中的 Google/News API 配置是否 work
  - 新增 `dbradar check` 命令，用于验证所有 API 配置
  - 各 API 添加 `validate()` 方法进行实际连通性测试
  - 测试结果：NewsAPI ✓ 正常，Google API Key 需检查
  
- ✅ 中文输出的结果太松散，没有英文的内容翔实；修复方案：在llm调用层面统一用英文输出，再使用llm将英文转成中文；实现方式：
  - `Summarizer._build_prompt()` 现在始终使用英文生成内容
  - 新增 `Summarizer._translate_to_chinese()` 方法，将英文结果翻译成中文
  - 新增 `Summarizer._translate_update_to_chinese()` 和 `_translate_release_note_to_chinese()` 用于翻译嵌套结构
  - 当 `language="zh"` 时，先生成英文摘要，然后自动调用翻译流程