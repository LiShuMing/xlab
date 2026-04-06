# tests/test_schemas/test_framework.py
from optimizer_analysis.schemas.framework import (
    Framework, OptimizerStyle, EngineType, OptimizerPhase
)


def test_framework_creation():
    """Framework must have engine_name and optimizer_style."""
    framework = Framework(
        engine_name="StarRocks",
        engine_type=EngineType.COLUMNAR_OLAP,
        optimizer_style=OptimizerStyle.CASCADES,
        main_entry="src/optimizer/optimizer.cpp",
        logical_physical_split=True,
        memo_or_equivalent="Memo table in CascadesStyle",
        search_strategy="Top-down with memoization",
        evidence=[]
    )
    assert framework.engine_name == "StarRocks"
    assert framework.optimizer_style == OptimizerStyle.CASCADES
    assert framework.logical_physical_split == True


def test_optimizer_styles():
    """All optimizer styles from DESIGN.md Section 4.1."""
    styles = [
        OptimizerStyle.CASCADES,
        OptimizerStyle.VOLCANO,
        OptimizerStyle.PLANNER_PATH_ENUM,
        OptimizerStyle.HEURISTIC_MIXED,
        OptimizerStyle.ANALYZER_PLANNER,
    ]
    assert len(styles) == 5


def test_optimizer_phases():
    """Standard optimizer lifecycle phases."""
    phases = [
        OptimizerPhase.PARSING,
        OptimizerPhase.LOGICAL_OPT,
        OptimizerPhase.PHYSICAL_OPT,
        OptimizerPhase.COST_ESTIMATION,
        OptimizerPhase.BEST_PLAN_SELECTION,
        OptimizerPhase.POST_OPTIMIZER,
    ]
    assert len(phases) == 6


def test_framework_with_phases():
    """Framework can include phase sequence."""
    framework = Framework(
        engine_name="PostgreSQL",
        engine_type=EngineType.ROW_STORE,
        optimizer_style=OptimizerStyle.PLANNER_PATH_ENUM,
        main_entry="src/backend/optimizer/planner/planner.c",
        optimizer_phases=[
            OptimizerPhase.PARSING,
            OptimizerPhase.LOGICAL_OPT,
            OptimizerPhase.COST_ESTIMATION,
            OptimizerPhase.BEST_PLAN_SELECTION,
        ],
        logical_physical_split=False,
        evidence=[]
    )
    assert len(framework.optimizer_phases) == 4