# 知识库迁移指南

## 迁移状态

| 目录 | 状态 | 行动 |
|------|------|------|
| `docs/_index/` | ✅ 已创建 | 新增索引系统 |
| `docs/learn/` | ✅ 已创建 | 迁移学习计划 |
| `docs/read/` | 🔄 待迁移 | 整合阅读笔记 |
| `docs/build/` | 🔄 待创建 | 为每个项目创建文档 |
| `docs/meta/` | 🔴 待创建 | 思考模式、反思笔记 |
| `_templates/` | ✅ 已创建 | 模板文件 |

## 迁移步骤

### 1. 整合现有阅读笔记

**Source:** `docs/reading-open-source/`, `docs/reading-papers/`, `docs/reading-websites/`

**Target:** `docs/read/`

**操作:**
```bash
# 示例：迁移 ClickHouse 阅读笔记
mkdir -p docs/read/code/clickhouse
cp docs/reading-open-source/clickhouse/notes.md docs/read/code/clickhouse/

# 添加 frontmatter 和 connections
```

### 2. 为活跃项目创建文档

**Target:** `docs/build/{project-name}/README.md`

**优先项目:**
- [ ] py-radar
- [ ] py-ego
- [ ] py-toydb
- [ ] query-engine (C++)

### 3. 创建学习主题笔记

**Target:** `docs/learn/{topic}.md`

**优先主题:**
- [ ] Vectorized Execution
- [ ] Query Optimization
- [ ] RAG Systems
- [ ] LLM Inference

### 4. 更新索引

每次新增笔记后，更新相关索引文件：
- `docs/_index/databases.md`
- `docs/_index/ai-llm.md`
- `docs/_index/projects.md`

## 使用新技能的工作流程

### 场景 1: 发现一篇好文章

```bash
# 1. 快速捕获到 inbox
echo "- [ ] https://example.com/article" >> docs/_index/inbox.md

# 2. 阅读后创建结构化笔记
mkdir -p docs/read/articles
cp _templates/reading-note.md docs/read/articles/article-name.md
# 填写内容

# 3. 更新索引
# 在 docs/_index/ai-llm.md 或相关索引中添加链接

# 4. 设置复习日期
# 在 frontmatter 中设置 review: YYYY-MM-DD
```

### 场景 2: 启动新项目

```bash
# 1. 创建项目文档目录
mkdir -p docs/build/my-new-project
cp _templates/project-readme.md docs/build/my-new-project/README.md

# 2. 填写项目信息，链接相关知识

# 3. 更新项目索引
# 在 docs/_index/projects.md 中添加
```

### 场景 3: 深入学习一个主题

```bash
# 1. 创建学习笔记
cp _templates/learning-note.md docs/learn/topic-name.md

# 2. 整合多个阅读笔记的内容

# 3. 添加实现示例和项目链接

# 4. 更新相关索引
```

## 定期维护

### 每周
- [ ] 清空 inbox
- [ ] 复习到期的笔记
- [ ] 更新项目状态

### 每月
- [ ] 归档不再活跃的笔记
- [ ] 更新索引中的链接
- [ ] 检查项目-知识连接

## 技能使用

使用 `/superpowers:personal-knowledge-base` 技能获取完整指南。
