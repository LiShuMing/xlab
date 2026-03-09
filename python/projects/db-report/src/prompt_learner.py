"""Prompt learner: scans Markdown files and extracts meta-prompt blocks."""
from __future__ import annotations

import json
import re
import logging
from datetime import datetime, timezone
from pathlib import Path

import structlog

log = structlog.get_logger()

REFERENCE_DOCS_PATH = Path("/home/lism/work/xlab/docs/reading-open-source")
PROMPTS_OUTPUT_PATH = Path("prompts/learned_prompts.json")
MAX_LINES = 300
SCHEMA_VERSION = "1.0"


def _read_first_lines(path: Path, max_lines: int = MAX_LINES) -> list[str]:
    """Read first max_lines lines from a file."""
    lines: list[str] = []
    try:
        with path.open(encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                if i >= max_lines:
                    break
                lines.append(line.rstrip("\n"))
    except OSError as exc:
        log.warning("cannot_read_file", path=str(path), error=str(exc))
    return lines


def _find_first_heading_index(lines: list[str]) -> int:
    """Return index of first # or ## heading line, or len(lines) if none."""
    for i, line in enumerate(lines):
        if re.match(r"^#{1,2}\s", line):
            return i
    return len(lines)


def _extract_yaml_front_matter(lines: list[str]) -> tuple[str, list[int]] | None:
    """Extract YAML front matter (--- ... ---)."""
    if not lines or lines[0].strip() != "---":
        return None
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return None
    text = "\n".join(lines[1:end])
    return text, [1, end + 1]


def _extract_fenced_prompt(lines: list[str]) -> tuple[str, list[int]] | None:
    """Extract ```prompt ... ``` fenced block."""
    start = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped in ("```prompt", "~~~prompt"):
            start = i
            fence = stripped[:3]
            break
        # stop at first heading if no fenced block found before it
        if re.match(r"^#{1,2}\s", line):
            return None
    if start is None:
        return None
    end = None
    for i in range(start + 1, len(lines)):
        if lines[i].strip() in (fence, fence + "prompt"):
            end = i
            break
    if end is None:
        return None
    text = "\n".join(lines[start + 1:end])
    return text, [start + 1, end + 1]


def _extract_blockquote(lines: list[str]) -> tuple[str, list[int]] | None:
    """Extract contiguous blockquote lines at the very top."""
    heading_idx = _find_first_heading_index(lines)
    pre_heading = lines[:heading_idx]
    # skip blank lines at start
    start = 0
    while start < len(pre_heading) and not pre_heading[start].strip():
        start += 1
    if start >= len(pre_heading) or not pre_heading[start].startswith(">"):
        return None
    end = start
    while end < len(pre_heading) and (pre_heading[end].startswith(">") or not pre_heading[end].strip()):
        end += 1
    block = [l for l in pre_heading[start:end] if l.strip()]
    if not block:
        return None
    text = "\n".join(block)
    return text, [start + 1, end + 1]


def _extract_html_comment(lines: list[str]) -> tuple[str, list[int]] | None:
    """Extract <!-- prompt: ... --> HTML comment block."""
    heading_idx = _find_first_heading_index(lines)
    pre = "\n".join(lines[:heading_idx])
    m = re.search(r"<!--\s*prompt:\s*(.*?)-->", pre, re.DOTALL)
    if not m:
        return None
    text = m.group(1).strip()
    # find line range
    before = pre[:m.start()]
    start_line = before.count("\n")
    end_line = start_line + m.group(0).count("\n")
    return text, [start_line + 1, end_line + 1]


def _extract_paragraph(lines: list[str]) -> tuple[str, list[int]] | None:
    """Extract first contiguous non-empty paragraph before the first heading."""
    heading_idx = _find_first_heading_index(lines)
    pre_heading = lines[:heading_idx]
    # find first non-empty line
    start = 0
    while start < len(pre_heading) and not pre_heading[start].strip():
        start += 1
    if start >= len(pre_heading):
        return None
    end = start
    while end < len(pre_heading) and pre_heading[end].strip():
        end += 1
    text = "\n".join(pre_heading[start:end])
    return text, [start + 1, end + 1]


def _normalize(text: str) -> str:
    """Normalize whitespace in extracted text."""
    # collapse multiple blank lines, strip leading/trailing whitespace
    lines = text.splitlines()
    result: list[str] = []
    blank_run = 0
    for line in lines:
        if not line.strip():
            blank_run += 1
            if blank_run <= 1:
                result.append("")
        else:
            blank_run = 0
            result.append(line.strip())
    return "\n".join(result).strip()


def extract_prompt(path: Path) -> dict | None:
    """Extract meta-prompt from a single Markdown file."""
    lines = _read_first_lines(path)
    if not lines:
        return None

    for extractor, prompt_type in [
        (_extract_yaml_front_matter, "yaml_front_matter"),
        (_extract_fenced_prompt, "fenced_block"),
        (_extract_html_comment, "html_comment"),
        (_extract_blockquote, "blockquote"),
        (_extract_paragraph, "paragraph"),
    ]:
        result = extractor(lines)
        if result:
            text, line_range = result
            if not text.strip():
                continue
            return {
                "source_file": str(path),
                "prompt_type": prompt_type,
                "raw_text": text,
                "normalized_text": _normalize(text),
                "line_range": line_range,
            }
    return None


def scan_and_learn(
    docs_path: Path = REFERENCE_DOCS_PATH,
    output_path: Path = PROMPTS_OUTPUT_PATH,
) -> dict:
    """Scan all .md files and save learned prompts to JSON."""
    md_files = sorted(docs_path.rglob("*.md"))
    log.info("scanning_docs", count=len(md_files), path=str(docs_path))

    prompts: list[dict] = []
    for md_file in md_files:
        result = extract_prompt(md_file)
        if result:
            # make source_file relative to docs_path
            try:
                result["source_file"] = str(md_file.relative_to(docs_path))
            except ValueError:
                pass
            prompts.append(result)
            log.debug("extracted_prompt", file=result["source_file"], type=result["prompt_type"])

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "prompts": prompts,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    log.info("prompts_saved", count=len(prompts), path=str(output_path))
    return manifest


def load_prompts(output_path: Path = PROMPTS_OUTPUT_PATH) -> dict:
    """Load previously learned prompts from JSON."""
    if not output_path.exists():
        return {"schema_version": SCHEMA_VERSION, "prompts": []}
    with output_path.open(encoding="utf-8") as f:
        return json.load(f)


def summarize_prompts(manifest: dict) -> str:
    """Create a concise summary of learned prompt styles for system prompt injection."""
    prompts = manifest.get("prompts", [])
    if not prompts:
        return "No existing style prompts found. Use professional technical writing."

    samples = prompts[:5]  # use first 5 as style examples
    summary_parts = [
        "Style and structure guidelines learned from existing deep-research reports:",
        "",
    ]
    for i, p in enumerate(samples, 1):
        excerpt = p["normalized_text"][:300].replace("\n", " ")
        summary_parts.append(f"{i}. [{p['source_file']}] ({p['prompt_type']}): {excerpt}...")
    return "\n".join(summary_parts)


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    docs = Path(sys.argv[1]) if len(sys.argv) > 1 else REFERENCE_DOCS_PATH
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else PROMPTS_OUTPUT_PATH
    scan_and_learn(docs, out)
    print(f"Done. Prompts saved to {out}")
