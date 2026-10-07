"""Deterministic extracts and traceable draft scaffolds; no remote model calls."""

from __future__ import annotations

import re
from typing import Any

TOPICS = [
    {
        "id": "database",
        "name": "数据库与系统",
        "color": "yellow",
        "keywords": ["数据库", "join", "spill", "算子", "存储", "rust", "hash", "sql"],
    },
    {
        "id": "ai",
        "name": "AI 与工具",
        "color": "blue",
        "keywords": ["ai", "llm", "模型", "agent", "prompt", "人工智能"],
    },
    {
        "id": "thinking",
        "name": "思考与方法",
        "color": "pink",
        "keywords": ["知识", "学习", "写作", "复习", "方法", "笔记", "思考"],
    },
]


def classify(content: str) -> str:
    lower = content.lower()
    scores = [sum(lower.count(word) for word in topic["keywords"]) for topic in TOPICS]
    return TOPICS[scores.index(max(scores))]["id"] if max(scores) else "thinking"


def excerpts(content: str, limit: int = 3) -> list[dict[str, Any]]:
    candidates = []
    fence: tuple[str, int] | None = None
    for number, line in enumerate(content.splitlines(), 1):
        match = re.match(r"^\s{0,3}(`{3,}|~{3,})(.*)$", line)
        if match:
            marker, tail = match.groups()
            if fence is None:
                fence = (marker[0], len(marker))
            elif marker[0] == fence[0] and len(marker) >= fence[1] and not tail.strip():
                fence = None
            continue
        clean = line.strip()
        if (
            fence
            or line.startswith(("    ", "\t"))
            or clean.startswith(("#", "---", "|", "http"))
            or len(clean) < 12
        ):
            continue
        clean = re.sub(r"^(?:>\s+|[-*]\s+|\d+\.\s+)", "", clean)
        candidates.append({"text": clean[:360], "line": number})
    return candidates[:limit]


def digest(content: str) -> dict[str, Any]:
    quotes = excerpts(content)
    return {
        "mode": "extractive",
        "quality_state": "has_excerpts" if quotes else "no_excerpts",
        "excerpts": quotes,
        "summary": quotes[0]["text"] if quotes else "素材已归档，正文尚不足以整理出摘录。",
        "questions": ["这份材料解决了什么问题？", "哪些结论值得用自己的例子验证？"],
    }


def blog_body(title: str, materials: list[dict[str, Any]]) -> str:
    paragraphs = [
        f"# {title}",
        "",
        "> 基于原始素材的写作框架。请补充个人理解与实验；尚未使用 AI 扩写。",
        "",
        "## 我想回答的问题",
        "",
        "在这里写下你真正想解释的问题，以及它为什么值得讨论。",
        "",
        "## 素材给出的线索",
        "",
    ]
    for material in materials:
        paragraphs += [f"### {material['title']}", ""]
        for quote in material.get("digest", {}).get("excerpts", []):
            paragraphs += [f"> {quote['text']}", ""]
        paragraphs += [
            f"[查看原始素材](#/materials/{material['id']}?revision={material['revision']})",
            "",
        ]
    paragraphs += [
        "## 我的理解",
        "",
        "待补充：用自己的话说明机制、条件与判断。",
        "",
        "## 例子与验证",
        "",
        "待验证：列出可以复现的例子，不填写未测量的结果。",
        "",
        "## 边界与下一步",
        "",
        "待补充：哪些条件会让结论失效？下一步要读什么或做什么？",
    ]
    return "\n".join(paragraphs)
