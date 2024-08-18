---
name: personal-knowledge-base
description: Use when managing personal learning materials, code labs, and research notes across multiple programming languages and AI projects. Use when feeling overwhelmed by scattered notes, struggling to connect learning with projects, or needing to build a systematic knowledge retention system.
---

# Personal Knowledge Base Management

## Overview

A systematic approach to managing multi-language learning labs, AI research, and project-driven knowledge accumulation. Transform scattered notes into a searchable, interconnected knowledge graph that supports both quick capture and deep learning.

**Core Principle:** Every piece of knowledge should have a clear entry point, contextual connections, and a path to practical application.

## When to Use

**Use this skill when:**
- Starting a new learning topic (language, framework, research area)
- Reading technical articles, papers, or source code
- Building personal projects and want to capture learnings
- Reviewing past notes to prepare for interviews or deep dives
- Feeling "I know I read something about this but can't find it"

**Don't use for:**
- Temporary scratch notes (use a scratchpad first, then migrate)
- Work-related confidential materials (keep in company systems)
- Purely personal non-technical content

## Knowledge Base Structure

```
xlab/
├── cc/                    # Language labs: code + learning notes
├── python/
├── java/
├── go/
├── rust/
├── docs/                  # Knowledge center
│   ├── _index/           # 🔗 Entry points and maps
│   ├── learn/            # 📚 Structured learning paths
│   ├── read/             # 📖 Reading notes (papers, code, articles)
│   ├── build/            # 🛠️ Project documentation
│   └── meta/             # 🧠 Thinking patterns and reflections
└── _templates/           # Reusable templates
```

## Quick Reference: Knowledge Capture Workflow

| Scenario | Action | Destination |
|----------|--------|-------------|
| Quick bookmark | Save URL + 1-line summary | `docs/read/inbox.md` |
| Article deep read | Structured notes + key takeaways | `docs/read/{topic}/` |
| Code reading | Architecture notes + key files | `docs/read/code/{project}/` |
| Project start | Project doc linking to relevant notes | `docs/build/{project}/` |
| Learning milestone | Synthesis doc connecting concepts | `docs/learn/{topic}/` |
| Weekly review | Update index, tag connections | `docs/_index/` |

## Core Patterns

### Pattern 1: Inbox-First Capture

**Problem:** Perfect note-taking systems prevent capturing.

**Solution:** Use an inbox for quick capture, process regularly.

```markdown
<!-- docs/read/inbox.md -->
# Reading Inbox

## 2026-03-27
- [ ] https://example.com/article - "Interesting approach to vectorization"
  - Source: Twitter
  - Context: Working on query engine optimization
  - Action: Read and take structured notes

## Processing Rules
- Process inbox weekly
- Each item: capture to proper location OR discard
- Empty inbox = clear mental space
```

### Pattern 2: Three-Layer Notes

**Problem:** Notes are either too shallow or too verbose.

**Solution:** Three layers for different depths.

```
Layer 1: Index Entry (30 seconds)
  "Read: Article about X. Key insight: Y."

Layer 2: Structured Notes (10 minutes)
  ## Article Title
  - Problem:
  - Solution:
  - Key insights:
  - Open questions:

Layer 3: Deep Synthesis (1+ hours)
  ## Concept Integration
  Connect to existing knowledge, create examples,
  identify gaps, plan experiments
```

### Pattern 3: Project-Driven Knowledge

**Problem:** Learning and projects are disconnected.

**Solution:** Every project has a knowledge map.

```markdown
<!-- docs/build/py-radar/README.md -->
# py-radar Project

## Overview
Personal data radar for monitoring various data sources.

## Knowledge Dependencies
- [Python async patterns](../../learn/python-async.md)
- [Data pipeline design](../../learn/data-pipelines.md)
- [Reading: Apache Airflow](../../read/code/airflow/)

## Key Decisions
| Decision | Context | Linked Notes |
|----------|---------|--------------|
| Use asyncio | High concurrency needed | python-async.md |
| SQLite for storage | Simplicity over scale | database-choice.md |

## Learnings
- What worked:
- What didn't:
- Next iteration:
```

### Pattern 4: Spaced Review System

**Problem:** Read once, forget forever.

**Solution:** Tag notes with review schedule.

```markdown
<!-- In note frontmatter -->
---
created: 2026-03-27
review: 2026-03-30  # First review: 3 days
stage: active       # active -> review -> archived
connections:
  - "../../learn/query-optimization.md"
  - "../code/clickhouse/vectorized-execution.md"
---

## Review Log
- 2026-03-30: Reviewed, added connection to X
- 2026-04-27: Second review, still relevant
```

## Implementation: Creating a New Learning Entry

### Step 1: Quick Capture (Inbox)
```markdown
<!-- docs/read/inbox.md -->
- [ ] https://arrow.apache.org/docs/format/Columnar.html
  - Topic: Columnar format for query engines
  - Source: Arrow documentation
  - Project context: py-toydb
```

### Step 2: Structured Notes
```markdown
<!-- docs/read/formats/arrow-columnar.md -->
---
created: 2026-03-27
topics: [storage, columnar, arrow]
projects: [py-toydb]
review: 2026-03-30
---

# Apache Arrow Columnar Format

## Why It Matters
Standard for in-memory columnar data - relevant for query engine design.

## Key Concepts
- **Columnar layout**: Contiguous memory per column
- **Null handling**: Validity bitmaps
- **Nested types**: Struct arrays, list arrays

## Relevance to My Projects
- py-toydb: Could use for result serialization
- Query engine: Understanding memory layout helps optimization

## Open Questions
- [ ] How does Arrow compare to proprietary columnar formats?
- [ ] Performance implications of validity bitmaps?

## Connections
- See also: [DuckDB storage](../../code/duckdb/storage.md)
- Related: [Columnar vs row storage](../../learn/columnar-storage.md)
```

### Step 3: Update Index
```markdown
<!-- docs/_index/storage-formats.md -->
# Storage Formats Index

## Columnar Formats
| Format | Source | Status | Key Learning |
|--------|--------|--------|--------------|
| Arrow | Apache | Read | Standard for in-memory |
| Parquet | Apache | TODO | On-disk columnar |
| ORC | Hive | TODO | Hadoop ecosystem |

## Code References
- [DuckDB storage implementation](../read/code/duckdb/)
- [ClickHouse MergeTree](../read/code/clickhouse/mergetree.md)
```

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Over-organizing before capturing | Use inbox, organize later |
| Perfect notes that never get written | Layer 1 first, expand if needed |
| No connections between notes | Always add "Connections" section |
| No review mechanism | Set review dates, use stage tags |
| Separating code and docs | Keep together, link liberally |

## Red Flags - STOP and Reassess

- Creating complex folder structures before adding content
- Spending more time organizing than learning
- Notes without any connections to other notes
- "I'll organize this later" (do it now or use inbox)
- Duplicating information instead of linking

## Weekly Review Checklist

- [ ] Inbox is empty (processed or discarded)
- [ ] New notes have connections added
- [ ] Review due notes are reviewed
- [ ] Project docs link to relevant learnings
- [ ] Index files are updated

## Real-World Impact

**Before:**
- 25 database projects in `reading-open-source/` with no reading progress
- Articles bookmarked but forgotten
- Projects built without leveraging prior learning
- "I know I read about this..." moments

**After:**
- Clear learning paths from capture to synthesis
- Notes interconnected by topic, project, and concept
- Regular review reinforces long-term retention
- Projects naturally build on accumulated knowledge
