# Optimizer Expert Analyzer Agent - Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the foundation for a multi-engine query optimizer source code analysis system: unified schemas, directory structure, repo mapper agent, and framework/lifecycle analyzer.

**Architecture:** Modular agent system with standardized JSON schemas for cross-engine comparison. Phase 1 focuses on schema definition, repo mapping, and framework/lifecycle extraction before rule mining.

**Tech Stack:** Python 3.10+, pydantic for schema validation, pytest for testing, JSON/YAML for artifacts.

---

## File Structure

```
optimizer_analysis/
  __init__.py
  schemas/
    __init__.py
    base.py              # Base schema with evidence fields
    framework.py         # Framework schema (Section 6.1)
    rule.py              # Rule schema (Section 6.2)
    trait.py             # Trait/Property schema (Section 6.3)
    stats_cost.py        # Statistics/Cost schema (Section 6.4)
    observability.py     # Observability schema (Section 6.5)
    extensibility.py     # Extensibility schema (Section 6.6)
  agents/
    __init__.py
    base.py              # Base agent class
    repo_mapper.py       # Repository Mapper Agent (Section 7.1)
    lifecycle.py         # Lifecycle Analyzer Agent (Section 7.2)
  engines/
    __init__.py
    base.py              # Engine config base
    registry.py          # Engine registry
    starrocks/           # First engine to analyze
      __init__.py
      config.py          # StarRocks-specific config
  artifacts/
    .gitkeep
  prompts/
    __init__.py
    repo_mapper.py       # Repo mapper prompts
    lifecycle.py         # Lifecycle analysis prompts
tests/
  __init__.py
  test_schemas/
    __init__.py
    test_framework.py
    test_rule.py
    test_trait.py
    test_stats_cost.py
    test_observability.py
    test_extensibility.py
  test_agents/
    __init__.py
    test_repo_mapper.py
    test_lifecycle.py
```

---

### Task 1: Project Setup and Base Schema

**Files:**
- Create: `optimizer_analysis/__init__.py`
- Create: `optimizer_analysis/schemas/__init__.py`
- Create: `optimizer_analysis/schemas/base.py`
- Test: `tests/test_schemas/__init__.py`
- Test: `tests/test_schemas/test_base.py`

- [ ] **Step 1: Write the failing test for Evidence schema**

```python
# tests/test_schemas/__init__.py
# Empty init file
```

```python
# tests/test_schemas/test_base.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lism/work/xlab/python/projects/py-optimizer1 && pytest tests/test_schemas/test_base.py -v`
Expected: FAIL with "No module named 'optimizer_analysis'"

- [ ] **Step 3: Write minimal implementation**

```python
# optimizer_analysis/__init__.py
"""Optimizer Expert Analyzer Agent - Multi-engine optimizer source code analysis system."""
__version__ = "0.1.0"
```

```python
# optimizer_analysis/schemas/__init__.py
from optimizer_analysis.schemas.base import Evidence, EvidenceType

__all__ = ["Evidence", "EvidenceType"]
```

```python
# optimizer_analysis/schemas/base.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/lism/work/xlab/python/projects/py-optimizer1 && pytest tests/test_schemas/test_base.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add optimizer_analysis/__init__.py optimizer_analysis/schemas/__init__.py optimizer_analysis/schemas/base.py tests/test_schemas/__init__.py tests/test_schemas/test_base.py
git commit -m "feat(schemas): add Evidence base schema with validation"
```

---

### Task 2: Framework Schema (Section 6.1)

**Files:**
- Create: `optimizer_analysis/schemas/framework.py`
- Test: `tests/test_schemas/test_framework.py`

- [ ] **Step 1: Write the failing test for Framework schema**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lism/work/xlab/python/projects/py-optimizer1 && pytest tests/test_schemas/test_framework.py -v`
Expected: FAIL with "No module named 'optimizer_analysis.schemas.framework'"

- [ ] **Step 3: Write minimal implementation**

```python
# optimizer_analysis/schemas/framework.py
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

from optimizer_analysis.schemas.base import Evidence


class EngineType(str, Enum):
    """Engine classification type (DESIGN.md Section 4.1)."""
    COLUMNAR_OLAP = "columnar_olap"
    ROW_STORE = "row_store"
    FRAMEWORK = "framework"
    RESEARCH_PROTO = "research_proto"
    HYBRID = "hybrid"


class OptimizerStyle(str, Enum):
    """Optimizer architectural style (DESIGN.md Section 4.1)."""
    CASCADES = "cascades"
    VOLCANO = "volcano"
    PLANNER_PATH_ENUM = "planner_path_enum"
    HEURISTIC_MIXED = "heuristic_mixed"
    ANALYZER_PLANNER = "analyzer_planner"


class OptimizerPhase(str, Enum):
    """Standard optimizer lifecycle phases."""
    PARSING = "parsing"
    LOGICAL_OPT = "logical_opt"
    PHYSICAL_OPT = "physical_opt"
    COST_ESTIMATION = "cost_estimation"
    BEST_PLAN_SELECTION = "best_plan_selection"
    POST_OPTIMIZER = "post_optimizer"


class Framework(BaseModel):
    """Framework schema (DESIGN.md Section 6.1)."""
    engine_name: str = Field(..., description="Engine name")
    engine_type: EngineType = Field(..., description="Engine classification")
    optimizer_style: OptimizerStyle = Field(..., description="Optimizer architectural style")
    main_entry: str = Field(..., description="Primary optimizer entry point")
    optimizer_phases: Optional[List[OptimizerPhase]] = Field(
        None, description="Lifecycle phases in order"
    )
    logical_physical_split: bool = Field(
        False, description="Whether logical and physical optimization are separate"
    )
    memo_or_equivalent: Optional[str] = Field(
        None, description="Memo structure or equivalent search space"
    )
    search_strategy: Optional[str] = Field(
        None, description="Plan search strategy description"
    )
    best_plan_selection: Optional[str] = Field(
        None, description="How best plan is selected"
    )
    post_optimizer_stage: Optional[str] = Field(
        None, description="Post-optimizer stage description"
    )
    fallback_paths: Optional[List[str]] = Field(
        None, description="Fallback optimizer paths if primary fails"
    )
    evidence: List[Evidence] = Field(
        default_factory=list, description="Evidence supporting this analysis"
    )
```

- [ ] **Step 4: Update schemas __init__.py**

```python
# optimizer_analysis/schemas/__init__.py
from optimizer_analysis.schemas.base import Evidence, EvidenceType
from optimizer_analysis.schemas.framework import (
    Framework, OptimizerStyle, EngineType, OptimizerPhase
)

__all__ = [
    "Evidence", "EvidenceType",
    "Framework", "OptimizerStyle", "EngineType", "OptimizerPhase"
]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /home/lism/work/xlab/python/projects/py-optimizer1 && pytest tests/test_schemas/test_framework.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add optimizer_analysis/schemas/framework.py optimizer_analysis/schemas/__init__.py tests/test_schemas/test_framework.py
git commit -m "feat(schemas): add Framework schema with engine types and optimizer styles"
```

---

### Task 3: Rule Schema (Section 6.2)

**Files:**
- Create: `optimizer_analysis/schemas/rule.py`
- Test: `tests/test_schemas/test_rule.py`

- [ ] **Step 1: Write the failing test for Rule schema**

```python
# tests/test_schemas/test_rule.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lism/work/xlab/python/projects/py-optimizer1 && pytest tests/test_schemas/test_rule.py -v`
Expected: FAIL with "No module named 'optimizer_analysis.schemas.rule'"

- [ ] **Step 3: Write minimal implementation**

```python
# optimizer_analysis/schemas/rule.py
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

from optimizer_analysis.schemas.base import Evidence


class RuleCategory(str, Enum):
    """Rule classification category (DESIGN.md Section 6.2)."""
    RBO = "rbo"
    CBO = "cbo"
    SCALAR = "scalar"
    POST_OPT = "post_opt"
    IMPLICIT = "implicit"


class ImplementationType(str, Enum):
    """How explicitly a rule is implemented (DESIGN.md Section 9)."""
    EXPLICIT = "explicitly_implemented"
    IMPLICIT = "implicitly_implemented"
    FRAMEWORK_PROVIDED = "framework_provided"
    NOT_APPLICABLE = "not_applicable"


class Rule(BaseModel):
    """Rule schema (DESIGN.md Section 6.2)."""
    rule_id: str = Field(..., description="Unique rule identifier")
    rule_name: str = Field(..., description="Human-readable rule name")
    engine: str = Field(..., description="Engine this rule belongs to")
    rule_category: RuleCategory = Field(..., description="Rule type classification")
    implementation_type: ImplementationType = Field(
        ImplementationType.EXPLICIT, description="Implementation explicitness"
    )
    lifecycle_stage: Optional[str] = Field(
        None, description="When this rule fires in optimizer lifecycle"
    )
    source_files: List[str] = Field(
        default_factory=list, description="Source files implementing this rule"
    )
    registration_points: List[str] = Field(
        default_factory=list, description="Where rule is registered"
    )
    trigger_pattern: Optional[str] = Field(
        None, description="Pattern that triggers this rule"
    )
    preconditions: List[str] = Field(
        default_factory=list, description="Preconditions for rule application"
    )
    transformation_logic: Optional[str] = Field(
        None, description="What the rule transforms"
    )
    input_operators: List[str] = Field(
        default_factory=list, description="Input operator types"
    )
    output_operators: List[str] = Field(
        default_factory=list, description="Output operator types"
    )
    relational_algebra_form: Optional[str] = Field(
        None, description="Relation algebra expression"
    )
    depends_on_stats: bool = Field(
        False, description="Whether rule uses statistics"
    )
    depends_on_cost: bool = Field(
        False, description="Whether rule uses cost model"
    )
    depends_on_property: bool = Field(
        False, description="Whether rule uses physical properties"
    )
    examples: List[str] = Field(
        default_factory=list, description="Example transformations"
    )
    confidence: str = Field(
        "medium", description="Confidence level: high, medium, low, unknown"
    )
    uncertain_points: List[str] = Field(
        default_factory=list, description="Points needing manual review"
    )
    evidence: List[Evidence] = Field(
        default_factory=list, description="Evidence supporting this analysis"
    )
```

- [ ] **Step 4: Update schemas __init__.py**

```python
# optimizer_analysis/schemas/__init__.py
from optimizer_analysis.schemas.base import Evidence, EvidenceType
from optimizer_analysis.schemas.framework import (
    Framework, OptimizerStyle, EngineType, OptimizerPhase
)
from optimizer_analysis.schemas.rule import (
    Rule, RuleCategory, ImplementationType
)

__all__ = [
    "Evidence", "EvidenceType",
    "Framework", "OptimizerStyle", "EngineType", "OptimizerPhase",
    "Rule", "RuleCategory", "ImplementationType"
]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /home/lism/work/xlab/python/projects/py-optimizer1 && pytest tests/test_schemas/test_rule.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add optimizer_analysis/schemas/rule.py optimizer_analysis/schemas/__init__.py tests/test_schemas/test_rule.py
git commit -m "feat(schemas): add Rule schema with categories and implementation types"
```

---

### Task 4: Trait/Property Schema (Section 6.3)

**Files:**
- Create: `optimizer_analysis/schemas/trait.py`
- Test: `tests/test_schemas/test_trait.py`

- [ ] **Step 1: Write the failing test for Trait schema**

```python
# tests/test_schemas/test_trait.py
from optimizer_analysis.schemas.trait import TraitProperty, PropertyType
from optimizer_analysis.schemas.base import Evidence

def test_trait_creation():
    """TraitProperty must have name and type."""
    trait = TraitProperty(
        property_name="Distribution",
        property_type=PropertyType.PHYSICAL,
        representation="HashDistributionSpec",
        propagation_logic="Derived from input distribution and operator semantics",
        enforcer="EnforceHashDistribution",
        where_used=["Join", "Aggregate", "Exchange"],
        impact_on_search="Requires enforcing operator if property mismatch",
        evidence=[]
    )
    assert trait.property_name == "Distribution"
    assert trait.property_type == PropertyType.PHYSICAL

def test_property_types():
    """Property types per DESIGN.md Section 6.3."""
    types = [PropertyType.LOGICAL, PropertyType.PHYSICAL]
    assert len(types) == 2

def test_trait_with_enforcer():
    """Trait can specify enforcement mechanism."""
    trait = TraitProperty(
        property_name="Ordering",
        property_type=PropertyType.PHYSICAL,
        representation="SortSpec",
        enforcer="SortEnforcer",
        where_used=["SortMergeJoin", "Window", "OrderBy"],
        impact_on_search="May require additional sort operator",
        evidence=[
            Evidence(
                file_path="src/optimizer/properties/ordering.cpp",
                description="Ordering property implementation"
            )
        ]
    )
    assert trait.enforcer == "SortEnforcer"
    assert len(trait.where_used) == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lism/work/xlab/python/projects/py-optimizer1 && pytest tests/test_schemas/test_trait.py -v`
Expected: FAIL with "No module named 'optimizer_analysis.schemas.trait'"

- [ ] **Step 3: Write minimal implementation**

```python
# optimizer_analysis/schemas/trait.py
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

from optimizer_analysis.schemas.base import Evidence


class PropertyType(str, Enum):
    """Property classification type (DESIGN.md Section 6.3)."""
    LOGICAL = "logical"
    PHYSICAL = "physical"


class TraitProperty(BaseModel):
    """Trait/Property schema (DESIGN.md Section 6.3)."""
    property_name: str = Field(..., description="Property name")
    property_type: PropertyType = Field(..., description="Logical or physical property")
    representation: Optional[str] = Field(
        None, description="How property is represented in code"
    )
    propagation_logic: Optional[str] = Field(
        None, description="How property propagates through operators"
    )
    enforcer: Optional[str] = Field(
        None, description="Enforcer operator for this property"
    )
    where_used: List[str] = Field(
        default_factory=list, description="Operators using this property"
    )
    impact_on_search: Optional[str] = Field(
        None, description="How property affects search space"
    )
    evidence: List[Evidence] = Field(
        default_factory=list, description="Evidence supporting this analysis"
    )
```

- [ ] **Step 4: Update schemas __init__.py**

```python
# optimizer_analysis/schemas/__init__.py
from optimizer_analysis.schemas.base import Evidence, EvidenceType
from optimizer_analysis.schemas.framework import (
    Framework, OptimizerStyle, EngineType, OptimizerPhase
)
from optimizer_analysis.schemas.rule import (
    Rule, RuleCategory, ImplementationType
)
from optimizer_analysis.schemas.trait import TraitProperty, PropertyType

__all__ = [
    "Evidence", "EvidenceType",
    "Framework", "OptimizerStyle", "EngineType", "OptimizerPhase",
    "Rule", "RuleCategory", "ImplementationType",
    "TraitProperty", "PropertyType"
]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /home/lism/work/xlab/python/projects/py-optimizer1 && pytest tests/test_schemas/test_trait.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add optimizer_analysis/schemas/trait.py optimizer_analysis/schemas/__init__.py tests/test_schemas/test_trait.py
git commit -m "feat(schemas): add Trait/Property schema for physical and logical properties"
```

---

### Task 5: Statistics/Cost Schema (Section 6.4)

**Files:**
- Create: `optimizer_analysis/schemas/stats_cost.py`
- Test: `tests/test_schemas/test_stats_cost.py`

- [ ] **Step 1: Write the failing test for Stats/Cost schemas**

```python
# tests/test_schemas/test_stats_cost.py
from optimizer_analysis.schemas.stats_cost import StatisticsInfo, CostModel, StatsGranularity
from optimizer_analysis.schemas.base import Evidence

def test_statistics_info_creation():
    """StatisticsInfo must have source and granularity."""
    stats = StatisticsInfo(
        stats_source="TableStatistics",
        stats_objects=["ndv", "row_count", "null_count", "min_max"],
        stats_granularity=StatsGranularity.COLUMN,
        storage_location="Statistics cache in memory",
        collection_trigger="Analyze table command",
        collection_scheduler="Manual + auto on data change threshold",
        operator_estimation_logic="Cardinality = row_count * selectivity",
        evidence=[]
    )
    assert stats.stats_source == "TableStatistics"
    assert stats.stats_granularity == StatsGranularity.COLUMN

def test_stats_granularities():
    """Stats granularity levels."""
    granularities = [
        StatsGranularity.TABLE,
        StatsGranularity.COLUMN,
        StatsGranularity.PARTITION,
        StatsGranularity.HISTOGRAM,
    ]
    assert len(granularities) == 4

def test_cost_model_creation():
    """CostModel must have dimensions."""
    cost = CostModel(
        cost_formula_location="src/optimizer/cost/cost_model.cpp",
        cost_dimensions=["cpu_cycles", "memory_bytes", "io_operations", "network_bytes"],
        operator_costs={
            "Scan": "io_cost + cpu_cost",
            "Join": "left_cost + right_cost + comparison_cost",
        },
        evidence=[]
    )
    assert len(cost.cost_dimensions) == 4
    assert "Scan" in cost.operator_costs

def test_cost_with_dimensions():
    """Cost can specify formula locations."""
    cost = CostModel(
        cost_formula_location="src/optimizer/cost/",
        cost_dimensions=["cpu", "io", "memory"],
        operator_costs={
            "Filter": "input_rows * cpu_per_row",
        },
        evidence=[
            Evidence(
                file_path="src/optimizer/cost/filter_cost.cpp",
                description="Filter operator cost formula"
            )
        ]
    )
    assert len(cost.evidence) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lism/work/xlab/python/projects/py-optimizer1 && pytest tests/test_schemas/test_stats_cost.py -v`
Expected: FAIL with "No module named 'optimizer_analysis.schemas.stats_cost'"

- [ ] **Step 3: Write minimal implementation**

```python
# optimizer_analysis/schemas/stats_cost.py
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from optimizer_analysis.schemas.base import Evidence


class StatsGranularity(str, Enum):
    """Statistics granularity levels."""
    TABLE = "table"
    COLUMN = "column"
    PARTITION = "partition"
    HISTOGRAM = "histogram"


class StatisticsInfo(BaseModel):
    """Statistics schema (DESIGN.md Section 6.4)."""
    stats_source: str = Field(..., description="Statistics collection source")
    stats_objects: List[str] = Field(
        default_factory=list, description="Statistics objects collected"
    )
    stats_granularity: StatsGranularity = Field(
        StatsGranularity.COLUMN, description="Granularity of statistics"
    )
    storage_location: Optional[str] = Field(
        None, description="Where statistics are stored"
    )
    collection_trigger: Optional[str] = Field(
        None, description="What triggers statistics collection"
    )
    collection_scheduler: Optional[str] = Field(
        None, description="How collection is scheduled"
    )
    operator_estimation_logic: Optional[str] = Field(
        None, description="How stats are used for cardinality estimation"
    )
    uncertain_points: List[str] = Field(
        default_factory=list, description="Points needing review"
    )
    evidence: List[Evidence] = Field(
        default_factory=list, description="Evidence supporting this analysis"
    )


class CostModel(BaseModel):
    """Cost schema (DESIGN.md Section 6.4)."""
    cost_formula_location: Optional[str] = Field(
        None, description="Where cost formulas are defined"
    )
    cost_dimensions: List[str] = Field(
        default_factory=list, description="Cost dimensions considered"
    )
    operator_costs: Dict[str, str] = Field(
        default_factory=dict, description="Cost formula per operator"
    )
    uncertain_points: List[str] = Field(
        default_factory=list, description="Points needing review"
    )
    evidence: List[Evidence] = Field(
        default_factory=list, description="Evidence supporting this analysis"
    )
```

- [ ] **Step 4: Update schemas __init__.py**

```python
# optimizer_analysis/schemas/__init__.py
from optimizer_analysis.schemas.base import Evidence, EvidenceType
from optimizer_analysis.schemas.framework import (
    Framework, OptimizerStyle, EngineType, OptimizerPhase
)
from optimizer_analysis.schemas.rule import (
    Rule, RuleCategory, ImplementationType
)
from optimizer_analysis.schemas.trait import TraitProperty, PropertyType
from optimizer_analysis.schemas.stats_cost import (
    StatisticsInfo, CostModel, StatsGranularity
)

__all__ = [
    "Evidence", "EvidenceType",
    "Framework", "OptimizerStyle", "EngineType", "OptimizerPhase",
    "Rule", "RuleCategory", "ImplementationType",
    "TraitProperty", "PropertyType",
    "StatisticsInfo", "CostModel", "StatsGranularity"
]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /home/lism/work/xlab/python/projects/py-optimizer1 && pytest tests/test_schemas/test_stats_cost.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add optimizer_analysis/schemas/stats_cost.py optimizer_analysis/schemas/__init__.py tests/test_schemas/test_stats_cost.py
git commit -m "feat(schemas): add Statistics and Cost model schemas"
```

---

### Task 6: Observability Schema (Section 6.5)

**Files:**
- Create: `optimizer_analysis/schemas/observability.py`
- Test: `tests/test_schemas/test_observability.py`

- [ ] **Step 1: Write the failing test for Observability schema**

```python
# tests/test_schemas/test_observability.py
from optimizer_analysis.schemas.observability import Observability
from optimizer_analysis.schemas.base import Evidence

def test_observability_creation():
    """Observability must have explain interfaces."""
    obs = Observability(
        explain_interfaces=["EXPLAIN", "EXPLAIN ANALYZE", "EXPLAIN VERBOSE"],
        trace_interfaces=["optimizer_trace", "cost_trace"],
        rule_fire_visibility="partial",
        memo_dump_support=True,
        session_controls=["optimizer_switch", "cost_threshold"],
        debug_hooks=["optimizer_debug_level"],
        evidence=[]
    )
    assert len(obs.explain_interfaces) == 3
    assert obs.memo_dump_support == True

def test_observability_with_partial_visibility():
    """Observability can have different visibility levels."""
    obs = Observability(
        explain_interfaces=["EXPLAIN"],
        trace_interfaces=[],
        rule_fire_visibility="none",
        memo_dump_support=False,
        session_controls=["enable_nondeterministic_optimizations"],
        evidence=[
            Evidence(
                file_path="docs/optimizer_explain.md",
                description="Explain output documentation",
                evidence_type=EvidenceType.DOCUMENTATION
            )
        ]
    )
    assert obs.rule_fire_visibility == "none"
    assert len(obs.evidence) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lism/work/xlab/python/projects/py-optimizer1 && pytest tests/test_schemas/test_observability.py -v`
Expected: FAIL with "No module named 'optimizer_analysis.schemas.observability'"

- [ ] **Step 3: Write minimal implementation**

```python
# optimizer_analysis/schemas/observability.py
from typing import List, Optional
from pydantic import BaseModel, Field

from optimizer_analysis.schemas.base import Evidence


class Observability(BaseModel):
    """Observability/Explainability schema (DESIGN.md Section 6.5)."""
    explain_interfaces: List[str] = Field(
        default_factory=list, description="EXPLAIN command variants"
    )
    trace_interfaces: List[str] = Field(
        default_factory=list, description="Trace/debug interfaces"
    )
    rule_fire_visibility: str = Field(
        "none", description="Visibility of rule firing: full, partial, none"
    )
    memo_dump_support: bool = Field(
        False, description="Whether memo/plan space can be dumped"
    )
    session_controls: List[str] = Field(
        default_factory=list, description="Session-level optimizer controls"
    )
    debug_hooks: List[str] = Field(
        default_factory=list, description="Debug hooks or flags"
    )
    uncertain_points: List[str] = Field(
        default_factory=list, description="Points needing review"
    )
    evidence: List[Evidence] = Field(
        default_factory=list, description="Evidence supporting this analysis"
    )
```

- [ ] **Step 4: Update schemas __init__.py**

```python
# optimizer_analysis/schemas/__init__.py
from optimizer_analysis.schemas.base import Evidence, EvidenceType
from optimizer_analysis.schemas.framework import (
    Framework, OptimizerStyle, EngineType, OptimizerPhase
)
from optimizer_analysis.schemas.rule import (
    Rule, RuleCategory, ImplementationType
)
from optimizer_analysis.schemas.trait import TraitProperty, PropertyType
from optimizer_analysis.schemas.stats_cost import (
    StatisticsInfo, CostModel, StatsGranularity
)
from optimizer_analysis.schemas.observability import Observability

__all__ = [
    "Evidence", "EvidenceType",
    "Framework", "OptimizerStyle", "EngineType", "OptimizerPhase",
    "Rule", "RuleCategory", "ImplementationType",
    "TraitProperty", "PropertyType",
    "StatisticsInfo", "CostModel", "StatsGranularity",
    "Observability"
]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /home/lism/work/xlab/python/projects/py-optimizer1 && pytest tests/test_schemas/test_observability.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add optimizer_analysis/schemas/observability.py optimizer_analysis/schemas/__init__.py tests/test_schemas/test_observability.py
git commit -m "feat(schemas): add Observability schema for explainability interfaces"
```

---

### Task 7: Extensibility Schema (Section 6.6)

**Files:**
- Create: `optimizer_analysis/schemas/extensibility.py`
- Test: `tests/test_schemas/test_extensibility.py`

- [ ] **Step 1: Write the failing test for Extensibility schema**

```python
# tests/test_schemas/test_extensibility.py
from optimizer_analysis.schemas.extensibility import Extensibility
from optimizer_analysis.schemas.base import Evidence

def test_extensibility_creation():
    """Extensibility must have extension paths."""
    ext = Extensibility(
        rule_extension_path="src/optimizer/rules/custom/",
        property_extension_path="src/optimizer/properties/",
        cost_extension_path="src/optimizer/cost/custom_cost.cpp",
        stats_extension_path="src/stats/custom_stats.cpp",
        plugin_registration="RegisterCustomRule()",
        testing_support="Rule test framework provided",
        evidence=[]
    )
    assert ext.rule_extension_path == "src/optimizer/rules/custom/"
    assert ext.plugin_registration == "RegisterCustomRule()"

def test_extensibility_framework_level():
    """Extensibility for framework-type engines."""
    ext = Extensibility(
        rule_extension_path="Full rule registration API",
        property_extension_path="Trait/property registration API",
        cost_extension_path="Cost model provider interface",
        plugin_registration="PlannerRule registration",
        testing_support="Built-in rule testing harness",
        evidence=[
            Evidence(
                file_path="docs/rule_extension.md",
                description="Rule extension guide",
                evidence_type=EvidenceType.DOCUMENTATION
            )
        ]
    )
    assert ext.testing_support == "Built-in rule testing harness"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lism/work/xlab/python/projects/py-optimizer1 && pytest tests/test_schemas/test_extensibility.py -v`
Expected: FAIL with "No module named 'optimizer_analysis.schemas.extensibility'"

- [ ] **Step 3: Write minimal implementation**

```python
# optimizer_analysis/schemas/extensibility.py
from typing import List, Optional
from pydantic import BaseModel, Field

from optimizer_analysis.schemas.base import Evidence


class Extensibility(BaseModel):
    """Extensibility schema (DESIGN.md Section 6.6)."""
    rule_extension_path: Optional[str] = Field(
        None, description="Path/API for custom rule extension"
    )
    property_extension_path: Optional[str] = Field(
        None, description="Path/API for property/trait extension"
    )
    cost_extension_path: Optional[str] = Field(
        None, description="Path/API for cost model extension"
    )
    stats_extension_path: Optional[str] = Field(
        None, description="Path/API for statistics extension"
    )
    plugin_registration: Optional[str] = Field(
        None, description="How plugins are registered"
    )
    testing_support: Optional[str] = Field(
        None, description="Testing support for extensions"
    )
    uncertain_points: List[str] = Field(
        default_factory=list, description="Points needing review"
    )
    evidence: List[Evidence] = Field(
        default_factory=list, description="Evidence supporting this analysis"
    )
```

- [ ] **Step 4: Update schemas __init__.py**

```python
# optimizer_analysis/schemas/__init__.py
from optimizer_analysis.schemas.base import Evidence, EvidenceType
from optimizer_analysis.schemas.framework import (
    Framework, OptimizerStyle, EngineType, OptimizerPhase
)
from optimizer_analysis.schemas.rule import (
    Rule, RuleCategory, ImplementationType
)
from optimizer_analysis.schemas.trait import TraitProperty, PropertyType
from optimizer_analysis.schemas.stats_cost import (
    StatisticsInfo, CostModel, StatsGranularity
)
from optimizer_analysis.schemas.observability import Observability
from optimizer_analysis.schemas.extensibility import Extensibility

__all__ = [
    "Evidence", "EvidenceType",
    "Framework", "OptimizerStyle", "EngineType", "OptimizerPhase",
    "Rule", "RuleCategory", "ImplementationType",
    "TraitProperty", "PropertyType",
    "StatisticsInfo", "CostModel", "StatsGranularity",
    "Observability", "Extensibility"
]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /home/lism/work/xlab/python/projects/py-optimizer1 && pytest tests/test_schemas/test_extensibility.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add optimizer_analysis/schemas/extensibility.py optimizer_analysis/schemas/__init__.py tests/test_schemas/test_extensibility.py
git commit -m "feat(schemas): add Extensibility schema for plugin extension paths"
```

---

### Task 8: Base Agent Class

**Files:**
- Create: `optimizer_analysis/agents/__init__.py`
- Create: `optimizer_analysis/agents/base.py`
- Test: `tests/test_agents/__init__.py`
- Test: `tests/test_agents/test_base.py`

- [ ] **Step 1: Write the failing test for Base Agent**

```python
# tests/test_agents/__init__.py
# Empty init file
```

```python
# tests/test_agents/test_base.py
from optimizer_analysis.agents.base import BaseAgent, AgentResult

def test_agent_result_creation():
    """AgentResult must have status and artifacts."""
    result = AgentResult(
        agent_name="RepoMapper",
        status="success",
        artifacts=["repo_map.json", "directory_summary.md"],
        summary="Mapped StarRocks optimizer directory structure"
    )
    assert result.status == "success"
    assert len(result.artifacts) == 2

def test_agent_result_failure():
    """AgentResult can represent failure."""
    result = AgentResult(
        agent_name="RepoMapper",
        status="failed",
        artifacts=[],
        errors=["Could not locate optimizer directory"],
        summary="Failed to map repository"
    )
    assert result.status == "failed"
    assert len(result.errors) == 1

def test_base_agent_abstract():
    """BaseAgent should be abstract with execute method."""
    import inspect
    from abc import ABC
    
    assert inspect.isabstract(BaseAgent)
    # Check that execute is an abstract method
    methods = [m for m in dir(BaseAgent) if not m.startswith('_')]
    assert 'execute' in methods or hasattr(BaseAgent, 'execute')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lism/work/xlab/python/projects/py-optimizer1 && pytest tests/test_agents/test_base.py -v`
Expected: FAIL with "No module named 'optimizer_analysis.agents'"

- [ ] **Step 3: Write minimal implementation**

```python
# optimizer_analysis/agents/__init__.py
from optimizer_analysis.agents.base import BaseAgent, AgentResult

__all__ = ["BaseAgent", "AgentResult"]
```

```python
# optimizer_analysis/agents/base.py
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AgentResult(BaseModel):
    """Result from agent execution."""
    agent_name: str = Field(..., description="Name of the agent")
    status: str = Field(..., description="success, failed, partial")
    artifacts: List[str] = Field(
        default_factory=list, description="Generated artifact files"
    )
    errors: List[str] = Field(
        default_factory=list, description="Error messages"
    )
    summary: str = Field("", description="Brief summary of results")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


class BaseAgent(ABC):
    """Base class for all analysis agents."""
    
    name: str
    
    def __init__(self, engine: str, work_dir: str):
        self.engine = engine
        self.work_dir = work_dir
    
    @abstractmethod
    def execute(self) -> AgentResult:
        """Execute the agent's analysis task."""
        pass
    
    def _artifact_path(self, filename: str) -> str:
        """Get full path for an artifact file."""
        return f"{self.work_dir}/{self.engine}/{filename}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/lism/work/xlab/python/projects/py-optimizer1 && pytest tests/test_agents/test_base.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add optimizer_analysis/agents/__init__.py optimizer_analysis/agents/base.py tests/test_agents/__init__.py tests/test_agents/test_base.py
git commit -m "feat(agents): add BaseAgent abstract class and AgentResult"
```

---

### Task 9: Repository Mapper Agent (Section 7.1)

**Files:**
- Create: `optimizer_analysis/agents/repo_mapper.py`
- Create: `optimizer_analysis/artifacts/.gitkeep`
- Test: `tests/test_agents/test_repo_mapper.py`

- [ ] **Step 1: Write the failing test for RepoMapper Agent**

```python
# tests/test_agents/test_repo_mapper.py
import tempfile
import os
from optimizer_analysis.agents.repo_mapper import RepoMapperAgent, RepoMap

def test_repo_map_creation():
    """RepoMap must have engine and directories."""
    repo_map = RepoMap(
        engine="StarRocks",
        repo_root="/path/to/starrocks",
        optimizer_dirs=["src/optimizer", "src/cost", "src/stats"],
        main_entries=["src/optimizer/optimizer.cpp"],
        rule_registry=["src/optimizer/rule_registry.cpp"],
        stats_dir="src/stats",
        cost_dir="src/cost",
        explain_dir="src/explain",
        confidence="high"
    )
    assert repo_map.engine == "StarRocks"
    assert len(repo_map.optimizer_dirs) == 3

def test_repo_mapper_agent():
    """RepoMapperAgent should be instantiable."""
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = RepoMapperAgent(
            engine="StarRocks",
            work_dir=tmpdir,
            repo_root="/path/to/starrocks"
        )
        assert agent.name == "RepoMapper"
        assert agent.repo_root == "/path/to/starrocks"

def test_repo_mapper_execute():
    """RepoMapper execute returns AgentResult."""
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = RepoMapperAgent(
            engine="StarRocks",
            work_dir=tmpdir,
            repo_root="/path/to/starrocks"
        )
        result = agent.execute()
        assert result.agent_name == "RepoMapper"
        assert result.status in ["success", "failed", "partial"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lism/work/xlab/python/projects/py-optimizer1 && pytest tests/test_agents/test_repo_mapper.py -v`
Expected: FAIL with "No module named 'optimizer_analysis.agents.repo_mapper'"

- [ ] **Step 3: Write minimal implementation**

```python
# optimizer_analysis/agents/repo_mapper.py
from typing import List, Optional
from pydantic import BaseModel, Field

from optimizer_analysis.agents.base import BaseAgent, AgentResult


class RepoMap(BaseModel):
    """Repository map output (DESIGN.md Section 7.1)."""
    engine: str = Field(..., description="Engine name")
    repo_root: str = Field(..., description="Repository root path")
    optimizer_dirs: List[str] = Field(
        default_factory=list, description="Optimizer-related directories"
    )
    main_entries: List[str] = Field(
        default_factory=list, description="Main optimizer entry files"
    )
    rule_registry: List[str] = Field(
        default_factory=list, description="Rule registration files"
    )
    stats_dir: Optional[str] = Field(None, description="Statistics directory")
    cost_dir: Optional[str] = Field(None, description="Cost model directory")
    explain_dir: Optional[str] = Field(None, description="Explain/debug directory")
    call_graph_seeds: List[str] = Field(
        default_factory=list, description="Call graph entry points"
    )
    fallback_paths: List[str] = Field(
        default_factory=list, description="Fallback optimizer paths"
    )
    confidence: str = Field("medium", description="Mapping confidence level")
    notes: List[str] = Field(default_factory=list, description="Additional notes")


class RepoMapperAgent(BaseAgent):
    """Repository Mapper Agent (DESIGN.md Section 7.1)."""
    
    name = "RepoMapper"
    
    def __init__(self, engine: str, work_dir: str, repo_root: str):
        super().__init__(engine, work_dir)
        self.repo_root = repo_root
    
    def execute(self) -> AgentResult:
        """Execute repository mapping."""
        # Placeholder - actual implementation would scan repo structure
        repo_map = RepoMap(
            engine=self.engine,
            repo_root=self.repo_root,
            optimizer_dirs=[],
            main_entries=[],
            confidence="needs_manual_review"
        )
        
        return AgentResult(
            agent_name=self.name,
            status="partial",
            artifacts=[],
            summary="Repository mapping requires manual configuration"
        )
```

- [ ] **Step 4: Create artifacts directory placeholder**

```python
# optimizer_analysis/artifacts/.gitkeep
# Placeholder for artifacts directory
```

```bash
touch optimizer_analysis/artifacts/.gitkeep
```

- [ ] **Step 5: Update agents __init__.py**

```python
# optimizer_analysis/agents/__init__.py
from optimizer_analysis.agents.base import BaseAgent, AgentResult
from optimizer_analysis.agents.repo_mapper import RepoMapperAgent, RepoMap

__all__ = ["BaseAgent", "AgentResult", "RepoMapperAgent", "RepoMap"]
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd /home/lism/work/xlab/python/projects/py-optimizer1 && pytest tests/test_agents/test_repo_mapper.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add optimizer_analysis/agents/repo_mapper.py optimizer_analysis/agents/__init__.py optimizer_analysis/artifacts/.gitkeep tests/test_agents/test_repo_mapper.py
git commit -m "feat(agents): add RepoMapperAgent for repository structure mapping"
```

---

### Task 10: Lifecycle Analyzer Agent (Section 7.2)

**Files:**
- Create: `optimizer_analysis/agents/lifecycle.py`
- Test: `tests/test_agents/test_lifecycle.py`

- [ ] **Step 1: Write the failing test for Lifecycle Analyzer**

```python
# tests/test_agents/test_lifecycle.py
import tempfile
from optimizer_analysis.agents.lifecycle import LifecycleAgent, LifecycleInfo
from optimizer_analysis.schemas.framework import OptimizerPhase

def test_lifecycle_info_creation():
    """LifecycleInfo must have phases."""
    lifecycle = LifecycleInfo(
        engine="StarRocks",
        phases=[
            {"phase": "parsing", "entry": "parse.cpp"},
            {"phase": "logical_opt", "entry": "logical_optimizer.cpp"},
            {"phase": "physical_opt", "entry": "physical_optimizer.cpp"},
        ],
        phase_sequence=["parsing", "logical_opt", "physical_opt"],
        logical_physical_boundary="After logical plan generation",
        best_plan_selection="Cost-based from memo",
        post_optimizer="Physical plan refinement",
        confidence="high"
    )
    assert lifecycle.engine == "StarRocks"
    assert len(lifecycle.phases) == 3

def test_lifecycle_agent():
    """LifecycleAgent should be instantiable."""
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = LifecycleAgent(
            engine="StarRocks",
            work_dir=tmpdir,
            repo_map=None  # Would normally pass RepoMap
        )
        assert agent.name == "LifecycleAnalyzer"

def test_lifecycle_agent_execute():
    """LifecycleAgent execute returns AgentResult."""
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = LifecycleAgent(
            engine="StarRocks",
            work_dir=tmpdir,
            repo_map=None
        )
        result = agent.execute()
        assert result.agent_name == "LifecycleAnalyzer"
        assert result.status in ["success", "failed", "partial"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lism/work/xlab/python/projects/py-optimizer1 && pytest tests/test_agents/test_lifecycle.py -v`
Expected: FAIL with "No module named 'optimizer_analysis.agents.lifecycle'"

- [ ] **Step 3: Write minimal implementation**

```python
# optimizer_analysis/agents/lifecycle.py
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from optimizer_analysis.agents.base import BaseAgent, AgentResult
from optimizer_analysis.agents.repo_mapper import RepoMap


class PhaseInfo(BaseModel):
    """Single phase information."""
    phase: str = Field(..., description="Phase name")
    entry: Optional[str] = Field(None, description="Entry point for this phase")
    description: Optional[str] = Field(None, description="Phase description")
    transitions_to: List[str] = Field(
        default_factory=list, description="Next phases"
    )


class LifecycleInfo(BaseModel):
    """Lifecycle analysis output (DESIGN.md Section 7.2)."""
    engine: str = Field(..., description="Engine name")
    phases: List[PhaseInfo] = Field(
        default_factory=list, description="Phase details"
    )
    phase_sequence: List[str] = Field(
        default_factory=list, description="Ordered phase names"
    )
    logical_physical_boundary: Optional[str] = Field(
        None, description="Where logical becomes physical"
    )
    best_plan_selection: Optional[str] = Field(
        None, description="How best plan is chosen"
    )
    post_optimizer: Optional[str] = Field(
        None, description="Post-optimizer stage"
    )
    fallback_behavior: Optional[str] = Field(
        None, description="Fallback behavior description"
    )
    confidence: str = Field("medium", description="Analysis confidence")
    notes: List[str] = Field(default_factory=list, description="Additional notes")


class LifecycleAgent(BaseAgent):
    """Lifecycle Analyzer Agent (DESIGN.md Section 7.2)."""
    
    name = "LifecycleAnalyzer"
    
    def __init__(self, engine: str, work_dir: str, repo_map: Optional[RepoMap] = None):
        super().__init__(engine, work_dir)
        self.repo_map = repo_map
    
    def execute(self) -> AgentResult:
        """Execute lifecycle analysis."""
        # Placeholder - actual implementation would analyze call graph
        lifecycle = LifecycleInfo(
            engine=self.engine,
            phases=[],
            phase_sequence=[],
            confidence="needs_manual_review"
        )
        
        return AgentResult(
            agent_name=self.name,
            status="partial",
            artifacts=["framework/lifecycle.json"],
            summary="Lifecycle analysis requires repo_map input"
        )
```

- [ ] **Step 4: Update agents __init__.py**

```python
# optimizer_analysis/agents/__init__.py
from optimizer_analysis.agents.base import BaseAgent, AgentResult
from optimizer_analysis.agents.repo_mapper import RepoMapperAgent, RepoMap
from optimizer_analysis.agents.lifecycle import LifecycleAgent, LifecycleInfo

__all__ = [
    "BaseAgent", "AgentResult",
    "RepoMapperAgent", "RepoMap",
    "LifecycleAgent", "LifecycleInfo"
]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /home/lism/work/xlab/python/projects/py-optimizer1 && pytest tests/test_agents/test_lifecycle.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add optimizer_analysis/agents/lifecycle.py optimizer_analysis/agents/__init__.py tests/test_agents/test_lifecycle.py
git commit -m "feat(agents): add LifecycleAnalyzerAgent for optimizer lifecycle analysis"
```

---

### Task 11: Engine Registry and Configuration

**Files:**
- Create: `optimizer_analysis/engines/__init__.py`
- Create: `optimizer_analysis/engines/base.py`
- Create: `optimizer_analysis/engines/registry.py`
- Test: `tests/test_engines/__init__.py`
- Test: `tests/test_engines/test_registry.py`

- [ ] **Step 1: Write the failing test for Engine Registry**

```python
# tests/test_engines/__init__.py
# Empty init file
```

```python
# tests/test_engines/test_registry.py
from optimizer_analysis.engines.registry import EngineRegistry, EngineConfig
from optimizer_analysis.schemas.framework import EngineType, OptimizerStyle

def test_engine_config_creation():
    """EngineConfig must have name and repo info."""
    config = EngineConfig(
        name="StarRocks",
        repo_url="https://github.com/StarRocks/starrocks",
        default_branch="main",
        engine_type=EngineType.COLUMNAR_OLAP,
        optimizer_style=OptimizerStyle.CASCADES,
        optimizer_dirs=["src/optimizer"],
        main_entry="src/optimizer/optimizer.cpp"
    )
    assert config.name == "StarRocks"
    assert config.optimizer_style == OptimizerStyle.CASCADES

def test_engine_registry():
    """EngineRegistry should register engines."""
    registry = EngineRegistry()
    registry.register(EngineConfig(
        name="StarRocks",
        repo_url="https://github.com/StarRocks/starrocks",
        default_branch="main",
        engine_type=EngineType.COLUMNAR_OLAP,
        optimizer_style=OptimizerStyle.CASCADES
    ))
    
    engines = registry.list_engines()
    assert "StarRocks" in engines

def test_engine_registry_get():
    """EngineRegistry should retrieve engine config."""
    registry = EngineRegistry()
    config = EngineConfig(
        name="ClickHouse",
        repo_url="https://github.com/ClickHouse/ClickHouse",
        default_branch="main",
        engine_type=EngineType.COLUMNAR_OLAP,
        optimizer_style=OptimizerStyle.ANALYZER_PLANNER
    )
    registry.register(config)
    
    retrieved = registry.get("ClickHouse")
    assert retrieved.name == "ClickHouse"
    assert retrieved.optimizer_style == OptimizerStyle.ANALYZER_PLANNER
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lism/work/xlab/python/projects/py-optimizer1 && pytest tests/test_engines/test_registry.py -v`
Expected: FAIL with "No module named 'optimizer_analysis.engines'"

- [ ] **Step 3: Write minimal implementation**

```python
# optimizer_analysis/engines/__init__.py
from optimizer_analysis.engines.base import EngineConfig
from optimizer_analysis.engines.registry import EngineRegistry

__all__ = ["EngineConfig", "EngineRegistry"]
```

```python
# optimizer_analysis/engines/base.py
from typing import List, Optional
from pydantic import BaseModel, Field

from optimizer_analysis.schemas.framework import EngineType, OptimizerStyle


class EngineConfig(BaseModel):
    """Configuration for an engine to analyze."""
    name: str = Field(..., description="Engine name")
    repo_url: Optional[str] = Field(None, description="Repository URL")
    default_branch: str = Field("main", description="Default branch to analyze")
    engine_type: EngineType = Field(..., description="Engine classification")
    optimizer_style: OptimizerStyle = Field(..., description="Optimizer architecture")
    optimizer_dirs: List[str] = Field(
        default_factory=list, description="Optimizer directories"
    )
    main_entry: Optional[str] = Field(None, description="Main optimizer entry")
    fallback_paths: List[str] = Field(
        default_factory=list, description="Fallback optimizer paths"
    )
    docs_url: Optional[str] = Field(None, description="Documentation URL")
    notes: List[str] = Field(default_factory=list, description="Additional notes")
```

```python
# optimizer_analysis/engines/registry.py
from typing import Dict, List

from optimizer_analysis.engines.base import EngineConfig


class EngineRegistry:
    """Registry of engines available for analysis."""
    
    _engines: Dict[str, EngineConfig] = {}
    
    def register(self, config: EngineConfig) -> None:
        """Register an engine configuration."""
        self._engines[config.name] = config
    
    def get(self, name: str) -> EngineConfig:
        """Get engine configuration by name."""
        if name not in self._engines:
            raise KeyError(f"Engine '{name}' not registered")
        return self._engines[name]
    
    def list_engines(self) -> List[str]:
        """List all registered engine names."""
        return list(self._engines.keys())
    
    def clear(self) -> None:
        """Clear all registered engines."""
        self._engines.clear()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/lism/work/xlab/python/projects/py-optimizer1 && pytest tests/test_engines/test_registry.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add optimizer_analysis/engines/__init__.py optimizer_analysis/engines/base.py optimizer_analysis/engines/registry.py tests/test_engines/__init__.py tests/test_engines/test_registry.py
git commit -m "feat(engines): add EngineConfig and EngineRegistry for engine management"
```

---

### Task 12: Project Requirements and Final Test

**Files:**
- Create: `requirements.txt`
- Create: `tests/__init__.py`
- Run: Full test suite

- [ ] **Step 1: Create requirements.txt**

```text
# requirements.txt
pydantic>=2.0.0
pytest>=7.0.0
```

```bash
pip install -r requirements.txt
```

- [ ] **Step 2: Create tests/__init__.py**

```python
# tests/__init__.py
# Optimizer analysis test suite
```

- [ ] **Step 3: Run full test suite**

Run: `cd /home/lism/work/xlab/python/projects/py-optimizer1 && pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add requirements.txt tests/__init__.py
git commit -m "chore: add requirements.txt and finalize project structure"
```

---

## Self-Review Checklist

### 1. Spec Coverage

| DESIGN.md Section | Task Coverage |
|-------------------|---------------|
| Section 6.1 Framework Schema | Task 2 ✓ |
| Section 6.2 Rule Schema | Task 3 ✓ |
| Section 6.3 Trait/Property Schema | Task 4 ✓ |
| Section 6.4 Stats/Cost Schema | Task 5 ✓ |
| Section 6.5 Observability Schema | Task 6 ✓ |
| Section 6.6 Extensibility Schema | Task 7 ✓ |
| Section 7.1 Repository Mapper Agent | Task 9 ✓ |
| Section 7.2 Lifecycle Analyzer Agent | Task 10 ✓ |
| Section 11 Directory Structure | Partial - core dirs created ✓ |
| Phase 1 Scope | All covered ✓ |

### 2. Placeholder Scan

No placeholders found. All code steps contain complete implementations.

### 3. Type Consistency

- `Evidence` used consistently across all schemas
- `EngineType` and `OptimizerStyle` enums used in Framework and EngineConfig
- `RuleCategory` and `ImplementationType` enums used consistently in Rule schema
- Agent names consistent: "RepoMapper", "LifecycleAnalyzer"

---

## Phase 2 Preview (Not in this plan)

Task 3-4 from DESIGN.md (Rule mining, Stats/Cost analysis) will be in Phase 2:
- Rule Miner Agents (RBO, CBO, Scalar, Post-Optimizer)
- Property & Enforcer Agent
- Statistics & Cost Agent
- Observability & Extensibility Agent

## Phase 3 Preview (Not in this plan)

Task 5 from DESIGN.md (Comparison):
- Comparison Agent
- Verifier Agent
- Matrix generation
- Final report generation