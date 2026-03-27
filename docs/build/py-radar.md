# py-radar Project

## Overview

A deterministic, extensible system for collecting and summarizing DB/OLAP industry updates from curated sources.

**Inspiration:** https://database.news/

## Goals

1. **信息聚合** - 自动收集数据库行业新闻、Release Notes、技术博客
2. **AI摘要** - 使用LLM生成内容摘要，快速了解要点
3. **Web展示** - Hacker News风格的界面，按日期浏览
4. **数据持久化** - 使用DuckDB存储，支持历史查询

## Knowledge Dependencies

### Python技术
- [Python Async Patterns](../learn/python-async.md)
- [DuckDB Usage](../learn/duckdb-usage.md)
- [Flask Web Development](../learn/flask-web-dev.md)
- [RSS/Feed Parsing](../learn/rss-parsing.md)

### AI/LLM
- [LLM API Integration](../learn/llm-api-integration.md)
- [Prompt Engineering](../learn/prompt-engineering.md)
- [Background Task Processing](../learn/background-tasks.md)

### 系统设计
- [Data Pipeline Design](../learn/data-pipelines.md)
- [Content Classification](../learn/content-classification.md)
- [Web UI Patterns](../learn/web-ui-patterns.md)

## Key Decisions

| Decision | Context | Alternatives | Linked Notes |
|----------|---------|--------------|--------------|
| DuckDB for storage | 简单高效，支持SQL查询 | SQLite, PostgreSQL | [DuckDB vs SQLite](../learn/duckdb-vs-sqlite.md) |
| ThreadPool for LLM | I/O密集型任务，控制并发 | asyncio, Celery | [Concurrency Patterns](../learn/concurrency-patterns.md) |
| Flask for web | 轻量，快速开发 | FastAPI, Django | [Flask Patterns](../learn/flask-patterns.md) |
| HN-style UI | 简洁，信息密度高 | 自定义设计 | [UI Design Patterns](../learn/ui-design.md) |

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Sources   │────▶│   Fetcher   │────▶│   Parser    │
│ (RSS/Feeds) │     │  (async)    │     │(classifier) │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
┌─────────────┐     ┌─────────────┐           │
│    Web UI   │◀────│   Server    │◀──────────┘
│  (Flask)    │     │  (Flask)    │
└─────────────┘     └──────┬──────┘
                           │
                    ┌──────┴──────┐
                    │   DuckDB    │
                    │  (storage)  │
                    └─────────────┘
                           ▲
                    ┌──────┴──────┐
                    │  Background │
                    │  Summarizer │
                    │  (LLM)      │
                    └─────────────┘
```

## Learnings

### What Worked
- DuckDB简化了数据查询和统计
- ThreadPool控制LLM并发，避免API限流
- HN风格UI开发快速，用户体验好
- 背景摘要生成提升浏览效率

### What Didn't
- 初始JSON存储难以查询，迁移到DuckDB
- 需要更好的去重机制（URL+标题hash）
- 摘要质量依赖Prompt，需要调优

### Open Questions
- [ ] 如何自动发现新的数据源？
- [ ] 是否支持用户自定义关注主题？
- [ ] 如何评估摘要质量？

## Code

- **Location:** [../../python/projects/py-radar/](../../python/projects/py-radar/)
- **Main Module:** `dbradar/`
- **Tests:** `tests/`
- **Data:** `data/items.duckdb`

## Related Projects

- [py-ego](./py-ego.md) - 个人知识助手（可消费radar数据）
- [py-paper](./py-paper.md) - 论文管理

## Resources

- [DuckDB Documentation](https://duckdb.org/docs/)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [Feedparser Library](https://feedparser.readthedocs.io/)

## Changelog

See [../../python/projects/py-radar/CHANGE_LOGS.md](../../python/projects/py-radar/CHANGE_LOGS.md)
