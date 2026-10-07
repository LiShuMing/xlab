---
template: daily-report
schema_version: 1
report_day: "{{report_day}}"
timezone: "{{timezone}}"
cutoff_at: "{{cutoff_at}}"
revision: "{{revision}}"
artifact_id: "{{artifact_id}}"
coverage_state: "{{coverage_state}}"
sensitivity: private
---

# 盘铭 · {{report_day}} 每日 Report

> 模板占位符需由真实数据替换。没有内容时明确写无更新/证据不足，不填充虚构条目。

## 今日概览

输入截止：{{cutoff_at}} · 时区：{{timezone}} · 本版：{{revision}}。

| 收到 | 去重后 | 已归纳 | 待输入 | 失败 | 预算延期 | 策略受限 | 截止后新到 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| {{received}} | {{unique}} | {{ready}} | {{needs_input}} | {{failed}} | {{budget_deferred}} | {{policy_blocked}} | {{late}} |

预期来源检查 {{sources_checked}} / {{sources_expected}}。状态与范围：{{coverage_note}}。本份 Report 的“完整”只针对冻结清单；晚到素材另行补录。

## 今日值得读

### {{item_title}}

为什么值得看：{{personal_relevance}}。

来源实际说了什么：{{supported_claim}}。

我的理解/仍需判断：{{user_view_or_question}}。

证据：{{source_revision_and_anchor_link}}。证据类型：{{evidence_kind}}；校验：{{validation_state}}。

## 按主题归纳

### {{topic_title}}

- 新输入：{{new_input}}。
- 与已有认识的差异：{{delta_or_unknown}}。
- 不同观点与局限：{{conflict_and_limitations}}。
- 可以做的实验/下一步：{{next_step}}。
- 相关旧知识：{{library_revision_link}}。

## 关注更新

| 来源 | 新项/更新 | 发生时间 | 收到时间 | 正文能力/状态 |
| --- | --- | --- | --- | --- |
| {{source}} | {{update}} | {{published_or_unknown}} | {{received_at}} | {{fetch_state}} |

## 个人研究输入

AI 对话中的推断：{{model_inference}}。个人观察：{{user_observation}}。实际实验结果：{{experiment_or_not_run}}。

“模型提出”与“已经实验验证”必须分开；未执行实验不能填结果。

## 博客素材包

选题数量允许为 0。

### {{brief_title}}

中心问题：{{central_question}}。面向读者：{{audience}}。建议放入系列：{{series}}。

拟形成的个人观点：{{thesis_or_needed_view}}。

证据清单：{{source_set}}。初步结构：{{outline}}。缺口：{{missing_evidence}}。

准备度：{{ready_to_outline_or_needs_evidence_or_needs_personal_view}}。下一步：采纳 / 合并已有选题 / 延后 / 拒绝。

## 图书馆修订与复习

受影响条目：{{entry}}。变更依据：{{source_revision}}。建议：{{change_proposal}}。本期仅提出建议，未自动改写条目。

到期复习：{{review_questions}}。

## 待验证、未处理与补录

| 项目 | 原采集日期 | 为什么未完成 | 下一步 |
| --- | --- | --- | --- |
| {{material}} | {{original_capture_day}} | {{reason}} | {{retry_or_provide_content}} |

## 来源与生成记录

输入 manifest：{{manifest_id}}。Provider/模型：{{model}}。Prompt/pipeline：{{prompt_version}} / {{pipeline_version}}。输入/输出 tokens：{{usage}}。费用/未知用量：{{cost_note}}。

Source revisions：{{source_revision_list}}。上一版：{{previous_revision}}。本版变化：{{revision_delta}}。
