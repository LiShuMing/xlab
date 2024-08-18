"""Statistics and Cost Agent for extracting statistics and cost model information."""

import json
import re
from os import makedirs
from os.path import exists, join
from typing import List, Optional

from optimizer_analysis.agents.base import AgentResult, BaseAgent
from optimizer_analysis.llm_client import ChatMessage
from optimizer_analysis.prompts.stats_prompts import (
    COST_EXTRACTION_PROMPT,
    STATS_EXTRACTION_PROMPT,
)
from optimizer_analysis.schemas.base import Evidence, EvidenceType
from optimizer_analysis.schemas.stats_cost import CostModel, StatisticsInfo, StatsGranularity
from optimizer_analysis.scanners.base import CodeFile
from optimizer_analysis.scanners.java_scanner import JavaScanner


class StatsCostAgent(BaseAgent):
    """Agent for extracting statistics and cost model information from source code.

    This agent analyzes source files to identify and extract statistics
    collection mechanisms and cost model formulas used in query optimization.
    """

    name = "StatsCostAgent"

    def __init__(
        self,
        engine: str,
        work_dir: str,
        stats_path: str,
        cost_path: str,
        llm_client: Optional[object] = None
    ):
        """Initialize the statistics and cost agent.

        Args:
            engine: The optimizer engine name.
            work_dir: Working directory for storing artifacts.
            stats_path: Path to source files containing statistics implementations.
            cost_path: Path to source files containing cost model implementations.
            llm_client: Optional LLM client for enhanced analysis.
        """
        super().__init__(engine, work_dir)
        self.stats_path = stats_path
        self.cost_path = cost_path
        self.llm_client = llm_client

    def execute(self) -> AgentResult:
        """Execute the statistics and cost extraction task.

        Scans the configured paths for statistics and cost model implementations,
        analyzes them, and saves the results to the appropriate artifact files.

        Returns:
            AgentResult containing the extraction results and execution status.
        """
        errors: List[str] = []
        artifacts: List[str] = []

        try:
            # Ensure work directory exists
            if not exists(self.work_dir):
                makedirs(self.work_dir, exist_ok=True)

            # Create stats and cost subdirectories
            stats_dir = join(self.work_dir, "stats")
            cost_dir = join(self.work_dir, "cost")
            if not exists(stats_dir):
                makedirs(stats_dir, exist_ok=True)
            if not exists(cost_dir):
                makedirs(cost_dir, exist_ok=True)

            # Scan and extract statistics
            stats_results = self.scan_statistics()
            stats_count = len(stats_results)

            # Scan and extract cost models
            cost_results = self.scan_cost_models()
            cost_count = len(cost_results)

            # Save statistics index
            stats_index_path = join(stats_dir, "index.json")
            stats_data = {
                "engine": self.engine,
                "stats_found": stats_count,
                "statistics": [s.model_dump() for s in stats_results],
                "confidence": "medium" if self.llm_client else "low",
                "notes": [
                    f"Scanned statistics path: {self.stats_path}",
                    f"Found {stats_count} statistics implementations",
                    "Manual review recommended for verification",
                ]
            }
            with open(stats_index_path, "w") as f:
                json.dump(stats_data, f, indent=2)
            artifacts.append(stats_index_path)

            # Save cost index
            cost_index_path = join(cost_dir, "index.json")
            cost_data = {
                "engine": self.engine,
                "costs_found": cost_count,
                "cost_models": [c.model_dump() for c in cost_results],
                "confidence": "medium" if self.llm_client else "low",
                "notes": [
                    f"Scanned cost path: {self.cost_path}",
                    f"Found {cost_count} cost model implementations",
                    "Manual review recommended for verification",
                ]
            }
            with open(cost_index_path, "w") as f:
                json.dump(cost_data, f, indent=2)
            artifacts.append(cost_index_path)

            status = "partial" if errors or not self.llm_client else "success"

            return AgentResult(
                agent_name=self.name,
                status=status,
                artifacts=artifacts,
                errors=errors,
                summary=(
                    f"Extracted {stats_count} statistics and {cost_count} cost models "
                    f"from {self.engine}. Results saved to stats/index.json and "
                    f"cost/index.json."
                ),
                metadata={
                    "needs_manual_review": not self.llm_client or len(errors) > 0,
                    "stats_found": stats_count,
                    "costs_found": cost_count,
                    "has_llm_client": self.llm_client is not None,
                    "stats_path": self.stats_path,
                    "cost_path": self.cost_path,
                }
            )

        except Exception as e:
            errors.append(f"Stats/Cost extraction failed: {str(e)}")
            return AgentResult(
                agent_name=self.name,
                status="failed",
                artifacts=artifacts,
                errors=errors,
                summary=f"Stats/Cost extraction failed for {self.engine}",
                metadata={"error": str(e)}
            )

    def analyze_statistics(self, code_file: CodeFile) -> Optional[StatisticsInfo]:
        """Analyze a source file for statistics information using LLM.

        Args:
            code_file: A CodeFile object containing the source code to analyze.

        Returns:
            A StatisticsInfo object if extraction is successful, None otherwise.

        Raises:
            ValueError: If no LLM client is available.
        """
        if self.llm_client is None:
            raise ValueError("LLM client is required for statistics analysis")

        # Use the statistics extraction prompt
        user_prompt = STATS_EXTRACTION_PROMPT.format(
            engine=self.engine,
            code=code_file.content
        )

        # Call LLM
        response = self.llm_client.chat([
            ChatMessage(role="user", content=user_prompt),
        ])

        # Parse the JSON response
        stats_data = self._parse_llm_response(response)

        if stats_data is None or "error" in stats_data:
            return None

        # Create StatisticsInfo object from parsed data
        return self._create_statistics_from_data(stats_data, code_file)

    def analyze_cost_model(self, code_file: CodeFile) -> Optional[CostModel]:
        """Analyze a source file for cost model information using LLM.

        Args:
            code_file: A CodeFile object containing the source code to analyze.

        Returns:
            A CostModel object if extraction is successful, None otherwise.

        Raises:
            ValueError: If no LLM client is available.
        """
        if self.llm_client is None:
            raise ValueError("LLM client is required for cost model analysis")

        # Use the cost extraction prompt
        user_prompt = COST_EXTRACTION_PROMPT.format(
            engine=self.engine,
            code=code_file.content
        )

        # Call LLM
        response = self.llm_client.chat([
            ChatMessage(role="user", content=user_prompt),
        ])

        # Parse the JSON response
        cost_data = self._parse_llm_response(response)

        if cost_data is None or "error" in cost_data:
            return None

        # Create CostModel object from parsed data
        return self._create_cost_from_data(cost_data, code_file)

    def scan_statistics(self) -> List[StatisticsInfo]:
        """Scan the statistics path and extract statistics information.

        Returns:
            List of StatisticsInfo objects extracted from the source files.
        """
        results: List[StatisticsInfo] = []

        # Check if path exists
        if not exists(self.stats_path):
            return results

        # Use JavaScanner to scan the path
        scanner = JavaScanner()
        scan_result = scanner.scan_directory(self.stats_path)

        # Filter for statistics-related files
        for code_file in scan_result.code_files:
            if not self._is_statistics_file(code_file):
                continue

            try:
                if self.llm_client is not None:
                    stats_info = self.analyze_statistics(code_file)
                    if stats_info is not None:
                        results.append(stats_info)
                else:
                    # Without LLM, create placeholder
                    results.append(StatisticsInfo(
                        stats_source="Pending Analysis",
                        stats_objects=["Unknown"],
                        stats_granularity=StatsGranularity.COLUMN,
                        evidence=[
                            Evidence(
                                file_path=code_file.path,
                                description="Statistics file pending LLM analysis",
                                evidence_type=EvidenceType.SOURCE_CODE,
                            )
                        ],
                        uncertain_points=["Requires LLM analysis for full extraction"]
                    ))
            except Exception:
                # Skip files that fail analysis
                continue

        return results

    def scan_cost_models(self) -> List[CostModel]:
        """Scan the cost path and extract cost model information.

        Returns:
            List of CostModel objects extracted from the source files.
        """
        results: List[CostModel] = []

        # Check if path exists
        if not exists(self.cost_path):
            return results

        # Use JavaScanner to scan the path
        scanner = JavaScanner()
        scan_result = scanner.scan_directory(self.cost_path)

        # Filter for cost-related files
        for code_file in scan_result.code_files:
            if not self._is_cost_file(code_file):
                continue

            try:
                if self.llm_client is not None:
                    cost_model = self.analyze_cost_model(code_file)
                    if cost_model is not None:
                        results.append(cost_model)
                else:
                    # Without LLM, create placeholder
                    results.append(CostModel(
                        cost_formula_location="Pending Analysis",
                        cost_dimensions=["Unknown"],
                        operator_costs={"Unknown": "Pending LLM analysis"},
                        evidence=[
                            Evidence(
                                file_path=code_file.path,
                                description="Cost model file pending LLM analysis",
                                evidence_type=EvidenceType.SOURCE_CODE,
                            )
                        ],
                        uncertain_points=["Requires LLM analysis for full extraction"]
                    ))
            except Exception:
                # Skip files that fail analysis
                continue

        return results

    def _parse_llm_response(self, response: str) -> Optional[dict]:
        """Parse JSON response from LLM.

        Args:
            response: Raw response string from LLM.

        Returns:
            Parsed dictionary or None if parsing fails.
        """
        # Try to extract JSON from response
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                return None
        return None

    def _create_statistics_from_data(
        self,
        stats_data: dict,
        code_file: CodeFile
    ) -> StatisticsInfo:
        """Create StatisticsInfo object from parsed LLM response data.

        Args:
            stats_data: Parsed dictionary from LLM response.
            code_file: The source CodeFile being analyzed.

        Returns:
            A StatisticsInfo object populated with extracted data.
        """
        # Parse evidence from response
        evidence_list = []
        for ev_data in stats_data.get("evidence", []):
            evidence_list.append(Evidence(
                file_path=ev_data.get("file_path", code_file.path),
                description=ev_data.get("description", ""),
                line_start=ev_data.get("line_start"),
                line_end=ev_data.get("line_end"),
                evidence_type=EvidenceType(ev_data.get("evidence_type", "source_code")),
            ))

        # Add default evidence if none provided
        if not evidence_list:
            evidence_list.append(Evidence(
                file_path=code_file.path,
                description="Source file analyzed for statistics extraction",
                evidence_type=EvidenceType.SOURCE_CODE,
            ))

        # Parse granularity
        granularity_str = stats_data.get("stats_granularity", "column")
        granularity = StatsGranularity(granularity_str)

        return StatisticsInfo(
            stats_source=stats_data.get("stats_source", "Unknown"),
            stats_objects=stats_data.get("stats_objects", []),
            stats_granularity=granularity,
            storage_location=stats_data.get("storage_location"),
            collection_trigger=stats_data.get("collection_trigger"),
            collection_scheduler=stats_data.get("collection_scheduler"),
            operator_estimation_logic=stats_data.get("operator_estimation_logic"),
            uncertain_points=stats_data.get("uncertain_points", []),
            evidence=evidence_list,
        )

    def _create_cost_from_data(
        self,
        cost_data: dict,
        code_file: CodeFile
    ) -> CostModel:
        """Create CostModel object from parsed LLM response data.

        Args:
            cost_data: Parsed dictionary from LLM response.
            code_file: The source CodeFile being analyzed.

        Returns:
            A CostModel object populated with extracted data.
        """
        # Parse evidence from response
        evidence_list = []
        for ev_data in cost_data.get("evidence", []):
            evidence_list.append(Evidence(
                file_path=ev_data.get("file_path", code_file.path),
                description=ev_data.get("description", ""),
                line_start=ev_data.get("line_start"),
                line_end=ev_data.get("line_end"),
                evidence_type=EvidenceType(ev_data.get("evidence_type", "source_code")),
            ))

        # Add default evidence if none provided
        if not evidence_list:
            evidence_list.append(Evidence(
                file_path=code_file.path,
                description="Source file analyzed for cost model extraction",
                evidence_type=EvidenceType.SOURCE_CODE,
            ))

        return CostModel(
            cost_formula_location=cost_data.get("cost_formula_location"),
            cost_dimensions=cost_data.get("cost_dimensions", []),
            operator_costs=cost_data.get("operator_costs", {}),
            uncertain_points=cost_data.get("uncertain_points", []),
            evidence=evidence_list,
        )

    def _is_statistics_file(self, code_file: CodeFile) -> bool:
        """Check if a file contains statistics-related code.

        Args:
            code_file: A CodeFile object to check.

        Returns:
            True if the file appears to contain statistics code.
        """
        path_lower = code_file.path.lower()
        content_lower = code_file.content.lower()

        # Check for statistics indicators in path
        path_indicators = ["stats", "statistics", "stat", "histogram", "analyze"]
        has_path_indicator = any(ind in path_lower for ind in path_indicators)

        # Check for statistics indicators in content
        content_indicators = [
            "statistics", "stats", "histogram", "ndv", "cardinality",
            "row_count", "null_count", "min_max", "analyze", "sample",
            "distinct", "selectivity"
        ]
        has_content_indicator = any(ind in content_lower for ind in content_indicators)

        return has_path_indicator or has_content_indicator

    def _is_cost_file(self, code_file: CodeFile) -> bool:
        """Check if a file contains cost model-related code.

        Args:
            code_file: A CodeFile object to check.

        Returns:
            True if the file appears to contain cost model code.
        """
        path_lower = code_file.path.lower()
        content_lower = code_file.content.lower()

        # Check for cost indicators in path
        path_indicators = ["cost", "estimate", "plan_cost"]
        has_path_indicator = any(ind in path_lower for ind in path_indicators)

        # Check for cost indicators in content
        content_indicators = [
            "cost", "costmodel", "compute_cost", "estimate",
            "cpu_cost", "io_cost", "memory_cost", "network_cost",
            "operator_cost", "plan_cost"
        ]
        has_content_indicator = any(ind in content_lower for ind in content_indicators)

        return has_path_indicator or has_content_indicator