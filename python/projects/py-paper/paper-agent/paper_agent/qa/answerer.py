"""Answer questions about a paper with citations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from paper_agent.llm.client import LLMClient
from paper_agent.utils.logging import get_logger

logger = get_logger(__name__)

_PROMPT_FILE = Path(__file__).parent.parent / "llm" / "prompts" / "qa_answer.txt"


def answer_question(
    question: str,
    chunks: list[dict[str, Any]],
    schema: dict[str, Any],
    evidence: list[dict[str, Any]],
    llm: LLMClient,
) -> dict[str, Any]:
    """
    Answer a question given retrieved chunks and paper schema.

    Returns:
        {
            "answer": str,
            "citations": [{"chunk_id": str, "pages": list[int], "section": str}]
        }
    """
    system_prompt = _PROMPT_FILE.read_text() if _PROMPT_FILE.exists() else _DEFAULT_SYSTEM

    context = _format_context(chunks)
    schema_summary = _format_schema_summary(schema)

    prompt = f"""Here is the paper's structured summary:

<paper_summary>
{schema_summary}
</paper_summary>

Here are the most relevant paper sections:

<context>
{context}
</context>

Question: {question}

Answer the question based on the paper content above. Include specific page numbers and chunk IDs as citations.
Format your response as:

ANSWER:
<your detailed answer here>

CITATIONS:
- chunk_id: <id>, pages: <pages>, section: <section>
"""

    logger.info("answering_question", question=question[:80])
    raw = llm.complete(prompt, system=system_prompt, max_tokens=2000)

    return _parse_answer(raw, chunks)


def _format_context(chunks: list[dict[str, Any]]) -> str:
    parts = []
    for c in chunks:
        cid = c.get("chunk_id", "")[:8]
        sec = c.get("section", c.get("section_normalized", ""))
        pages = f"p{c['page_start']}-{c['page_end']}"
        parts.append(f"[{cid} | {sec} | {pages}]\n{c['text'][:600]}")
    return "\n\n".join(parts)


def _format_schema_summary(schema: dict[str, Any]) -> str:
    lines = [
        f"Title: {schema.get('title', '')}",
        f"Problem: {schema.get('problem_statement', '')}",
        "Contributions:",
    ]
    for c in schema.get("main_contributions", [])[:3]:
        text = c.get("text", c) if isinstance(c, dict) else str(c)
        lines.append(f"  - {text}")
    return "\n".join(lines)


def _parse_answer(raw: str, chunks: list[dict[str, Any]]) -> dict[str, Any]:
    """Parse LLM output into structured answer + citations."""
    answer = raw
    citations = []

    if "ANSWER:" in raw and "CITATIONS:" in raw:
        parts = raw.split("CITATIONS:", 1)
        answer_part = parts[0].replace("ANSWER:", "").strip()
        cit_part = parts[1].strip() if len(parts) > 1 else ""

        answer = answer_part

        # Build chunk lookup
        chunk_map = {c["chunk_id"][:8]: c for c in chunks}

        for line in cit_part.splitlines():
            line = line.strip("- ").strip()
            if not line:
                continue
            # Try to extract chunk_id
            import re
            cid_match = re.search(r"chunk_id:\s*([a-f0-9]+)", line)
            pages_match = re.search(r"pages?:\s*([\d,\s]+)", line)
            sec_match = re.search(r"section:\s*(.+?)(?:,|$)", line)

            cit: dict[str, Any] = {}
            if cid_match:
                cid = cid_match.group(1)[:8]
                cit["chunk_id"] = cid
                if cid in chunk_map:
                    c = chunk_map[cid]
                    cit["pages"] = list(range(c["page_start"], c["page_end"] + 1))
                    cit["section"] = c.get("section", "")
            if pages_match and "pages" not in cit:
                raw_pages = pages_match.group(1)
                cit["pages"] = [int(p.strip()) for p in raw_pages.split(",") if p.strip().isdigit()]
            if sec_match and "section" not in cit:
                cit["section"] = sec_match.group(1).strip()
            if cit:
                citations.append(cit)
    elif "ANSWER:" in raw:
        answer = raw.split("ANSWER:", 1)[1].strip()

    return {"answer": answer, "citations": citations}


_DEFAULT_SYSTEM = """You are a scientific paper reading assistant. Answer questions about papers accurately and concisely.
- Base answers strictly on the provided context
- Always cite specific page numbers and sections
- If the answer is not in the context, say so clearly
- Distinguish between what the authors claim vs what you infer
"""
