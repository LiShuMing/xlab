---
created: 2026-03-27
topics: [llm, rag, ai-systems]
projects: [py-ego]
review: 2026-03-30
stage: active
---

# RAG Systems

## Overview

Retrieval-Augmented Generation (RAG) enhances LLM responses by retrieving relevant context from a knowledge base before generation.

**Core Problem:** LLMs have knowledge cutoff and can't access private/updated data.

**Solution:** Retrieve relevant documents → Add to context → Generate answer.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
                         RAG Pipeline                          │
├─────────────────────────────────────────────────────────────┤
                                                              │
  Offline: Indexing                                           │
  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐  │
  │ Documents│──▶│  Chunk   │──▶│ Embed    │──▶│  Vector  │  │
  │          │   │  Split   │   │  Model   │   │  Store   │  │
  └──────────┘   └──────────┘   └──────────┘   └──────────┘  │
                                                              │
  Online: Query                                               │
  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐  │
  │  Query   │──▶│  Embed   │──▶│  Vector  │──▶│ Retrieve │  │
  │          │   │  Query   │   │  Search  │   │  Top-K   │  │
  └──────────┘   └──────────┘   └──────────┘   └────┬─────┘  │
                                                     │        │
  ┌──────────┐   ┌──────────┐   ┌──────────┐        │        │
  │  Final   │◀──│   LLM    │◀──│  Prompt  │◀───────┘        │
  │  Answer  │   │ Generate │   │(Query+Ctx)│                 │
  └──────────┘   └──────────┘   └──────────┘                  │
                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. Document Processing

**Chunking Strategies:**

| Strategy | When to Use | Trade-offs |
|----------|-------------|------------|
| Fixed size | Simple docs | May split semantic units |
| Paragraph | Structured text | Better semantic coherence |
| Semantic | Complex docs | Requires understanding |
| Recursive | Hierarchical docs | Preserves structure |

**Best Practices:**
- Chunk size: 200-500 tokens typically
- Overlap: 10-20% to preserve context
- Metadata: Preserve source, section, timestamp

### 2. Embedding Models

**Popular Models:**

| Model | Dimensions | Best For |
|-------|-----------|----------|
| text-embedding-3-small | 1536 | General purpose, cost-effective |
| text-embedding-3-large | 3072 | High quality, higher cost |
| BGE-large | 1024 | Chinese + English |
| E5-large | 1024 | Passage retrieval |
| GTE-large | 1024 | General text embedding |

**Selection Criteria:**
- Language support (English vs multilingual)
- Context length
- Performance on your domain
- Cost (API vs self-hosted)

### 3. Vector Stores

| Store | Type | Best For |
|-------|------|----------|
| Chroma | Embedded | Prototyping, small scale |
| Pinecone | Managed | Production, scale |
| Weaviate | Self-hosted | Complex queries |
| Milvus | Distributed | Large scale |
| pgvector | PostgreSQL | Existing PG infrastructure |
| DuckDB | Embedded | Analytics workloads |

### 4. Retrieval Strategies

**Basic:**
```python
# Pure vector similarity
results = vector_store.similarity_search(query, k=5)
```

**Advanced:**
```python
# Hybrid search: vector + keyword
results = hybrid_search(
    query=query,
    vector_weight=0.7,
    keyword_weight=0.3
)

# Multi-stage: retrieve -> rerank
candidates = vector_store.similarity_search(query, k=20)
results = reranker.rerank(query, candidates, k=5)
```

**Rerankers:**
- Cross-encoders (higher quality, slower)
- Cohere Rerank API
- BGE Reranker

### 5. Context Construction

**Prompt Template:**
```
Answer the question based on the following context:

{context}

Question: {question}

Instructions:
- Answer based only on the provided context
- If the context doesn't contain the answer, say "I don't know"
- Cite the source of your information
```

**Context Window Management:**
- Token budget allocation
- Relevance scoring
- Deduplication
- Truncation strategies

## Evaluation

### Metrics

| Metric | Measures | How to Compute |
|--------|----------|----------------|
| Recall@K | Retrieval coverage | % of relevant docs in top-K |
| MRR | Rank quality | Mean reciprocal rank |
| NDCG | Ranking quality | Discounted cumulative gain |
| Answer relevance | Generation quality | Human or LLM judge |
| Citation accuracy | Faithfulness | Correct source attribution |

### Test Set Creation

```python
# Example QA pairs for evaluation
test_cases = [
    {
        "question": "What is vectorized execution?",
        "ground_truth": "Vectorized execution processes data in batches...",
        "relevant_docs": ["doc1", "doc5"]
    },
    # ...
]
```

## My RAG Projects

### py-ego (Planned)
Personal knowledge assistant using my knowledge base.

**Features:**
- Index all docs/read notes
- Answer questions about my learning
- Suggest connections between notes

**Tech Stack:**
- Embedding: text-embedding-3-small
- Vector Store: Chroma or DuckDB
- LLM: GPT-4 / Claude
- Framework: LangChain or LlamaIndex

## Common Pitfalls

| Pitfall | Solution |
|---------|----------|
| Chunk too large | Smaller chunks, better retrieval |
| No metadata filtering | Add source, date, type metadata |
| Single retrieval | Multi-stage: retrieve + rerank |
| No evaluation | Build test set early |
| Ignoring citations | Require source attribution |

## Connections

### Related Topics
- [LLM Fundamentals](./llm-fundamentals.md)
- [Vector Search](./vector-search.md)
- [Prompt Engineering](./prompt-engineering.md)

### Projects
- [py-ego](../build/py-ego.md) - Personal RAG assistant
- [py-radar](../build/py-radar.md) - Data source for RAG

### Readings
- [RAG Survey Paper](../read/papers/rag-survey.md)
- [LlamaIndex Docs](../read/code/llamaindex/)
- [LangChain RAG Tutorial](../read/articles/langchain-rag.md)

## Resources

### Papers
- Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks
- Dense Passage Retrieval for Open-Domain QA

### Code
- [LangChain RAG](https://python.langchain.com/docs/use_cases/question_answering/)
- [LlamaIndex](https://docs.llamaindex.ai/)
- [RAGFlow](https://github.com/infiniflow/ragflow)

## Review Log
- 2026-03-27: Created, based on learning plan Phase 2
