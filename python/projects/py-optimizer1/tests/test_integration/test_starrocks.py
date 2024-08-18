"""Tests for configuration and StarRocks integration."""
import os
import tempfile
from pathlib import Path

import pytest

from optimizer_analysis.config import LLMConfig, AppConfig
from optimizer_analysis.engines.presets import STARROCKS_CONFIG, get_default_engines
from optimizer_analysis.engines.registry import EngineRegistry
from optimizer_analysis.agents.repo_mapper import RepoMapperAgent, RepoMap
from optimizer_analysis.schemas.framework import EngineType, OptimizerStyle


class TestLLMConfig:
    """Tests for LLM configuration."""

    def test_from_env_file(self):
        """Load LLM config from ~/.env file."""
        config = LLMConfig.from_env_file("~/.env")
        assert config.base_url != ""
        assert config.api_key != ""
        assert config.model != ""
        assert config.timeout > 0

    def test_from_env_with_defaults(self):
        """Load LLM config with environment variables."""
        # Set test values
        os.environ["LLM_BASE_URL"] = "https://test.example.com/v1"
        os.environ["LLM_API_KEY"] = "test-key"
        os.environ["LLM_MODEL"] = "test-model"
        os.environ["LLM_TIMEOUT"] = "60"

        config = LLMConfig.from_env()
        assert config.base_url == "https://test.example.com/v1"
        assert config.api_key == "test-key"
        assert config.model == "test-model"
        assert config.timeout == 60


class TestAppConfig:
    """Tests for application configuration."""

    def test_load_config(self):
        """Load full application config."""
        config = AppConfig.load("~/.env")
        assert config.llm is not None
        assert config.log_level in ["DEBUG", "INFO", "WARNING", "ERROR"]


class TestStarRocksConfig:
    """Tests for StarRocks engine configuration."""

    def test_starrocks_config_values(self):
        """Verify StarRocks configuration values."""
        assert STARROCKS_CONFIG.name == "StarRocks"
        assert STARROCKS_CONFIG.engine_type == EngineType.COLUMNAR_OLAP
        assert STARROCKS_CONFIG.optimizer_style == OptimizerStyle.CASCADES
        assert len(STARROCKS_CONFIG.optimizer_dirs) > 0
        assert STARROCKS_CONFIG.main_entry is not None

    def test_get_default_engines(self):
        """Get default engines dictionary."""
        engines = get_default_engines()
        assert "StarRocks" in engines
        assert engines["StarRocks"].name == "StarRocks"


class TestStarRocksRepoMapper:
    """Tests for RepoMapperAgent against StarRocks source."""

    STARROCKS_PATH = "/home/lism/work/starrocks"

    @pytest.fixture
    def starrocks_exists(self):
        """Check if StarRocks source exists."""
        return Path(self.STARROCKS_PATH).exists()

    def test_repo_mapper_with_starrocks(self, starrocks_exists):
        """Test RepoMapperAgent against StarRocks source."""
        if not starrocks_exists:
            pytest.skip(f"StarRocks source not found at {self.STARROCKS_PATH}")

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = RepoMapperAgent(
                engine="StarRocks",
                work_dir=tmpdir,
                repo_root=self.STARROCKS_PATH
            )

            result = agent.execute()
            assert result.agent_name == "RepoMapper"
            assert result.status in ["success", "partial", "failed"]

    def test_starrocks_optimizer_structure(self, starrocks_exists):
        """Verify StarRocks optimizer directory structure."""
        if not starrocks_exists:
            pytest.skip(f"StarRocks source not found at {self.STARROCKS_PATH}")

        optimizer_path = Path(self.STARROCKS_PATH) / "fe/fe-core/src/main/java/com/starrocks/sql/optimizer"
        assert optimizer_path.exists(), f"Optimizer directory not found: {optimizer_path}"

        # Check key files exist
        assert (optimizer_path / "Optimizer.java").exists()
        assert (optimizer_path / "Memo.java").exists()
        assert (optimizer_path / "Group.java").exists()
        assert (optimizer_path / "rule").exists()
        assert (optimizer_path / "cost").exists()
        assert (optimizer_path / "statistics").exists()

    def test_starrocks_rule_structure(self, starrocks_exists):
        """Verify StarRocks rule directory structure."""
        if not starrocks_exists:
            pytest.skip(f"StarRocks source not found at {self.STARROCKS_PATH}")

        rule_path = Path(self.STARROCKS_PATH) / "fe/fe-core/src/main/java/com/starrocks/sql/optimizer/rule"
        assert rule_path.exists(), f"Rule directory not found: {rule_path}"

        # Check rule subdirectories
        assert (rule_path / "Rule.java").exists()
        assert (rule_path / "RuleSet.java").exists()
        assert (rule_path / "RuleType.java").exists()
        assert (rule_path / "transformation").exists()
        assert (rule_path / "implementation").exists()


class TestEngineRegistryIntegration:
    """Tests for EngineRegistry with StarRocks."""

    def test_register_starrocks(self):
        """Register StarRocks in the engine registry."""
        registry = EngineRegistry()
        registry.register(STARROCKS_CONFIG)

        assert "StarRocks" in registry.list_engines()
        config = registry.get("StarRocks")
        assert config.name == "StarRocks"
        assert config.optimizer_style == OptimizerStyle.CASCADES