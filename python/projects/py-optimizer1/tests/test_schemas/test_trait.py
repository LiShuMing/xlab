from optimizer_analysis.schemas.trait import TraitProperty, PropertyType
from optimizer_analysis.schemas.base import Evidence


def test_trait_creation():
    """TraitProperty must have name and type."""
    trait = TraitProperty(
        property_name="Distribution",
        property_type=PropertyType.PHYSICAL,
        representation="HashDistributionSpec",
        propagation_logic="Derived from input distribution and operator semantics",
        enforcer="EnforceHashDistribution",
        where_used=["Join", "Aggregate", "Exchange"],
        impact_on_search="Requires enforcing operator if property mismatch",
        evidence=[]
    )
    assert trait.property_name == "Distribution"
    assert trait.property_type == PropertyType.PHYSICAL


def test_property_types():
    """Property types per DESIGN.md Section 6.3."""
    types = [PropertyType.LOGICAL, PropertyType.PHYSICAL]
    assert len(types) == 2


def test_trait_with_enforcer():
    """Trait can specify enforcement mechanism."""
    trait = TraitProperty(
        property_name="Ordering",
        property_type=PropertyType.PHYSICAL,
        representation="SortSpec",
        enforcer="SortEnforcer",
        where_used=["SortMergeJoin", "Window", "OrderBy"],
        impact_on_search="May require additional sort operator",
        evidence=[
            Evidence(
                file_path="src/optimizer/properties/ordering.cpp",
                description="Ordering property implementation"
            )
        ]
    )
    assert trait.enforcer == "SortEnforcer"
    assert len(trait.where_used) == 3