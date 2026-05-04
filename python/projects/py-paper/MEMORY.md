## 项目定位
py-paper 是一个 CLI-first 的论文阅读与分析工具，核心产物为 `paper-agent` CLI。目标是将单篇学术论文 PDF 自动转换为结构化分析报告，面向工程师、研究者与技术调研场景。

## 核心能力链
PDF 解析（PyMuPDF）→ 章节感知文本分块 → BM25+FAISS 混合检索索引 → LLM 结构化抽取（背景/问题/创新点/方法/实验/结果/局限性）→ 证据绑定（结论与原文段落可追溯引用）→ Related Work 扩展 → 多模板报告生成（summary/deep-dive/blog/group-talk/interview-note）。

## CLI 命令体系
基于 typer 子命令模式：`parse`（仅PDF解析）、`analyze`（完整分析流程）、`ask`（带引用问答）、`report`（多风格报告生成）、`related`（单独related work扩展）。

## 技术栈
Python ≥ 3.11，pydantic v2 数据校验，structlog 结构化日志，tenacity 重试，rich 终端美化，ruff+mypy --strict 代码质量。LLM 支持 Anthropic 和 OpenAI 双后端，prompt 模板外置。

## 设计原则
严格类型标注、数据驱动（Pydantic）、关注点分离（确定性逻辑与LLM非确定性交互严格分离）、可观测性优先（结构化日志+上下文追踪+LLM I/O全量记录）、优雅降级（LLM失败重试与回退）。

## 模块架构
cli/（命令入口）、core/（配置/状态/Pipeline执行器/路径管理）、parser/（PDF解析/章节检测/分块）、extraction/（骨架抽取/声明提取/证据绑定）、qa/（检索器/问答）、report/（模板渲染）、llm/（客户端封装）、utils/（日志/异常/IO工具）。

## 当前状态
MVP 架构搭建完成，模块骨架和核心代码文件已就位，pyproject.toml 已配置依赖和构建，入口命令 paper-agent 已注册。处于待联调验证阶段。memory/ 目录为空，记忆系统尚未开始沉淀。
