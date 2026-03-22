"""Run state management - tracks stage completion for resume support."""

from __future__ import annotations

import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from paper_agent.utils.io import read_json, write_json


class Stage(str, Enum):
    PARSE = "parse"
    CHUNK = "chunk"
    INDEX = "index"
    EXTRACT = "extract"
    BIND_EVIDENCE = "bind_evidence"
    RELATED = "related"
    REPORT = "report"


STAGE_ORDER = [
    Stage.PARSE,
    Stage.CHUNK,
    Stage.INDEX,
    Stage.EXTRACT,
    Stage.BIND_EVIDENCE,
    Stage.RELATED,
    Stage.REPORT,
]


class StageStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class RunState:
    """Tracks stage completion state for a single run directory."""

    def __init__(self, metadata_path: Path) -> None:
        self._path = metadata_path
        self._data: dict = {}
        if metadata_path.exists():
            self._data = read_json(metadata_path)

    @classmethod
    def create(
        cls,
        metadata_path: Path,
        document_id: str,
        filename: str,
        sha256: str,
        config: dict,
    ) -> "RunState":
        """Create a new run state."""
        state = cls(metadata_path)
        state._data = {
            "document_id": document_id,
            "filename": filename,
            "sha256": sha256,
            "created_at": datetime.datetime.now().isoformat(),
            "updated_at": datetime.datetime.now().isoformat(),
            "stages": {stage.value: StageStatus.NOT_STARTED.value for stage in Stage},
        }
        state._save()
        return state

    def get_stage_status(self, stage: Stage) -> StageStatus:
        stages = self._data.get("stages", {})
        return StageStatus(stages.get(stage.value, StageStatus.NOT_STARTED.value))

    def is_completed(self, stage: Stage) -> bool:
        return self.get_stage_status(stage) == StageStatus.COMPLETED

    def mark_in_progress(self, stage: Stage) -> None:
        self._data.setdefault("stages", {})[stage.value] = StageStatus.IN_PROGRESS.value
        self._data["updated_at"] = datetime.datetime.now().isoformat()
        self._save()

    def mark_completed(self, stage: Stage) -> None:
        self._data.setdefault("stages", {})[stage.value] = StageStatus.COMPLETED.value
        self._data["updated_at"] = datetime.datetime.now().isoformat()
        self._save()

    def mark_failed(self, stage: Stage, error: Optional[str] = None) -> None:
        self._data.setdefault("stages", {})[stage.value] = StageStatus.FAILED.value
        if error:
            self._data.setdefault("errors", {})[stage.value] = error
        self._data["updated_at"] = datetime.datetime.now().isoformat()
        self._save()

    def should_skip(self, stage: Stage, resume: bool) -> bool:
        """Return True if the stage should be skipped (already completed and resume=True)."""
        return resume and self.is_completed(stage)

    @property
    def document_id(self) -> str:
        return self._data.get("document_id", "")

    @property
    def filename(self) -> str:
        return self._data.get("filename", "")

    def _save(self) -> None:
        write_json(self._path, self._data)
