"""Report generation for optimizer engine comparison.

This module provides the ReportGenerator class for creating formatted
reports from comparison matrices.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List

from optimizer_analysis.schemas import ComparisonMatrix


class ReportGenerator:
    """Generate reports from comparison matrices.

    Takes comparison matrices and generates formatted reports in
    Markdown and JSON formats with key findings and recommendations.
    """

    def __init__(self, matrices: List[ComparisonMatrix]):
        """Initialize the report generator with comparison matrices.

        Args:
            matrices: List of ComparisonMatrix instances to analyze.
        """
        self.matrices = matrices
        self._findings: List[str] = []
        self._recommendations: List[str] = []
        self._analyze_matrices()

    def _analyze_matrices(self) -> None:
        """Analyze matrices to extract findings and recommendations."""
        self._findings = self._extract_findings()
        self._recommendations = self._extract_recommendations()

    def _extract_findings(self) -> List[str]:
        """Extract key findings from matrices.

        Returns:
            List of finding strings.
        """
        findings = []

        for matrix in self.matrices:
            if not matrix.cells:
                continue

            # Group cells by dimension for analysis
            dimension = matrix.dimensions[0] if matrix.dimensions else None
            if not dimension:
                continue

            dimension_findings = self._analyze_dimension(matrix, dimension)
            findings.extend(dimension_findings)

        return findings

    def _analyze_dimension(self, matrix: ComparisonMatrix, dimension) -> List[str]:
        """Analyze a single dimension matrix for findings.

        Args:
            matrix: The ComparisonMatrix to analyze.
            dimension: The ComparisonDimension being analyzed.

        Returns:
            List of findings for this dimension.
        """
        findings = []
        dim_name = dimension.value.replace("_", " ").title()

        # Group cells by engine
        cells_by_engine = {}
        for cell in matrix.cells:
            if cell.engine not in cells_by_engine:
                cells_by_engine[cell.engine] = []
            cells_by_engine[cell.engine].append(cell)

        # Analyze based on dimension type
        if dimension.value == "lifecycle":
            findings.extend(self._analyze_lifecycle(matrix, cells_by_engine))
        elif dimension.value == "rule_coverage":
            findings.extend(self._analyze_rule_coverage(matrix, cells_by_engine))
        elif dimension.value == "property_system":
            findings.extend(self._analyze_property_system(matrix, cells_by_engine))
        elif dimension.value == "observability":
            findings.extend(self._analyze_observability(matrix, cells_by_engine))

        # Prefix findings with dimension name if not already
        prefixed_findings = []
        for finding in findings:
            if not finding.startswith(dim_name):
                prefixed_findings.append(f"[{dim_name}] {finding}")
            else:
                prefixed_findings.append(finding)

        return prefixed_findings

    def _analyze_lifecycle(self, matrix: ComparisonMatrix,
                           cells_by_engine: dict) -> List[str]:
        """Analyze lifecycle dimension for findings.

        Args:
            matrix: The ComparisonMatrix to analyze.
            cells_by_engine: Dictionary mapping engine name to its cells.

        Returns:
            List of lifecycle findings.
        """
        findings = []

        # Check for Cascades-style optimizers
        cascades_engines = []
        for engine, cells in cells_by_engine.items():
            for cell in cells:
                if cell.value == "cascades":
                    cascades_engines.append(engine)
                    break

        if len(cascades_engines) > 0:
            findings.append(
                f"Cascades-style optimization found in: {', '.join(cascades_engines)}"
            )

        # Check for logical/physical split
        split_engines = []
        for engine, cells in cells_by_engine.items():
            for i, cell in enumerate(cells):
                # logical_physical_split is typically the second metric
                if "split" in cell.details.lower() if cell.details else False:
                    if cell.value == "yes":
                        split_engines.append(engine)
                    break
                # Fallback: check by position (index 1 in lifecycle matrix)
                if i == 1 and cell.value == "yes":
                    split_engines.append(engine)
                    break

        if split_engines:
            findings.append(
                f"Logical/physical optimization split present in: "
                f"{', '.join(split_engines)}"
            )

        # Check for memo support
        memo_engines = []
        for engine, cells in cells_by_engine.items():
            for i, cell in enumerate(cells):
                # memo_support is typically the third metric
                if i == 2 and cell.value == "yes":
                    memo_engines.append(engine)
                    break

        if memo_engines:
            findings.append(
                f"Memoization/Memo structure supported by: "
                f"{', '.join(memo_engines)}"
            )

        return findings

    def _analyze_rule_coverage(self, matrix: ComparisonMatrix,
                               cells_by_engine: dict) -> List[str]:
        """Analyze rule coverage dimension for findings.

        Args:
            matrix: The ComparisonMatrix to analyze.
            cells_by_engine: Dictionary mapping engine name to its cells.

        Returns:
            List of rule coverage findings.
        """
        findings = []

        # Calculate total rules and CBO ratio per engine
        for engine, cells in cells_by_engine.items():
            if len(cells) >= 2:
                try:
                    rbo_count = int(cells[0].value)
                    cbo_count = int(cells[1].value)
                    total = rbo_count + cbo_count

                    if total > 0:
                        cbo_ratio = cbo_count / total
                        if cbo_ratio > 0.5:
                            findings.append(
                                f"{engine} favors cost-based optimization "
                                f"({cbo_count} CBO vs {rbo_count} RBO rules)"
                            )
                        elif rbo_count > cbo_count:
                            findings.append(
                                f"{engine} has more rule-based optimization "
                                f"({rbo_count} RBO vs {cbo_count} CBO rules)"
                            )
                except ValueError:
                    pass

        # Check for scalar rules
        for engine, cells in cells_by_engine.items():
            if len(cells) >= 3:
                try:
                    scalar_count = int(cells[2].value)
                    if scalar_count > 0:
                        findings.append(
                            f"{engine} has {scalar_count} scalar optimization rules"
                        )
                except ValueError:
                    pass

        return findings

    def _analyze_property_system(self, matrix: ComparisonMatrix,
                                 cells_by_engine: dict) -> List[str]:
        """Analyze property system dimension for findings.

        Args:
            matrix: The ComparisonMatrix to analyze.
            cells_by_engine: Dictionary mapping engine name to its cells.

        Returns:
            List of property system findings.
        """
        findings = []

        # Check for distribution support
        for engine, cells in cells_by_engine.items():
            if len(cells) >= 1:
                try:
                    dist_count = int(cells[0].value)
                    if dist_count > 0:
                        findings.append(
                            f"{engine} supports distribution properties ({dist_count} found)"
                        )
                except ValueError:
                    pass

        # Check for ordering support
        for engine, cells in cells_by_engine.items():
            if len(cells) >= 2:
                try:
                    order_count = int(cells[1].value)
                    if order_count > 0:
                        findings.append(
                            f"{engine} has ordering/property enforcement support "
                            f"({order_count} ordering properties)"
                        )
                except ValueError:
                    pass

        # Check for enforcer mechanisms
        for engine, cells in cells_by_engine.items():
            if len(cells) >= 3:
                try:
                    enforcer_count = int(cells[2].value)
                    if enforcer_count > 0:
                        findings.append(
                            f"{engine} has {enforcer_count} property enforcer mechanisms"
                        )
                except ValueError:
                    pass

        return findings

    def _analyze_observability(self, matrix: ComparisonMatrix,
                              cells_by_engine: dict) -> List[str]:
        """Analyze observability dimension for findings.

        Args:
            matrix: The ComparisonMatrix to analyze.
            cells_by_engine: Dictionary mapping engine name to its cells.

        Returns:
            List of observability findings.
        """
        findings = []

        # Check for EXPLAIN support
        for engine, cells in cells_by_engine.items():
            if len(cells) >= 1:
                try:
                    explain_count = int(cells[0].value)
                    if explain_count > 0:
                        findings.append(
                            f"{engine} provides {explain_count} EXPLAIN interface(s)"
                        )
                except ValueError:
                    pass

        # Check for trace support
        for engine, cells in cells_by_engine.items():
            if len(cells) >= 2:
                try:
                    trace_count = int(cells[1].value)
                    if trace_count > 0:
                        findings.append(
                            f"{engine} has tracing capabilities ({trace_count} trace interface(s))"
                        )
                except ValueError:
                    pass

        # Check for memo dump support
        for engine, cells in cells_by_engine.items():
            if len(cells) >= 3:
                if cells[2].value == "yes":
                    findings.append(f"{engine} supports memo dump for debugging")

        # Check for session controls
        for engine, cells in cells_by_engine.items():
            if len(cells) >= 4:
                try:
                    session_count = int(cells[3].value)
                    if session_count > 0:
                        findings.append(
                            f"{engine} provides {session_count} session control option(s)"
                        )
                except ValueError:
                    pass

        return findings

    def _extract_recommendations(self) -> List[str]:
        """Generate recommendations based on analysis.

        Returns:
            List of recommendation strings.
        """
        recommendations = []

        # Check if we have multiple engines to compare
        all_engines = set()
        for matrix in self.matrices:
            all_engines.update(matrix.engines)

        if len(all_engines) < 2:
            recommendations.append(
                "Compare at least two optimizer engines for meaningful analysis"
            )
            return recommendations

        # Analyze for recommendations based on findings
        for finding in self._findings:
            if "Cascades-style" in finding:
                recommendations.append(
                    "Consider adopting Cascades-style optimization for better "
                    "cost-based optimization with memoization"
                )
            elif "Logical/physical optimization split" in finding:
                recommendations.append(
                    "Separate logical and physical optimization phases for "
                    "cleaner rule organization and better optimization"
                )
            elif "favors cost-based optimization" in finding:
                recommendations.append(
                    "Ensure cost model accuracy for cost-based optimization rules"
                )
            elif "more rule-based optimization" in finding:
                recommendations.append(
                    "Consider adding cost-based optimization rules for better "
                    "plan quality in complex queries"
                )
            elif "tracing capabilities" in finding:
                recommendations.append(
                    "Implement tracing interfaces for better optimizer debugging"
                )
            elif "memo dump" in finding:
                recommendations.append(
                    "Add memo dump support for advanced optimizer debugging and analysis"
                )

        # Deduplicate recommendations while preserving order
        seen = set()
        unique_recommendations = []
        for rec in recommendations:
            if rec not in seen:
                seen.add(rec)
                unique_recommendations.append(rec)

        # Add general recommendations if none specific
        if not unique_recommendations:
            unique_recommendations.append(
                "Review the comparison matrices for potential optimizer improvements"
            )

        return unique_recommendations

    def identify_findings(self) -> List[str]:
        """Identify key findings from matrices.

        Returns:
            List of key findings discovered from the comparison matrices.
        """
        return self._findings.copy()

    def generate_recommendations(self) -> List[str]:
        """Generate recommendations based on analysis.

        Returns:
            List of recommendations derived from the analysis.
        """
        return self._recommendations.copy()

    def generate_markdown_report(self) -> str:
        """Generate a Markdown formatted report.

        Returns:
            Markdown formatted string containing the full report.
        """
        lines = []

        # Title
        lines.append("# Optimizer Engine Comparison Report")
        lines.append("")

        # Date
        lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # Executive Summary
        lines.append("## Executive Summary")
        lines.append("")

        # Get all engines
        all_engines = set()
        for matrix in self.matrices:
            all_engines.update(matrix.engines)

        lines.append(f"This report compares {len(all_engines)} optimizer engine(s): "
                    f"{', '.join(sorted(all_engines))}.")
        lines.append("")

        # Dimension summary
        dimensions = set()
        for matrix in self.matrices:
            dimensions.update(d.value for d in matrix.dimensions)
        lines.append(f"Analysis covers {len(dimensions)} dimension(s): "
                    f"{', '.join(sorted(dimensions))}.")
        lines.append("")

        # Comparison Tables
        lines.append("## Comparison Tables")
        lines.append("")

        for matrix in self.matrices:
            dimension = matrix.dimensions[0] if matrix.dimensions else None
            if not dimension:
                continue

            lines.append(f"### {dimension.value.replace('_', ' ').title()}")
            lines.append("")

            # Build table header
            header = "| Metric | " + " | ".join(matrix.engines) + " |"
            separator = "|--------|" + "|".join(["------|" for _ in matrix.engines])

            lines.append(header)
            lines.append(separator)

            # Group cells by metric
            cells_by_engine = {}
            for cell in matrix.cells:
                if cell.engine not in cells_by_engine:
                    cells_by_engine[cell.engine] = []
                cells_by_engine[cell.engine].append(cell)

            # Get metric names based on dimension
            metric_names = self._get_metric_names(dimension)

            # Build rows
            for i, metric in enumerate(metric_names):
                row_values = [metric]
                for engine in matrix.engines:
                    engine_cells = cells_by_engine.get(engine, [])
                    if i < len(engine_cells):
                        row_values.append(engine_cells[i].value)
                    else:
                        row_values.append("n/a")
                lines.append("| " + " | ".join(row_values) + " |")

            lines.append("")

        # Key Findings
        lines.append("## Key Findings")
        lines.append("")

        if self._findings:
            for finding in self._findings:
                lines.append(f"- {finding}")
        else:
            lines.append("No significant findings identified.")

        lines.append("")

        # Recommendations
        lines.append("## Recommendations")
        lines.append("")

        if self._recommendations:
            for rec in self._recommendations:
                lines.append(f"- {rec}")
        else:
            lines.append("No specific recommendations at this time.")

        lines.append("")

        return "\n".join(lines)

    def _get_metric_names(self, dimension) -> List[str]:
        """Get metric names for a dimension.

        Args:
            dimension: The ComparisonDimension.

        Returns:
            List of metric names for this dimension.
        """
        from optimizer_analysis.schemas import ComparisonDimension

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
            ],
            ComparisonDimension.EXTENSIBILITY: [
                "custom_rules",
                "plugins",
                "hooks"
            ]
        }
        return metric_names.get(dimension, [])

    def generate_json_report(self) -> str:
        """Generate a JSON formatted report.

        Returns:
            JSON formatted string containing the full report.
        """
        # Get all engines
        all_engines = set()
        dimensions = set()
        for matrix in self.matrices:
            all_engines.update(matrix.engines)
            dimensions.update(d.value for d in matrix.dimensions)

        # Build matrices data
        matrices_data = []
        for matrix in self.matrices:
            dimension = matrix.dimensions[0] if matrix.dimensions else None

            # Group cells by metric
            cells_by_engine = {}
            for cell in matrix.cells:
                if cell.engine not in cells_by_engine:
                    cells_by_engine[cell.engine] = []
                cells_by_engine[cell.engine].append(cell)

            # Get metric names
            metric_names = self._get_metric_names(dimension) if dimension else []

            # Build rows
            rows = []
            for i, metric in enumerate(metric_names):
                row = {"metric": metric}
                for engine in matrix.engines:
                    engine_cells = cells_by_engine.get(engine, [])
                    if i < len(engine_cells):
                        cell = engine_cells[i]
                        row[engine] = {
                            "value": cell.value,
                            "details": cell.details
                        }
                    else:
                        row[engine] = {"value": "n/a", "details": None}
                rows.append(row)

            matrices_data.append({
                "dimension": dimension.value if dimension else None,
                "engines": matrix.engines,
                "generated_at": matrix.generated_at.isoformat(),
                "rows": rows
            })

        report = {
            "title": "Optimizer Engine Comparison Report",
            "generated_at": datetime.now().isoformat(),
            "engines_compared": sorted(list(all_engines)),
            "dimensions_analyzed": sorted(list(dimensions)),
            "matrices": matrices_data,
            "findings": self._findings,
            "recommendations": self._recommendations
        }

        return json.dumps(report, indent=2)

    def save_report(self, path: str, format: str = "markdown") -> None:
        """Save report to a file.

        Args:
            path: File path for the output report.
            format: Output format, either "markdown" or "json".
        """
        # Ensure directory exists
        Path(path).parent.mkdir(parents=True, exist_ok=True)

        if format == "markdown":
            content = self.generate_markdown_report()
        elif format == "json":
            content = self.generate_json_report()
        else:
            raise ValueError(f"Unsupported format: {format}. "
                           f"Use 'markdown' or 'json'.")

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)