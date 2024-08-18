"""Pre-configured engine configurations."""
from optimizer_analysis.engines.base import EngineConfig
from optimizer_analysis.schemas.framework import EngineType, OptimizerStyle


# StarRocks Engine Configuration
# StarRocks uses a Cascades-style optimizer with memo-based search
STARROCKS_CONFIG = EngineConfig(
    name="StarRocks",
    repo_url="https://github.com/StarRocks/starrocks",
    default_branch="main",
    engine_type=EngineType.COLUMNAR_OLAP,
    optimizer_style=OptimizerStyle.CASCADES,
    optimizer_dirs=[
        "fe/fe-core/src/main/java/com/starrocks/sql/optimizer",
    ],
    main_entry="fe/fe-core/src/main/java/com/starrocks/sql/optimizer/Optimizer.java",
    fallback_paths=[],
    docs_url="https://docs.starrocks.io/docs/sql-reference/sql-statements/query-operators/",
    notes=[
        "Cascades-style optimizer with Memo, Group, GroupExpression",
        "Rules organized in rule/transformation/, rule/implementation/",
        "Cost model in cost/ directory",
        "Statistics in statistics/ directory",
        "Properties in property/ directory",
        "Java-based optimizer in FE (Frontend)",
    ],
)


# Apache Calcite Engine Configuration
# Calcite is a framework with Volcano/Cascades-style planner
CALCITE_CONFIG = EngineConfig(
    name="Calcite",
    repo_url="https://github.com/apache/calcite",
    default_branch="main",
    engine_type=EngineType.FRAMEWORK,
    optimizer_style=OptimizerStyle.VOLCANO,
    optimizer_dirs=[
        "core/src/main/java/org/apache/calcite/rel/rules",
        "core/src/main/java/org/apache/calcite/plan",
        "core/src/main/java/org/apache/calcite/tools",
    ],
    main_entry="core/src/main/java/org/apache/calcite/tools/Planner.java",
    fallback_paths=[],
    docs_url="https://calcite.apache.org/docs/",
    notes=[
        "Volcano/Cascades-style planner framework",
        "Rules in rel/rules/ directory (hundreds of rules)",
        "Plan rules in plan/ directory (RelOptRule, RelOptPlanner)",
        "Traits and conventions support",
        "Pure Java implementation",
        "Used by many projects (Hive, Drill, Flink, etc.)",
    ],
)


# Apache Doris Engine Configuration
# Doris uses Nereids optimizer (Cascades-style)
DORIS_CONFIG = EngineConfig(
    name="Doris",
    repo_url="https://github.com/apache/doris",
    default_branch="master",
    engine_type=EngineType.COLUMNAR_OLAP,
    optimizer_style=OptimizerStyle.CASCADES,
    optimizer_dirs=[
        "fe/fe-core/src/main/java/org/apache/doris/nereids",
    ],
    main_entry="fe/fe-core/src/main/java/org/apache/doris/nereids/NereidsPlanner.java",
    fallback_paths=[],
    docs_url="https://doris.apache.org/docs/",
    notes=[
        "Nereids optimizer - Cascades-style with memo",
        "Rules organized in rules/analysis, rules/exploration, rules/implementation, rules/rewrite",
        "Cost model in cost/ directory",
        "CascadesContext for memo management",
        "Java-based optimizer in FE (Frontend)",
        "Evolved from old optimizer to Nereids",
    ],
)


def get_default_engines():
    """Get dictionary of pre-configured engines."""
    return {
        "StarRocks": STARROCKS_CONFIG,
        "Calcite": CALCITE_CONFIG,
        "Doris": DORIS_CONFIG,
    }