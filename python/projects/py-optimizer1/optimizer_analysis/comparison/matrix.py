"""Matrix generation for optimizer engine comparison.

This module provides the MatrixGenerator class for creating comparison
matrices across multiple optimizer engines.
"""

import csv
from pathlib import Path
from typing import Any, Dict, List, Optional

from optimizer_analysis.schemas import (
    ComparisonCell,
    ComparisonDimension,
    ComparisonMatrix,
    Framework,
    Observability,
    Rule,
    RuleCategory,
    TraitProperty,
)


class MatrixGenerator:
    """Generate comparison matrices for optimizer engines.

    Takes analysis results from multiple engines and generates structured
    comparison matrices for various dimensions.
    """

    def __init__(self, engines_data: Dict[str, Dict[str, Any]]):
        """Initialize the matrix generator with engine analysis data.

        Args:
            engines_data: Dictionary mapping engine name to its analysis results.
                Expected keys in each engine's data:
                - "framework": Framework schema instance
                - "rules": List of Rule schema instances
                - "properties": List of TraitProperty schema instances
                - "observability": Observability schema instance
        """
        self.engines_data = engines_data
        self.engine_names = list(engines_data.keys())

    def _get_framework(self, engine: str) -> Optional[Framework]:
        """Get framework data for an engine."""
        data = self.engines_data.get(engine, {})
        return data.get("framework")

    def _get_rules(self, engine: str) -> List[Rule]:
        """Get rules data for an engine."""
        data = self.engines_data.get(engine, {})
        return data.get("rules", [])

    def _get_properties(self, engine: str) -> List[TraitProperty]:
        """Get properties data for an engine."""
        data = self.engines_data.get(engine, {})
        return data.get("properties", [])

    def _get_observability(self, engine: str) -> Optional[Observability]:
        """Get observability data for an engine."""
        data = self.engines_data.get(engine, {})
        return data.get("observability")

    def _count_rules_by_category(self, rules: List[Rule], category: RuleCategory) -> int:
        """Count rules by category."""
        return sum(1 for rule in rules if rule.rule_category == category)

    def _format_phase_list(self, phases: Optional[List[str]]) -> str:
        """Format phase list for matrix display."""
        if not phases:
            return "none"
        return ", ".join(p.value if hasattr(p, "value") else str(p) for p in phases)

    def generate_lifecycle_matrix(self) -> ComparisonMatrix:
        """Generate a comparison matrix for optimizer lifecycle.

        Compares:
        - optimizer_style (cascades/volcano/etc)
        - logical_physical_split (yes/no)
        - memo_support (yes/no)
        - phases_present

        Returns:
            ComparisonMatrix with lifecycle dimension data.
        """
        cells: List[ComparisonCell] = []

        for engine in self.engine_names:
            framework = self._get_framework(engine)

            # optimizer_style
            style_value = "n/a"
            style_details = None
            if framework:
                style_value = framework.optimizer_style.value
                style_details = f"Architecture style: {style_value}"
            cells.append(ComparisonCell(
                engine=engine,
                dimension=ComparisonDimension.LIFECYCLE,
                value=style_value,
                details=style_details,
                evidence=framework.evidence if framework else []
            ))

            # logical_physical_split
            split_value = "no"
            split_details = None
            if framework:
                split_value = "yes" if framework.logical_physical_split else "no"
                split_details = "Logical and physical optimization are separate phases"
            cells.append(ComparisonCell(
                engine=engine,
                dimension=ComparisonDimension.LIFECYCLE,
                value=split_value,
                details=split_details,
                evidence=framework.evidence if framework else []
            ))

            # memo_support
            memo_value = "no"
            memo_details = None
            if framework and framework.memo_or_equivalent:
                memo_value = "yes"
                memo_details = f"Memo structure: {framework.memo_or_equivalent}"
            cells.append(ComparisonCell(
                engine=engine,
                dimension=ComparisonDimension.LIFECYCLE,
                value=memo_value,
                details=memo_details,
                evidence=framework.evidence if framework else []
            ))

            # phases_present
            phases_value = "none"
            phases_details = None
            if framework and framework.optimizer_phases:
                phases_value = self._format_phase_list(framework.optimizer_phases)
                phases_details = f"Lifecycle phases: {phases_value}"
            cells.append(ComparisonCell(
                engine=engine,
                dimension=ComparisonDimension.LIFECYCLE,
                value=phases_value,
                details=phases_details,
                evidence=framework.evidence if framework else []
            ))

        return ComparisonMatrix(
            engines=self.engine_names,
            dimensions=[ComparisonDimension.LIFECYCLE],
            cells=cells
        )

    def generate_rule_coverage_matrix(self) -> ComparisonMatrix:
        """Generate a comparison matrix for rule coverage.

        Compares:
        - rbo_rules_count
        - cbo_rules_count
        - scalar_rules_count
        - post_opt_rules_count

        Returns:
            ComparisonMatrix with rule coverage dimension data.
        """
        cells: List[ComparisonCell] = []

        for engine in self.engine_names:
            rules = self._get_rules(engine)

            # rbo_rules_count
            rbo_count = self._count_rules_by_category(rules, RuleCategory.RBO)
            cells.append(ComparisonCell(
                engine=engine,
                dimension=ComparisonDimension.RULE_COVERAGE,
                value=str(rbo_count),
                details=f"Rule-based optimization rules: {rbo_count}",
                evidence=[]
            ))

            # cbo_rules_count
            cbo_count = self._count_rules_by_category(rules, RuleCategory.CBO)
            cells.append(ComparisonCell(
                engine=engine,
                dimension=ComparisonDimension.RULE_COVERAGE,
                value=str(cbo_count),
                details=f"Cost-based optimization rules: {cbo_count}",
                evidence=[]
            ))

            # scalar_rules_count
            scalar_count = self._count_rules_by_category(rules, RuleCategory.SCALAR)
            cells.append(ComparisonCell(
                engine=engine,
                dimension=ComparisonDimension.RULE_COVERAGE,
                value=str(scalar_count),
                details=f"Scalar rules: {scalar_count}",
                evidence=[]
            ))

            # post_opt_rules_count
            post_opt_count = self._count_rules_by_category(rules, RuleCategory.POST_OPT)
            cells.append(ComparisonCell(
                engine=engine,
                dimension=ComparisonDimension.RULE_COVERAGE,
                value=str(post_opt_count),
                details=f"Post-optimization rules: {post_opt_count}",
                evidence=[]
            ))

        return ComparisonMatrix(
            engines=self.engine_names,
            dimensions=[ComparisonDimension.RULE_COVERAGE],
            cells=cells
        )

    def generate_property_matrix(self) -> ComparisonMatrix:
        """Generate a comparison matrix for property system.

        Compares:
        - distribution_support
        - ordering_support
        - enforcer_mechanisms

        Returns:
            ComparisonMatrix with property system dimension data.
        """
        cells: List[ComparisonCell] = []

        for engine in self.engine_names:
            properties = self._get_properties(engine)

            # distribution_support
            distribution_props = [p for p in properties
                                if "distribution" in p.property_name.lower()]
            dist_value = str(len(distribution_props))
            dist_details = None
            if distribution_props:
                dist_details = f"Distribution properties: {[p.property_name for p in distribution_props]}"
            cells.append(ComparisonCell(
                engine=engine,
                dimension=ComparisonDimension.PROPERTY_SYSTEM,
                value=dist_value,
                details=dist_details,
                evidence=distribution_props[0].evidence if distribution_props else []
            ))

            # ordering_support
            ordering_props = [p for p in properties
                            if "order" in p.property_name.lower()]
            order_value = str(len(ordering_props))
            order_details = None
            if ordering_props:
                order_details = f"Ordering properties: {[p.property_name for p in ordering_props]}"
            cells.append(ComparisonCell(
                engine=engine,
                dimension=ComparisonDimension.PROPERTY_SYSTEM,
                value=order_value,
                details=order_details,
                evidence=ordering_props[0].evidence if ordering_props else []
            ))

            # enforcer_mechanisms
            enforcers = [p for p in properties if p.enforcer]
            enforcer_value = str(len(enforcers))
            enforcer_details = None
            if enforcers:
                enforcer_details = f"Enforcers: {[p.enforcer for p in enforcers if p.enforcer]}"
            cells.append(ComparisonCell(
                engine=engine,
                dimension=ComparisonDimension.PROPERTY_SYSTEM,
                value=enforcer_value,
                details=enforcer_details,
                evidence=enforcers[0].evidence if enforcers else []
            ))

        return ComparisonMatrix(
            engines=self.engine_names,
            dimensions=[ComparisonDimension.PROPERTY_SYSTEM],
            cells=cells
        )

    def generate_observability_matrix(self) -> ComparisonMatrix:
        """Generate a comparison matrix for observability.

        Compares:
        - explain_support
        - trace_support
        - memo_dump_support
        - session_controls

        Returns:
            ComparisonMatrix with observability dimension data.
        """
        cells: List[ComparisonCell] = []

        for engine in self.engine_names:
            observability = self._get_observability(engine)

            # explain_support
            explain_value = "none"
            explain_details = None
            if observability and observability.explain_interfaces:
                explain_value = str(len(observability.explain_interfaces))
                explain_details = f"EXPLAIN variants: {observability.explain_interfaces}"
            cells.append(ComparisonCell(
                engine=engine,
                dimension=ComparisonDimension.OBSERVABILITY,
                value=explain_value,
                details=explain_details,
                evidence=observability.evidence if observability else []
            ))

            # trace_support
            trace_value = "none"
            trace_details = None
            if observability and observability.trace_interfaces:
                trace_value = str(len(observability.trace_interfaces))
                trace_details = f"Trace interfaces: {observability.trace_interfaces}"
            cells.append(ComparisonCell(
                engine=engine,
                dimension=ComparisonDimension.OBSERVABILITY,
                value=trace_value,
                details=trace_details,
                evidence=observability.evidence if observability else []
            ))

            # memo_dump_support
            memo_dump_value = "no"
            memo_dump_details = None
            if observability:
                memo_dump_value = "yes" if observability.memo_dump_support else "no"
                memo_dump_details = "Memo dump support available" if observability.memo_dump_support else None
            cells.append(ComparisonCell(
                engine=engine,
                dimension=ComparisonDimension.OBSERVABILITY,
                value=memo_dump_value,
                details=memo_dump_details,
                evidence=observability.evidence if observability else []
            ))

            # session_controls
            session_value = "none"
            session_details = None
            if observability and observability.session_controls:
                session_value = str(len(observability.session_controls))
                session_details = f"Session controls: {observability.session_controls}"
            cells.append(ComparisonCell(
                engine=engine,
                dimension=ComparisonDimension.OBSERVABILITY,
                value=session_value,
                details=session_details,
                evidence=observability.evidence if observability else []
            ))

        return ComparisonMatrix(
            engines=self.engine_names,
            dimensions=[ComparisonDimension.OBSERVABILITY],
            cells=cells
        )

    def generate_all_matrices(self) -> List[ComparisonMatrix]:
        """Generate all comparison matrices.

        Returns:
            List of all ComparisonMatrix instances.
        """
        return [
            self.generate_lifecycle_matrix(),
            self.generate_rule_coverage_matrix(),
            self.generate_property_matrix(),
            self.generate_observability_matrix(),
        ]

    def to_dataframe(self, matrix: ComparisonMatrix) -> Dict[str, Any]:
        """Convert a ComparisonMatrix to a dictionary suitable for table format.

        Args:
            matrix: The ComparisonMatrix to convert.

        Returns:
            Dictionary with 'columns' and 'data' keys that can be converted
            to various table formats (pandas DataFrame, tabulate, etc.).
        """
        # Build column headers: first column is 'metric', then engine names
        columns = ["metric"] + matrix.engines

        # Group cells by metric type for each dimension
        # For lifecycle matrix, we have 4 metrics per engine
        data = []

        # Define metric rows based on dimension
        metric_names = {
            ComparisonDimension.LIFECYCLE: [
                "optimizer_style",
                "logical_physical_split",
                "memo_support",
                "phases_present"
            ],
            ComparisonDimension.RULE_COVERAGE: [
                "rbo_rules_count",
                "cbo_rules_count",
                "scalar_rules_count",
                "post_opt_rules_count"
            ],
            ComparisonDimension.PROPERTY_SYSTEM: [
                "distribution_support",
                "ordering_support",
                "enforcer_mechanisms"
            ],
            ComparisonDimension.OBSERVABILITY: [
                "explain_support",
                "trace_support",
                "memo_dump_support",
                "session_controls"
            ]
        }

        # Get the dimension for this matrix
        dimension = matrix.dimensions[0] if matrix.dimensions else None
        metrics = metric_names.get(dimension, [])

        # Organize cells by metric
        cells_by_engine = {engine: [] for engine in matrix.engines}
        for cell in matrix.cells:
            cells_by_engine[cell.engine].append(cell)

        # Build rows
        for i, metric in enumerate(metrics):
            row = {"metric": metric}
            for engine in matrix.engines:
                engine_cells = cells_by_engine.get(engine, [])
                if i < len(engine_cells):
                    row[engine] = engine_cells[i].value
                else:
                    row[engine] = "n/a"
            data.append(row)

        return {
            "columns": columns,
            "data": data,
            "dimension": dimension.value if dimension else None,
            "generated_at": matrix.generated_at.isoformat()
        }

    def to_csv(self, matrix: ComparisonMatrix, path: str) -> None:
        """Write a ComparisonMatrix to a CSV file.

        Args:
            matrix: The ComparisonMatrix to write.
            path: File path for the output CSV file.
        """
        df_data = self.to_dataframe(matrix)
        columns = df_data["columns"]
        data = df_data["data"]

        # Ensure directory exists
        Path(path).parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=columns)
            writer.writeheader()
            for row in data:
                writer.writerow(row)