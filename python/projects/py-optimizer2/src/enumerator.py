"""Rule enumerator for extracting rules from engine source code."""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from src.models import (
    EngineConfig,
    Language,
    OptimizerFramework,
    RuleCategory,
    Task,
    TaskStatus,
)
from src.scanners import (
    CppClassScanner,
    CppFunctionScanner,
    JavaScanner,
    OptgenScanner,
    CScanner,
    ScanResult,
)


class RuleEnumerator:
    """Enumerates rules from engine source code."""

    def __init__(self, engine_config_path: Path, source_root: Path):
        """Initialize with engine configuration."""
        self.config_path = engine_config_path
        self.source_root = source_root
        self.config = self._load_config()

    def _load_config(self) -> EngineConfig:
        """Load engine configuration from YAML."""
        with open(self.config_path, 'r') as f:
            data = yaml.safe_load(f)

        return EngineConfig(
            engine_id=data['engine_id'],
            display_name=data['display_name'],
            version=data['version'],
            language=Language(data['language']),
            optimizer_framework=OptimizerFramework(data['optimizer_framework']),
            optimizer_root=data['optimizer_root'],
            patterns=data.get('patterns', {}),
            lifecycle_entry=data.get('lifecycle_entry', {}),
            rule_registry=data.get('rule_registry', {}),
            scanner_hints=data.get('scanner_hints', {}),
        )

    def enumerate_rules(self) -> List[ScanResult]:
        """Enumerate all rules from the engine source."""
        scanner = self._create_scanner()
        return scanner.scan()

    def _create_scanner(self):
        """Create appropriate scanner for the engine language."""
        lang = self.config.language
        framework = self.config.optimizer_framework
        config_dict = {
            'engine_id': self.config.engine_id,
            'optimizer_root': self.config.optimizer_root,
            'patterns': self.config.patterns,
            'scanner_hints': self.config.scanner_hints,
        }

        if lang == Language.CPP:
            if framework == OptimizerFramework.CUSTOM:
                # ClickHouse uses function-based approach
                return CppFunctionScanner(config_dict, self.source_root)
            else:
                # StarRocks, GPDB, Columbia use class-based approach
                return CppClassScanner(config_dict, self.source_root)
        elif lang == Language.JAVA:
            return JavaScanner(config_dict, self.source_root)
        elif lang == Language.GO:
            return OptgenScanner(config_dict, self.source_root)
        elif lang == Language.C:
            return CScanner(config_dict, self.source_root)
        else:
            raise ValueError(f"Unsupported language: {lang}")

    def generate_tasks(self, scan_results: List[ScanResult]) -> List[Task]:
        """Generate analysis tasks from scan results."""
        tasks = []

        for i, result in enumerate(scan_results):
            category_map = {
                'rbo_rules': RuleCategory.RBO,
                'cbo_rules': RuleCategory.CBO,
                'scalar_rules': RuleCategory.SCALAR,
                'post_opt': RuleCategory.POST_OPT,
                'properties': RuleCategory.PROPERTY,
                'statistics': RuleCategory.STATISTICS,
            }

            category = category_map.get(result.category, RuleCategory.RBO)

            # Priority: RBO/CBO (P1), Properties/Statistics (P2), Scalar/Post-Opt (P3)
            priority_map = {
                RuleCategory.RBO: 1,
                RuleCategory.CBO: 1,
                RuleCategory.PROPERTY: 2,
                RuleCategory.STATISTICS: 2,
                RuleCategory.SCALAR: 3,
                RuleCategory.POST_OPT: 3,
            }
            priority = priority_map.get(category, 3)

            # Estimate tokens
            estimated_tokens = len(result.source_snippet) // 4

            task = Task(
                task_id=f"{self.config.engine_id}::{result.category}::{result.rule_name}",
                engine_id=self.config.engine_id,
                category=category,
                rule_name=result.rule_name,
                source_file=str(result.source_file),
                source_snippet=result.source_snippet,
                optimizer_framework=self.config.optimizer_framework,
                language=self.config.language,
                status=TaskStatus.PENDING,
                priority=priority,
                estimated_tokens=estimated_tokens,
                dsl_file=str(result.dsl_file) if result.dsl_file else None,
                dsl_snippet=result.dsl_snippet,
            )
            tasks.append(task)

        return tasks

    def save_tasks(self, tasks: List[Task], output_path: Path):
        """Save tasks to task queue JSON."""
        tasks_data = []
        for task in tasks:
            task_dict = {
                'task_id': task.task_id,
                'engine_id': task.engine_id,
                'category': task.category.value,
                'rule_name': task.rule_name,
                'source_file': task.source_file,
                'source_snippet': task.source_snippet,
                'dsl_file': task.dsl_file,
                'dsl_snippet': task.dsl_snippet,
                'optimizer_framework': task.optimizer_framework.value,
                'language': task.language.value,
                'status': task.status.value,
                'priority': task.priority,
                'estimated_tokens': task.estimated_tokens,
                'created_at': task.created_at,
                'analyzed_at': task.analyzed_at,
                'retries': task.retries,
            }
            tasks_data.append(task_dict)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(tasks_data, f, indent=2)

        return len(tasks_data)
