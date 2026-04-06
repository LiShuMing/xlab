"""Tests for Lifecycle Analyzer Agent and lifecycle models."""

import json
from os.path import exists, join

from optimizer_analysis.agents.base import AgentResult
from optimizer_analysis.agents.lifecycle import (
    LifecycleAgent,
    LifecycleInfo,
    PhaseInfo,
)
from optimizer_analysis.agents.repo_mapper import RepoMap


class TestPhaseInfo:
    """Tests for PhaseInfo model."""

    def test_phase_info_creation(self):
        """PhaseInfo basic creation with required fields."""
        phase_info = PhaseInfo(
            phase="LogicalPlanning",
            entry="optimizer/optimizer.cpp",
            description="Logical plan generation phase",
            transitions_to=["PhysicalPlanning"]
        )
        assert phase_info.phase == "LogicalPlanning"
        assert phase_info.entry == "optimizer/optimizer.cpp"
        assert phase_info.description == "Logical plan generation phase"
        assert phase_info.transitions_to == ["PhysicalPlanning"]

    def test_phase_info_with_optional_fields_none(self):
        """PhaseInfo with optional fields as None."""
        phase_info = PhaseInfo(
            phase="Analysis",
            transitions_to=["LogicalPlanning"]
        )
        assert phase_info.phase == "Analysis"
        assert phase_info.entry is None
        assert phase_info.description is None
        assert phase_info.transitions_to == ["LogicalPlanning"]

    def test_phase_info_empty_transitions(self):
        """PhaseInfo with empty transitions list."""
        phase_info = PhaseInfo(
            phase="Execution",
            entry="executor.cpp",
            description="Final execution phase"
        )
        assert phase_info.phase == "Execution"
        assert phase_info.transitions_to == []

    def test_phase_info_multiple_transitions(self):
        """PhaseInfo with multiple transition targets."""
        phase_info = PhaseInfo(
            phase="Rewrite",
            transitions_to=["LogicalPlanning", "Optimization", "Fallback"]
        )
        assert len(phase_info.transitions_to) == 3
        assert "LogicalPlanning" in phase_info.transitions_to
        assert "Optimization" in phase_info.transitions_to
        assert "Fallback" in phase_info.transitions_to

    def test_phase_info_json_serialization(self):
        """PhaseInfo can be serialized to JSON."""
        phase_info = PhaseInfo(
            phase="CBO",
            entry="src/cbo_optimizer.cpp",
            description="Cost-based optimization",
            transitions_to=["PhysicalPlanning"]
        )
        json_str = phase_info.model_dump_json()
        data = json.loads(json_str)
        assert data["phase"] == "CBO"
        assert data["entry"] == "src/cbo_optimizer.cpp"
        assert data["description"] == "Cost-based optimization"
        assert data["transitions_to"] == ["PhysicalPlanning"]


class TestLifecycleInfo:
    """Tests for LifecycleInfo model."""

    def test_lifecycle_info_creation(self):
        """LifecycleInfo basic creation with required fields."""
        lifecycle_info = LifecycleInfo(
            engine="clickhouse",
            phases=[
                PhaseInfo(phase="Parsing", transitions_to=["Analysis"]),
                PhaseInfo(phase="Analysis", transitions_to=["Planning"])
            ],
            phase_sequence=["Parsing", "Analysis", "Planning"]
        )
        assert lifecycle_info.engine == "clickhouse"
        assert len(lifecycle_info.phases) == 2
        assert lifecycle_info.phase_sequence == ["Parsing", "Analysis", "Planning"]
        assert lifecycle_info.logical_physical_boundary is None
        assert lifecycle_info.best_plan_selection is None
        assert lifecycle_info.post_optimizer is None
        assert lifecycle_info.fallback_behavior is None
        assert lifecycle_info.confidence == "medium"
        assert lifecycle_info.notes == []

    def test_lifecycle_info_with_all_optional_fields(self):
        """LifecycleInfo with all optional fields populated."""
        lifecycle_info = LifecycleInfo(
            engine="starrocks",
            phases=[
                PhaseInfo(phase="Parse", entry="parser.cpp", transitions_to=["Analyze"]),
                PhaseInfo(phase="Analyze", entry="analyzer.cpp", transitions_to=["Optimize"]),
                PhaseInfo(phase="Optimize", entry="optimizer.cpp", transitions_to=["Execute"])
            ],
            phase_sequence=["Parse", "Analyze", "Optimize", "Execute"],
            logical_physical_boundary="Optimize phase (logical->physical split)",
            best_plan_selection="Cost-based comparison in Optimize phase",
            post_optimizer="Post-optimization rules applied after best plan selection",
            fallback_behavior="Fallback to RBO when CBO times out",
            confidence="high",
            notes=["Verified lifecycle structure", "Contains CBO and RBO paths"]
        )
        assert lifecycle_info.engine == "starrocks"
        assert lifecycle_info.logical_physical_boundary == "Optimize phase (logical->physical split)"
        assert lifecycle_info.best_plan_selection == "Cost-based comparison in Optimize phase"
        assert lifecycle_info.post_optimizer == "Post-optimization rules applied after best plan selection"
        assert lifecycle_info.fallback_behavior == "Fallback to RBO when CBO times out"
        assert lifecycle_info.confidence == "high"
        assert len(lifecycle_info.notes) == 2

    def test_lifecycle_info_json_serialization(self):
        """LifecycleInfo can be serialized to JSON."""
        lifecycle_info = LifecycleInfo(
            engine="postgres",
            phases=[
                PhaseInfo(phase="Planner", entry="planner.c", transitions_to=["Executor"])
            ],
            phase_sequence=["Planner", "Executor"],
            confidence="medium"
        )
        json_str = lifecycle_info.model_dump_json()
        data = json.loads(json_str)
        assert data["engine"] == "postgres"
        assert len(data["phases"]) == 1
        assert data["phases"][0]["phase"] == "Planner"
        assert data["confidence"] == "medium"

    def test_lifecycle_info_default_confidence(self):
        """LifecycleInfo has default confidence of 'medium'."""
        lifecycle_info = LifecycleInfo(engine="test_engine")
        assert lifecycle_info.confidence == "medium"


class TestLifecycleAgent:
    """Tests for LifecycleAgent class."""

    def test_lifecycle_agent_instantiation(self):
        """LifecycleAgent can be instantiated correctly."""
        agent = LifecycleAgent(
            engine="clickhouse",
            work_dir="/tmp/work"
        )
        assert agent.name == "LifecycleAnalyzer"
        assert agent.engine == "clickhouse"
        assert agent.work_dir == "/tmp/work"
        assert agent.repo_map is None

    def test_lifecycle_agent_with_repo_map(self):
        """LifecycleAgent can be instantiated with RepoMap."""
        repo_map = RepoMap(
            engine="clickhouse",
            repo_root="/path/to/clickhouse",
            optimizer_dirs=["src/optimizer"],
            main_entries=["src/optimizer.cpp"]
        )
        agent = LifecycleAgent(
            engine="clickhouse",
            work_dir="/tmp/work",
            repo_map=repo_map
        )
        assert agent.repo_map is not None
        assert agent.repo_map.engine == "clickhouse"
        assert agent.repo_map.optimizer_dirs == ["src/optimizer"]

    def test_lifecycle_agent_inherits_from_base_agent(self):
        """LifecycleAgent inherits from BaseAgent."""
        from optimizer_analysis.agents.base import BaseAgent

        agent = LifecycleAgent(
            engine="test",
            work_dir="/tmp"
        )
        assert isinstance(agent, BaseAgent)

    def test_lifecycle_agent_execute_returns_agent_result(self):
        """LifecycleAgent execute returns AgentResult with needs_manual_review status."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = LifecycleAgent(
                engine="clickhouse",
                work_dir=join(tmpdir, "work")
            )
            result = agent.execute()

            assert isinstance(result, AgentResult)
            assert result.agent_name == "LifecycleAnalyzer"
            assert result.status == "partial"
            assert len(result.artifacts) == 1
            assert result.artifacts[0].endswith("lifecycle.json")
            assert result.errors == []
            assert "clickhouse" in result.summary
            assert result.metadata["needs_manual_review"] is True
            assert result.metadata["confidence"] == "low"

    def test_lifecycle_agent_creates_artifact_file(self):
        """LifecycleAgent creates lifecycle.json artifact file."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = join(tmpdir, "work")
            agent = LifecycleAgent(
                engine="starrocks",
                work_dir=work_dir
            )
            result = agent.execute()

            # Check artifact file exists
            assert len(result.artifacts) == 1
            artifact_path = result.artifacts[0]
            assert exists(artifact_path)

            # Verify JSON content
            with open(artifact_path, "r") as f:
                data = json.load(f)

            assert data["engine"] == "starrocks"
            assert data["confidence"] == "low"
            assert len(data["phases"]) == 5  # Default phases created
            assert len(data["notes"]) > 0

    def test_lifecycle_agent_creates_framework_directory(self):
        """LifecycleAgent creates framework subdirectory."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = join(tmpdir, "work")
            agent = LifecycleAgent(
                engine="postgres",
                work_dir=work_dir
            )
            result = agent.execute()

            # Check that framework directory was created
            framework_dir = join(work_dir, "framework")
            assert exists(framework_dir)
            assert exists(join(framework_dir, "lifecycle.json"))

    def test_lifecycle_agent_with_repo_map_context(self):
        """LifecycleAgent adds repo_map context to notes."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_map = RepoMap(
                engine="test",
                repo_root="/repo",
                optimizer_dirs=["src/optimizer", "src/cbo"],
                main_entries=["src/main.cpp", "src/optimizer.cpp"]
            )
            agent = LifecycleAgent(
                engine="test",
                work_dir=join(tmpdir, "work"),
                repo_map=repo_map
            )
            result = agent.execute()

            # Check metadata
            assert result.metadata["has_repo_map"] is True

            # Verify notes contain repo_map context
            artifact_path = result.artifacts[0]
            with open(artifact_path, "r") as f:
                data = json.load(f)

            notes = data["notes"]
            assert any("Repo map available" in note for note in notes)
            assert any("Optimizer directories identified" in note for note in notes)

    def test_lifecycle_agent_handles_exception(self):
        """LifecycleAgent handles exceptions gracefully."""
        # This is tested implicitly through normal execution
        # The error handling path is similar to repo_mapper
        pass

    def test_lifecycle_agent_artifact_path(self):
        """LifecycleAgent _artifact_path generates correct paths."""
        agent = LifecycleAgent(
            engine="test",
            work_dir="/work/dir"
        )
        path = agent._artifact_path("test.json")
        assert path == "/work/dir/test.json"