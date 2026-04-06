from optimizer_analysis.schemas.rule import (
    Rule, RuleCategory, ImplementationType
)
from optimizer_analysis.schemas.base import Evidence, EvidenceType


def test_rule_creation():
    """Rule must have rule_id, name, and category."""
    rule = Rule(
        rule_id="SR-PUSH-PRED-001",
        rule_name="PredicatePushDown",
        engine="StarRocks",
        rule_category=RuleCategory.RBO,
        implementation_type=ImplementationType.EXPLICIT,
        lifecycle_stage="logical_opt",
        source_files=["src/optimizer/rules/predicate_pushdown.cpp"],
        registration_points=["src/optimizer/rule_registry.cpp:45"],
        trigger_pattern="Predicate appears above Scan operator",
        transformation_logic="Move predicate from parent to child Scan",
        input_operators=["Filter", "Scan"],
        output_operators=["Scan"],
        evidence=[]
    )
    assert rule.rule_id == "SR-PUSH-PRED-001"
    assert rule.rule_category == RuleCategory.RBO
    assert rule.implementation_type == ImplementationType.EXPLICIT


def test_rule_categories():
    """Rule categories per DESIGN.md Section 6.2."""
    categories = [
        RuleCategory.RBO,
        RuleCategory.CBO,
        RuleCategory.SCALAR,
        RuleCategory.POST_OPT,
        RuleCategory.IMPLICIT,
    ]
    assert len(categories) == 5


def test_implementation_types():
    """Implementation explicitness levels per DESIGN.md Section 9."""
    types = [
        ImplementationType.EXPLICIT,
        ImplementationType.IMPLICIT,
        ImplementationType.FRAMEWORK_PROVIDED,
        ImplementationType.NOT_APPLICABLE,
    ]
    assert len(types) == 4


def test_rule_with_dependencies():
    """Rule can specify stats/cost/property dependencies."""
    rule = Rule(
        rule_id="SR-JOIN-ORDER-001",
        rule_name="JoinOrderOptimization",
        engine="StarRocks",
        rule_category=RuleCategory.CBO,
        implementation_type=ImplementationType.EXPLICIT,
        depends_on_stats=True,
        depends_on_cost=True,
        depends_on_property=True,
        confidence="high",
        evidence=[
            Evidence(
                file_path="src/optimizer/rules/join_order.cpp",
                description="Cost-based join reorder implementation",
                evidence_type=EvidenceType.SOURCE_CODE
            )
        ]
    )
    assert rule.depends_on_stats == True
    assert rule.depends_on_cost == True
    assert len(rule.evidence) == 1