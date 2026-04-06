"""Analysis harness for running LLM analysis on rules."""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.models import (
    RuleAnalysis,
    RuleCategory,
    Task,
    TaskStatus,
)


class AnalysisHarness:
    """Harness for running LLM analysis on optimizer rules."""

    def __init__(
        self,
        task_queue_path: Path,
        output_dir: Path,
        api_key: Optional[str] = None,
        model: str = "claude-3-sonnet-20240229",
        base_url: Optional[str] = None,
    ):
        """Initialize the analysis harness."""
        self.task_queue_path = task_queue_path
        self.output_dir = output_dir
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.tasks: List[Task] = []
        self.prompts_dir = Path(__file__).parent / "prompts"

        # Load prompts
        self.prompts = self._load_prompts()

        # Initialize LLM client
        self.client = None
        self.openai_client = None

        # Always load config for missing values
        from src.config import get_settings
        settings = get_settings()
        api_key = api_key or settings.llm_api_key
        base_url = base_url or settings.llm_base_url
        model = model or settings.llm_model
        self.model = model

        if api_key:
            # Check if using OpenAI-compatible API (qwen, glm, etc.)
            if model.startswith(('qwen', 'glm', 'deepseek')) or 'dashscope' in (base_url or ''):
                try:
                    from openai import OpenAI
                    self.openai_client = OpenAI(
                        api_key=api_key,
                        base_url=base_url or "https://coding.dashscope.aliyuncs.com/v1"
                    )
                    print(f"Using OpenAI-compatible API with model: {model}")
                except ImportError:
                    print("Warning: openai package not installed")
            else:
                # Anthropic Claude
                try:
                    from anthropic import Anthropic
                    if base_url:
                        self.client = Anthropic(api_key=api_key, base_url=base_url)
                    else:
                        self.client = Anthropic(api_key=api_key)
                except ImportError:
                    print("Warning: anthropic package not installed")

    def _load_prompts(self) -> Dict[str, str]:
        """Load prompt templates."""
        prompts = {}
        for prompt_file in self.prompts_dir.glob("*.txt"):
            category = prompt_file.stem.replace("_prompt", "")
            with open(prompt_file, 'r') as f:
                prompts[category] = f.read()
        return prompts

    def load_tasks(self, engine_id: Optional[str] = None) -> List[Task]:
        """Load tasks from task queue."""
        with open(self.task_queue_path, 'r') as f:
            tasks_data = json.load(f)

        self.tasks = []
        for task_dict in tasks_data:
            if engine_id and task_dict['engine_id'] != engine_id:
                continue

            task = Task(
                task_id=task_dict['task_id'],
                engine_id=task_dict['engine_id'],
                category=RuleCategory(task_dict['category']),
                rule_name=task_dict['rule_name'],
                source_file=task_dict['source_file'],
                source_snippet=task_dict['source_snippet'],
                optimizer_framework=task_dict['optimizer_framework'],
                language=task_dict['language'],
                status=TaskStatus(task_dict['status']),
                priority=task_dict['priority'],
                estimated_tokens=task_dict['estimated_tokens'],
                dsl_file=task_dict.get('dsl_file'),
                dsl_snippet=task_dict.get('dsl_snippet'),
                created_at=task_dict['created_at'],
                analyzed_at=task_dict.get('analyzed_at'),
                retries=task_dict.get('retries', 0),
            )
            self.tasks.append(task)

        return self.tasks

    def run_analysis(
        self,
        engine_id: Optional[str] = None,
        max_tasks: Optional[int] = None,
        resume: bool = True,
    ) -> Dict[str, int]:
        """Run analysis on pending tasks."""
        if not self.tasks:
            self.load_tasks(engine_id)

        # Filter to pending tasks
        pending_tasks = [t for t in self.tasks if t.status == TaskStatus.PENDING]
        if resume:
            # Also include failed tasks up to retry limit
            pending_tasks += [t for t in self.tasks
                           if t.status == TaskStatus.FAILED and t.retries < 2]

        if max_tasks:
            pending_tasks = pending_tasks[:max_tasks]

        print(f"Found {len(pending_tasks)} tasks to analyze")

        stats = {"completed": 0, "failed": 0, "needs_review": 0}

        for i, task in enumerate(pending_tasks):
            print(f"[{i+1}/{len(pending_tasks)}] Analyzing {task.task_id}...")

            try:
                result = self._analyze_task(task)

                if result:
                    task.result = result
                    task.status = TaskStatus.DONE
                    task.analyzed_at = datetime.now().isoformat()
                    task.confidence = result.get('confidence', 0.5)

                    if result.get('confidence', 0.5) < 0.7:
                        task.status = TaskStatus.NEEDS_REVIEW
                        stats["needs_review"] += 1
                    else:
                        stats["completed"] += 1

                    # Save result immediately
                    self._save_result(task, result)
                else:
                    task.status = TaskStatus.FAILED
                    task.retries += 1
                    stats["failed"] += 1

            except Exception as e:
                print(f"Error analyzing {task.task_id}: {e}")
                task.status = TaskStatus.FAILED
                task.error_message = str(e)
                task.retries += 1
                stats["failed"] += 1

            # Update task queue periodically
            if (i + 1) % 20 == 0:
                self._update_task_queue()

        # Final save
        self._update_task_queue()

        return stats

    def _analyze_task(self, task: Task) -> Optional[Dict[str, Any]]:
        """Analyze a single task using LLM."""
        # Check if any client is available
        if not self.client and not self.openai_client:
            # Return mock result for testing
            return self._mock_result(task)

        # Build prompt
        prompt = self._build_prompt(task)

        # Use OpenAI-compatible client (qwen, glm, etc.)
        if self.openai_client:
            return self._analyze_with_openai(prompt)

        # Use Anthropic client (Claude)
        return self._analyze_with_anthropic(prompt)

    def _analyze_with_openai(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Analyze using OpenAI-compatible API."""
        for attempt in range(3):
            try:
                response = self.openai_client.chat.completions.create(
                    model=self.model,
                    max_tokens=2000,
                    temperature=0,
                    messages=[{
                        "role": "user",
                        "content": prompt,
                    }],
                )

                content = response.choices[0].message.content if response.choices else ""

                # Debug: print first 500 chars
                if attempt == 0:
                    print(f"\n  LLM response preview: {content[:200]}...")

                # Parse JSON response
                result = self._parse_json_response(content)
                if result:
                    return result
                else:
                    print(f"  Failed to parse JSON, retrying...")

            except Exception as e:
                print(f"API error (attempt {attempt + 1}): {e}")
                time.sleep(2 ** attempt)

        return None

    def _analyze_with_anthropic(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Analyze using Anthropic API."""
        for attempt in range(3):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=2000,
                    temperature=0,
                    messages=[{
                        "role": "user",
                        "content": prompt,
                    }],
                )

                content = response.content[0].text if response.content else ""

                # Parse JSON response
                result = self._parse_json_response(content)
                if result:
                    return result

            except Exception as e:
                print(f"API error (attempt {attempt + 1}): {e}")
                time.sleep(2 ** attempt)

        return None

    def _build_prompt(self, task: Task) -> str:
        """Build analysis prompt for a task."""
        # Select prompt template based on category
        category_map = {
            RuleCategory.RBO: "rbo",
            RuleCategory.CBO: "cbo",
            RuleCategory.SCALAR: "scalar",
            RuleCategory.PROPERTY: "property",
            RuleCategory.POST_OPT: "rbo",  # Use RBO template as base
            RuleCategory.STATISTICS: "cbo",  # Use CBO template as base
        }

        template_key = category_map.get(task.category, "rbo")
        template = self.prompts.get(template_key, self.prompts["rbo"])

        # Build framework-specific questions
        framework_questions = self._get_framework_questions(task)

        # Build DSL section if applicable
        dsl_section = ""
        if task.dsl_snippet:
            dsl_section = f"DSL Snippet ({task.dsl_file}):\n```\n{task.dsl_snippet}\n```\n\n"

        # Fill template
        prompt = template.format(
            engine=task.engine_id,
            optimizer_framework=task.optimizer_framework,
            rule_name=task.rule_name,
            language=task.language,
            source_snippet=task.source_snippet[:8000],  # Limit snippet size
            dsl_section=dsl_section,
            framework_specific_questions=framework_questions,
        )

        return prompt

    def _get_framework_questions(self, task: Task) -> str:
        """Get framework-specific questions."""
        framework = task.optimizer_framework

        if framework == "cascades":
            return """Cascades-specific questions:
- Does this rule trigger Enforcer insertion?
- How does it control Memo explore depth?
- Which group expressions does it match?"""

        elif framework == "optgen":
            return """Optgen DSL-specific questions:
- What is the algebraic semantics of the match pattern?
- What is the algebraic semantics of the replace pattern?
- What Memo expression does this transform?"""

        elif framework == "custom":
            return """Custom optimizer questions:
- In which Pass does this optimization execute?
- Is this transformation idempotent?
- What are the dependencies between Passes?"""

        elif framework == "path_based":
            return """Path-based questions:
- What type of Path does this function generate?
- Which cost functions does it interact with?
- How does it compare path costs?"""

        elif framework == "volcano":
            return """Volcano-specific questions:
- Does this rule belong to HepPlanner or VolcanoPlanner?
- What is the rule's place in the optimization phase?
- How does it interact with the trait system?"""

        return ""

    def _parse_json_response(self, content: str) -> Optional[Dict[str, Any]]:
        """Parse JSON from LLM response."""
        # Try to find JSON block
        json_match = None

        # Look for ```json blocks
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            if end > start:
                json_match = content[start:end].strip()
        elif "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            if end > start:
                json_match = content[start:end].strip()

        if json_match:
            try:
                return json.loads(json_match)
            except json.JSONDecodeError:
                pass

        # Try parsing entire content
        try:
            return json.loads(content.strip())
        except json.JSONDecodeError:
            pass

        return None

    def _mock_result(self, task: Task) -> Dict[str, Any]:
        """Generate mock result for testing without API."""
        return {
            "summary": f"Mock analysis for {task.rule_name}",
            "ra_input_pattern": "Mock input pattern",
            "ra_output_pattern": "Mock output pattern",
            "ra_condition": "Mock condition",
            "correctness_conditions": ["Mock condition 1"],
            "performance_impact": "Mock performance impact",
            "edge_cases": ["Mock edge case"],
            "canonical_name": f"mock.category.{task.rule_name.lower()}",
            "logical_category": "other",
            "framework_notes": "Mock framework notes",
            "confidence": 0.5,
        }

    def _save_result(self, task: Task, result: Dict[str, Any]):
        """Save analysis result to JSONL file."""
        # Build RuleAnalysis object
        analysis = RuleAnalysis(
            task_id=task.task_id,
            engine_id=task.engine_id,
            category=task.category.value,
            rule_name=task.rule_name,
            source_file=task.source_file,
            dsl_snippet=task.dsl_snippet,
            optimizer_framework=task.optimizer_framework,
            summary=result.get('summary', ''),
            ra_input_pattern=result.get('ra_input_pattern', ''),
            ra_output_pattern=result.get('ra_output_pattern', ''),
            ra_condition=result.get('ra_condition', ''),
            correctness_conditions=result.get('correctness_conditions', []),
            performance_impact=result.get('performance_impact', ''),
            edge_cases=result.get('edge_cases', []),
            framework_notes=result.get('framework_notes'),
            enforcer_triggered=result.get('enforcer_triggered'),
            stats_dependencies=result.get('stats_dependencies', []),
            logical_category=result.get('logical_category', 'other'),
            canonical_name=result.get('canonical_name', ''),
            related_rules=result.get('related_rules', []),
            confidence=result.get('confidence', 0.0),
            needs_review=task.status == TaskStatus.NEEDS_REVIEW,
            model_version=self.model,
        )

        # Create engine output directory
        engine_dir = self.output_dir / task.engine_id
        engine_dir.mkdir(parents=True, exist_ok=True)

        # Append to category-specific JSONL file
        output_file = engine_dir / f"{task.category.value}_rules.jsonl"
        with open(output_file, 'a') as f:
            f.write(json.dumps(analysis.to_dict(), ensure_ascii=False) + "\n")

    def _update_task_queue(self):
        """Update task queue file with current statuses."""
        tasks_data = []
        for task in self.tasks:
            task_dict = {
                'task_id': task.task_id,
                'engine_id': task.engine_id,
                'category': task.category.value,
                'rule_name': task.rule_name,
                'source_file': task.source_file,
                'source_snippet': task.source_snippet,
                'dsl_file': task.dsl_file,
                'dsl_snippet': task.dsl_snippet,
                'optimizer_framework': task.optimizer_framework.value if hasattr(task.optimizer_framework, 'value') else task.optimizer_framework,
                'language': task.language.value if hasattr(task.language, 'value') else task.language,
                'status': task.status.value,
                'priority': task.priority,
                'estimated_tokens': task.estimated_tokens,
                'created_at': task.created_at,
                'analyzed_at': task.analyzed_at,
                'retries': task.retries,
                'confidence': task.confidence,
            }
            if task.error_message:
                task_dict['error_message'] = task.error_message
            tasks_data.append(task_dict)

        with open(self.task_queue_path, 'w') as f:
            json.dump(tasks_data, f, indent=2)
