#!/usr/bin/env python3
"""Generate comprehensive rule analysis with input/output and execution details."""
import re
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from optimizer_analysis.scanners.java_scanner import JavaScanner
from optimizer_analysis.engines.presets import STARROCKS_CONFIG, CALCITE_CONFIG, DORIS_CONFIG
from optimizer_analysis.llm_client import LLMClient, ChatMessage
from optimizer_analysis.config import LLMConfig


# Engine source paths
ENGINE_PATHS = {
    "StarRocks": "/home/lism/work/starrocks",
    "Calcite": "/home/lism/work/calcite",
    "Doris": "/home/lism/work/doris",
}


class DetailedRuleAnalyzer:
    """Analyze rules with complete input/output and execution details."""

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.scanner = JavaScanner()

    def analyze_rule_comprehensive(self, class_name: str, code: str, filename: str) -> Dict:
        """Comprehensive rule analysis with LLM."""

        prompt = f"""你是一位数据库优化器专家。请详细分析以下优化规则。

## 规则信息
- 类名: {class_name}
- 文件: {filename}

## 源代码
```java
{code[:4000]}
```

## 请用中文回答以下问题，以JSON格式输出：

1. **规则名称**: 给出该规则的中文名称（简洁准确）

2. **功能概述**: 用1-2句话描述这个规则做什么

3. **关系代数表达式**: 使用标准关系代数符号表示转换
   - σ (选择/过滤)
   - π (投影)
   - ⋈ (连接)
   - γ (聚合)
   - τ (排序)
   - × (笛卡尔积)
   格式: "输入表达式 → 输出表达式"

4. **输入模式**: 描述规则的输入算子模式
   - 算子类型（如: Filter, Scan, Join, Aggregate等）
   - 算子结构（如: Filter(Scan), Join(Scan, Scan)等）
   - 触发条件

5. **输出模式**: 描述规则应用后的输出算子模式
   - 生成的算子类型
   - 算子结构变化

6. **执行过程**: 详细描述规则的执行步骤
   - 第一步: 如何匹配输入
   - 第二步: 如何进行转换
   - 第三步: 如何生成输出

7. **优化效果**: 描述应用此规则带来的优化收益
   - 减少的数据量
   - 降低的计算复杂度
   - 减少的IO操作

8. **依赖条件**: 规则执行需要的前置条件
   - 是否依赖统计信息
   - 是否依赖代价模型
   - 是否依赖物理属性

9. **适用场景**: 描述该规则最适用的查询场景

10. **SQL示例**: 给出一个具体的SQL优化示例
    - 原始SQL
    - 优化后的执行计划

## 输出格式
```json
{{
  "rule_name_cn": "规则中文名",
  "description": "功能概述",
  "relational_algebra": "σ_p(R) → ...",
  "input_pattern": {{
    "operators": ["Filter", "Scan"],
    "structure": "Filter(Scan(table))",
    "trigger_conditions": ["存在可下推的谓词", "谓词只涉及单表"]
  }},
  "output_pattern": {{
    "operators": ["Scan"],
    "structure": "Scan(table, filter=[p])",
    "changes": "谓词被下推到Scan算子内部"
  }},
  "execution_process": [
    "第一步: 从根节点开始，查找Filter算子",
    "第二步: 检查Filter的子节点是否为Scan",
    "第三步: 分析谓词是否可以下推",
    "第四步: 将谓词合并到Scan的条件中"
  ],
  "optimization_benefit": {{
    "data_reduction": "减少X%的中间数据量",
    "complexity": "从O(n)降低到O(m) where m < n",
    "io_reduction": "减少磁盘IO次数"
  }},
  "dependencies": {{
    "requires_stats": false,
    "requires_cost": false,
    "requires_property": false
  }},
  "applicable_scenarios": ["点查询", "大表过滤", "OLAP场景"],
  "sql_example": {{
    "before": "SELECT * FROM t WHERE id = 1",
    "after": "IndexScan(t, filter=[id=1])"
  }}
}}
```

只返回JSON，不要其他内容。"""

        try:
            response = self.llm_client.chat([
                ChatMessage(role="system", content="你是数据库查询优化器专家，擅长分析优化规则的实现细节。"),
                ChatMessage(role="user", content=prompt)
            ], temperature=0.3)

            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                result = json.loads(json_match.group())
                result["class_name"] = class_name
                result["filename"] = filename
                result["analysis_status"] = "success"
                return result
        except Exception as e:
            pass

        # Fallback to basic analysis
        return self._basic_analysis(class_name, code, filename)

    def _basic_analysis(self, class_name: str, code: str, filename: str) -> Dict:
        """Basic analysis without LLM."""
        return {
            "class_name": class_name,
            "filename": filename,
            "rule_name_cn": self._infer_chinese_name(class_name),
            "description": "需要LLM深度分析",
            "relational_algebra": "Pattern(R) → Transformed(R)",
            "input_pattern": {
                "operators": ["待分析"],
                "structure": "待分析",
                "trigger_conditions": []
            },
            "output_pattern": {
                "operators": ["待分析"],
                "structure": "待分析",
                "changes": "待分析"
            },
            "execution_process": ["需要LLM深度分析"],
            "optimization_benefit": {},
            "dependencies": {
                "requires_stats": "cost" in code.lower(),
                "requires_cost": "cost" in code.lower(),
                "requires_property": "property" in code.lower() or "trait" in code.lower()
            },
            "applicable_scenarios": [],
            "sql_example": {},
            "analysis_status": "basic"
        }

    def _infer_chinese_name(self, class_name: str) -> str:
        """Infer Chinese name from class name."""
        name_map = {
            "PushDown": "下推", "Predicate": "谓词", "Project": "投影",
            "Join": "连接", "Aggregate": "聚合", "Filter": "过滤",
            "Scan": "扫描", "Limit": "Limit", "Sort": "排序",
            "Union": "Union", "Intersect": "交集", "Except": "差集",
            "Subquery": "子查询", "Merge": "合并", "Transpose": "转置",
            "Eliminate": "消除", "Prune": "裁剪", "Constant": "常量",
            "Fold": "折叠", "Reorder": "重排序", "Exchange": "交换",
            "Implement": "实现", "Transform": "转换", "Rewrite": "重写",
            "HashJoin": "Hash连接", "MergeJoin": "归并连接",
        }
        name = class_name.replace("Rule", "")
        for eng, chn in name_map.items():
            name = name.replace(eng, chn)
        return name if name != class_name else class_name


def scan_all_rules(path: str) -> List[Dict]:
    """Scan all rule files."""
    scanner = JavaScanner()
    rules = []
    p = Path(path)

    if not p.exists():
        return rules

    for java_file in p.rglob("*.java"):
        if "Test" in java_file.name:
            continue
        try:
            code = java_file.read_text(encoding="utf-8", errors="ignore")
            classes = scanner.extract_classes(code)
            if classes:
                rules.append({
                    "class_name": classes[0],
                    "code": code,
                    "filename": java_file.name,
                    "path": str(java_file.relative_to(p.parent))
                })
        except:
            pass

    return rules


def generate_comprehensive_report(
    engine_name: str,
    source_path: str,
    output_dir: str,
    max_rules: int = 30  # Limit rules per engine for detailed analysis
) -> str:
    """Generate comprehensive report with detailed rule analysis."""

    print(f"\n{'='*60}")
    print(f"正在生成 {engine_name} 详细分析报告...")
    print(f"{'='*60}")

    config = {
        "StarRocks": STARROCKS_CONFIG,
        "Calcite": CALCITE_CONFIG,
        "Doris": DORIS_CONFIG,
    }[engine_name]

    # Initialize LLM client
    try:
        llm_client = LLMClient(LLMConfig.from_env_file())
        analyzer = DetailedRuleAnalyzer(llm_client)
    except Exception as e:
        print(f"  警告: LLM初始化失败: {e}")
        print("  将生成基础报告")
        return None

    # Get rule directories
    rule_dirs = get_rule_directories(engine_name, source_path)
    all_rules = []

    for category, dir_path in rule_dirs.items():
        rules = scan_all_rules(dir_path)
        for rule in rules:
            rule["category"] = category
        all_rules.extend(rules)
        print(f"  {category}: {len(rules)} 条规则")

    # Limit for detailed analysis
    if len(all_rules) > max_rules:
        print(f"\n  注意: 规则数量({len(all_rules)})超过限制({max_rules})")
        print(f"  将选择代表性规则进行详细分析")
        # Select diverse rules
        selected = []
        categories_seen = set()
        for rule in all_rules:
            cat = rule.get("category", "")
            if cat not in categories_seen or len(selected) < max_rules:
                selected.append(rule)
                categories_seen.add(cat)
            if len(selected) >= max_rules:
                break
        all_rules = selected

    # Analyze rules (with progress)
    print(f"\n  正在分析 {len(all_rules)} 条规则...")
    analyzed_rules = []

    for i, rule in enumerate(all_rules):
        print(f"  [{i+1}/{len(all_rules)}] 分析 {rule['class_name'][:40]}...", end="\r")
        try:
            analysis = analyzer.analyze_rule_comprehensive(
                rule["class_name"],
                rule["code"],
                rule["filename"]
            )
            analysis["category"] = rule.get("category", "其他")
            analysis["path"] = rule.get("path", "")
            analyzed_rules.append(analysis)
        except Exception as e:
            print(f"\n  警告: 分析 {rule['class_name']} 失败: {e}")

    print(f"\n  完成 {len(analyzed_rules)} 条规则分析")

    # Generate report
    report = generate_report_markdown(engine_name, config, analyzed_rules)

    # Save report
    output_file = Path(output_dir) / f"{engine_name.lower()}_规则深度分析.md"
    output_file.write_text(report, encoding="utf-8")
    print(f"  已保存: {output_file}")

    return str(output_file)


def get_rule_directories(engine_name: str, source_path: str) -> Dict[str, str]:
    """Get rule directories for each engine."""
    dirs = {}

    if engine_name == "StarRocks":
        base = f"{source_path}/fe/fe-core/src/main/java/com/starrocks/sql/optimizer/rule"
        dirs = {
            "转换规则 (Transformation)": f"{base}/transformation",
            "实现规则 (Implementation)": f"{base}/implementation",
        }
    elif engine_name == "Calcite":
        dirs = {
            "优化规则 (Rules)": f"{source_path}/core/src/main/java/org/apache/calcite/rel/rules",
        }
    elif engine_name == "Doris":
        base = f"{source_path}/fe/fe-core/src/main/java/org/apache/doris/nereids/rules"
        dirs = {
            "分析规则 (Analysis)": f"{base}/analysis",
            "探索规则 (Exploration)": f"{base}/exploration",
            "实现规则 (Implementation)": f"{base}/implementation",
            "重写规则 (Rewrite)": f"{base}/rewrite",
            "表达式规则 (Expression)": f"{base}/expression",
        }

    return dirs


def generate_report_markdown(engine_name: str, config, rules: List[Dict]) -> str:
    """Generate comprehensive markdown report."""
    lines = []

    # Header
    lines.append(f"# {engine_name} 优化规则深度分析报告\n")
    lines.append(f"> **生成时间:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append(f"> **引擎类型:** {config.engine_type.value}\n")
    lines.append(f"> **优化器风格:** {config.optimizer_style.value}\n")
    lines.append(f"> **分析规则数:** {len(rules)}\n")

    # Table of Contents
    lines.append("\n## 📑 目录\n")
    lines.append("- [一、规则概览](#一规则概览)")
    lines.append("- [二、关系代数符号说明](#二关系代数符号说明)")
    lines.append("- [三、规则详细分析](#三规则详细分析)")

    # Group by category
    by_category = {}
    for rule in rules:
        cat = rule.get("category", "其他规则")
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(rule)

    section_num = 1
    for category in by_category.keys():
        lines.append(f"  - [{category}](#三{section_num}-{category.replace(' ', '-')})")
        section_num += 1

    lines.append("- [四、优化原理总结](#四优化原理总结)")
    lines.append("- [五、最佳实践建议](#五最佳实践建议)")

    # Section 1: Overview
    lines.append("\n## 一、规则概览\n")

    lines.append("### 1.1 规则分类统计\n")
    lines.append("| 规则类别 | 数量 |\n|----------|------|\n")
    for cat, cat_rules in by_category.items():
        lines.append(f"| {cat} | {len(cat_rules)} |")
    lines.append(f"| **总计** | **{len(rules)}** |")

    # Success rate
    success_count = sum(1 for r in rules if r.get("analysis_status") == "success")
    lines.append(f"\n### 1.2 分析完成度\n")
    lines.append(f"- 成功深度分析: {success_count}/{len(rules)} ({success_count/len(rules)*100:.1f}%)")

    # Section 2: Relational Algebra Symbols
    lines.append("\n## 二、关系代数符号说明\n")
    lines.append("""
| 符号 | 名称 | 含义 | 示例 |
|------|------|------|------|
| σ | Sigma (选择) | 筛选满足条件的行 | `σ_{age>18}(Student)` |
| π | Pi (投影) | 选择特定列 | `π_{name,age}(Student)` |
| ⋈ | Theta Join | 条件连接 | `R ⋈_{R.id=S.id} S` |
| × | Cartesian | 笛卡尔积 | `R × S` |
| γ | Gamma (聚合) | 分组聚合 | `γ_{dept, AVG(salary)}(Employee)` |
| τ | Tau (排序) | 排序 | `τ_{salary DESC}(Employee)` |
| ∪ | Union | 并集 | `R ∪ S` |
| ∩ | Intersect | 交集 | `R ∩ S` |
| − | Difference | 差集 | `R − S` |
| → | Transform | 转换为 | `A → B` |
| ρ | Rho (重命名) | 重命名 | `ρ_{S}(R)` |

### 2.1 常用优化等价式

```
1. 选择下推: σ_{p}(R ⋈ S) ≡ R ⋈ σ_{p}(S)  (当p只涉及S的属性)
2. 投影下推: π_{A}(σ_{p}(R)) ≡ π_{A}(R)  (当A包含p的所有属性)
3. 选择合并: σ_{p1}(σ_{p2}(R)) ≡ σ_{p1∧p2}(R)
4. 投影合并: π_{A}(π_{B}(R)) ≡ π_{A∩B}(R)
5. 连接交换: R ⋈ S ≡ S ⋈ R  (对于内连接)
6. 连接结合: (R ⋈ S) ⋈ T ≡ R ⋈ (S ⋈ T)
```
""")

    # Section 3: Detailed Analysis
    lines.append("\n## 三、规则详细分析\n")

    section_num = 1
    for category, cat_rules in by_category.items():
        lines.append(f"\n### 3.{section_num} {category}\n")
        lines.append(f"> 共 {len(cat_rules)} 条规则\n")

        for i, rule in enumerate(cat_rules, 1):
            class_name = rule.get("class_name", "Unknown")
            name_cn = rule.get("rule_name_cn", class_name)
            desc = rule.get("description", "")
            algebra = rule.get("relational_algebra", "")
            input_pat = rule.get("input_pattern", {})
            output_pat = rule.get("output_pattern", {})
            exec_process = rule.get("execution_process", [])
            opt_benefit = rule.get("optimization_benefit", {})
            deps = rule.get("dependencies", {})
            scenarios = rule.get("applicable_scenarios", [])
            sql_ex = rule.get("sql_example", {})
            path = rule.get("path", "")

            # Rule header
            lines.append(f"\n#### 3.{section_num}.{i} `{class_name}`\n")

            if name_cn and name_cn != class_name:
                lines.append(f"**📋 规则名称:** {name_cn}\n")

            if path:
                lines.append(f"**📁 源码位置:** `{path}`\n")

            if desc:
                lines.append(f"\n**📝 功能概述:**\n\n{desc}\n")

            # Relational Algebra
            if algebra:
                lines.append(f"\n**🔢 关系代数表达式:**\n\n```\n{algebra}\n```\n")

            # Input Pattern
            if input_pat and input_pat.get("operators"):
                lines.append(f"\n**📥 输入模式:**\n")
                lines.append("| 属性 | 值 |\n|------|----|\n")
                if input_pat.get("operators"):
                    ops = input_pat["operators"]
                    if isinstance(ops, list):
                        lines.append(f"| 算子类型 | {', '.join(ops)} |")
                if input_pat.get("structure"):
                    lines.append(f"| 算子结构 | `{input_pat['structure']}` |")
                if input_pat.get("trigger_conditions"):
                    conds = input_pat["trigger_conditions"]
                    if isinstance(conds, list) and conds:
                        lines.append(f"| 触发条件 | {'; '.join(conds[:3])} |")

            # Output Pattern
            if output_pat and output_pat.get("operators"):
                lines.append(f"\n**📤 输出模式:**\n")
                lines.append("| 属性 | 值 |\n|------|----|\n")
                if output_pat.get("operators"):
                    ops = output_pat["operators"]
                    if isinstance(ops, list):
                        lines.append(f"| 算子类型 | {', '.join(ops)} |")
                if output_pat.get("structure"):
                    lines.append(f"| 算子结构 | `{output_pat['structure']}` |")
                if output_pat.get("changes"):
                    lines.append(f"| 结构变化 | {output_pat['changes']} |")

            # Execution Process
            if exec_process and isinstance(exec_process, list) and exec_process:
                lines.append(f"\n**⚙️ 执行过程:**\n")
                lines.append("```mermaid\nflowchart TD\n")
                for j, step in enumerate(exec_process):
                    step_text = step.replace('"', "'")[:50]
                    lines.append(f"    step{j+1}[\"{step_text}\"]\n")
                    if j > 0:
                        lines.append(f"    step{j} --> step{j+1}\n")
                lines.append("```\n")

                lines.append("\n**详细步骤:**\n")
                for j, step in enumerate(exec_process, 1):
                    lines.append(f"{j}. {step}")
                lines.append("")

            # Optimization Benefit
            if opt_benefit:
                lines.append(f"\n**✨ 优化收益:**\n")
                benefits = []
                if opt_benefit.get("data_reduction"):
                    benefits.append(f"- 📊 数据量减少: {opt_benefit['data_reduction']}")
                if opt_benefit.get("complexity"):
                    benefits.append(f"- ⏱️ 复杂度降低: {opt_benefit['complexity']}")
                if opt_benefit.get("io_reduction"):
                    benefits.append(f"- 💾 IO优化: {opt_benefit['io_reduction']}")
                if benefits:
                    lines.append("\n".join(benefits) + "\n")

            # Dependencies
            if deps:
                lines.append(f"\n**🔗 依赖条件:**\n")
                dep_list = []
                if deps.get("requires_stats"):
                    dep_list.append("统计信息")
                if deps.get("requires_cost"):
                    dep_list.append("代价模型")
                if deps.get("requires_property"):
                    dep_list.append("物理属性")
                if dep_list:
                    lines.append(f"需要: {', '.join(dep_list)}\n")
                else:
                    lines.append("无特殊依赖\n")

            # Applicable Scenarios
            if scenarios and isinstance(scenarios, list) and scenarios:
                lines.append(f"\n**🎯 适用场景:**\n")
                for s in scenarios[:5]:
                    lines.append(f"- {s}")
                lines.append("")

            # SQL Example
            if sql_ex and (sql_ex.get("before") or sql_ex.get("after")):
                lines.append(f"\n**💡 SQL优化示例:**\n")
                if sql_ex.get("before"):
                    lines.append(f"**优化前:**\n```sql\n{sql_ex['before']}\n```\n")
                if sql_ex.get("after"):
                    lines.append(f"**优化后:**\n```\n{sql_ex['after']}\n```\n")

            lines.append("---")

        section_num += 1

    # Section 4: Optimization Principles
    lines.append("\n## 四、优化原理总结\n")
    lines.append("""
### 4.1 核心优化原则

查询优化的核心是利用关系代数的**等价变换规则**，在保持查询语义不变的前提下，找到执行代价最小的等价表达式。

#### 4.1.1 选择下推 (Selection Pushdown)

**原理:** 尽早过滤，减少中间结果

```
原始: σ_{p}(R ⋈ S)
优化: R ⋈ σ_{p}(S)  -- 当p只涉及S的属性时
```

**收益:**
- 减少连接操作的输入数据量
- 降低内存使用
- 减少网络传输（分布式场景）

#### 4.1.2 投影下推 (Projection Pushdown)

**原理:** 只读取需要的列

```
原始: π_{A,B}(Scan(R))  -- 扫描所有列
优化: Scan(R, columns=[A,B])  -- 只扫描指定列
```

**收益:**
- 减少磁盘IO
- 降低内存占用
- 提高缓存命中率

#### 4.1.3 连接重排序 (Join Reordering)

**原理:** 选择产生最小中间结果的连接顺序

```
原始: (R ⋈ S) ⋈ T  -- 可能产生大量中间结果
优化: R ⋈ (S ⋈ T)  -- 如果这个顺序产生更少中间结果
```

**收益:**
- 减少中间结果大小
- 降低内存和磁盘使用
- 缩短查询响应时间

#### 4.1.4 聚合下推 (Aggregation Pushdown)

**原理:** 先聚合减少数据量

```
原始: γ_{g,a}(R ⋈ S)  -- 先连接再聚合
优化: γ_{g,a}(R) ⋈ S  -- 当分组属性都在R上时
```

**收益:**
- 减少连接操作的输入
- 降低计算开销
""")

    # Section 5: Best Practices
    lines.append("\n## 五、最佳实践建议\n")
    lines.append("""
### 5.1 SQL编写建议

1. **使用明确的过滤条件**
   - 将过滤条件写在WHERE子句中，而不是HAVING
   - 避免在WHERE子句中使用函数

2. **合理使用索引**
   - 为高频查询条件创建索引
   - 遵循最左前缀原则

3. **避免SELECT ***
   - 只选择需要的列
   - 让优化器可以应用投影下推

4. **合理使用JOIN**
   - 小表驱动大表
   - 避免笛卡尔积

### 5.2 调优建议

1. **查看执行计划**
   - 使用EXPLAIN分析查询计划
   - 检查是否有预期的优化规则被应用

2. **监控统计信息**
   - 确保统计信息是最新的
   - 对于大表变更后及时更新统计信息

3. **会话变量调优**
   - 了解优化器相关的会话变量
   - 根据场景调整优化器行为
""")

    # Footer
    lines.append("\n---\n")
    lines.append(f"*本报告由 Optimizer Expert Analyzer 自动生成*\n")
    lines.append(f"*包含规则的输入输出模式和执行过程分析*\n")
    lines.append(f"*生成时间: {datetime.now().isoformat()}*\n")

    return "\n".join(lines)


def main():
    """Generate comprehensive reports."""
    import argparse

    parser = argparse.ArgumentParser(description="生成优化规则深度分析报告")
    parser.add_argument("--engines", nargs="+", default=["StarRocks"],
                        help="要分析的引擎")
    parser.add_argument("--output", default="./analysis_output/comprehensive_reports",
                        help="输出目录")
    parser.add_argument("--max-rules", type=int, default=30,
                        help="每个引擎详细分析的最大规则数")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("优化规则深度分析报告生成器")
    print("(包含输入输出模式和执行过程)")
    print("=" * 60)

    for engine_name in args.engines:
        if engine_name not in ENGINE_PATHS:
            print(f"未知引擎: {engine_name}")
            continue

        source_path = ENGINE_PATHS[engine_name]
        if not Path(source_path).exists():
            print(f"源码不存在: {source_path}")
            continue

        generate_comprehensive_report(
            engine_name, source_path, args.output, args.max_rules
        )

    print("\n" + "=" * 60)
    print("报告生成完成")
    print("=" * 60)


if __name__ == "__main__":
    main()