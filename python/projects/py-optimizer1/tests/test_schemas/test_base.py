from optimizer_analysis.schemas.base import Evidence, EvidenceType


def test_evidence_creation():
    """Evidence must have file_path and description."""
    evidence = Evidence(
        file_path="src/optimizer/optimizer.cpp",
        description="Main optimizer entry point",
        line_start=100,
        line_end=150,
        evidence_type=EvidenceType.SOURCE_CODE
    )
    assert evidence.file_path == "src/optimizer/optimizer.cpp"
    assert evidence.evidence_type == EvidenceType.SOURCE_CODE


def test_evidence_requires_file_path():
    """Evidence without file_path should fail validation."""
    from pydantic import ValidationError
    try:
        Evidence(description="missing path")
        assert False, "Should have raised ValidationError"
    except ValidationError as e:
        assert "file_path" in str(e)


def test_evidence_types():
    """All evidence types should be available."""
    types = [EvidenceType.SOURCE_CODE, EvidenceType.DOCUMENTATION,
             EvidenceType.TEST, EvidenceType.COMMENT, EvidenceType.CONFIG]
    assert len(types) == 5