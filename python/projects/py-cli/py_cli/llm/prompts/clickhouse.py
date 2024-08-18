"""ClickHouse-specific analysis prompt."""

from __future__ import annotations

SYSTEM_PROMPT = """You are a senior database kernel engineer with deep expertise in ClickHouse internals, C++ systems programming, and distributed OLAP architecture.

Your task is to analyze ClickHouse Git commits and produce a structured technical report. When analyzing commits, you must:

1. Classify each commit by subsystem: Storage Engine, Query Execution, MergeTree, Replication, Network/Protocol, Parser/AST, Functions/Operators, DDL, Configuration, Testing, Build System, Documentation

2. Identify the engineering motivation: bug fix, performance optimization, new feature, refactoring, correctness fix, compatibility, security

3. For non-trivial commits, explain the BEFORE vs AFTER behavior at the code level

4. Focus on areas critical to OLAP systems:
   - Query optimizer changes
   - Execution engine improvements
   - Storage layer modifications
   - Metadata/catalog management
   - Concurrency and locking
   - Memory management
   - Replication and distributed coordination
   - External integrations

Output must be in Chinese. Use precise technical terminology. Avoid vague summaries — ground every conclusion in specific file paths, function names, or data structure changes visible in the diff."""

USER_PROMPT_TEMPLATE = """请对 ClickHouse (或类似的数据库/查询引擎) 最近 {time_range} 的 Git Commits 进行深度源码级分析，并生成结构化汇总报告。

仓库: {repo_name}

## 整体统计
- 总提交数: {total_commits}
- 作者: {authors}
- 变更文件: {files_changed}
- 新增行数: {additions}
- 删除行数: {deletions}

## 提交详情

{commit_details}

## 分析要求

请按照以下结构输出报告：

### 一、整体统计
- 按子系统分布的提交数量
- 按工程意图分类的统计
- 最活跃的贡献者

### 二、重点 Commit 深度解析 (Top 10-15)
每条包含：
- Commit SHA、作者、日期
- 变更模块定位 (精确到子目录)
- 源码级变更分析 (修改前 vs 修改后)
- 工程意图分类
- 影响面评估

### 三、子系统专题分析
1. **存储引擎 & MergeTree**: Part 管理、Merge 策略、索引结构变化
2. **查询执行引擎**: Pipeline/Processor 改动、向量化执行优化、内存管理
3. **复制 & 分布式协调**: ReplicatedMergeTree、Keeper/ZooKeeper 交互变更
4. **SQL 解析 & 函数层**: Parser、AST、内置函数、聚合函数变更
5. **网络层 & 协议**: HTTP/Native 协议、连接管理、序列化

### 四、趋势与工程洞察
- 本月核心优化方向
- 潜在 Breaking Changes 或兼容性风险
- 值得借鉴的设计决策

### 五、附录
- 完整 Commit 列表

输出语言：中文，技术术语保留英文原名
代码引用使用 ```cpp 代码块
每个重点 commit 分析不少于 100 字"""


def format_commit_details(commits: list[dict]) -> str:
    """Format commit details for the prompt.

    Args:
        commits: List of commit dictionaries

    Returns:
        Formatted commit details string
    """
    lines = []
    for commit in commits:
        lines.extend(
            [
                f"### {commit.get('short_sha', 'unknown')} - {commit.get('author', 'unknown')}",
                f"日期: {commit.get('date', 'unknown')}",
                f"提交信息: {commit.get('message', 'no message')}",
                f"文件: {', '.join(commit.get('files_changed', [])[:15])}",
            ]
        )
        if len(commit.get("files_changed", [])) > 15:
            lines.append(f"... 还有 {len(commit['files_changed']) - 15} 个文件")

        diff_preview = commit.get("diff", "")[:3000]
        if diff_preview:
            lines.extend(
                [
                    "",
                    "Diff 预览:",
                    "```cpp",
                    diff_preview,
                    "..." if len(commit.get("diff", "")) > 3000 else "",
                    "```",
                ]
            )
        lines.append("")

    return "\n".join(lines)
