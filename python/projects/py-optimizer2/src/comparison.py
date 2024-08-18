"""Comparison engine for multi-engine analysis."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.models import LOGICAL_CATEGORIES, DiffMatrixEntry


class CanonicalNormalizer:
    """Normalizes rule names across engines."""

    def __init__(self, data_dir: Path, api_key: Optional[str] = None):
        self.data_dir = data_dir
        self.api_key = api_key
        self.canonical_map: Dict[str, Dict[str, str]] = {}

    def normalize(self) -> Dict[str, Dict[str, str]]:
        """Normalize canonical names across all engines."""
        # Load all rules
        all_rules = self._load_all_rules()

        # Group by logical category
        by_category: Dict[str, List[Dict]] = {cat: [] for cat in LOGICAL_CATEGORIES}
        for rule in all_rules:
            cat = rule.get("logical_category", "other")
            if cat in by_category:
                by_category[cat].append(rule)

        # For each category, build mapping
        for category, rules in by_category.items():
            if not rules:
                continue

            # Group by engine
            by_engine: Dict[str, List[str]] = {}
            for rule in rules:
                engine = rule["engine_id"]
                name = rule.get("canonical_name", rule["rule_name"])
                if engine not in by_engine:
                    by_engine[engine] = []
                by_engine[engine].append(name)

            # Build mapping (simplified version without LLM for now)
            self._build_mapping_for_category(category, by_engine)

        # Save mapping
        self._save_mapping()

        return self.canonical_map

    def _load_all_rules(self) -> List[Dict[str, Any]]:
        """Load all analyzed rules."""
        all_rules = []

        for engine_dir in self.data_dir.iterdir():
            if not engine_dir.is_dir():
                continue

            for jsonl_file in engine_dir.glob("*.jsonl"):
                with open(jsonl_file, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            all_rules.append(json.loads(line))

        return all_rules

    def _build_mapping_for_category(self, category: str, by_engine: Dict[str, List[str]]):
        """Build canonical name mapping for a category."""
        self.canonical_map[category] = {}

        # Simple heuristic: group by common keywords
        for engine, names in by_engine.items():
            for name in names:
                # Use name as canonical if it looks standardized
                if "." in name:
                    canonical = name
                else:
                    canonical = f"{category}.{name.lower().replace(' ', '_')}"

                key = f"{engine}::{name}"
                self.canonical_map[category][key] = canonical

    def _save_mapping(self):
        """Save canonical name mapping."""
        output_file = self.data_dir / "canonical_name_map.json"
        with open(output_file, "w") as f:
            json.dump(self.canonical_map, f, indent=2)


class DiffMatrixGenerator:
    """Generates diff matrix across engines."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.engines = [
            "starrocks",
            "doris",
            "clickhouse",
            "gpdb_orca",
            "calcite",
            "cockroachdb",
            "postgres",
            "columbia",
        ]

    def generate(self) -> List[DiffMatrixEntry]:
        """Generate diff matrix for all canonical rules."""
        # Load canonical mapping
        canonical_map = self._load_canonical_map()

        # Load all rules
        all_rules = self._load_all_rules()

        # Group by canonical name
        by_canonical: Dict[str, List[Dict]] = {}
        for rule in all_rules:
            canonical = rule.get("canonical_name", rule["rule_name"])
            if canonical not in by_canonical:
                by_canonical[canonical] = []
            by_canonical[canonical].append(rule)

        # Generate diff entries
        entries = []
        for canonical_name, rules in by_canonical.items():
            entry = self._create_diff_entry(canonical_name, rules)
            entries.append(entry)

        # Save matrix
        self._save_matrix(entries)

        return entries

    def _load_canonical_map(self) -> Dict:
        """Load canonical name mapping."""
        map_file = self.data_dir / "canonical_name_map.json"
        if map_file.exists():
            with open(map_file) as f:
                return json.load(f)
        return {}

    def _load_all_rules(self) -> List[Dict[str, Any]]:
        """Load all analyzed rules."""
        all_rules = []

        for engine_dir in self.data_dir.iterdir():
            if not engine_dir.is_dir():
                continue

            for jsonl_file in engine_dir.glob("*.jsonl"):
                with open(jsonl_file, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            all_rules.append(json.loads(line))

        return all_rules

    def _create_diff_entry(self, canonical_name: str, rules: List[Dict]) -> DiffMatrixEntry:
        """Create diff entry for a canonical rule."""
        # Build engine presence map
        engines_data = {}
        for engine in self.engines:
            engine_rules = [r for r in rules if r["engine_id"] == engine]
            if engine_rules:
                rule = engine_rules[0]
                engines_data[engine] = {
                    "present": True,
                    "rule_name": rule["rule_name"],
                    "confidence": rule.get("confidence", 0.5),
                    "ra_input": rule.get("ra_input_pattern", ""),
                    "ra_output": rule.get("ra_output_pattern", ""),
                }
            else:
                engines_data[engine] = {"present": False}

        # Check if all present
        all_present = all(e.get("present", False) for e in engines_data.values())

        # Calculate alignment score
        present_count = sum(1 for e in engines_data.values() if e.get("present", False))
        alignment_score = present_count / len(self.engines)

        return DiffMatrixEntry(
            canonical_name=canonical_name,
            logical_category=rules[0].get("logical_category", "other"),
            engines=engines_data,
            all_present=all_present,
            semantic_equivalent=False,  # Would need LLM analysis
            diff_summary="",
            alignment_score=alignment_score,
        )

    def _save_matrix(self, entries: List[DiffMatrixEntry]):
        """Save diff matrix to JSON."""
        matrix_data = []
        for entry in entries:
            matrix_data.append(
                {
                    "canonical_name": entry.canonical_name,
                    "logical_category": entry.logical_category,
                    "engines": entry.engines,
                    "all_present": entry.all_present,
                    "semantic_equivalent": entry.semantic_equivalent,
                    "diff_summary": entry.diff_summary,
                    "alignment_score": entry.alignment_score,
                }
            )

        output_file = self.data_dir / "diff_matrix.json"
        with open(output_file, "w") as f:
            json.dump(matrix_data, f, indent=2)


class ScoringEngine:
    """Scores engines on various dimensions."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.engines = [
            "starrocks",
            "doris",
            "clickhouse",
            "gpdb_orca",
            "calcite",
            "cockroachdb",
            "postgres",
            "columbia",
        ]

    def calculate_scores(self) -> Dict[str, Dict[str, float]]:
        """Calculate scores for all engines."""
        # Load diff matrix
        matrix_file = self.data_dir / "diff_matrix.json"
        if not matrix_file.exists():
            return {}

        with open(matrix_file) as f:
            matrix = json.load(f)

        scores = {}

        for engine in self.engines:
            # Calculate coverage
            present_count = sum(
                1 for entry in matrix if entry["engines"].get(engine, {}).get("present", False)
            )
            coverage = present_count / len(matrix) if matrix else 0

            # Calculate average confidence
            confidences = [
                entry["engines"][engine]["confidence"]
                for entry in matrix
                if entry["engines"].get(engine, {}).get("present", False)
                and "confidence" in entry["engines"][engine]
            ]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0

            scores[engine] = {
                "coverage_score": coverage * 100,
                "avg_confidence": avg_confidence * 100,
                "overall_score": (coverage + avg_confidence) / 2 * 100,
            }

        # Save scores
        scores_file = self.data_dir / "scoring.json"
        with open(scores_file, "w") as f:
            json.dump(scores, f, indent=2)

        return scores
