# Project Prompt: LLM API Product Deep Research Report Generator

## 0. Environment Constraints

| Item | Value |
|---|---|
| **Reference corpus** | `/home/lism/work/xlab/docs/reading-open-source` |
| **Python venv** | `/home/lism/env/venv` |
| **Activation** | `source /home/lism/env/venv/bin/activate` |
| **Python binary** | `/home/lism/env/venv/bin/python` |
| **pip / tooling** | All installs must target the venv above — never use system Python |

> All `Makefile` targets, `pyproject.toml` scripts, and CI commands must reference the venv explicitly. No `python` / `pip` bare calls; always use the full venv path or activate first.

---

## Project Overview

Create a Python-based automated research pipeline that:
1. **Learns** prompt patterns from existing Markdown files in the repository
2. **Calls** a large model API (Qwen / OpenAI-compatible) to generate structured deep research reports on LLM API products
3. **Renders** the latest report as a beautiful web page (MkDocs) that refreshes on every query

---

## 1. Prompt Learning Module (`prompt_learner.py`)

### Task
Scan every Markdown (`.md`) file under the **reference report directory** (see §0 below). Read the **first 300 lines** of each file. Identify and extract the **meta-prompt block** that appears before the main body content (typically a YAML front matter block, a fenced code block, or a specially-delimited section at the top of the file). Normalize and persist all discovered prompts.

### Reference Source
```
REFERENCE_DOCS_PATH = /home/lism/work/xlab/docs/reading-open-source
```
This directory contains existing **database product deep-research reports** written in Markdown. The prompt learner must treat these as the **ground-truth style corpus** — all structural, tonal, and formatting conventions in generated LLM API reports must mirror what is learned from these files.

### Rules for Extraction
- A meta-prompt block is defined as any content that appears **before the first level-1 or level-2 Markdown heading** (`#` / `##`) and is either:
  - Wrapped in `---` YAML front matter fences
  - Wrapped in ` ```prompt ``` ` fenced blocks
  - A contiguous block of `>` blockquote lines at the very top
  - An HTML comment block `<!-- prompt: ... -->`
- If none of the above are found, treat the first contiguous non-empty paragraph before the first heading as the prompt.

### Output Format
Save all discovered prompts to `prompts/learned_prompts.json`:
```json
{
  "schema_version": "1.0",
  "extracted_at": "<ISO-8601 timestamp>",
  "prompts": [
    {
      "source_file": "relative/path/to/file.md",
      "prompt_type": "yaml_front_matter | fenced_block | blockquote | html_comment | paragraph",
      "raw_text": "...",
      "normalized_text": "...",
      "line_range": [1, 42]
    }
  ]
}
```

---

## 2. Research Report Generator (`researcher.py`)

### Task
Using the learned prompts as style/structure references, call the Qwen API to generate a **deep research report** on a given LLM API product (e.g., OpenAI GPT-4o, Anthropic Claude, Google Gemini, Mistral, Cohere, etc.).

### Environment
```python
import os
api_key = os.environ["QWEN_API_KEY"]
base_url = os.environ.get("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
model = os.environ.get("QWEN_MODEL", "qwen-max")
```

### System Prompt (Assembled from Learned Prompts + Template)
```
You are a senior AI product analyst specializing in large language model APIs and developer tooling.

Your task is to produce a comprehensive, structured deep-research report about the following LLM API product: {product_name}.

Follow these structural and stylistic guidelines learned from existing research documents:
{learned_prompt_summary}

The report MUST include the following sections:
1. Executive Summary (3–5 sentences)
2. Product Overview
   - Provider & background
   - Model family & versions
   - Core capabilities
3. Technical Deep Dive
   - Architecture & training approach (what is publicly known)
   - Context window, multimodal capabilities, tool use / function calling
   - Latency, throughput benchmarks (cite public sources where available)
4. API & Developer Experience
   - Authentication, SDKs, rate limits, pricing tiers
   - Ease of integration (REST, streaming, batch)
   - Playground / UI tooling
5. Competitive Positioning
   - Strengths vs. key competitors
   - Weaknesses / gaps
   - SWOT table (Markdown table format)
6. Use Case Analysis
   - Best-fit scenarios
   - Anti-patterns / poor-fit scenarios
7. Ecosystem & Community
   - Documentation quality
   - Community size, GitHub activity, third-party integrations
8. Pricing & Commercial Terms
   - Input/output token pricing
   - Fine-tuning, batch, cached token pricing
   - Enterprise / volume discounts
9. Recent Developments & Roadmap (last 6 months)
10. Analyst Verdict
    - Score (1–10) for: Capability / Dev Experience / Pricing / Ecosystem / Innovation
    - Final recommendation

Output the entire report in Markdown format. Use tables, code blocks, and callout blockquotes where appropriate.
Report language: {report_language}
Research depth: {research_depth}  # "standard" | "deep" | "executive"
```

### Report Persistence
- Save each report as `reports/{product_slug}_{YYYYMMDD_HHMMSS}.md`
- Maintain a `reports/index.json` manifest tracking all generated reports
- Always symlink / copy the latest report to `docs/index.md` for MkDocs rendering

---

## 3. Web Rendering (`mkdocs` + auto-refresh)

### MkDocs Configuration (`mkdocs.yml`)
```yaml
site_name: LLM API Deep Research Hub
theme:
  name: material
  palette:
    - scheme: default
      primary: indigo
      accent: deep purple
  features:
    - navigation.instant
    - navigation.tabs
    - content.code.annotate
    - content.tabs.link
plugins:
  - search
  - tags
markdown_extensions:
  - tables
  - admonition
  - pymdownx.superfences
  - pymdownx.highlight
  - attr_list
  - md_in_html
```

### Auto-Refresh Endpoint (`server.py`)
- Use **FastAPI** to expose:
  - `GET /refresh?product={name}` — triggers a new research call and rebuilds MkDocs
  - `GET /reports` — lists all available reports
  - `GET /` — serves the MkDocs-built `site/` directory
- On each refresh, run:
  ```python
  subprocess.run(["mkdocs", "build", "--clean"])
  ```

---

## 4. Project Structure

```
llm-research/
├── prompts/
│   └── learned_prompts.json        # Auto-generated by prompt_learner.py
├── reports/                        # Generated .md reports
│   └── index.json
├── docs/                           # MkDocs source
│   ├── index.md                    # Symlink → latest report
│   └── stylesheets/
│       └── extra.css
├── site/                           # MkDocs build output (gitignored)
├── tests/
│   ├── test_prompt_learner.py
│   ├── test_researcher.py
│   └── test_server.py
├── src/
│   ├── __init__.py
│   ├── prompt_learner.py
│   ├── researcher.py
│   ├── report_manager.py
│   └── server.py
├── mkdocs.yml
├── pyproject.toml
├── .env.example
└── README.md
```

---

## 5. Makefile Targets (venv-aware)

All commands must invoke the venv directly so they work without manual activation:

```makefile
VENV     := /home/lism/env/venv
PYTHON   := $(VENV)/bin/python
PIP      := $(VENV)/bin/pip
PYTEST   := $(VENV)/bin/pytest
RUFF     := $(VENV)/bin/ruff
MKDOCS   := $(VENV)/bin/mkdocs
UVICORN  := $(VENV)/bin/uvicorn

.PHONY: install lint test build serve refresh

install:
	$(PIP) install -e ".[dev]"

lint:
	$(RUFF) check src/ tests/
	$(VENV)/bin/mypy src/

test:
	$(PYTEST) tests/ --cov=src --cov-report=term-missing

build:
	$(MKDOCS) build --clean

serve:
	$(UVICORN) src.server:app --reload --port 8080

refresh:
	$(PYTHON) -m llm_research --product "$(PRODUCT)" --depth $(DEPTH)
	$(MKDOCS) build --clean
```

---

## 6. Code Standards & Conventions

- **Python ≥ 3.11** with full type annotations (`from __future__ import annotations`)
- **Async-first**: use `asyncio` + `httpx.AsyncClient` for all API calls
- **Dependency management**: `pyproject.toml` with `[project.optional-dependencies]` for dev/test
- **Linting**: `ruff` + `black` + `mypy --strict`
- **All comments and docstrings in English**
- **Logging**: `structlog` with JSON output in production
- **Secrets**: loaded via `python-dotenv`; never hardcoded
- **Error handling**: custom exception hierarchy under `src/exceptions.py`

---

## 7. Testing Requirements

| Test File | Coverage Target | Key Scenarios |
|---|---|---|
| `test_prompt_learner.py` | ≥ 90% | YAML front matter, fenced block, no-prompt fallback, empty file, 300-line truncation |
| `test_researcher.py` | ≥ 85% | API call mocking, prompt assembly, file persistence, symlink creation |
| `test_server.py` | ≥ 80% | `/refresh` endpoint, `/reports` listing, MkDocs build trigger |

Use `pytest` + `pytest-asyncio` + `pytest-cov`. Mock all external API calls with `respx`.

---

## 8. README Requirements

The `README.md` must include:
1. **Project description** (2–3 sentences)
2. **Architecture diagram** (Mermaid)
3. **Quick start** (copy-paste commands from `git clone` to viewing the report)
4. **Environment variables table**
5. **CLI usage** (`python -m llm_research --product "Claude API" --depth deep`)
6. **API endpoint reference**
7. **How to add a new prompt template**
8. **Contributing guide**
9. **License**

---

## 9. Deliverables Checklist

- [ ] `src/prompt_learner.py` — fully implemented & tested
- [ ] `src/researcher.py` — fully implemented & tested
- [ ] `src/report_manager.py` — report CRUD & manifest management
- [ ] `src/server.py` — FastAPI server with refresh endpoint
- [ ] `mkdocs.yml` — production-ready MkDocs config
- [ ] `tests/` — full test suite with ≥ 85% overall coverage
- [ ] `README.md` — complete documentation
- [ ] `pyproject.toml` — all dependencies declared
- [ ] `.env.example` — all required env vars documented
- [ ] Sample report for at least one product included in `reports/`
