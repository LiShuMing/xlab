# tests/test_engines/test_registry.py
import pytest

from optimizer_analysis.engines import EngineConfig, EngineRegistry
from optimizer_analysis.schemas import EngineType, OptimizerStyle


def test_engine_config_creation():
    """EngineConfig can be created with required fields."""
    config = EngineConfig(
        name="StarRocks",
        repo_url="https://github.com/StarRocks/starrocks",
        default_branch="main",
        engine_type=EngineType.COLUMNAR_OLAP,
        optimizer_style=OptimizerStyle.CASCADES,
        optimizer_dirs=["be/src/optimizer"],
        main_entry="be/src/optimizer/optimizer.cpp",
        fallback_paths=["be/src/optimizer/fallback"],
        docs_url="https://docs.starrocks.io",
        notes=["Uses Cascades-style optimizer"]
    )

    assert config.name == "StarRocks"
    assert config.repo_url == "https://github.com/StarRocks/starrocks"
    assert config.default_branch == "main"
    assert config.engine_type == EngineType.COLUMNAR_OLAP
    assert config.optimizer_style == OptimizerStyle.CASCADES
    assert config.optimizer_dirs == ["be/src/optimizer"]
    assert config.main_entry == "be/src/optimizer/optimizer.cpp"
    assert config.fallback_paths == ["be/src/optimizer/fallback"]
    assert config.docs_url == "https://docs.starrocks.io"
    assert config.notes == ["Uses Cascades-style optimizer"]


def test_engine_config_minimal():
    """EngineConfig can be created with minimal required fields."""
    config = EngineConfig(
        name="MinimalEngine",
        engine_type=EngineType.FRAMEWORK,
        optimizer_style=OptimizerStyle.HEURISTIC_MIXED
    )

    assert config.name == "MinimalEngine"
    assert config.repo_url is None
    assert config.default_branch == "main"
    assert config.engine_type == EngineType.FRAMEWORK
    assert config.optimizer_style == OptimizerStyle.HEURISTIC_MIXED
    assert config.optimizer_dirs == []
    assert config.main_entry is None
    assert config.fallback_paths == []
    assert config.docs_url is None
    assert config.notes == []


def test_engine_registry():
    """EngineRegistry can register and list engines."""
    registry = EngineRegistry()

    config1 = EngineConfig(
        name="Engine1",
        engine_type=EngineType.COLUMNAR_OLAP,
        optimizer_style=OptimizerStyle.CASCADES
    )
    config2 = EngineConfig(
        name="Engine2",
        engine_type=EngineType.ROW_STORE,
        optimizer_style=OptimizerStyle.VOLCANO
    )

    registry.register(config1)
    registry.register(config2)

    engines = registry.list_engines()
    assert len(engines) == 2
    assert "Engine1" in engines
    assert "Engine2" in engines


def test_engine_registry_get():
    """EngineRegistry can retrieve engines by name."""
    registry = EngineRegistry()

    config = EngineConfig(
        name="StarRocks",
        engine_type=EngineType.COLUMNAR_OLAP,
        optimizer_style=OptimizerStyle.CASCADES,
        optimizer_dirs=["be/src/optimizer"]
    )

    registry.register(config)
    retrieved = registry.get("StarRocks")

    assert retrieved.name == "StarRocks"
    assert retrieved.engine_type == EngineType.COLUMNAR_OLAP
    assert retrieved.optimizer_style == OptimizerStyle.CASCADES
    assert retrieved.optimizer_dirs == ["be/src/optimizer"]


def test_engine_registry_get_not_found():
    """EngineRegistry raises KeyError for unknown engine."""
    registry = EngineRegistry()

    with pytest.raises(KeyError, match="Engine 'Unknown' not found"):
        registry.get("Unknown")


def test_engine_registry_duplicate():
    """EngineRegistry raises ValueError for duplicate registration."""
    registry = EngineRegistry()

    config = EngineConfig(
        name="Duplicate",
        engine_type=EngineType.COLUMNAR_OLAP,
        optimizer_style=OptimizerStyle.CASCADES
    )

    registry.register(config)

    with pytest.raises(ValueError, match="Engine 'Duplicate' is already registered"):
        registry.register(config)


def test_engine_registry_clear():
    """EngineRegistry can clear all registered engines."""
    registry = EngineRegistry()

    config1 = EngineConfig(
        name="Engine1",
        engine_type=EngineType.COLUMNAR_OLAP,
        optimizer_style=OptimizerStyle.CASCADES
    )
    config2 = EngineConfig(
        name="Engine2",
        engine_type=EngineType.ROW_STORE,
        optimizer_style=OptimizerStyle.VOLCANO
    )

    registry.register(config1)
    registry.register(config2)

    assert len(registry.list_engines()) == 2

    registry.clear()

    assert len(registry.list_engines()) == 0