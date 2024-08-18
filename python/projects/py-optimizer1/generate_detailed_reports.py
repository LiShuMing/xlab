#!/usr/bin/env python3
"""Generate detailed Chinese reports with relational algebra for each rule."""
import re
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple

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

# Relational algebra symbols
RA = {
    "sigma": "σ",      # Selection
    "pi": "π",         # Projection
    "join": "⋈",       # Join
    "cross": "×",      # Cartesian product
    "union": "∪",      # Union
    "intersect": "∩",  # Intersection
    "diff": "−",       # Difference
    "rho": "ρ",        # Rename
    "gamma": "γ",      # Aggregation
    "tau": "τ",        # Sort
    "arrow": "→",      # Transform
    "subset": "⊆",     # Subset
}


class RuleAnalyzer:
    """Analyze optimization rules with relational algebra."""

    # Known rule patterns and their relational algebra expressions
    RULE_PATTERNS = {
        # Predicate Pushdown patterns
        "PushDown.*Predicate": {
            "name": "谓词下推",
            "description": "将过滤条件尽可能下推到数据源附近，减少中间结果集大小",
            "algebra": "σ_{p}(R ⋈ S) → R ⋈ σ_{p}(S)",
            "category": "RBO",
            "optimization_goal": "减少连接前的数据量",
            "example": "SELECT * FROM orders JOIN customers ON o_id = c_id WHERE c_status = 'active' → 先过滤customers再连接",
        },
        "PushDownPredicate.*Scan": {
            "name": "谓词下推到扫描",
            "description": "将过滤条件下推到表扫描操作",
            "algebra": "σ_{p}(R) → Scan_R[p]",
            "category": "RBO",
            "optimization_goal": "在数据源层面过滤，减少IO",
        },

        # Projection Pushdown
        "PushDown.*Project": {
            "name": "投影下推",
            "description": "将投影操作下推，只读取需要的列",
            "algebra": "π_{A}(σ_{p}(R)) → π_{A}(Scan_R[p])",
            "category": "RBO",
            "optimization_goal": "减少列扫描，降低IO和内存",
        },
        "Prune.*Column": {
            "name": "列裁剪",
            "description": "移除查询中不需要的列",
            "algebra": "π_{A,B,C}(R) → π_{A,B}(R) [if C unused]",
            "category": "RBO",
            "optimization_goal": "减少数据传输量",
        },

        # Join Reorder
        "Join.*Reorder": {
            "name": "连接重排序",
            "description": "调整多表连接顺序，优先连接小表",
            "algebra": "(R ⋈ S) ⋈ T → R ⋈ (S ⋈ T)",
            "category": "CBO",
            "optimization_goal": "最小化中间结果大小",
            "depends_on": ["统计信息", "代价模型"],
        },
        "Join.*Commute": {
            "name": "连接交换",
            "description": "利用连接交换律改变连接顺序",
            "algebra": "R ⋈_{cond} S → S ⋈_{cond} R",
            "category": "CBO",
            "optimization_goal": "选择更优的连接顺序",
        },

        # Aggregation rules
        "Aggregate.*Merge": {
            "name": "聚合合并",
            "description": "合并相邻的聚合操作",
            "algebra": "γ_{g1, a1}(γ_{g2, a2}(R)) → γ_{g1, a1'}(R)",
            "category": "RBO",
            "optimization_goal": "减少聚合计算次数",
        },
        "Aggregate.*Transpose": {
            "name": "聚合转置",
            "description": "交换聚合和连接的顺序",
            "algebra": "γ_{g,a}(R ⋈ S) → γ_{g,a}(R) ⋈ S",
            "category": "RBO",
            "optimization_goal": "先聚合减少数据量再连接",
        },

        # Filter rules
        "Filter.*Merge": {
            "name": "过滤合并",
            "description": "合并多个过滤条件",
            "algebra": "σ_{p1}(σ_{p2}(R)) → σ_{p1 ∧ p2}(R)",
            "category": "RBO",
            "optimization_goal": "减少扫描次数",
        },
        "Filter.*Transpose": {
            "name": "过滤转置",
            "description": "移动过滤操作的位置",
            "algebra": "σ_{p}(π_{A}(R)) → π_{A}(σ_{p}(R))",
            "category": "RBO",
            "optimization_goal": "尽早过滤减少数据量",
        },

        # Limit/TopN rules
        ".*Limit.*": {
            "name": "Limit下推",
            "description": "将Limit操作下推到数据源",
            "algebra": "τ_{order}^n(R) → Scan_R[order, limit=n]",
            "category": "RBO",
            "optimization_goal": "减少数据传输",
        },
        "TopN": {
            "name": "TopN优化",
            "description": "将排序+Limit转换为TopN操作",
            "algebra": "τ_{order}(R) LIMIT n → TopN_{order}^n(R)",
            "category": "RBO",
            "optimization_goal": "避免全排序，使用堆获取TopN",
        },

        # Union/Intersect rules
        "Union.*Merge": {
            "name": "Union合并",
            "description": "合并相同的Union分支",
            "algebra": "R ∪ R → R",
            "category": "RBO",
            "optimization_goal": "消除重复计算",
        },

        # Subquery rules
        "Subquery.*Flatten": {
            "name": "子查询展开",
            "description": "将子查询转换为连接操作",
            "algebra": "σ_{a IN (π_b(S))}(R) → R ⋈_{a=b} S",
            "category": "RBO",
            "optimization_goal": "使用更高效的连接算法",
        },
        "Apply.*Remove": {
            "name": "Apply消除",
            "description": "消除相关子查询的Apply操作",
            "algebra": "Apply_{R}(S) → R ⋈ S",
            "category": "RBO",
            "optimization_goal": "将相关子查询转换为连接",
        },

        # Expression rules
        "Constant.*Fold": {
            "name": "常量折叠",
            "description": "在编译期计算常量表达式",
            "algebra": "1+2 → 3, UPPER('abc') → 'ABC'",
            "category": "Scalar",
            "optimization_goal": "减少运行时计算",
        },
        "Expression.*Simplif": {
            "name": "表达式简化",
            "description": "简化复杂表达式",
            "algebra": "a AND true → a, a OR false → a",
            "category": "Scalar",
            "optimization_goal": "减少表达式计算开销",
        },

        # Implementation rules
        "HashJoin": {
            "name": "HashJoin实现",
            "description": "使用哈希表实现连接",
            "algebra": "R ⋈_{a=b} S → HashJoin_{a,b}(R, S)",
            "category": "Implementation",
            "optimization_goal": "O(n+m)时间复杂度的连接",
        },
        "MergeJoin": {
            "name": "MergeJoin实现",
            "description": "使用归并排序实现连接",
            "algebra": "R ⋈_{a=b} S → MergeJoin_{a,b}(sort_a(R), sort_b(S))",
            "category": "Implementation",
            "optimization_goal": "适用于已排序数据",
        },
        "NestedLoopJoin": {
            "name": "嵌套循环连接",
            "description": "使用嵌套循环实现连接",
            "algebra": "R ⋈ S → NestedLoop(R, S)",
            "category": "Implementation",
            "optimization_goal": "适用于小表连接",
        },
    }

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client

    def analyze_rule(self, class_name: str, code: str, filename: str) -> Dict:
        """Analyze a single rule and return detailed information."""
        result = {
            "class_name": class_name,
            "filename": filename,
            "chinese_name": None,
            "description": None,
            "relational_algebra": None,
            "category": None,
            "optimization_goal": None,
            "example": None,
            "input_pattern": None,
            "output_pattern": None,
            "dependencies": [],
            "conditions": [],
        }

        # Try to match known patterns
        matched = False
        for pattern, info in self.RULE_PATTERNS.items():
            if re.search(pattern, class_name, re.IGNORECASE):
                result.update(info)
                matched = True
                break

        # Extract from code if not matched
        if not matched:
            result = self._extract_from_code(class_name, code, result)

        # Use LLM for deeper analysis if available
        if self.llm_client and not matched:
            try:
                llm_result = self._analyze_with_llm(class_name, code)
                result.update(llm_result)
            except Exception as e:
                result["llm_error"] = str(e)

        return result

    def _extract_from_code(self, class_name: str, code: str, result: Dict) -> Dict:
        """Extract rule information from source code."""
        # Determine category from class name
        name = class_name.lower()

        if "transform" in name:
            result["category"] = "转换规则"
            result["optimization_goal"] = "逻辑等价变换，生成备选执行计划"
        elif "implement" in name:
            result["category"] = "实现规则"
            result["optimization_goal"] = "将逻辑算子转换为物理算子"
        elif "rewrite" in name:
            result["category"] = "重写规则"
            result["optimization_goal"] = "查询重写优化"
        elif "exploration" in name or "explore" in name:
            result["category"] = "探索规则"
            result["optimization_goal"] = "探索等价执行计划空间"
        elif "analysis" in name or "analyze" in name:
            result["category"] = "分析规则"
            result["optimization_goal"] = "语义分析和绑定"
        elif "expression" in name:
            result["category"] = "表达式规则"
            result["optimization_goal"] = "标量表达式优化"
        else:
            result["category"] = "其他规则"

        # Infer Chinese name from class name
        result["chinese_name"] = self._infer_chinese_name(class_name)

        # Try to infer algebra from method names
        result["relational_algebra"] = self._infer_algebra(class_name, code)

        # Check dependencies
        if "cost" in code.lower():
            result["dependencies"].append("代价模型")
        if "statistic" in code.lower():
            result["dependencies"].append("统计信息")
        if "property" in code.lower() or "trait" in code.lower():
            result["dependencies"].append("物理属性")

        return result

    def _infer_chinese_name(self, class_name: str) -> str:
        """Infer Chinese name from class name."""
        name_map = {
            "PushDown": "下推",
            "Predicate": "谓词",
            "Project": "投影",
            "Join": "连接",
            "Aggregate": "聚合",
            "Filter": "过滤",
            "Scan": "扫描",
            "Limit": "Limit",
            "Sort": "排序",
            "Union": "Union",
            "Intersect": "交集",
            "Except": "差集",
            "Subquery": "子查询",
            "Merge": "合并",
            "Transpose": "转置",
            "Eliminate": "消除",
            "Prune": "裁剪",
            "Constant": "常量",
            "Fold": "折叠",
            "Reorder": "重排序",
            "Exchange": "交换",
            "Implement": "实现",
            "Transform": "转换",
            "Rewrite": "重写",
            "HashJoin": "Hash连接",
            "MergeJoin": "归并连接",
            "NestedLoop": "嵌套循环",
        }

        name = class_name.replace("Rule", "")
        for eng, chn in name_map.items():
            if eng in name:
                name = name.replace(eng, chn)

        return name if name != class_name else class_name

    def _infer_algebra(self, class_name: str, code: str) -> str:
        """Infer relational algebra expression."""
        name = class_name.lower()

        # Common patterns
        if "pushdownpredicate" in name:
            return f"σ_{{p}}(R op S) {RA['arrow']} R op σ_{{p}}(S)"
        elif "pushdownproject" in name or "prune" in name:
            return f"π_{{A}}(R) {RA['arrow']} π_{{A'}}(R) where A' ⊆ A"
        elif "joinreorder" in name or "joincommut" in name:
            return f"(R {RA['join']} S) {RA['join']} T {RA['arrow']} R {RA['join']} (S {RA['join']} T)"
        elif "aggregatemerge" in name:
            return f"γ_{{g1,a1}}(γ_{{g2,a2}}(R)) {RA['arrow']} γ_{{g,a}}(R)"
        elif "filtermerge" in name:
            return f"σ_{{p1}}(σ_{{p2}}(R)) {RA['arrow']} σ_{{p1 {chr(0x2227)} p2}}(R)"
        elif "hashjoin" in name:
            return f"R {RA['join']}_{{cond}} S {RA['arrow']} HashJoin(R, S)"
        elif "mergejoin" in name:
            return f"R {RA['join']}_{{cond}} S {RA['arrow']} MergeJoin(sort(R), sort(S))"
        elif "limit" in name:
            return f"{RA['tau']}_{{order}}(R) LIMIT n {RA['arrow']} TopN^n(R)"
        elif "constant" in name or "fold" in name:
            return "expr(const) → const_value"
        else:
            return f"Pattern(R) {RA['arrow']} Transformed(R)"

    def _analyze_with_llm(self, class_name: str, code: str) -> Dict:
        """Use LLM to analyze rule in detail."""
        prompt = f"""分析以下数据库优化规则，用中文回答。

规则类名: {class_name}

代码片段:
```
{code[:2000]}
```

请用以下JSON格式回答：
{{
  "chinese_name": "规则中文名称",
  "description": "规则功能描述（1-2句话）",
  "relational_algebra": "关系代数表达式（使用σ,π,⋈,×,∪,∩等符号）",
  "optimization_goal": "优化目标",
  "input_pattern": "输入算子模式",
  "output_pattern": "输出算子模式",
  "conditions": ["触发条件列表"],
  "dependencies": ["依赖的资源"],
  "example": "具体SQL优化示例"
}}

只返回JSON，不要其他文字。"""

        try:
            response = self.llm_client.chat([
                ChatMessage(role="user", content=prompt)
            ])

            # Parse JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            pass

        return {}


def format_algebra_explanation(algebra: str) -> str:
    """Format relational algebra with explanation."""
    if not algebra:
        return ""

    explanations = {
        "σ": "σ (Sigma) = 选择/过滤操作",
        "π": "π (Pi) = 投影操作，选择特定列",
        "⋈": "⋈ = 连接操作",
        "×": "× = 笛卡尔积",
        "γ": "γ (Gamma) = 聚合操作",
        "τ": "τ (Tau) = 排序操作",
        "∪": "∪ = 并集",
        "∩": "∩ = 交集",
        "→": "→ = 转换为",
    }

    used_symbols = []
    for symbol, explanation in explanations.items():
        if symbol in algebra:
            used_symbols.append(explanation)

    if used_symbols:
        return f"`{algebra}`\n\n**符号说明:** {'; '.join(used_symbols)}"

    return f"`{algebra}`"


def generate_detailed_report(
    engine_name: str,
    source_path: str,
    output_dir: str,
    use_llm: bool = False
) -> str:
    """Generate detailed Chinese report with relational algebra."""
    config = {
        "StarRocks": STARROCKS_CONFIG,
        "Calcite": CALCITE_CONFIG,
        "Doris": DORIS_CONFIG,
    }[engine_name]

    print(f"正在深度分析 {engine_name} (包含关系代数)...")

    llm_client = None
    if use_llm:
        try:
            llm_client = LLMClient(LLMConfig.from_env_file())
        except:
            print("  警告: LLM不可用，将使用规则匹配分析")

    analyzer = RuleAnalyzer(llm_client)

    # Get rule directories
    rule_dirs = get_rule_directories(engine_name, source_path, config)
    all_rules = []
    total_rules = 0

    for category, dir_path in rule_dirs.items():
        rules = scan_rules_with_analysis(dir_path, engine_name, analyzer)
        for rule in rules:
            rule["category_display"] = category
        all_rules.extend(rules)
        total_rules += len(rules)
        print(f"  {category}: {len(rules)} 条规则")

    # Generate report
    report = generate_report_content(engine_name, config, all_rules, total_rules)

    # Save report
    output_file = Path(output_dir) / f"{engine_name.lower()}_优化规则详细分析.md"
    output_file.write_text(report, encoding="utf-8")
    print(f"  已保存: {output_file}")

    return str(output_file)


def get_rule_directories(engine_name: str, source_path: str, config) -> Dict[str, str]:
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


def scan_rules_with_analysis(path: str, engine_name: str, analyzer: RuleAnalyzer) -> List[Dict]:
    """Scan and analyze rules."""
    scanner = JavaScanner()
    rules = []

    p = Path(path)
    if not p.exists():
        return rules

    for java_file in p.rglob("*.java"):
        try:
            code = java_file.read_text(encoding="utf-8", errors="ignore")

            if "Test" in java_file.name:
                continue

            classes = scanner.extract_classes(code)
            if classes:
                class_name = classes[0]
                rule_info = analyzer.analyze_rule(class_name, code, java_file.name)
                rule_info["path"] = str(java_file.relative_to(p.parent))
                rules.append(rule_info)

        except Exception as e:
            pass

    return rules


def generate_report_content(engine_name: str, config, all_rules: List[Dict], total: int) -> str:
    """Generate markdown report content."""
    lines = []

    # Header
    lines.append(f"# {engine_name} 优化规则详细分析报告\n")
    lines.append(f"> **生成时间:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append(f"> **分析源码路径:** `{ENGINE_PATHS[engine_name]}`\n")
    lines.append(f"> **规则总数:** {total}\n")

    # Summary
    lines.append("## 📊 一、规则统计总览\n")

    # Category breakdown
    category_counts = {}
    for rule in all_rules:
        cat = rule.get("category", "其他")
        category_counts[cat] = category_counts.get(cat, 0) + 1

    lines.append("### 1.1 规则分类统计\n")
    lines.append("| 规则类型 | 数量 | 占比 |\n|----------|------|------|\n")
    for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
        pct = f"{count/total*100:.1f}%"
        lines.append(f"| {cat} | {count} | {pct} |")
    lines.append(f"| **总计** | **{total}** | **100%** |")

    # Relational algebra legend
    lines.append("\n### 1.2 关系代数符号说明\n")
    lines.append("""
| 符号 | 名称 | 含义 |
|------|------|------|
| σ | Sigma | 选择操作，筛选满足条件的行 |
| π | Pi | 投影操作，选择特定列 |
| ⋈ | Join | 连接操作，连接两个关系 |
| × | Cartesian | 笛卡尔积 |
| γ | Gamma | 聚合操作，分组和计算 |
| τ | Tau | 排序操作 |
| ∪ | Union | 并集 |
| ∩ | Intersect | 交集 |
| → | Arrow | 转换为 |
""")

    # Detailed rules by category
    lines.append("\n## 📚 二、规则详细分析\n")

    # Group rules by category_display
    by_category = {}
    for rule in all_rules:
        cat = rule.get("category_display", "其他规则")
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(rule)

    section_num = 1
    for category, rules in by_category.items():
        lines.append(f"\n### 2.{section_num} {category}\n")
        lines.append(f"> 共 {len(rules)} 条规则\n")

        for i, rule in enumerate(rules, 1):
            class_name = rule.get("class_name", "Unknown")
            chinese_name = rule.get("chinese_name", class_name)
            description = rule.get("description", "待分析")
            algebra = rule.get("relational_algebra", "")
            opt_goal = rule.get("optimization_goal", "")
            example = rule.get("example", "")
            dependencies = rule.get("dependencies", [])
            conditions = rule.get("conditions", [])

            lines.append(f"\n#### 2.{section_num}.{i} `{class_name}`\n")

            if chinese_name and chinese_name != class_name:
                lines.append(f"**中文名称:** {chinese_name}\n")

            if description:
                lines.append(f"**功能描述:** {description}\n")

            if algebra:
                lines.append(f"**关系代数表达:**\n```\n{algebra}\n```\n")

            if opt_goal:
                lines.append(f"**优化目标:** {opt_goal}\n")

            if dependencies:
                lines.append(f"**依赖资源:** {', '.join(dependencies)}\n")

            if conditions:
                lines.append(f"**触发条件:**\n")
                for cond in conditions:
                    lines.append(f"- {cond}")

            if example:
                lines.append(f"\n**优化示例:**\n```sql\n{example}\n```\n")

            lines.append("---")

        section_num += 1

    # Optimization principles
    lines.append("\n## 🔬 三、优化原理总结\n")

    # Analyze optimization goals
    goals = {}
    for rule in all_rules:
        goal = rule.get("optimization_goal", "其他")
        if goal:
            goals[goal] = goals.get(goal, 0) + 1

    lines.append("### 3.1 优化目标分布\n")
    lines.append("| 优化目标 | 规则数量 |\n|----------|----------|\n")
    for goal, count in sorted(goals.items(), key=lambda x: -x[1])[:10]:
        lines.append(f"| {goal} | {count} |")

    lines.append("\n### 3.2 关系代数优化原理\n")
    lines.append("""
查询优化的核心是利用关系代数的等价变换规则：

1. **选择下推 (Selection Pushdown)**
   - 原理: 尽早过滤减少中间结果
   - 公式: `σ_{p}(R ⋈ S) = R ⋈ σ_{p}(S)` (当p只涉及S的属性时)

2. **投影下推 (Projection Pushdown)**
   - 原理: 只保留需要的列
   - 公式: `π_{A}(R ⋈ S) = π_{A}(R ⋈ π_{A∩attr(S)}(S))`

3. **连接重排序 (Join Reordering)**
   - 原理: 选择产生最小中间结果的连接顺序
   - 公式: `(R ⋈ S) ⋈ T` 与 `R ⋈ (S ⋈ T)` 可能代价不同

4. **聚合下推 (Aggregation Pushdown)**
   - 原理: 先聚合减少数据量
   - 公式: 在特定条件下 `γ_{g,a}(R ⋈ S) = γ_{g,a}(R) ⋈ S`
""")

    # Comparison section
    lines.append("\n## 🔍 四、与其他引擎对比\n")

    if engine_name == "StarRocks":
        lines.append("""
### 4.1 规则完整性对比

| 维度 | StarRocks | Doris | Calcite |
|------|-----------|-------|---------|
| 规则总数 | 269 | 463 | 155 |
| 转换规则 | 224 | 191(重写)+82(探索) | 155 |
| 实现规则 | 45 | 54 | 框架提供 |

### 4.2 特点总结

**StarRocks优势:**
- 规则分类清晰（转换/实现）
- Cascades实现完整
- Memo管理高效

**可借鉴之处:**
- Doris的细粒度规则分类
- Calcite的Trait系统
""")
    elif engine_name == "Doris":
        lines.append("""
### 4.1 规则完整性对比

| 规则类别 | Doris | StarRocks | 说明 |
|----------|-------|-----------|------|
| 分析规则 | 48 | - | 绑定和语义分析 |
| 探索规则 | 82 | - | 计划空间探索 |
| 重写规则 | 191 | 224 | 逻辑等价变换 |
| 实现规则 | 54 | 45 | 物理实现选择 |
| 表达式规则 | 88 | - | 标量优化 |

### 4.2 特点总结

**Doris优势:**
- 规则最丰富，覆盖最全面
- 分类细致，职责清晰
- 表达式优化独立

**Nereids架构特点:**
- 现代Cascades实现
- 与旧优化器共存
""")
    elif engine_name == "Calcite":
        lines.append("""
### 4.1 框架特点

Calcite作为SQL优化框架，与其他数据库优化器的定位不同：

| 特性 | Calcite | StarRocks/Doris |
|------|---------|-----------------|
| 定位 | 框架/库 | 完整数据库 |
| Memo | 无内置 | 内置支持 |
| Trait系统 | 完整 | 有属性系统 |
| 扩展性 | 极高 | 中等 |

### 4.2 使用场景

**适合使用Calcite:**
- 构建新的SQL引擎
- 需要SQL解析和验证
- 需要可插拔的优化器

**Calcite用户:**
- Apache Hive
- Apache Flink
- Apache Drill
- Apache Kylin
""")

    # Reference
    lines.append("\n## 📖 五、参考资料\n")
    lines.append("""
### 5.1 关系代数基础

1. **选择操作 σ**: `σ_{condition}(R)` - 从关系R中选择满足条件的元组
2. **投影操作 π**: `π_{attributes}(R)` - 从关系R中选择指定属性
3. **连接操作 ⋈**: `R ⋈_{condition} S` - 连接两个关系
4. **聚合操作 γ**: `γ_{group, agg}(R)` - 分组聚合

### 5.2 优化理论

- **Volcano优化器**: Exodus项目提出的优化器框架
- **Cascades优化器**: Volcano的改进版本，使用Memo和Top-Down搜索
- **代价模型**: 基于统计信息估算查询执行代价
- **启发式优化**: 基于规则的优化，不依赖代价模型

### 5.3 相关论文

1. "The Cascades Framework for Query Optimization" - Graefe, 1995
2. "Volcano-An Extensible and Parallel Query Evaluation System" - Graefe, 1994
3. "Access Path Selection in a Relational Database Management System" - Selinger, 1979
""")

    lines.append("\n---\n")
    lines.append(f"*本报告由 Optimizer Expert Analyzer 自动生成*\n")
    lines.append(f"*使用关系代数符号描述规则语义*\n")

    return "\n".join(lines)


def main():
    """Generate detailed reports for all engines."""
    import argparse

    parser = argparse.ArgumentParser(description="生成优化规则详细分析报告(含关系代数)")
    parser.add_argument("--engines", nargs="+", default=["StarRocks", "Calcite", "Doris"],
                        help="要分析的引擎")
    parser.add_argument("--output", default="./analysis_output/detailed_reports",
                        help="输出目录")
    parser.add_argument("--llm", action="store_true",
                        help="使用LLM进行深度分析")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("优化规则详细分析报告生成器")
    print("(包含关系代数表达式)")
    print("=" * 60)

    generated = []

    for engine_name in args.engines:
        if engine_name not in ENGINE_PATHS:
            print(f"未知引擎: {engine_name}")
            continue

        source_path = ENGINE_PATHS[engine_name]
        if not Path(source_path).exists():
            print(f"源码不存在: {source_path}")
            continue

        output_file = generate_detailed_report(
            engine_name, source_path, args.output, args.llm
        )
        generated.append(output_file)

    print("\n" + "=" * 60)
    print("报告生成完成")
    print("=" * 60)
    for f in generated:
        print(f"  - {f}")


if __name__ == "__main__":
    main()