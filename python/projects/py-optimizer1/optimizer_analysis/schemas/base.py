from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class EvidenceType(str, Enum):
    """Type of evidence supporting a conclusion."""
    SOURCE_CODE = "source_code"
    DOCUMENTATION = "documentation"
    TEST = "test"
    COMMENT = "comment"
    CONFIG = "config"


class Evidence(BaseModel):
    """Evidence linking a conclusion to source material."""
    file_path: str = Field(..., description="Path to the source file")
    description: str = Field(..., description="What this evidence demonstrates")
    line_start: Optional[int] = Field(None, description="Starting line number")
    line_end: Optional[int] = Field(None, description="Ending line number")
    evidence_type: EvidenceType = Field(
        EvidenceType.SOURCE_CODE, description="Type of evidence"
    )
    commit_hash: Optional[str] = Field(None, description="Git commit hash")
    url: Optional[str] = Field(None, description="URL to documentation or external source")