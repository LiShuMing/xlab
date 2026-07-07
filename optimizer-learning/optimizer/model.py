"""
Shared relational algebra model.

Corresponds to Calcite's:
  - RelNode → RelNode (this file)
  - RelTrait / RelTraitSet → Trait / TraitSet
  - VolcanoCost → Cost
  - Convention → Convention
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
from abc import ABC, abstractmethod
from enum import Enum


# ──────────────────────────────────────────────
# Cost Model
# ──────────────────────────────────────────────

@dataclass(frozen=True)
class Cost:
    """
    Cost tuple: (rows, cpu, io).
    Mirrors Calcite's VolcanoCost.
    """
    rows: float = 0.0
    cpu: float = 0.0
    io: float = 0.0

    INFINITY: "Cost" = None  # type: ignore

    def __add__(self, other: "Cost") -> "Cost":
        if self is Cost.INFINITY or other is Cost.INFINITY:
            return Cost.INFINITY
        return Cost(
            rows=self.rows + other.rows,
            cpu=self.cpu + other.cpu,
            io=self.io + other.io,
        )

    def __le__(self, other: "Cost") -> bool:
        if other is Cost.INFINITY:
            return True
        if self is Cost.INFINITY:
            return False
        return (self.rows <= other.rows
                and self.cpu <= other.cpu
                and self.io <= other.io)

    def __lt__(self, other: "Cost") -> bool:
        if other is Cost.INFINITY:
            return self is not Cost.INFINITY
        if self is Cost.INFINITY:
            return False
        return (self.rows < other.rows
                or (self.rows == other.rows and self.cpu < other.cpu)
                or (self.rows == other.rows and self.cpu == other.cpu and self.io < other.io))

    def __gt__(self, other: "Cost") -> bool:
        if self is Cost.INFINITY:
            return other is not Cost.INFINITY
        if other is Cost.INFINITY:
            return False
        return other < self

    def __repr__(self) -> str:
        if self is Cost.INFINITY:
            return "Cost(∞)"
        return f"Cost(rows={self.rows:.1f}, cpu={self.cpu:.1f}, io={self.io:.1f})"


# Initialize INFINITY after class definition
Cost.INFINITY = Cost(rows=float("inf"), cpu=float("inf"), io=float("inf"))


# ──────────────────────────────────────────────
# Traits & Convention
# ──────────────────────────────────────────────

class Convention(Enum):
    """
    Calling convention, like Calcite's Convention.
    NONE = abstract (logical), others = physical implementations.
    """
    NONE = "NONE"
    HASH_JOIN = "HASH_JOIN"
    NESTED_LOOP = "NESTED_LOOP"
    SORT_MERGE = "SORT_MERGE"
    ENUMERABLE = "ENUMERABLE"


@dataclass(frozen=True)
class TraitSet:
    """
    A set of traits that a RelNode satisfies.
    Like Calcite's RelTraitSet.
    """
    convention: Convention = Convention.NONE
    sorted: bool = False  # whether output is sorted
    distributed: str = "single"  # distribution trait

    def __repr__(self) -> str:
        parts = [self.convention.value]
        if self.sorted:
            parts.append("sorted")
        if self.distributed != "single":
            parts.append(f"dist={self.distributed}")
        return f"TraitSet({', '.join(parts)})"

    def satisfies(self, other: "TraitSet") -> bool:
        """Check if this trait set satisfies the required traits."""
        if self.convention == other.convention or other.convention == Convention.NONE:
            if not other.sorted or self.sorted:
                return True
        return False


# ──────────────────────────────────────────────
# RelNode (base class)
# ──────────────────────────────────────────────

class RelNode(ABC):
    """
    Base class for all relational expressions.
    Like Calcite's RelNode.
    """

    _next_id: int = 0

    def __init__(self, inputs: list["RelNode"], trait_set: TraitSet | None = None):
        self.id = RelNode._next_id
        RelNode._next_id += 1

        self.inputs: list[RelNode] = list(inputs)
        self.trait_set = trait_set or TraitSet()

        # Metadata: row count estimate
        self._row_count: float | None = None

        # For tracking in optimizer structures
        self._rel_set_id: int | None = None
        self._rel_subset_key: str | None = None

    @property
    def rel_set_id(self) -> int | None:
        return self._rel_set_id

    @rel_set_id.setter
    def rel_set_id(self, value: int | None) -> None:
        self._rel_set_id = value

    @property
    def rel_subset_key(self) -> str | None:
        return self._rel_subset_key

    @rel_subset_key.setter
    def rel_subset_key(self, value: str | None) -> None:
        self._rel_subset_key = value

    @abstractmethod
    def explain_name(self) -> str:
        """Human-readable name for explain output."""
        ...

    @abstractmethod
    def compute_row_count(self) -> float:
        """Estimate output row count."""
        ...

    def row_count(self) -> float:
        if self._row_count is None:
            self._row_count = self.compute_row_count()
        return self._row_count

    def reset_id_counter():
        RelNode._next_id = 0

    def __repr__(self) -> str:
        return f"{self.explain_name()}#{self.id}"


# ──────────────────────────────────────────────
# Concrete RelNode types
# ──────────────────────────────────────────────

class TableScan(RelNode):
    def __init__(self, table: str, row_count: float, trait_set: TraitSet | None = None):
        super().__init__([], trait_set or TraitSet(convention=Convention.NONE))
        self.table = table
        self._rc = row_count

    def explain_name(self) -> str:
        return f"Scan({self.table})"

    def compute_row_count(self) -> float:
        return self._rc


class LogicalFilter(RelNode):
    def __init__(self, input: RelNode, condition: str, selectivity: float = 0.1):
        super().__init__([input], TraitSet(convention=Convention.NONE))
        self.condition = condition
        self.selectivity = selectivity

    @property
    def input(self) -> RelNode:
        return self.inputs[0]

    def explain_name(self) -> str:
        return f"Filter({self.condition})"

    def compute_row_count(self) -> float:
        return self.input.row_count() * self.selectivity


class LogicalProject(RelNode):
    def __init__(self, input: RelNode, columns: list[str]):
        super().__init__([input], TraitSet(convention=Convention.NONE))
        self.columns = columns

    @property
    def input(self) -> RelNode:
        return self.inputs[0]

    def explain_name(self) -> str:
        return f"Project({', '.join(self.columns)})"

    def compute_row_count(self) -> float:
        return self.input.row_count()


class LogicalJoin(RelNode):
    def __init__(self, left: RelNode, right: RelNode, condition: str,
                 join_type: str = "inner", selectivity: float = 0.5):
        super().__init__([left, right], TraitSet(convention=Convention.NONE))
        self.condition = condition
        self.join_type = join_type
        self.selectivity = selectivity

    @property
    def left(self) -> RelNode:
        return self.inputs[0]

    @property
    def right(self) -> RelNode:
        return self.inputs[1]

    def explain_name(self) -> str:
        return f"Join({self.condition}, {self.join_type})"

    def compute_row_count(self) -> float:
        return self.left.row_count() * self.right.row_count() * self.selectivity


class LogicalAggregate(RelNode):
    def __init__(self, input: RelNode, group_keys: list[str], agg_funcs: list[str]):
        super().__init__([input], TraitSet(convention=Convention.NONE))
        self.group_keys = group_keys
        self.agg_funcs = agg_funcs

    @property
    def input(self) -> RelNode:
        return self.inputs[0]

    def explain_name(self) -> str:
        aggs = ", ".join(self.agg_funcs) if self.agg_funcs else ""
        return f"Aggregate(group=[{', '.join(self.group_keys)}], {aggs})"

    def compute_row_count(self) -> float:
        # Aggregates reduce rows to at most NDV of group keys
        return min(self.input.row_count(), 100.0)


# ──────────────────────────────────────────────
# Physical RelNode types
# ──────────────────────────────────────────────

class PhysicalJoin(RelNode):
    """A physical join implementation (HashJoin, NestedLoop, etc.)."""

    def __init__(self, left: RelNode, right: RelNode, condition: str,
                 impl: str, trait_set: TraitSet, selectivity: float = 0.5):
        super().__init__([left, right], trait_set)
        self.condition = condition
        self.impl = impl
        self.selectivity = selectivity

    @property
    def left(self) -> RelNode:
        return self.inputs[0]

    @property
    def right(self) -> RelNode:
        return self.inputs[1]

    def explain_name(self) -> str:
        return f"{self.impl}({self.condition})"

    def compute_row_count(self) -> float:
        return self.left.row_count() * self.right.row_count() * self.selectivity


class PhysicalFilter(RelNode):
    def __init__(self, input: RelNode, condition: str,
                 trait_set: TraitSet, selectivity: float = 0.1):
        super().__init__([input], trait_set)
        self.condition = condition
        self.selectivity = selectivity

    @property
    def input(self) -> RelNode:
        return self.inputs[0]

    def explain_name(self) -> str:
        return f"PFilter({self.condition})"

    def compute_row_count(self) -> float:
        return self.input.row_count() * self.selectivity


class PhysicalProject(RelNode):
    def __init__(self, input: RelNode, columns: list[str],
                 trait_set: TraitSet):
        super().__init__([input], trait_set)
        self.columns = columns

    @property
    def input(self) -> RelNode:
        return self.inputs[0]

    def explain_name(self) -> str:
        return f"PProject({', '.join(self.columns)})"

    def compute_row_count(self) -> float:
        return self.input.row_count()


class PhysicalTableScan(RelNode):
    def __init__(self, table: str, row_count: float,
                 trait_set: TraitSet):
        super().__init__([], trait_set)
        self.table = table
        self._rc = row_count

    def explain_name(self) -> str:
        return f"PScan({self.table})"

    def compute_row_count(self) -> float:
        return self._rc
