"""Comparison Agent for comparing analysis results across multiple optimizer engines."""

import json
from os import makedirs
from os.path import exists, join
from typing import Any, Dict, List

from optimizer_analysis.agents.base import AgentResult, BaseAgent
from optimizer_analysis.comparison.matrix import MatrixGenerator
from optimizer_analysis.schemas import (
    ComparisonMatrix,
    ComparisonReport,
    ComparisonDimension,
)


class ReportGenerator:
    """Generate comparison reports from matrices.

    This class creates markdown reports and ComparisonReport objects
    from comparison matrices.
    """

    def __init__(self, engines: List[str], matrices: List[ComparisonMatrix]):
        """Initialize the report generator.

        Args:
            engines: List of engine names being compared.
            matrices: List of ComparisonMatrix objects to include in the report.
        """
        self.engines = engines
        self.matrices = matrices

    def generate_report(self) -> ComparisonReport:
        """Generate a ComparisonReport from the matrices.

        Returns:
            ComparisonReport containing all matrices and key findings.
        """
        findings: List[str] = []
        recommendations: List[str] = []

        # Extract key findings from matrices
        for matrix in self.matrices:
            findings.extend(self._extract_findings(matrix))

        # Generate recommendations based on findings
        recommendations.extend(self._generate_recommendations())

        return ComparisonReport(
            title=f"Optimizer Engine Comparison: {', '.join(self.engines)}",
            engines_compared=self.engines,
            matrices=self.matrices,
            findings=findings,
            recommendations=recommendations,
        )

    def generate_markdown(self) -> str:
        """Generate a markdown report from the matrices.

        Returns:
            Markdown formatted string containing the comparison report.
        """
        lines: List[str] = []

        # Title and header
        lines.append(f"# Optimizer Engine Comparison Report")
        lines.append("")
        lines.append(f"**Engines Compared:** {', '.join(self.engines)}")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Generate tables for each matrix
        for matrix in self.matrices:
            lines.extend(self._generate_matrix_table(matrix))
            lines.append("")

        # Key findings section
        findings = self._extract_all_findings()
        if findings:
            lines.append("## Key Findings")
            lines.append("")
            for finding in findings:
                lines.append(f"- {finding}")
            lines.append("")

        # Recommendations section
        recommendations = self._generate_recommendations()
        if recommendations:
            lines.append("## Recommendations")
            lines.append("")
            for rec in recommendations:
                lines.append(f"- {rec}")
            lines.append("")

        return "\n".join(lines)

    def _generate_matrix_table(self, matrix: ComparisonMatrix) -> List[str]:
        """Generate a markdown table for a single matrix.

        Args:
            matrix: The ComparisonMatrix to format as a table.

        Returns:
            List of markdown lines forming the table.
        """
        lines: List[str] = []

        # Table header
        dimension = matrix.dimensions[0] if matrix.dimensions else ComparisonDimension.LIFECYCLE
        lines.append(f"## {dimension.value.replace('_', ' ').title()} Comparison")
        lines.append("")

        # Create column headers
        headers = ["Metric"] + matrix.engines
        header_line = "| " + " | ".join(headers) + " |"
        separator_line = "|" + "|".join(["---" for _ in headers]) + "|"

        lines.append(header_line)
        lines.append(separator_line)

        # Group cells by metric type
        cells_by_engine: Dict[str, List[Any]] = {engine: [] for engine in matrix.engines}
        for cell in matrix.cells:
            cells_by_engine[cell.engine].append(cell)

        # Define metric names based on dimension
        metric_names = self._get_metric_names(dimension)

        # Generate rows
        for i, metric in enumerate(metric_names):
            row_values = [metric]
            for engine in matrix.engines:
                engine_cells = cells_by_engine.get(engine, [])
                if i < len(engine_cells):
                    value = engine_cells[i].value
                    details = engine_cells[i].details
                    if details:
                        value = f"{value} ({details})"
                else:
                    value = "n/a"
                row_values.append(value)
            row_line = "| " + " | ".join(row_values) + " |"
            lines.append(row_line)

        return lines

    def _get_metric_names(self, dimension: ComparisonDimension) -> List[str]:
        """Get metric names for a given dimension.

        Args:
            dimension: The ComparisonDimension.

        Returns:
            List of metric names for that dimension.
        """
        metric_names = {
            ComparisonDimension.LIFECYCLE: [
                "optimizer_style",
                "logical_physical_split",
                "memo_support",
                "phases_present",
            ],
            ComparisonDimension.RULE_COVERAGE: [
                "rbo_rules_count",
                "cbo_rules_count",
                "scalar_rules_count",
                "post_opt_rules_count",
            ],
            ComparisonDimension.PROPERTY_SYSTEM: [
                "distribution_support",
                "ordering_support",
                "enforcer_mechanisms",
            ],
            ComparisonDimension.OBSERVABILITY: [
                "explain_support",
                "trace_support",
                "memo_dump_support",
                "session_controls",
            ],
        }
        return metric_names.get(dimension, [])

    def _extract_findings(self, matrix: ComparisonMatrix) -> List[str]:
        """Extract key findings from a matrix.

        Args:
            matrix: The ComparisonMatrix to analyze.

        Returns:
            List of finding strings.
        """
        findings: List[str] = []
        dimension = matrix.dimensions[0] if matrix.dimensions else None

        if not dimension:
            return findings

        # Group cells by engine
        cells_by_engine: Dict[str, List[Any]] = {engine: [] for engine in matrix.engines}
        for cell in matrix.cells:
            cells_by_engine[cell.engine].append(cell)

        # Dimension-specific findings
        if dimension == ComparisonDimension.LIFECYCLE:
            # Check for Cascades-style optimizers
            cascades_engines = []
            for engine, cells in cells_by_engine.items():
                if cells and cells[0].value == "cascades":
                    cascades_engines.append(engine)
            if cascades_engines:
                findings.append(
                    f"Cascades-style optimization: {', '.join(cascades_engines)}"
                )
            # Check for memo support
            memo_engines = []
            for engine, cells in cells_by_engine.items():
                if len(cells) > 2 and cells[2].value == "yes":
                    memo_engines.append(engine)
            if memo_engines:
                findings.append(
                    f"Memo structure support: {', '.join(memo_engines)}"
                )

        elif dimension == ComparisonDimension.RULE_COVERAGE:
            # Check for CBO support
            cbo_engines = []
            for engine, cells in cells_by_engine.items():
                if len(cells) > 1 and int(cells[1].value) > 0:
                    cbo_engines.append(engine)
            if cbo_engines:
                findings.append(
                    f"Cost-based optimization rules: {', '.join(cbo_engines)}"
                )

        elif dimension == ComparisonDimension.OBSERVABILITY:
            # Check for EXPLAIN ANALYZE support
            explain_analyze_engines = []
            for engine, cells in cells_by_engine.items():
                if cells and int(cells[0].value) > 1:
                    explain_analyze_engines.append(engine)
            if explain_analyze_engines:
                findings.append(
                    f"Advanced EXPLAIN support: {', '.join(explain_analyze_engines)}"
                )

        return findings

    def _extract_all_findings(self) -> List[str]:
        """Extract all findings from all matrices.

        Returns:
            List of all finding strings.
        """
        findings: List[str] = []
        for matrix in self.matrices:
            findings.extend(self._extract_findings(matrix))
        return findings

    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on comparison.

        Returns:
            List of recommendation strings.
        """
        recommendations: List[str] = []

        if len(self.engines) < 2:
            recommendations.append("Compare at least two engines for meaningful analysis")
            return recommendations

        # General recommendations based on matrix analysis
        has_cascades = False
        has_memo = False
        has_cbo = False

        for matrix in self.matrices:
            for cell in matrix.cells:
                if cell.value == "cascades":
                    has_cascades = True
                if cell.value == "yes" and "memo" in str(cell.details).lower():
                    has_memo = True
                if "cbo" in str(cell.details).lower():
                    has_cbo = True

        if has_cascades and has_memo:
            recommendations.append(
                "Consider Cascades-style optimization with memo structure for extensibility"
            )

        if has_cbo:
            recommendations.append(
                "Cost-based optimization provides better plan quality for complex queries"
            )

        return recommendations


class ComparisonAgent(BaseAgent):
    """Agent for comparing analysis results across multiple optimizer engines.

    This agent takes analysis results from multiple engines and generates
    comparison matrices and reports. It compares engines across various
    dimensions including lifecycle, rule coverage, property system, and
    observability.
    """

    name = "ComparisonAgent"

    def __init__(
        self,
        engines: List[str],
        work_dir: str,
        analysis_results: Dict[str, Dict[str, Any]],
    ):
        """Initialize the comparison agent.

        Args:
            engines: List of engine names to compare.
            work_dir: Working directory for storing artifacts.
            analysis_results: Dictionary mapping engine name to its analysis results.
                Expected keys in each engine's results:
                - "framework": Framework schema instance
                - "rules": List of Rule schema instances
                - "properties": List of TraitProperty schema instances
                - "observability": Observability schema instance
        """
        # Use first engine as the primary engine for BaseAgent
        primary_engine = engines[0] if engines else "unknown"
        super().__init__(primary_engine, work_dir)
        self.engines = engines
        self.analysis_results = analysis_results

    def execute(self) -> AgentResult:
        """Execute the comparison task.

        Generates comparison matrices and reports for all engines,
        saving results to comparison/matrix.json and comparison/report.md.

        Returns:
            AgentResult containing execution status and artifact paths.
        """
        errors: List[str] = []
        artifacts: List[str] = []

        try:
            # Ensure work directory exists
            if not exists(self.work_dir):
                makedirs(self.work_dir, exist_ok=True)

            # Create comparison subdirectory
            comparison_dir = join(self.work_dir, "comparison")
            if not exists(comparison_dir):
                makedirs(comparison_dir, exist_ok=True)

            # Generate matrices
            matrices = self.generate_matrices()

            # Generate report
            report = self.generate_report(matrices)

            # Save matrices to JSON
            matrix_json_path = join(comparison_dir, "matrix.json")
            matrix_data = {
                "engines": self.engines,
                "matrices": [m.model_dump(mode='json') for m in matrices],
            }
            with open(matrix_json_path, "w") as f:
                json.dump(matrix_data, f, indent=2)
            artifacts.append(matrix_json_path)

            # Save report to markdown
            report_md_path = join(comparison_dir, "report.md")
            report_generator = ReportGenerator(self.engines, matrices)
            markdown_content = report_generator.generate_markdown()
            with open(report_md_path, "w") as f:
                f.write(markdown_content)
            artifacts.append(report_md_path)

            # Determine status
            status = "success" if len(matrices) >= 4 else "partial"

            return AgentResult(
                agent_name=self.name,
                status=status,
                artifacts=artifacts,
                errors=errors,
                summary=(
                    f"Comparison completed for {len(self.engines)} engines. "
                    f"Generated {len(matrices)} comparison matrices. "
                    f"Results saved to {comparison_dir}"
                ),
                metadata={
                    "engines_compared": self.engines,
                    "matrices_count": len(matrices),
                    "findings_count": len(report.findings),
                    "recommendations_count": len(report.recommendations),
                }
            )

        except Exception as e:
            errors.append(f"Comparison failed: {str(e)}")
            return AgentResult(
                agent_name=self.name,
                status="failed",
                artifacts=artifacts,
                errors=errors,
                summary=f"Comparison failed for engines: {', '.join(self.engines)}",
                metadata={"error": str(e)}
            )

    def generate_matrices(self) -> List[ComparisonMatrix]:
        """Generate all comparison matrices.

        Uses MatrixGenerator internally to create matrices for all dimensions.

        Returns:
            List of ComparisonMatrix objects.
        """
        generator = MatrixGenerator(self.analysis_results)
        return generator.generate_all_matrices()

    def generate_report(self, matrices: List[ComparisonMatrix]) -> ComparisonReport:
        """Generate a comparison report from matrices.

        Args:
            matrices: List of ComparisonMatrix objects.

        Returns:
            ComparisonReport containing all matrices and analysis.
        """
        generator = ReportGenerator(self.engines, matrices)
        return generator.generate_report()

    def compare_lifecycles(self) -> ComparisonMatrix:
        """Generate lifecycle comparison matrix.

        Compares optimizer styles, logical/physical split, memo support,
        and phases present for each engine.

        Returns:
            ComparisonMatrix for lifecycle dimension.
        """
        generator = MatrixGenerator(self.analysis_results)
        return generator.generate_lifecycle_matrix()

    def compare_rules(self) -> ComparisonMatrix:
        """Generate rule coverage comparison matrix.

        Compares RBO, CBO, scalar, and post-optimization rule counts
        for each engine.

        Returns:
            ComparisonMatrix for rule coverage dimension.
        """
        generator = MatrixGenerator(self.analysis_results)
        return generator.generate_rule_coverage_matrix()

    def compare_properties(self) -> ComparisonMatrix:
        """Generate property system comparison matrix.

        Compares distribution support, ordering support, and enforcer
        mechanisms for each engine.

        Returns:
            ComparisonMatrix for property system dimension.
        """
        generator = MatrixGenerator(self.analysis_results)
        return generator.generate_property_matrix()

    def compare_observability(self) -> ComparisonMatrix:
        """Generate observability comparison matrix.

        Compares EXPLAIN support, trace support, memo dump support,
        and session controls for each engine.

        Returns:
            ComparisonMatrix for observability dimension.
        """
        generator = MatrixGenerator(self.analysis_results)
        return generator.generate_observability_matrix()