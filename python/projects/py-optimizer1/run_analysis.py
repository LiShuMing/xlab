#!/usr/bin/env python3
"""Run optimizer analysis on multiple engines."""
import argparse
import json
import tempfile
from pathlib import Path
from datetime import datetime

from optimizer_analysis.config import AppConfig
from optimizer_analysis.engines.presets import STARROCKS_CONFIG, CALCITE_CONFIG, DORIS_CONFIG
from optimizer_analysis.agents.repo_mapper import RepoMapperAgent
from optimizer_analysis.agents.lifecycle import LifecycleAgent
from optimizer_analysis.agents.rule_miner import RBOMinerAgent, CBOMinerAgent
from optimizer_analysis.agents.property_agent import PropertyAgent
from optimizer_analysis.agents.stats_cost_agent import StatsCostAgent
from optimizer_analysis.agents.observability_agent import ObservabilityAgent
from optimizer_analysis.agents.comparison_agent import ComparisonAgent
from optimizer_analysis.agents.verifier_agent import VerifierAgent
from optimizer_analysis.llm_client import create_llm_client


# Engine source paths
ENGINE_PATHS = {
    "StarRocks": "/home/lism/work/starrocks",
    "Calcite": "/home/lism/work/calcite",
    "Doris": "/home/lism/work/doris",
}

ENGINE_CONFIGS = {
    "StarRocks": STARROCKS_CONFIG,
    "Calcite": CALCITE_CONFIG,
    "Doris": DORIS_CONFIG,
}


def analyze_engine(engine_name: str, source_path: str, work_dir: str, use_llm: bool = False) -> dict:
    """Run full analysis on a single engine."""
    print(f"\n{'='*60}")
    print(f"Analyzing {engine_name}")
    print(f"Source: {source_path}")
    print(f"{'='*60}")

    config = ENGINE_CONFIGS[engine_name]
    results = {"engine": engine_name, "config": config.model_dump()}

    # Determine optimizer path
    optimizer_rel_path = config.optimizer_dirs[0]
    optimizer_path = str(Path(source_path) / optimizer_rel_path)

    if not Path(optimizer_path).exists():
        print(f"  WARNING: Optimizer path not found: {optimizer_path}")
        return results

    llm_client = create_llm_client() if use_llm else None

    # 1. Repository Mapper
    print("\n[1/6] Repository Mapping...")
    repo_mapper = RepoMapperAgent(
        engine=engine_name,
        work_dir=work_dir,
        repo_root=source_path
    )
    repo_result = repo_mapper.execute()
    results["repo_map"] = repo_result.model_dump()
    print(f"  Status: {repo_result.status}")

    # 2. Lifecycle Analysis
    print("\n[2/6] Lifecycle Analysis...")
    lifecycle_agent = LifecycleAgent(
        engine=engine_name,
        work_dir=work_dir,
        repo_map=None
    )
    lifecycle_result = lifecycle_agent.execute()
    results["lifecycle"] = lifecycle_result.model_dump()
    print(f"  Status: {lifecycle_result.status}")

    # 3. RBO Rules Mining
    print("\n[3/6] RBO Rule Mining...")
    rbo_path = get_rule_path(optimizer_path, engine_name, "rbo")
    if rbo_path and Path(rbo_path).exists():
        rbo_miner = RBOMinerAgent(
            engine=engine_name,
            work_dir=work_dir,
            source_path=rbo_path,
            llm_client=llm_client
        )
        rbo_result = rbo_miner.execute()
        results["rbo_rules"] = rbo_result.model_dump()
        print(f"  Status: {rbo_result.status}")
    else:
        print(f"  Skipped: Rule path not found")

    # 4. Property Analysis
    print("\n[4/6] Property Analysis...")
    property_path = get_property_path(optimizer_path, engine_name)
    if property_path and Path(property_path).exists():
        property_agent = PropertyAgent(
            engine=engine_name,
            work_dir=work_dir,
            source_path=property_path,
            llm_client=llm_client
        )
        property_result = property_agent.execute()
        results["properties"] = property_result.model_dump()
        print(f"  Status: {property_result.status}")
    else:
        print(f"  Skipped: Property path not found")

    # 5. Stats/Cost Analysis
    print("\n[5/6] Stats/Cost Analysis...")
    stats_path = get_stats_path(optimizer_path, engine_name)
    cost_path = get_cost_path(optimizer_path, engine_name)
    if stats_path or cost_path:
        stats_agent = StatsCostAgent(
            engine=engine_name,
            work_dir=work_dir,
            stats_path=stats_path or "",
            cost_path=cost_path or "",
            llm_client=llm_client
        )
        stats_result = stats_agent.execute()
        results["stats_cost"] = stats_result.model_dump()
        print(f"  Status: {stats_result.status}")
    else:
        print(f"  Skipped: Stats/Cost paths not found")

    # 6. Observability Analysis
    print("\n[6/6] Observability Analysis...")
    observability_agent = ObservabilityAgent(
        engine=engine_name,
        work_dir=work_dir,
        source_path=optimizer_path,
        llm_client=llm_client
    )
    obs_result = observability_agent.execute()
    results["observability"] = obs_result.model_dump()
    print(f"  Status: {obs_result.status}")

    return results


def get_rule_path(optimizer_path: str, engine_name: str, rule_type: str) -> str:
    """Get rule directory path for an engine."""
    paths = {
        "StarRocks": {
            "rbo": f"{optimizer_path}/rule/transformation",
            "cbo": f"{optimizer_path}/rule/implementation",
        },
        "Calcite": {
            "rbo": f"{optimizer_path}/rules",
            "cbo": f"{optimizer_path}/rules",
        },
        "Doris": {
            "rbo": f"{optimizer_path}/rules/rewrite",
            "cbo": f"{optimizer_path}/rules/exploration",
        },
    }
    return paths.get(engine_name, {}).get(rule_type)


def get_property_path(optimizer_path: str, engine_name: str) -> str:
    """Get property directory path for an engine."""
    paths = {
        "StarRocks": f"{optimizer_path}/property",
        "Calcite": optimizer_path,  # Traits mixed in plan/
        "Doris": optimizer_path,  # Properties in nereids/
    }
    return paths.get(engine_name)


def get_stats_path(optimizer_path: str, engine_name: str) -> str:
    """Get statistics directory path for an engine."""
    paths = {
        "StarRocks": f"{optimizer_path}/statistics",
        "Calcite": "",
        "Doris": f"{optimizer_path}/statistics",
    }
    return paths.get(engine_name, "")


def get_cost_path(optimizer_path: str, engine_name: str) -> str:
    """Get cost directory path for an engine."""
    paths = {
        "StarRocks": f"{optimizer_path}/cost",
        "Calcite": "",
        "Doris": f"{optimizer_path}/cost",
    }
    return paths.get(engine_name, "")


def main():
    parser = argparse.ArgumentParser(description="Analyze optimizer source code")
    parser.add_argument("--engines", nargs="+", default=["StarRocks", "Calcite", "Doris"],
                        help="Engines to analyze")
    parser.add_argument("--output", default="./analysis_output",
                        help="Output directory")
    parser.add_argument("--llm", action="store_true",
                        help="Use LLM for deeper analysis")
    args = parser.parse_args()

    print("="*60)
    print("Optimizer Expert Analyzer")
    print(f"Started at: {datetime.now().isoformat()}")
    print("="*60)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_results = {}

    for engine_name in args.engines:
        if engine_name not in ENGINE_PATHS:
            print(f"Unknown engine: {engine_name}")
            continue

        source_path = ENGINE_PATHS[engine_name]
        if not Path(source_path).exists():
            print(f"Source not found for {engine_name}: {source_path}")
            continue

        engine_output = output_dir / engine_name.lower()
        engine_output.mkdir(parents=True, exist_ok=True)

        results = analyze_engine(
            engine_name=engine_name,
            source_path=source_path,
            work_dir=str(engine_output),
            use_llm=args.llm
        )
        all_results[engine_name] = results

        # Save engine results
        with open(engine_output / "analysis.json", "w") as f:
            json.dump(results, f, indent=2, default=str)

    # Generate comparison if multiple engines analyzed
    if len(all_results) > 1:
        print("\n" + "="*60)
        print("Generating Comparison Report")
        print("="*60)

        comparison_agent = ComparisonAgent(
            engines=list(all_results.keys()),
            work_dir=str(output_dir),
            analysis_results=all_results
        )
        comparison_result = comparison_agent.execute()

        print(f"\nComparison Status: {comparison_result.status}")
        print(f"Artifacts: {comparison_result.artifacts}")

    print("\n" + "="*60)
    print(f"Analysis complete at: {datetime.now().isoformat()}")
    print(f"Results saved to: {output_dir}")
    print("="*60)


if __name__ == "__main__":
    main()