# TO-FIX
- 将该项目refactor，再保障当前核心逻辑不变的情况(辅助阅读论文),主要改造内容：
    - 去重没有用的codes
    - 使用~/.env下的llm api配置，不再支持llm配置化
    - 在代码中红不要使用中文，符合现代python语言的规范
- 注意在改造的过程，请教改造变更事项最好用markdown文件保留主要变更逻辑

# FIXED
- Refactored project (2026-03-22):
    - Removed unused code: `config_new.py`, commented-out legacy plugins
    - LLM API keys now loaded exclusively from `~/.env` — see `CHANGES.md`
    - Chinese → English: plugin names, group names, core function names, comments in `config.py`, `core_functional.py`, `crazy_functional.py`, `shared_utils/config_loader.py`
    - All changes documented in `CHANGES.md`