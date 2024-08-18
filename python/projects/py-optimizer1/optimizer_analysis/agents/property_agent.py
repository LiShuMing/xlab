"""Property Agent for extracting property/trait information from optimizer source code."""

import json
import re
from os import makedirs
from os.path import exists, join
from typing import List, Optional

from pydantic import BaseModel, Field

from optimizer_analysis.agents.base import AgentResult, BaseAgent
from optimizer_analysis.llm_client import ChatMessage
from optimizer_analysis.prompts.property_prompts import (
    PROPERTY_EXTRACTION_PROMPT,
    PROPERTY_SYSTEM_PROMPT,
    PROPERTY_ANALYSIS_PROMPT,
)
from optimizer_analysis.schemas.base import Evidence, EvidenceType
from optimizer_analysis.schemas.trait import TraitProperty, PropertyType
from optimizer_analysis.scanners.base import CodeFile
from optimizer_analysis.scanners.java_scanner import JavaScanner


class PropertyAnalysisResult(BaseModel):
    """Result of analyzing properties from source code.

    This model captures the properties discovered during analysis,
    along with metadata about the analysis process.
    """

    engine: str = Field(..., description="Name of the optimizer engine")
    properties_found: int = Field(
        0,
        description="Number of properties found"
    )
    properties: List[TraitProperty] = Field(
        default_factory=list,
        description="List of discovered properties"
    )
    confidence: str = Field(
        "medium",
        description="Confidence level of the analysis: high, medium, low, unknown"
    )
    notes: List[str] = Field(
        default_factory=list,
        description="Additional notes about the analysis process"
    )


class PropertyAgent(BaseAgent):
    """Agent for extracting property/trait information from optimizer source code.

    This agent analyzes source files to identify and extract
    properties/traits used in the optimization process, including
    their representation, propagation logic, and enforcer operators.
    """

    name = "PropertyAgent"

    def __init__(
        self,
        engine: str,
        work_dir: str,
        source_path: str,
        llm_client: Optional[object] = None
    ):
        """Initialize the property agent.

        Args:
            engine: The optimizer engine name.
            work_dir: Working directory for storing artifacts.
            source_path: Path to source files containing property definitions.
            llm_client: Optional LLM client for enhanced analysis.
        """
        super().__init__(engine, work_dir)
        self.source_path = source_path
        self.llm_client = llm_client

    def execute(self) -> AgentResult:
        """Execute the property extraction task.

        Scans the source_path for Java files and extracts property information.
        Saves results to traits/index.json.

        Returns:
            AgentResult containing the PropertyAnalysisResult and execution status.
        """
        errors: List[str] = []
        artifacts: List[str] = []
        properties: List[TraitProperty] = []

        try:
            # Ensure work directory exists
            if not exists(self.work_dir):
                makedirs(self.work_dir, exist_ok=True)

            # Create traits subdirectory
            traits_dir = join(self.work_dir, "traits")
            if not exists(traits_dir):
                makedirs(traits_dir, exist_ok=True)

            # Use JavaScanner to scan source_path
            scanner = JavaScanner()
            scan_result = scanner.scan_directory(self.source_path)

            # Track any scan errors
            if scan_result.errors:
                errors.extend(scan_result.errors)

            # Filter and extract properties from each file
            for code_file in scan_result.code_files:
                try:
                    # Skip files that don't appear to be property-related
                    if not self._is_property_file({"content": code_file.content, "path": code_file.path}):
                        continue

                    # If LLM client is available, extract structured property
                    if self.llm_client is not None:
                        property = self.analyze_property_from_code(code_file)
                        if property is not None:
                            properties.append(property)
                    else:
                        # Without LLM, create placeholder entry
                        properties.append(TraitProperty(
                            property_name=f"Property_{len(properties) + 1}",
                            property_type=PropertyType.PHYSICAL,  # Default to physical
                            representation="Pending analysis",
                            propagation_logic="Requires LLM analysis",
                            enforcer="Unknown",
                            where_used=[],
                            confidence="low",
                            uncertain_points=["Requires LLM analysis for full extraction"]
                        ))

                except Exception as e:
                    errors.append(f"Failed to process {code_file.path}: {str(e)}")

            # Create analysis result
            analysis_result = PropertyAnalysisResult(
                engine=self.engine,
                properties_found=len(properties),
                properties=properties,
                confidence="low" if not self.llm_client else "medium",
                notes=[
                    f"Scanned {scan_result.files_scanned} Java files",
                    f"Identified {len(properties)} potential properties",
                    f"Source path: {self.source_path}",
                    "Manual review recommended for property verification",
                ]
            )

            # Add LLM availability note
            if self.llm_client is not None:
                analysis_result.notes.append(
                    "LLM client available for enhanced analysis."
                )
            else:
                analysis_result.notes.append(
                    "No LLM client provided. Manual analysis required."
                )

            # Save the analysis result to traits/index.json
            index_path = join(traits_dir, "index.json")
            with open(index_path, "w") as f:
                f.write(analysis_result.model_dump_json(indent=2))
            artifacts.append(index_path)

            return AgentResult(
                agent_name=self.name,
                status="partial" if errors or not self.llm_client else "success",
                artifacts=artifacts,
                errors=errors,
                summary=(
                    f"Extracted {len(properties)} properties from {self.engine}. "
                    f"Scanned {scan_result.files_scanned} files. "
                    f"Results saved to {index_path}"
                ),
                metadata={
                    "needs_manual_review": not self.llm_client or len(errors) > 0,
                    "confidence": analysis_result.confidence,
                    "properties_found": len(properties),
                    "files_scanned": scan_result.files_scanned,
                    "has_llm_client": self.llm_client is not None
                }
            )

        except Exception as e:
            errors.append(f"Property extraction failed: {str(e)}")
            return AgentResult(
                agent_name=self.name,
                status="failed",
                artifacts=artifacts,
                errors=errors,
                summary=f"Property extraction failed for {self.engine}",
                metadata={"error": str(e)}
            )

    def analyze_property_from_code(self, code_file: CodeFile) -> Optional[TraitProperty]:
        """Extract a TraitProperty object from a CodeFile using LLM analysis.

        This method uses the LLM client to analyze the source code and
        extract structured information about optimizer properties/traits.

        Args:
            code_file: A CodeFile object containing the source code to analyze.

        Returns:
            A TraitProperty object if extraction is successful, None otherwise.

        Raises:
            ValueError: If no LLM client is available.
        """
        if self.llm_client is None:
            raise ValueError("LLM client is required for property extraction")

        # Prepare the prompt
        user_prompt = PROPERTY_EXTRACTION_PROMPT.format(
            engine=self.engine,
            context=self.source_path,
            code=code_file.content
        )

        # Call LLM with the appropriate prompt
        response = self.llm_client.chat([
            ChatMessage(role="system", content=PROPERTY_SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_prompt),
        ])

        # Parse the JSON response
        property_data = self._parse_llm_response(response)

        if property_data is None or "error" in property_data:
            return None

        # Create TraitProperty object from parsed data
        return self._create_property_from_data(property_data, code_file)

    def scan_properties(self) -> List[TraitProperty]:
        """Scan the source path and extract all properties.

        This is a convenience method that wraps execute() and returns
        just the list of extracted properties.

        Returns:
            List of TraitProperty objects found in the source code.
        """
        result = self.execute()

        # If we have artifacts, read the properties from them
        if result.artifacts:
            for artifact_path in result.artifacts:
                if "index.json" in artifact_path:
                    try:
                        with open(artifact_path, "r") as f:
                            data = json.loads(f.read())
                        return [
                            TraitProperty(**p) for p in data.get("properties", [])
                        ]
                    except Exception:
                        pass

        # Fall back to returning from metadata if available
        return []

    def _parse_llm_response(self, response: str) -> Optional[dict]:
        """Parse JSON response from LLM.

        Args:
            response: Raw response string from LLM.

        Returns:
            Parsed dictionary or None if parsing fails.
        """
        # Try to extract JSON from response
        # Handle cases where LLM might include extra text
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                return None
        return None

    def _create_property_from_data(
        self,
        property_data: dict,
        code_file: CodeFile
    ) -> TraitProperty:
        """Create a TraitProperty object from parsed LLM response data.

        Args:
            property_data: Parsed dictionary from LLM response.
            code_file: The source CodeFile being analyzed.

        Returns:
            A TraitProperty object populated with extracted data.
        """
        # Parse evidence from response
        evidence_list = []
        for ev_data in property_data.get("evidence", []):
            evidence_list.append(Evidence(
                file_path=ev_data.get("file_path", code_file.path),
                description=ev_data.get("description", ""),
                line_start=ev_data.get("line_start"),
                line_end=ev_data.get("line_end"),
                evidence_type=EvidenceType(ev_data.get("evidence_type", "source_code")),
            ))

        # Add default evidence pointing to the analyzed file
        if not evidence_list:
            evidence_list.append(Evidence(
                file_path=code_file.path,
                description="Source file analyzed for property extraction",
                evidence_type=EvidenceType.SOURCE_CODE,
            ))

        # Parse property type
        property_type_str = property_data.get("property_type", "physical")
        try:
            property_type = PropertyType(property_type_str.lower())
        except ValueError:
            property_type = PropertyType.PHYSICAL

        # Create TraitProperty object
        return TraitProperty(
            property_name=property_data.get("property_name", "UnknownProperty"),
            property_type=property_type,
            representation=property_data.get("representation"),
            propagation_logic=property_data.get("propagation_logic"),
            enforcer=property_data.get("enforcer"),
            where_used=property_data.get("where_used", []),
            impact_on_search=property_data.get("impact_on_search"),
            evidence=evidence_list,
        )

    def _is_property_file(self, file_dict: dict) -> bool:
        """Check if a file contains property/trait-related code.

        Property files typically have these characteristics:
        - Class names containing 'Property', 'Trait', 'Requirement', 'PhysicalProperty'
        - References to property enforcement, propagation
        - Located in property-related directories

        Args:
            file_dict: Dictionary containing file content and path.

        Returns:
            True if the file appears to be property-related.
        """
        content = file_dict.get("content", "")
        path = file_dict.get("path", "")

        path_lower = path.lower()
        content_lower = content.lower()

        # Check for property-related class names
        has_property_class = any(pattern in content_lower for pattern in [
            "class property", "class trait", "class requirement",
            "physicalproperty", "logicalproperty", "orderingproperty",
            "distributionproperty", "traitdef", "propertydef"
        ])

        # Check for property-related terminology
        has_property_terms = any(pattern in content_lower for pattern in [
            "enforceproperty", "requiredproperty", "propertyprovider",
            "trait", "property propagation", "satisfy", "requireproperty"
        ])

        # Check for property-specific directories
        in_property_directory = any(pattern in path_lower for pattern in [
            "property", "trait", "requirement", "physical", "enforcer"
        ])

        # If it's in a property directory
        if in_property_directory:
            return True

        # If it has property class or terminology
        if has_property_class or has_property_terms:
            return True

        return False