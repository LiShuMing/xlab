# tests/test_schemas/test_observability.py
"""Tests for Observability schema (DESIGN.md Section 6.5)."""
from optimizer_analysis.schemas.observability import Observability
from optimizer_analysis.schemas.base import Evidence


def test_observability_creation():
    """Observability must have explain and trace interfaces."""
    obs = Observability(
        explain_interfaces=["EXPLAIN", "EXPLAIN ANALYZE", "EXPLAIN VERBOSE"],
        trace_interfaces=["optimizer_trace", "debug_trace"],
        evidence=[]
    )
    assert len(obs.explain_interfaces) == 3
    assert len(obs.trace_interfaces) == 2
    assert obs.rule_fire_visibility == "none"  # default
    assert obs.memo_dump_support == False  # default


def test_observability_with_partial_visibility():
    """Observability can have partial rule fire visibility."""
    obs = Observability(
        explain_interfaces=["EXPLAIN"],
        trace_interfaces=[],
        rule_fire_visibility="partial",
        memo_dump_support=True,
        session_controls=["enable_optimizer_trace", "optimizer_cost_limit"],
        debug_hooks=["optimizer_debug_mode", "rule_fire_log"],
        uncertain_points=["memo dump format not documented"],
        evidence=[
            Evidence(
                file_path="src/optimizer/explain.cpp",
                description="EXPLAIN command implementation"
            )
        ]
    )
    assert obs.rule_fire_visibility == "partial"
    assert obs.memo_dump_support == True
    assert len(obs.session_controls) == 2
    assert len(obs.debug_hooks) == 2
    assert len(obs.uncertain_points) == 1
    assert len(obs.evidence) == 1


def test_observability_visibility_levels():
    """Observability supports full, partial, none visibility levels."""
    for visibility in ["full", "partial", "none"]:
        obs = Observability(
            explain_interfaces=["EXPLAIN"],
            trace_interfaces=[],
            rule_fire_visibility=visibility,
            evidence=[]
        )
        assert obs.rule_fire_visibility == visibility


def test_observability_full_visibility():
    """Observability with full visibility shows all rule firings."""
    obs = Observability(
        explain_interfaces=["EXPLAIN", "EXPLAIN ANALYZE", "EXPLAIN OPTIMIZER"],
        trace_interfaces=["optimizer_trace", "rule_trace", "cost_trace"],
        rule_fire_visibility="full",
        memo_dump_support=True,
        session_controls=["optimizer_mode", "cost_model_version"],
        debug_hooks=["optimizer_debug", "memo_dump", "rule_fire_log"],
        uncertain_points=[],
        evidence=[
            Evidence(
                file_path="src/optimizer/explain/optimizer_explain.cpp",
                description="Full optimizer trace support"
            ),
            Evidence(
                file_path="src/optimizer/memo/memo_dump.cpp",
                description="Memo dump implementation"
            )
        ]
    )
    assert obs.rule_fire_visibility == "full"
    assert obs.memo_dump_support == True
    assert len(obs.explain_interfaces) == 3
    assert len(obs.trace_interfaces) == 3
    assert len(obs.session_controls) == 2
    assert len(obs.debug_hooks) == 3
    assert len(obs.evidence) == 2