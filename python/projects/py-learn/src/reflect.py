"""
Reflect 模块 - 评估引擎

基于 LLM 对用户答案进行评估和评分，
并将结果写回数据库用于自适应调整。
"""

import json
import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from config import LLMConfig
from db import Database


@dataclass
class EvaluationResult:
    """评估结果"""
    concept_score: float      # 概念准确性 (0-3)
    depth_score: float        # 系统深度 (0-4)
    boundary_score: float     # 边界思考 (0-3)
    total_score: float        # 总分 (0-10)
    strengths: List[str]      # 答得好的点
    gaps: List[str]           # 遗漏的关键点
    summary: str              # 标准答案摘要
    followup: str             # 推荐追问方向


class LLMClient:
    """LLM 客户端（与 generate.py 共享）"""

    def __init__(self, config: LLMConfig):
        self.config = config
        self._client = None

    def _get_client(self):
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

    def generate(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """调用 LLM"""
        client = self._get_client()

        max_tokens = max_tokens or self.config.reflect_max_tokens

        response = client.chat.completions.create(
            model=self.config.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.3,  # 评分需要更稳定
        )

        return response.choices[0].message.content


class ReflectEngine:
    """
    评估引擎

    对用户答案进行多维度评分。
    """

    # 评分提示词模板
    EVALUATION_TEMPLATE = """【题目】
{question_main}

【考察意图】
{question_intent}

【用户回答】
{user_answer}

请按以下维度评分，输出 JSON 格式：

评分标准：
- concept_score (0-3)：概念准确性
  - 0-1：概念理解有严重错误
  - 1-2：概念基本正确但不够深入
  - 2-3：概念准确且有深入理解

- depth_score (0-4)：系统深度
  - 0-1：仅表面描述
  - 1-2：涉及实现原理但不完整
  - 2-3：深入实现原理
  - 3-4：触及系统级影响和优化

- boundary_score (0-3)：边界思考
  - 0-1：未提及 tradeoff 或边界情况
  - 1-2：简单提及但未展开
  - 2-3：深入分析 tradeoff 和失效场景

total = concept_score + depth_score + boundary_score

输出格式：
```json
{{
  "concept_score": float,
  "depth_score": float,
  "boundary_score": float,
  "total": float,
  "strengths": ["..."],
  "gaps": ["..."],
  "summary": "...",
  "followup": "..."
}}
```
"""

    def __init__(self, llm_config: LLMConfig, db: Database):
        """
        初始化评估引擎

        Args:
            llm_config: LLM 配置
            db: 数据库实例
        """
        self.llm = LLMClient(llm_config)
        self.db = db
        self.retry_max = llm_config.retry_max

    def evaluate(
        self,
        question_main: str,
        question_intent: List[str],
        user_answer: str
    ) -> EvaluationResult:
        """
        评估用户答案

        Args:
            question_main: 题目内容
            question_intent: 考察意图
            user_answer: 用户答案

        Returns:
            评估结果
        """
        prompt = self.EVALUATION_TEMPLATE.format(
            question_main=question_main,
            question_intent="\n".join(f"- {i}" for i in question_intent),
            user_answer=user_answer
        )

        for attempt in range(self.retry_max):
            try:
                content = self.llm.generate(prompt)
                result = self._parse_response(content)

                # 验证结果
                if self._validate_result(result):
                    return result

            except Exception as e:
                if attempt == self.retry_max - 1:
                    # 返回一个基础评估
                    return self._fallback_evaluation()

        return self._fallback_evaluation()

    def _parse_response(self, content: str) -> EvaluationResult:
        """解析 LLM 响应"""
        # 提取 JSON 部分
        json_match = re.search(r'```json\n(.*?)```', content, re.DOTALL)
        if json_match:
            json_content = json_match.group(1)
        else:
            # 尝试直接解析
            json_content = content

        # 清理可能的 markdown
        json_content = re.sub(r'^```|```$', '', json_content.strip())

        data = json.loads(json_content)

        return EvaluationResult(
            concept_score=float(data.get('concept_score', 0)),
            depth_score=float(data.get('depth_score', 0)),
            boundary_score=float(data.get('boundary_score', 0)),
            total_score=float(data.get('total', 0)),
            strengths=data.get('strengths', []),
            gaps=data.get('gaps', []),
            summary=data.get('summary', ''),
            followup=data.get('followup', '')
        )

    def _validate_result(self, result: EvaluationResult) -> bool:
        """验证评估结果"""
        # 检查分数范围
        if not (0 <= result.concept_score <= 3):
            return False
        if not (0 <= result.depth_score <= 4):
            return False
        if not (0 <= result.boundary_score <= 3):
            return False

        # 总分计算是否正确
        expected_total = result.concept_score + result.depth_score + result.boundary_score
        if abs(result.total_score - expected_total) > 0.5:
            result.total_score = expected_total

        return True

    def _fallback_evaluation(self) -> EvaluationResult:
        """兜底评估"""
        return EvaluationResult(
            concept_score=1.0,
            depth_score=1.0,
            boundary_score=1.0,
            total_score=3.0,
            strengths=["已尝试作答"],
            gaps=["评估过程出错，请稍后查看详细反馈"],
            summary="系统暂时无法提供完整评估",
            followup="建议重新阅读相关资料"
        )

    def save_evaluation(
        self,
        question_id: int,
        user_answer: str,
        result: EvaluationResult
    ) -> None:
        """
        保存评估结果

        Args:
            question_id: 题目 ID
            user_answer: 用户答案
            result: 评估结果
        """
        # 保存答案
        scores = {
            'concept_score': result.concept_score,
            'depth_score': result.depth_score,
            'boundary_score': result.boundary_score,
            'total_score': result.total_score,
        }

        self.db.save_answer(
            question_id=question_id,
            answer_text=user_answer,
            scores=scores,
            gaps=result.gaps,
            summary=result.summary
        )

        # 获取题目信息以更新 topic 统计
        question = self.db.get_question_by_id(question_id)
        if question:
            # 判断是否需要调整难度
            new_level = question.level
            is_weak = False

            # 获取历史统计
            stats = self.db.get_topic_stats(question.topic_id)
            if stats:
                # 简单的难度调整逻辑
                if result.total_score >= 9.0:
                    new_level = min(4, question.level + 1)
                elif result.total_score <= 4.0:
                    new_level = max(2, question.level - 1)

                # 判断薄弱点
                avg_score = (stats.avg_score * stats.attempt_count + result.total_score) / (stats.attempt_count + 1)
                is_weak = avg_score < 6.0

            # 更新 topic 统计
            self.db.update_topic_stats(
                topic_id=question.topic_id,
                new_score=result.total_score,
                new_level=new_level,
                is_weak=is_weak
            )


def evaluate_answer(
    question_main: str,
    question_intent: List[str],
    user_answer: str,
    llm_config: LLMConfig,
    db: Database,
    question_id: int
) -> EvaluationResult:
    """
    便捷的评估函数

    Args:
        question_main: 题目内容
        question_intent: 考察意图
        user_answer: 用户答案
        llm_config: LLM 配置
        db: 数据库实例
        question_id: 题目 ID

    Returns:
        评估结果
    """
    engine = ReflectEngine(llm_config, db)
    result = engine.evaluate(question_main, question_intent, user_answer)
    engine.save_evaluation(question_id, user_answer, result)
    return result
