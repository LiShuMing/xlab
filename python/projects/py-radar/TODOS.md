# TO-FIX

(No pending issues)

---

# FIXED

- ✅ 支持 feeds.json 格式订阅源（2026-03-23）
  - 新增 `dbradar/feeds.py` 模块，定义 `FeedSource` 数据类
  - 更新 `config.py` 将 `website_file` 改为 `feeds_file`
  - 更新 `fetcher.py` 支持 `FeedSource` 类型
  - CLI 改用 `--feeds-file` 参数，默认检测 `./feeds.json`
  - 新增 `dbradar/templates/briefing.html.j2` HTML 模板
  - 默认采用 feeds.json，抛弃原来 websites.txt 的实现

- ✅ 个性化 HTML Briefing 功能实现（2026-03-23）

- ✅ 确认 ~/.env 中的 Google/News API 配置是否 work
  - 新增 `dbradar check` 命令，用于验证所有 API 配置
  - 各 API 添加 `validate()` 方法进行实际连通性测试
  - 测试结果：NewsAPI ✓ 正常，Google API Key 需检查

- ✅ 中文输出的结果太松散，没有英文的内容翔实；修复方案：在 llm 调用层面统一用英文输出，再使用 llm 将英文转成中文；实现方式：
  - `Summarizer._build_prompt()` 现在始终使用英文生成内容
  - 新增 `Summarizer._translate_to_chinese()` 方法，将英文结果翻译成中文
  - 新增 `Summarizer._translate_update_to_chinese()` 和 `_translate_release_note_to_chinese()` 用于翻译嵌套结构
  - 当 `language="zh"` 时，先生成英文摘要，然后自动调用翻译流程

- ✅ 个性化 HTML Briefing 功能实现（2026-03-23）
  - 新增 `dbradar/interests.py` 模块，支持 `interests.yaml` 配置
  - 更新 `ranker.py` 支持产品权重和关键词加权
  - 新增 `writer.py` 支持 HTML 输出（Jinja2 模板）
  - CLI 新增 `--html`, `--open`, `--interests-file` 参数
  - HTML 输出包含：score bars、boosted badges、兴趣配置 sidebar
