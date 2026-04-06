"""Data models for the Optimizer Expert Analyzer."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime


class TaskStatus(Enum):
    """Task status in the analysis pipeline."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


class RuleCategory(Enum):
    """Categories of optimizer rules."""
    RBO = "rbo"
    CBO = "cbo"
    SCALAR = "scalar"
    POST_OPT = "post_opt"
    PROPERTY = "property"
    STATISTICS = "statistics"


class OptimizerFramework(Enum):
    """Optimizer framework types."""
    CASCADES = "cascades"
    VOLCANO = "volcano"
    PATH_BASED = "path_based"
    OPTGEN = "optgen"
    CUSTOM = "custom"
    COLUMBIA = "columbia"


class Language(Enum):
    """Programming languages for source code."""
    CPP = "cpp"
    JAVA = "java"
    GO = "go"
    C = "c"


# 22 standard logical categories for cross-engine comparison
LOGICAL_CATEGORIES = [
    "predicate_pushdown",
    "join_reorder",
    "join_elimination",
    "subquery_unnesting",
    "aggregation_pushdown",
    "aggregation_elimination",
    "projection_pruning",
    "view_merging",
    "cte_reuse",
    "sort_elimination",
    "limit_pushdown",
    "partition_pruning",
    "constant_folding",
    "expression_simplification",
    "distribution_optimization",
    "physical_join_impl",
    "physical_agg_impl",
    "physical_scan_impl",
    "mv_rewrite",
    "set_operation",
    "window_function",
    "other",
]


@dataclass
class EngineConfig:
    """Configuration for a database engine."""
    engine_id: str
    display_name: str
    version: str
    language: Language
    optimizer_framework: OptimizerFramework
    optimizer_root: str
    patterns: Dict[str, Any]
    lifecycle_entry: Dict[str, str]
    rule_registry: Dict[str, str]
    scanner_hints: Dict[str, Any]


@dataclass
class Task:
    """A single analysis task."""
    task_id: str
    engine_id: str
    category: RuleCategory
    rule_name: str
    source_file: str
    source_snippet: str
    optimizer_framework: OptimizerFramework
    language: Language
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 1
    estimated_tokens: int = 0
    dsl_file: Optional[str] = None
    dsl_snippet: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    analyzed_at: Optional[str] = None
    retries: int = 0
    confidence: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


@dataclass
class RuleAnalysis:
    """Structured output from rule analysis."""
    # Identification
    task_id: str
    engine_id: str
    category: str
    rule_name: str
    source_file: str
    optimizer_framework: str
    dsl_snippet: Optional[str] = None

    # Core analysis
    summary: str = ""
    ra_input_pattern: str = ""
    ra_output_pattern: str = ""
    ra_condition: str = ""

    # Correctness and applicability
    correctness_conditions: List[str] = field(default_factory=list)
    performance_impact: str = ""
    edge_cases: List[str] = field(default_factory=list)

    # Framework-specific fields
    framework_notes: Optional[str] = None
    enforcer_triggered: Optional[bool] = None
    stats_dependencies: List[str] = field(default_factory=list)

    # Cross-engine comparison fields
    logical_category: str = "other"
    canonical_name: str = ""
    related_rules: List[str] = field(default_factory=list)

    # Quality metadata
    confidence: float = 0.0
    needs_review: bool = False
    analyzed_at: str = field(default_factory=lambda: datetime.now().isoformat())
    model_version: str = "claude-3-sonnet-20240229"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "engine_id": self.engine_id,
            "category": self.category,
            "rule_name": self.rule_name,
            "source_file": self.source_file,
            "dsl_snippet": self.dsl_snippet,
            "optimizer_framework": self.optimizer_framework,
            "summary": self.summary,
            "ra_input_pattern": self.ra_input_pattern,
            "ra_output_pattern": self.ra_output_pattern,
            "ra_condition": self.ra_condition,
            "correctness_conditions": self.correctness_conditions,
            "performance_impact": self.performance_impact,
            "edge_cases": self.edge_cases,
            "framework_notes": self.framework_notes,
            "enforcer_triggered": self.enforcer_triggered,
            "stats_dependencies": self.stats_dependencies,
            "logical_category": self.logical_category,
            "canonical_name": self.canonical_name,
            "related_rules": self.related_rules,
            "confidence": self.confidence,
            "needs_review": self.needs_review,
            "analyzed_at": self.analyzed_at,
            "model_version": self.model_version,
        }


@dataclass
class DiffMatrixEntry:
    """Entry in the cross-engine diff matrix."""
    canonical_name: str
    logical_category: str
    engines: Dict[str, Dict[str, Any]]
    all_present: bool
    semantic_equivalent: bool
    diff_summary: str
    alignment_score: float


@dataclass
class EngineScore:
    """Scoring result for an engine."""
    engine_id: str
    coverage_score: float
    semantic_equivalence_score: float
    trigger_completeness_score: float
    framework_maturity_score: float
    overall_score: float
