# LLM Benchmark 调研报告

> 调研日期：2026-08-03
> 目标：筛选适合本地执行的数学推理与编程能力评测基准

## 调研范围

共调研 7 个主流 benchmark，按能力维度分为数学推理和编程能力两大类。

---

## 一、数学推理 Benchmark

### 1. MATH (hendrycks/competition_math)

| 属性 | 详情 |
|------|------|
| **数据集规模** | 训练集 7,500 题，测试集 5,000 题 |
| **题目格式** | LaTeX 数学题，涵盖代数、几何、概率、数论等 7 个子领域 |
| **难度分级** | Level 1-5（从 AMC 到 AIME 级别） |
| **评分方式** | Exact Match on final answer（\boxed{...} 提取） |
| **许可证** | MIT |
| **HuggingFace** | ✅ `hendrycks/competition_math` |
| **本地可执行** | ✅ 仅需 JSON/Arrow 数据，无需外部依赖 |
| **推荐优先级** | ⭐⭐⭐⭐⭐ 首选 |

### 2. GSM8K (gsm8k)

| 属性 | 详情 |
|------|------|
| **数据集规模** | 训练集 7,473 题，测试集 1,319 题 |
| **题目格式** | 自然语言小学数学应用题，逐步推理 |
| **难度分级** | 无（小学水平） |
| **评分方式** | Exact Match on final numeric answer（#### 提取） |
| **许可证** | MIT |
| **HuggingFace** | ✅ `gsm8k`（main 配置） |
| **本地可执行** | ✅ |
| **推荐优先级** | ⭐⭐⭐⭐⭐ 首选 |

### 3. AIME (AI-MO/aimo-validation-aime)

| 属性 | 详情 |
|------|------|
| **数据集规模** | ~100-150 题（历年 AIME 竞赛真题） |
| **题目格式** | 整数答案的数学竞赛题（AMC → AIME 级别） |
| **难度分级** | 高难度（Level 4-5 对应 MATH 最高难度） |
| **评分方式** | Exact Match（整数答案 000-999） |
| **许可证** | 取决于来源（AI-MO 为 CC-BY） |
| **HuggingFace** | ✅ `AI-MO/aimo-validation-aime` |
| **本地可执行** | ✅ |
| **推荐优先级** | ⭐⭐⭐ 第二批纳入 |

---

## 二、编程能力 Benchmark

### 4. HumanEval (openai/openai_humaneval)

| 属性 | 详情 |
|------|------|
| **数据集规模** | 164 题 |
| **题目格式** | Python 函数签名 + docstring → 补全函数体 |
| **难度分级** | 无（混合难度） |
| **评分方式** | pass@k（k=1,10,100），通过 assert 测试用例验证 |
| **许可证** | MIT |
| **HuggingFace** | ✅ `openai/openai_humaneval` |
| **本地可执行** | ✅ 需代码执行沙箱 |
| **推荐优先级** | ⭐⭐⭐⭐⭐ 首选 |

### 5. MBPP (google-research-datasets/mbpp)

| 属性 | 详情 |
|------|------|
| **数据集规模** | 训练集 374 题，测试集 500 题 |
| **题目格式** | 自然语言编程题描述 + 3 个测试用例 |
| **难度分级** | 无 |
| **评分方式** | pass@k（k=1,5,10），通过测试用例验证 |
| **许可证** | CC-BY 4.0 |
| **HuggingFace** | ✅ `google-research-datasets/mbpp`（full 配置） |
| **本地可执行** | ✅ 需代码执行沙箱 |
| **推荐优先级** | ⭐⭐⭐⭐⭐ 首选 |

### 6. LiveCodeBench (livecodebench)

| 属性 | 详情 |
|------|------|
| **数据集规模** | 动态更新，~400+ 题（来自 LeetCode/AtCoder/Codeforces） |
| **题目格式** | 竞赛编程题，含输入输出样例 |
| **难度分级** | Easy/Medium/Hard |
| **评分方式** | pass@1（通过完整测试用例） |
| **许可证** | MIT |
| **HuggingFace** | ✅ `livecodebench/code_generation_lite` |
| **本地可执行** | ✅ 需代码执行 + I/O 测试 |
| **推荐优先级** | ⭐⭐⭐⭐ 第二批纳入 |

### 7. BigCodeBench (bigcode/bigcodebench)

| 属性 | 详情 |
|------|------|
| **数据集规模** | 1,140 题 |
| **题目格式** | 多样化 Python 编程任务（含库调用、文件操作等） |
| **难度分级** | 无 |
| **评分方式** | pass@1（功能正确性） |
| **许可证** | Apache 2.0 |
| **HuggingFace** | ✅ `bigcode/bigcodebench` |
| **本地可执行** | ✅ 需代码执行沙箱 |
| **推荐优先级** | ⭐⭐⭐ 第二批纳入 |

---

## 三、纳入计划

### 首批（Phase 1）

| 数据集 | 能力 | 题数 | 理由 |
|--------|------|------|------|
| MATH | 数学推理 | 5,000 | 业界标准，分难度，MIT 许可 |
| GSM8K | 数学推理 | 1,319 | 经典基准，轻量快速 |
| HumanEval | 编程能力 | 164 | 编程评测标准，MIT 许可 |
| MBPP | 编程能力 | 500 | 补充 HumanEval，题目更多样 |

### 第二批（后续）

| 数据集 | 理由 |
|--------|------|
| AIME | 高难度数学竞赛，补充 MATH 天花板 |
| LiveCodeBench | 竞赛编程 + 动态更新，时效性好 |
| BigCodeBench | 覆盖更多编程场景（库调用、文件操作） |

---

## 四、总结

| 指标 | 数值 |
|------|------|
| 调研总数 | 7 个 benchmark |
| 首批纳入 | 4 个（2 数学 + 2 编程） |
| 首批总题数 | 约 6,983 题 |
| 许可证合规 | 全部 MIT / CC-BY / Apache 2.0 |
| 本地可执行 | 全部 ✅ |