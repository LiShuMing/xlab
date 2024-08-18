"""Tests for Property Agent and PropertyAnalysisResult model."""

import json
import pytest
from os import makedirs
from os.path import exists, join
from unittest.mock import MagicMock, Mock
import tempfile

from optimizer_analysis.agents.base import AgentResult, BaseAgent
from optimizer_analysis.agents.property_agent import (
    PropertyAgent,
    PropertyAnalysisResult,
)
from optimizer_analysis.llm_client import ChatMessage
from optimizer_analysis.schemas.trait import TraitProperty, PropertyType
from optimizer_analysis.schemas.base import Evidence, EvidenceType
from optimizer_analysis.scanners.base import CodeFile


class TestPropertyAnalysisResult:
    """Tests for PropertyAnalysisResult model."""

    def test_property_analysis_result_creation(self):
        """PropertyAnalysisResult basic creation with required fields."""
        result = PropertyAnalysisResult(
            engine="clickhouse",
            properties_found=2,
            properties=[
                TraitProperty(
                    property_name="ordering",
                    property_type=PropertyType.PHYSICAL,
                    enforcer="Sort"
                ),
                TraitProperty(
                    property_name="distribution",
                    property_type=PropertyType.PHYSICAL,
                    enforcer="Exchange"
                )
            ],
            confidence="medium",
            notes=["Initial analysis", "Requires manual review"]
        )
        assert result.engine == "clickhouse"
        assert result.properties_found == 2
        assert len(result.properties) == 2
        assert result.confidence == "medium"
        assert len(result.notes) == 2
        assert "Initial analysis" in result.notes

    def test_property_analysis_result_with_empty_properties(self):
        """PropertyAnalysisResult with no properties found."""
        result = PropertyAnalysisResult(
            engine="starrocks",
            properties_found=0,
            properties=[],
            confidence="low",
            notes=["No properties found in source"]
        )
        assert result.engine == "starrocks"
        assert result.properties_found == 0
        assert result.properties == []
        assert result.confidence == "low"

    def test_property_analysis_result_json_serialization(self):
        """PropertyAnalysisResult can be serialized to JSON."""
        result = PropertyAnalysisResult(
            engine="postgres",
            properties_found=1,
            properties=[
                TraitProperty(
                    property_name="ordering",
                    property_type=PropertyType.PHYSICAL,
                    representation="OrderingProperty class",
                    enforcer="Sort"
                )
            ],
            confidence="high",
            notes=["Verified property"]
        )
        json_str = result.model_dump_json(indent=2)
        data = json.loads(json_str)
        assert data["engine"] == "postgres"
        assert data["properties_found"] == 1
        assert data["confidence"] == "high"
        assert len(data["properties"]) == 1
        assert data["properties"][0]["property_name"] == "ordering"


class TestPropertyAgent:
    """Tests for PropertyAgent class."""

    def test_property_agent_creation(self):
        """PropertyAgent can be instantiated correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = PropertyAgent(
                engine="clickhouse",
                work_dir=tmpdir,
                source_path="/path/to/properties"
            )
            assert agent.name == "PropertyAgent"
            assert agent.engine == "clickhouse"
            assert agent.work_dir == tmpdir
            assert agent.source_path == "/path/to/properties"
            assert agent.llm_client is None

    def test_property_agent_with_llm_client(self):
        """PropertyAgent can be instantiated with LLM client."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_llm = object()  # Mock LLM client
            agent = PropertyAgent(
                engine="starrocks",
                work_dir=tmpdir,
                source_path="/path/to/properties",
                llm_client=mock_llm
            )
            assert agent.llm_client is mock_llm

    def test_property_agent_inherits_from_base_agent(self):
        """PropertyAgent inherits from BaseAgent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = PropertyAgent(
                engine="test",
                work_dir=tmpdir,
                source_path="/path/to/properties"
            )
            assert isinstance(agent, BaseAgent)

    def test_property_agent_execute_without_source(self):
        """PropertyAgent execute handles missing source directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = PropertyAgent(
                engine="test",
                work_dir=tmpdir,
                source_path="/nonexistent/path"
            )
            result = agent.execute()
            assert result.agent_name == "PropertyAgent"
            assert result.status in ["partial", "failed"]
            assert len(result.errors) > 0 or result.metadata.get("files_scanned", 0) == 0

    def test_property_agent_execute_creates_traits_directory(self):
        """PropertyAgent execute creates traits directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a source directory with a sample Java file
            source_dir = join(tmpdir, "source")
            makedirs(source_dir, exist_ok=True)

            # Create a sample property file
            sample_file = join(source_dir, "OrderingProperty.java")
            with open(sample_file, "w") as f:
                f.write("""
package com.example.optimizer.property;

public class OrderingProperty {
    private List<String> orderingColumns;

    public OrderingProperty(List<String> columns) {
        this.orderingColumns = columns;
    }

    public boolean isSatisfiedBy(PhysicalPlan plan) {
        return plan.getOrdering().equals(this);
    }

    public Sort enforce(PhysicalPlan plan) {
        return new Sort(plan, orderingColumns);
    }
}
""")

            agent = PropertyAgent(
                engine="test",
                work_dir=tmpdir,
                source_path=source_dir
            )
            result = agent.execute()

            # Check traits directory was created
            traits_dir = join(tmpdir, "traits")
            assert exists(traits_dir)

            # Check index.json was created
            index_path = join(traits_dir, "index.json")
            assert exists(index_path)
            assert index_path in result.artifacts


class TestAnalyzePropertyFromCode:
    """Tests for analyze_property_from_code method."""

    def test_analyze_property_from_code_requires_llm_client(self):
        """analyze_property_from_code raises ValueError without LLM client."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = PropertyAgent(
                engine="test",
                work_dir=tmpdir,
                source_path="/path"
            )

            code_file = CodeFile(
                path="/test/OrderingProperty.java",
                content="public class OrderingProperty {}",
                language="java"
            )

            with pytest.raises(ValueError, match="LLM client is required"):
                agent.analyze_property_from_code(code_file)

    def test_analyze_property_from_code_with_mock_llm(self):
        """analyze_property_from_code works with mock LLM client."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create mock LLM client
            mock_llm = MagicMock()
            mock_llm.chat = Mock(return_value=json.dumps({
                "property_name": "ordering",
                "property_type": "physical",
                "representation": "OrderingProperty class",
                "propagation_logic": "Preserved by Sort, destroyed by Exchange",
                "enforcer": "Sort operator",
                "where_used": ["JoinRule", "AggregateRule"],
                "confidence": "high",
                "uncertain_points": [],
                "evidence": []
            }))

            agent = PropertyAgent(
                engine="test",
                work_dir=tmpdir,
                source_path="/path",
                llm_client=mock_llm
            )

            code_file = CodeFile(
                path="/test/OrderingProperty.java",
                content="public class OrderingProperty { private List<String> columns; }",
                language="java"
            )

            property = agent.analyze_property_from_code(code_file)

            assert property is not None
            assert property.property_name == "ordering"
            assert property.property_type == PropertyType.PHYSICAL
            assert property.representation == "OrderingProperty class"
            assert property.enforcer == "Sort operator"
            assert "JoinRule" in property.where_used

    def test_analyze_property_from_code_handles_error_response(self):
        """analyze_property_from_code handles LLM error responses."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_llm = MagicMock()
            mock_llm.chat = Mock(return_value=json.dumps({
                "error": "No property found",
                "reason": "Code does not contain property definition"
            }))

            agent = PropertyAgent(
                engine="test",
                work_dir=tmpdir,
                source_path="/path",
                llm_client=mock_llm
            )

            code_file = CodeFile(
                path="/test/SomeOther.java",
                content="public class SomeOther {}",
                language="java"
            )

            property = agent.analyze_property_from_code(code_file)
            assert property is None


class TestScanProperties:
    """Tests for scan_properties method."""

    def test_scan_properties_returns_list(self):
        """scan_properties returns list of TraitProperty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = join(tmpdir, "source")
            makedirs(source_dir, exist_ok=True)

            sample_file = join(source_dir, "Property.java")
            with open(sample_file, "w") as f:
                f.write("public class Property {}")

            agent = PropertyAgent(
                engine="test",
                work_dir=tmpdir,
                source_path=source_dir
            )

            properties = agent.scan_properties()
            assert isinstance(properties, list)


class TestIsPropertyFile:
    """Tests for _is_property_file method."""

    def test_is_property_file_detects_property_class(self):
        """_is_property_file detects property class definitions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = PropertyAgent(
                engine="test",
                work_dir=tmpdir,
                source_path="/path"
            )

            file_dict = {
                "content": "public class OrderingProperty { }",
                "path": "/src/Property.java"
            }
            assert agent._is_property_file(file_dict) is True

    def test_is_property_file_detects_trait_class(self):
        """_is_property_file detects trait class definitions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = PropertyAgent(
                engine="test",
                work_dir=tmpdir,
                source_path="/path"
            )

            file_dict = {
                "content": "public class DistributionTrait { }",
                "path": "/src/Trait.java"
            }
            assert agent._is_property_file(file_dict) is True

    def test_is_property_file_detects_property_directory(self):
        """_is_property_file detects files in property directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = PropertyAgent(
                engine="test",
                work_dir=tmpdir,
                source_path="/path"
            )

            file_dict = {
                "content": "public class SomeClass { }",
                "path": "/src/property/SomeClass.java"
            }
            assert agent._is_property_file(file_dict) is True

    def test_is_property_file_rejects_non_property_files(self):
        """_is_property_file rejects non-property files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = PropertyAgent(
                engine="test",
                work_dir=tmpdir,
                source_path="/path"
            )

            file_dict = {
                "content": "public class RegularRule { public void transform() {} }",
                "path": "/src/rules/RegularRule.java"
            }
            assert agent._is_property_file(file_dict) is False


class TestPropertyPromptsIntegration:
    """Integration tests for property prompts with agent."""

    def test_property_agent_uses_prompts(self):
        """PropertyAgent uses property prompts from prompts module."""
        from optimizer_analysis.prompts.property_prompts import (
            PROPERTY_EXTRACTION_PROMPT,
            PROPERTY_SYSTEM_PROMPT,
        )

        # Verify prompts exist and have placeholders
        assert "{code}" in PROPERTY_EXTRACTION_PROMPT
        assert "{engine}" in PROPERTY_EXTRACTION_PROMPT
        assert "{context}" in PROPERTY_EXTRACTION_PROMPT

        assert isinstance(PROPERTY_SYSTEM_PROMPT, str)
        assert len(PROPERTY_SYSTEM_PROMPT) > 0


class TestTraitPropertyWithConfidence:
    """Tests for TraitProperty with confidence field."""

    def test_trait_property_with_confidence(self):
        """TraitProperty can have confidence field."""
        prop = TraitProperty(
            property_name="ordering",
            property_type=PropertyType.PHYSICAL,
            confidence="high"
        )
        assert prop.confidence == "high"

    def test_trait_property_with_uncertain_points(self):
        """TraitProperty can have uncertain_points field."""
        prop = TraitProperty(
            property_name="distribution",
            property_type=PropertyType.PHYSICAL,
            confidence="low",
            uncertain_points=["Propagation logic unclear", "Enforcer unknown"]
        )
        assert len(prop.uncertain_points) == 2
        assert "Propagation logic unclear" in prop.uncertain_points

    def test_trait_property_default_confidence(self):
        """TraitProperty defaults to medium confidence."""
        prop = TraitProperty(
            property_name="unique",
            property_type=PropertyType.LOGICAL
        )
        assert prop.confidence == "medium"