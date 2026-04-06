"""Tests for base agent class and AgentResult model."""

from optimizer_analysis.agents.base import AgentResult, BaseAgent


def test_agent_result_creation():
    """AgentResult basic creation with required fields."""
    result = AgentResult(
        agent_name="test_agent",
        status="success",
        artifacts=["output.txt"],
        errors=[],
        summary="Test completed successfully",
        metadata={"duration": 1.5}
    )
    assert result.agent_name == "test_agent"
    assert result.status == "success"
    assert result.artifacts == ["output.txt"]
    assert result.errors == []
    assert result.summary == "Test completed successfully"
    assert result.metadata == {"duration": 1.5}


def test_agent_result_failure():
    """AgentResult failure case with errors."""
    result = AgentResult(
        agent_name="failing_agent",
        status="failed",
        artifacts=[],
        errors=["Connection timeout", "Invalid response"],
        summary="Agent failed to complete",
        metadata={"attempt": 3}
    )
    assert result.status == "failed"
    assert len(result.errors) == 2
    assert "Connection timeout" in result.errors
    assert result.artifacts == []


def test_agent_result_partial():
    """AgentResult partial success case."""
    result = AgentResult(
        agent_name="partial_agent",
        status="partial",
        artifacts=["partial_output.txt"],
        errors=["Warning: missing optional field"],
        summary="Partially completed with warnings",
        metadata={}
    )
    assert result.status == "partial"
    assert len(result.artifacts) == 1
    assert len(result.errors) == 1


def test_base_agent_abstract():
    """BaseAgent is abstract and requires execute method."""
    import inspect

    # Verify BaseAgent has abstract execute method
    assert hasattr(BaseAgent, 'execute')
    execute_method = getattr(BaseAgent, 'execute')
    assert callable(execute_method)

    # Verify we cannot instantiate BaseAgent directly
    from abc import ABC
    assert issubclass(BaseAgent, ABC)


def test_base_agent_artifact_path():
    """BaseAgent _artifact_path helper method."""
    # Create a concrete implementation for testing
    class ConcreteAgent(BaseAgent):
        name = "concrete_agent"

        def execute(self) -> AgentResult:
            return AgentResult(
                agent_name=self.name,
                status="success",
                artifacts=[],
                errors=[],
                summary="Done",
                metadata={}
            )

    agent = ConcreteAgent(engine="test_engine", work_dir="/tmp/work")
    artifact_path = agent._artifact_path("output.json")
    assert artifact_path == "/tmp/work/output.json"


def test_base_agent_concrete_implementation():
    """Concrete agent implementation works correctly."""
    class ConcreteAgent(BaseAgent):
        name = "test_concrete"

        def execute(self) -> AgentResult:
            return AgentResult(
                agent_name=self.name,
                status="success",
                artifacts=[self._artifact_path("result.txt")],
                errors=[],
                summary="Execution complete",
                metadata={"engine": self.engine}
            )

    agent = ConcreteAgent(engine="my_engine", work_dir="/workspace")
    result = agent.execute()

    assert result.agent_name == "test_concrete"
    assert result.status == "success"
    assert result.artifacts == ["/workspace/result.txt"]
    assert result.metadata["engine"] == "my_engine"