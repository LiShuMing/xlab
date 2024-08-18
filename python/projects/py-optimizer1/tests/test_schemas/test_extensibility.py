# tests/test_schemas/test_extensibility.py
"""Tests for Extensibility schema (DESIGN.md Section 6.6)."""
from optimizer_analysis.schemas.extensibility import Extensibility
from optimizer_analysis.schemas.base import Evidence


def test_extensibility_creation():
    """Extensibility must have extension paths for plugins."""
    ext = Extensibility(
        rule_extension_path="plugins/rules/",
        property_extension_path="plugins/properties/",
        evidence=[]
    )
    assert ext.rule_extension_path == "plugins/rules/"
    assert ext.property_extension_path == "plugins/properties/"
    assert ext.cost_extension_path is None  # default
    assert ext.stats_extension_path is None  # default
    assert ext.plugin_registration is None  # default
    assert ext.testing_support is None  # default


def test_extensibility_framework_level():
    """Extensibility with full API-level extensibility."""
    ext = Extensibility(
        rule_extension_path="api/v1/rules/register",
        property_extension_path="api/v1/properties/register",
        cost_extension_path="api/v1/cost/register",
        stats_extension_path="api/v1/stats/register",
        plugin_registration="PluginManager::register()",
        testing_support="PluginTestHarness",
        uncertain_points=[
            "Plugin versioning not documented",
            "Hot reload support unclear"
        ],
        evidence=[
            Evidence(
                file_path="src/optimizer/plugin/plugin_manager.cpp",
                description="Plugin registration implementation"
            ),
            Evidence(
                file_path="src/optimizer/plugin/test_harness.cpp",
                description="Testing support for plugins"
            )
        ]
    )
    assert ext.rule_extension_path == "api/v1/rules/register"
    assert ext.property_extension_path == "api/v1/properties/register"
    assert ext.cost_extension_path == "api/v1/cost/register"
    assert ext.stats_extension_path == "api/v1/stats/register"
    assert ext.plugin_registration == "PluginManager::register()"
    assert ext.testing_support == "PluginTestHarness"
    assert len(ext.uncertain_points) == 2
    assert len(ext.evidence) == 2


def test_extensibility_with_partial_paths():
    """Extensibility can have some paths defined and others not."""
    ext = Extensibility(
        rule_extension_path="custom_rules/",
        stats_extension_path="custom_stats/",
        uncertain_points=["Property extension not supported"],
        evidence=[
            Evidence(
                file_path="docs/architecture.md",
                description="Extension points documented"
            )
        ]
    )
    assert ext.rule_extension_path == "custom_rules/"
    assert ext.property_extension_path is None
    assert ext.cost_extension_path is None
    assert ext.stats_extension_path == "custom_stats/"
    assert len(ext.uncertain_points) == 1
    assert len(ext.evidence) == 1


def test_extensibility_empty_defaults():
    """Extensibility with minimal configuration uses defaults."""
    ext = Extensibility()
    assert ext.rule_extension_path is None
    assert ext.property_extension_path is None
    assert ext.cost_extension_path is None
    assert ext.stats_extension_path is None
    assert ext.plugin_registration is None
    assert ext.testing_support is None
    assert ext.uncertain_points == []
    assert ext.evidence == []