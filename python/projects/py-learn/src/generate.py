"""
Generate 模块 - 题目生成器

基于 LLM 生成结构化的学习题目。
支持自适应难度和题型，生成高质量的面试级别题目。
"""

import json
import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

import yaml

from config import LLMConfig
from plan import PlanResult, QuestionType


@dataclass
class GeneratedQuestion:
    """生成的题目"""
    main: str                      # 主问题
    intent: List[str]              # 考察意图
    followups: List[Dict[str, str]]  # 追问预案
    extension: str                 # 跨域延伸题
    references: List[str]          # 参考资料


class LLMClient:
    """
    LLM 客户端封装

    支持 OpenAI 兼容的 API 接口。
    """

    def __init__(self, config: LLMConfig):
        """
        初始化客户端

        Args:
            config: LLM 配置
        """
        self.config = config
        self._client = None

    def _get_client(self):
        """延迟初始化客户端"""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    base_url=self.config.base_url,
                    api_key=self.config.api_key,
                )
            except ImportError:
                raise ImportError("请先安装 openai: pip install openai")
        return self._client

    def generate(self, system_prompt: str, user_prompt: str,
                 max_tokens: Optional[int] = None) -> str:
        """
        调用 LLM 生成内容

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            max_tokens: 最大 token 数

        Returns:
            生成的文本
        """
        client = self._get_client()

        max_tokens = max_tokens or self.config.question_max_tokens

        response = client.chat.completions.create(
            model=self.config.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=max_tokens,
            temperature=0.7,
        )

        return response.choices[0].message.content


class QuestionGenerator:
    """
    题目生成器

    基于 Plan 结果和工具上下文生成结构化题目。
    """

    # 系统提示词（固定部分）
    SYSTEM_PROMPT = """你是一位资深架构师导师，专注大数据/OLAP/OS/高性能计算领域。
学员背景：10年工程师，C++/Java/Go/Python，目标成为架构师。

出题原则：
1. 不出知识点罗列题，只出需要推理和 tradeoff 的题
2. 每题必须包含：主问题 / 考察意图 / 追问预案 / 参考资料
3. 难度锚定：
   - L2: 基础概念理解
   - L3: 需要分析和比较（默认）
   - L4: 能在 VLDB 论文中找到对应讨论的深度

输出格式要求：
- 使用 YAML 格式
- 主问题 (main) 必须 >= 50 字
- 考察意图 (intent) 列表，用于评分标准
- 追问预案 (followups) 列表，每个包含 trigger 和 prompt
- 跨域延伸题 (extension) 可选
- 参考资料 (references) 必须准确具体
"""

    # 题型特定的提示词
    TYPE_PROMPTS = {
        QuestionType.CONCEPT: "侧重概念深度理解和原理分析",
        QuestionType.DEBUG: "提供有缺陷的代码或场景，要求找出问题",
        QuestionType.IMPLEMENTATION: "要求写出关键代码或伪代码",
        QuestionType.TRADEOFF: "重点讨论不同方案的优劣和适用场景",
        QuestionType.SYSTEM_DESIGN: "设计完整的系统架构",
        QuestionType.MANAGEMENT: "从技术管理角度分析决策",
        QuestionType.PAPER_REVIEW: "基于论文或技术文章进行评述",
        QuestionType.ANALYSIS: "分析系统行为或性能",
    }

    def __init__(self, llm_config: LLMConfig):
        """
        初始化生成器

        Args:
            llm_config: LLM 配置
        """
        self.llm = LLMClient(llm_config)
        self.retry_max = llm_config.retry_max

    def generate(self, plan: PlanResult,
                 knowledge_context: Dict[str, Any],
                 memory_context: Dict[str, Any]) -> GeneratedQuestion:
        """
        生成题目

        Args:
            plan: 规划结果
            knowledge_context: 知识图谱上下文
            memory_context: 历史记忆上下文

        Returns:
            生成的题目
        """
        user_prompt = self._build_prompt(plan, knowledge_context, memory_context)

        for attempt in range(self.retry_max):
            try:
                content = self.llm.generate(
                    self.SYSTEM_PROMPT,
                    user_prompt
                )

                question = self._parse_response(content)

                # 验证题目质量
                if self._validate_question(question):
                    return question

            except Exception as e:
                if attempt == self.retry_max - 1:
                    raise RuntimeError(f"题目生成失败，已重试 {self.retry_max} 次: {e}")

        # 如果都失败了，返回一个基础题目
        return self._fallback_question(plan)

    def _build_prompt(self, plan: PlanResult,
                      knowledge_context: Dict[str, Any],
                      memory_context: Dict[str, Any]) -> str:
        """构建用户提示词"""
        lines = [
            "## 今日出题要求",
            "",
            f"领域: {plan.domain.label} ({plan.domain.id})",
            f"主题: {plan.topic.name} ({plan.topic.id})",
            f"难度: L{plan.level}",
            f"题型: {plan.qtype.value}",
            "",
        ]

        # 题型说明
        type_hint = self.TYPE_PROMPTS.get(plan.qtype, "")
        if type_hint:
            lines.extend([f"题型要求: {type_hint}", ""])

        # 知识上下文
        if knowledge_context:
            lines.extend([
                "## 知识上下文",
                "",
                "考察维度:",
            ])
            for point in knowledge_context.get('key_points', []):
                lines.append(f"- {point}")

            if knowledge_context.get('subtopics'):
                lines.extend(["", "子主题:"])
                for sub in knowledge_context.get('subtopics', []):
                    lines.append(f"- {sub}")

            if knowledge_context.get('references'):
                lines.extend(["", "参考资料:"])
                for ref in knowledge_context.get('references', []):
                    lines.append(f"- {ref}")
            lines.append("")

        # 历史上下文
        if memory_context:
            lines.extend([
                "## 历史表现",
                "",
            ])
            stats = memory_context.get('stats', {})
            if stats.get('attempt_count', 0) > 0:
                lines.append(f"历史答题次数: {stats['attempt_count']}")
                lines.append(f"平均得分: {stats['avg_score']:.1f}")
                if stats.get('is_weak'):
                    lines.append("状态: 薄弱点，请适当降低难度")
            lines.append("")

        lines.extend([
            "## 输出格式",
            "",
            "```yaml",
            "question:",
            "  main: \"...\"  # 主问题，必须 >= 50 字",
            "  intent:",
            "    - \"...\"  # 考察意图",
            "  followups:",
            "    - trigger: \"...\"",
            "      prompt: \"...\"",
            "  extension: \"...\"  # 跨域延伸题",
            "  references:",
            "    - \"...\"  # 参考资料",
            "```",
        ])

        return "\n".join(lines)

    def _parse_response(self, content: str) -> GeneratedQuestion:
        """解析 LLM 响应"""
        # 提取 YAML 部分
        yaml_match = re.search(r'```yaml\n(.*?)```', content, re.DOTALL)
        if yaml_match:
            yaml_content = yaml_match.group(1)
        else:
            # 尝试直接解析
            yaml_content = content

        # 解析 YAML
        data = yaml.safe_load(yaml_content)
        question_data = data.get('question', data)

        return GeneratedQuestion(
            main=question_data.get('main', ''),
            intent=question_data.get('intent', []),
            followups=question_data.get('followups', []),
            extension=question_data.get('extension', ''),
            references=question_data.get('references', [])
        )

    def _validate_question(self, question: GeneratedQuestion) -> bool:
        """验证题目质量"""
        # 主问题必须 >= 50 字
        if len(question.main) < 50:
            return False

        # 必须有考察意图
        if not question.intent:
            return False

        # 主问题不能为空
        if not question.main.strip():
            return False

        return True

    def _fallback_question(self, plan: PlanResult) -> GeneratedQuestion:
        """生成兜底题目"""
        return GeneratedQuestion(
            main=f"请详细阐述 {plan.topic.name} 的核心概念、实现原理和典型应用场景，"
                 f"并分析其中的关键 tradeoff。",
            intent=[
                f"考察 {plan.topic.name} 的概念理解",
                "考察实现原理的掌握",
                "考察 tradeoff 分析能力",
            ],
            followups=[
                {
                    "trigger": "若答出核心概念",
                    "prompt": "能否深入讲解一下实现细节？"
                },
                {
                    "trigger": "若遗漏边界情况",
                    "prompt": "这种情况下会有什么问题？"
                },
            ],
            extension=f"这与 {plan.domain.label} 中的其他技术有什么联系？",
            references=["请查阅相关文档"]
        )


def generate_question(
    plan: PlanResult,
    llm_config: LLMConfig,
    knowledge_context: Dict[str, Any],
    memory_context: Dict[str, Any]
) -> GeneratedQuestion:
    """
    便捷的题目生成函数

    Args:
        plan: 规划结果
        llm_config: LLM 配置
        knowledge_context: 知识图谱上下文
        memory_context: 历史记忆上下文

    Returns:
        生成的题目
    """
    generator = QuestionGenerator(llm_config)
    return generator.generate(plan, knowledge_context, memory_context)
