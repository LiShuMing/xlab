"""Run state management - tracks stage completion for resume support."""

from __future__ import annotations

import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from paper_agent.utils.io import read_json, write_json
from paper_agent.utils.logging import get_logger

logger = get_logger(__name__)


class Stage(str, Enum):
    """Pipeline stages in execution order."""

    PARSE = "parse"
    CHUNK = "chunk"
    INDEX = "index"
    EXTRACT = "extract"
    BIND_EVIDENCE = "bind_evidence"
    RELATED = "related"
    REPORT = "report"


class StageStatus(str, Enum):
    """Status of a pipeline stage."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


# Stage execution order for resume support
STAGE_ORDER: list[Stage] = [
    Stage.PARSE,
    Stage.CHUNK,
    Stage.INDEX,
    Stage.EXTRACT,
    Stage.BIND_EVIDENCE,
    Stage.RELATED,
    Stage.REPORT,
]


class RunState:
    """Tracks stage completion state for a single run directory.

    This class manages the pipeline state machine, enabling resume functionality
    and failure recovery.
    """

    def __init__(self, metadata_path: Path) -> None:
        """Initialize from existing or new metadata file.

        Args:
            metadata_path: Path to the metadata JSON file
        """
        self._path = metadata_path
        self._data: dict[str, Any] = {}
        if metadata_path.exists():
            self._data = read_json(metadata_path)
            logger.debug(
                "run_state_loaded",
                path=str(metadata_path),
                document_id=self._data.get("document_id"),
            )

    @classmethod
    def create(
        cls,
        metadata_path: Path,
        document_id: str,
        filename: str,
        sha256: str,
        config: dict[str, Any],
    ) -> RunState:
        """Create a new run state.

        Args:
            metadata_path: Path to store the metadata
            document_id: Unique document identifier
            filename: Original filename
            sha256: Document hash for integrity verification
            config: Run configuration dictionary

        Returns:
            New RunState instance
        """
        state = cls(metadata_path)
        now = datetime.datetime.now().isoformat()
        state._data = {
            "document_id": document_id,
            "filename": filename,
            "sha256": sha256,
            "created_at": now,
            "updated_at": now,
            "stages": {stage.value: StageStatus.NOT_STARTED.value for stage in Stage},
        }
        state._save()
        logger.info(
            "run_state_created",
            document_id=document_id,
            path=str(metadata_path),
        )
        return state

    def get_stage_status(self, stage: Stage) -> StageStatus:
        """Get the current status of a stage.

        Args:
            stage: The stage to check

        Returns:
            Current stage status
        """
        stages = self._data.get("stages", {})
        return StageStatus(stages.get(stage.value, StageStatus.NOT_STARTED.value))

    def is_completed(self, stage: Stage) -> bool:
        """Check if a stage is completed.

        Args:
            stage: The stage to check

        Returns:
            True if the stage is completed
        """
        return self.get_stage_status(stage) == StageStatus.COMPLETED

    def is_failed(self, stage: Stage) -> bool:
        """Check if a stage has failed.

        Args:
            stage: The stage to check

        Returns:
            True if the stage has failed
        """
        return self.get_stage_status(stage) == StageStatus.FAILED

    def mark_in_progress(self, stage: Stage) -> None:
        """Mark a stage as in progress.

        Args:
            stage: The stage to update
        """
        self._data.setdefault("stages", {})[stage.value] = StageStatus.IN_PROGRESS.value
        self._data["updated_at"] = datetime.datetime.now().isoformat()
        self._save()
        logger.debug("stage_in_progress", stage=stage.value)

    def mark_completed(self, stage: Stage) -> None:
        """Mark a stage as completed.

        Args:
            stage: The stage to update
        """
        self._data.setdefault("stages", {})[stage.value] = StageStatus.COMPLETED.value
        self._data["updated_at"] = datetime.datetime.now().isoformat()
        self._save()
        logger.info("stage_completed", stage=stage.value)

    def mark_failed(self, stage: Stage, error: str | None = None) -> None:
        """Mark a stage as failed.

        Args:
            stage: The stage to update
            error: Optional error message
        """
        self._data.setdefault("stages", {})[stage.value] = StageStatus.FAILED.value
        if error:
            self._data.setdefault("errors", {})[stage.value] = error
        self._data["updated_at"] = datetime.datetime.now().isoformat()
        self._save()
        logger.error("stage_failed", stage=stage.value, error=error)

    def should_skip(self, stage: Stage, resume: bool) -> bool:
        """Determine if a stage should be skipped.

        A stage is skipped if resume is True and the stage is already completed.

        Args:
            stage: The stage to check
            resume: Whether resume mode is enabled

        Returns:
            True if the stage should be skipped
        """
        return resume and self.is_completed(stage)

    @property
    def document_id(self) -> str:
        """Get the document ID."""
        return str(self._data.get("document_id", ""))

    @property
    def filename(self) -> str:
        """Get the original filename."""
        return str(self._data.get("filename", ""))

    @property
    def sha256(self) -> str:
        """Get the document SHA256 hash."""
        return str(self._data.get("sha256", ""))

    @property
    def created_at(self) -> str:
        """Get the creation timestamp."""
        return str(self._data.get("created_at", ""))

    def get_error(self, stage: Stage) -> str | None:
        """Get the error message for a failed stage.

        Args:
            stage: The stage to check

        Returns:
            Error message if the stage failed, None otherwise
        """
        errors = self._data.get("errors", {})
        error = errors.get(stage.value)
        return str(error) if error is not None else None

    def get_completed_stages(self) -> list[Stage]:
        """Get list of completed stages.

        Returns:
            List of completed stages in order
        """
        return [s for s in STAGE_ORDER if self.is_completed(s)]

    def _save(self) -> None:
        """Persist state to disk."""
        write_json(self._path, self._data)
