# SP6 — Python eval 层骨架 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** Run `make eval-py` and see 4 eval suites pass with mock providers, producing a markdown report.

**Architecture:** Pure Python 3.11+, pydantic v2 for schemas, mock providers with fixed outputs, argparse for CLI entrypoints.

**Tech Stack:** Python 3.11.15, pydantic >2, jinja2 (optional for reports), pytest (CI).

---

### Task 1: pydantic domain schemas

**Files:**
- Create: `python/schemas/__init__.py`
- Create: `python/schemas/domain.py`

- [ ] **Step 1: domain.py**

Align with Go domain types from `internal/domain/`:

```python
from __future__ import annotations
from datetime import datetime
from enum import IntEnum, StrEnum
from typing import Optional
from pydantic import BaseModel, Field

class Visibility(StrEnum):
    private = "private"
    match_only = "match_only"
    public = "public"
    friend_only = "friend_only"
    blocked = "blocked"

class Sensitivity(IntEnum):
    low = 0
    normal = 1
    sensitive = 2
    highly_sensitive = 3

class Purpose(StrEnum):
    self_memory = "self_memory"
    matching = "matching"
    generation = "generation"

class State(StrEnum):
    active = "active"
    pending_review = "pending_review"
    expired = "expired"
    deleted = "deleted"
    rejected = "rejected"

class ContextItem(BaseModel):
    id: str
    user_id: str
    type: str = ""
    text: str = ""
    visibility: Visibility = Visibility.match_only
    sensitivity: Sensitivity = Sensitivity.normal
    purpose: list[Purpose] = Field(default_factory=list)
    state: State = State.active
    source_asset_id: str = ""
    expires_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

class PhotoExtraction(BaseModel):
    text: str = ""
    topics: list[str] = Field(default_factory=list)
    sensitivity: Sensitivity = Sensitivity.normal
    confidence: float = 0.0
    privacy_flags: dict[str, bool] = Field(default_factory=dict)

class EmbeddingResult(BaseModel):
    embeddings: list[list[float]] = Field(default_factory=list)
    provider: str = ""
    model: str = ""
    fallback_used: bool = False
    error: str = ""
    latency_ms: int = 0

class BridgeResult(BaseModel):
    connection_reason: str = ""
    icebreakers: list[str] = Field(default_factory=list)
    provider: str = ""
    model: str = ""
    fallback_used: bool = False
    error: str = ""
    latency_ms: int = 0

class MatchResult(BaseModel):
    id: str
    user_id: str = ""
    target_user_id: str = ""
    target_handle: str = ""
    target_name: str = ""
    score: float = 0.0
    connection_reason: str = ""
    icebreakers: list[str] = Field(default_factory=list)
    context_ids: list[str] = Field(default_factory=list)
    safe_context_pack: dict = Field(default_factory=dict)
    bridge_result: dict = Field(default_factory=dict)
    privacy_check: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)

class SourceAsset(BaseModel):
    id: str
    user_id: str = ""
    asset_type: str = ""
    original_filename: str = ""
    visibility: Visibility = Visibility.private
    state: State = State.active
```

- [ ] **Step 2: __init__.py**

Export all from domain:
```python
from python.schemas.domain import *
```

Actually, since the project root is `projects/llm-wiki/`, the package path should be relative. Use flat imports from the `python/` directory.

- [ ] **Step 3: Verify — `python -c "from python.schemas.domain import ContextItem, BridgeResult; print(ContextItem(id='x'))"`**

- [ ] **Step 4: Commit**

---

### Task 2: mock providers

**Files:**
- Create: `python/providers/__init__.py`
- Create: `python/providers/qwen.py`
- Create: `python/providers/doubao.py`
- Create: `python/providers/local_model.py`

Each provider exports a function:
```python
def extract_photo_context(filename: str, metadata: dict) -> PhotoExtraction
```

- [ ] qwen.py — returns Chinese photo extraction mock
- [ ] doubao.py — similar with doubao-specific provider name
- [ ] local_model.py — returns basic extraction

All providers are pure mock — no real API calls. Each returns a fixed deterministic PhotoExtraction.

- [ ] **Step 3: Commit**

---

### Task 3: eval scripts + report

**Files:**
- Create: `python/eval/run_extraction_eval.py`
- Create: `python/eval/run_privacy_eval.py`
- Create: `python/eval/run_matching_eval.py`
- Create: `python/eval/run_bridge_eval.py`
- Create: `python/eval/report.py`

Each eval script:
1. Loads (or creates inline) at least 1 test case
2. Runs the provider against it
3. Compares output to expected (simple pass/fail)
4. Prints result

`report.py` collects outputs from all 4 scripts and writes `evals/reports/<date>.md`.

- [ ] **Step 3: Commit**

---

### Task 4: golden cases + fixtures

**Files:**
- Create: `evals/golden/bridge/bridge_case_01.json`
- Create: `evals/golden/photo_extract/photo_extract_case_01.json`
- Create: `evals/golden/summary/summary_case_01.json`
- Create: `evals/cases/sample_case.json`
- Create: `evals/fixtures/sample_users.json`

Golden file format:
```json
{
  "name": "bridge_case_01",
  "input": {
    "user_a_contexts": [...],
    "user_b_contexts": [...]
  },
  "expected": {
    "connection_reason": "...",
    "icebreakers": ["..."]
  }
}
```

- [ ] **Step 3: Commit**

---

### Task 5: Makefile + README

**Files:**
- Modify: `projects/llm-wiki/Makefile`
- Modify: `projects/llm-wiki/README.md`

- [ ] **Step 1: Add eval-py target**

```makefile
.PHONY: eval-py
eval-py:
	cd python && python -m eval.run_extraction_eval
	cd python && python -m eval.run_privacy_eval
	cd python && python -m eval.run_matching_eval
	cd python && python -m eval.run_bridge_eval
	cd python && python -m eval.report
```

Or use a single entry point:
```makefile
.PHONY: eval-py
eval-py:
	PYTHONPATH=python:$$PYTHONPATH python -c "\
		from eval.run_extraction_eval import run; run(); \
		from eval.run_privacy_eval import run; run(); \
		from eval.run_matching_eval import run; run(); \
		from eval.run_bridge_eval import run; run(); \
		from eval.report import main; main(); \
	"
```

- [ ] **Step 2: Update README**

Add eval section explaining `make eval-py`.

- [ ] **Step 3: Verify — `make eval-py`**

- [ ] **Step 4: Commit**

---

### Task 6: Full regression

- [ ] **Step 1: Go tests**

```bash
go test ./... -count=1
```

- [ ] **Step 2: Python eval**

```bash
make eval-py
```

- [ ] **Step 3: Go build**

```bash
go build ./cmd/ctx/ ./cmd/ctx-web/
```

- [ ] **Step 4: Demo flow**

```bash
go run ./cmd/ctx --data $(mktemp -d) demo run 2>&1 | head -10
```

---

### 验收标准

1. `make eval-py` 4 suite + report 无 fatal
2. `evals/reports/` 产出 `.md` 报告
3. pydantic schemas 可 import
4. Mock providers 可 import 并调用
5. Go 侧 `go test ./...` 通过
6. `ctx demo run` 无回归
