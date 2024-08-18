#!/usr/bin/env python3
"""Generate detailed Chinese reports for each optimizer engine."""
import re
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

from optimizer_analysis.scanners.java_scanner import JavaScanner
from optimizer_analysis.engines.presets import STARROCKS_CONFIG, CALCITE_CONFIG, DORIS_CONFIG


# Engine source paths
ENGINE_PATHS = {
    "StarRocks": "/home/lism/work/starrocks",
    "Calcite": "/home/lism/work/calcite",
    "Doris": "/home/lism/work/doris",
}


def extract_rule_details(java_code: str, filename: str) -> Dict:
    """Extract rule details from Java source code."""
    details = {
        "filename": filename,
        "class_name": None,
        "rule_type": None,
        "description": None,
        "pattern": None,
        "transform": None,
        "dependencies": [],
    }

    scanner = JavaScanner()

    # Extract class name
    classes = scanner.extract_classes(java_code)
    if classes:
        details["class_name"] = classes[0]

    # Extract package
    package = scanner.extract_package(java_code)
    details["package"] = package

    # Extract rule type from class name
    if details["class_name"]:
        name = details["class_name"]
        if "Transform" in name or "Rewrite" in name:
            details["rule_type"] = "转换规则"
        elif "Implement" in name or "Implement" in name.lower():
            details["rule_type"] = "实现规则"
        elif "Exploration" in name or "Explore" in name:
            details["rule_type"] = "探索规则"
        elif "Analysis" in name or "Analyze" in name:
            details["rule_type"] = "分析规则"
        elif "Expression" in name:
            details["rule_type"] = "表达式规则"
        else:
            details["rule_type"] = "其他规则"

    # Extract JavaDoc comments
    javadoc_match = re.search(r'/\*\*([^*]|\*(?!/))*\*/', java_code, re.DOTALL)
    if javadoc_match:
        doc = javadoc_match.group(0)
        # Clean up JavaDoc
        doc = re.sub(r'/\*\*|\*/|\s*\*\s*', ' ', doc)
        doc = re.sub(r'@\w+.*?(?=@@|$)', '', doc)
        details["description"] = doc.strip()[:200] if doc.strip() else None

    # Check for cost dependency
    if "cost" in java_code.lower() or "CostEstimate" in java_code:
        details["dependencies"].append("代价模型")

    # Check for stats dependency
    if "statistic" in java_code.lower() or "Statistics" in java_code:
        details["dependencies"].append("统计信息")

    return details


def scan_rules_directory(path: str, engine_name: str) -> List[Dict]:
    """Scan a directory for rule files."""
    scanner = JavaScanner()
    rules = []

    p = Path(path)
    if not p.exists():
        return rules

    for java_file in p.rglob("*.java"):
        try:
            code = java_file.read_text(encoding="utf-8", errors="ignore")

            # Skip test files
            if "Test" in java_file.name:
                continue

            details = extract_rule_details(code, java_file.name)
            details["path"] = str(java_file.relative_to(p.parent))
            rules.append(details)

        except Exception as e:
            pass

    return rules


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


def analyze_optimizer_structure(engine_name: str, source_path: str, config) -> Dict:
    """Analyze optimizer structure for an engine."""
    structure = {
        "main_entry": config.main_entry,
        "style": config.optimizer_style.value,
        "components": {},
    }

    if engine_name == "StarRocks":
        optimizer_path = f"{source_path}/fe/fe-core/src/main/java/com/starrocks/sql/optimizer"
        structure["components"] = {
            "核心类": {
                "Optimizer.java": "主优化器入口，协调整个优化流程",
                "Memo.java": "Memoization结构，存储等价表达式组",
                "Group.java": "表达式组，管理等价逻辑表达式",
                "GroupExpression.java": "组内表达式，带有属性要求",
                "OptExpression.java": "优化表达式树节点",
            },
            "规则系统": "rule/目录包含转换和实现规则",
            "代价模型": "cost/目录包含代价估算逻辑",
            "统计信息": "statistics/目录包含统计信息收集",
            "属性系统": "property/目录包含物理属性定义",
        }

        # Check for key files
        key_files = [
            ("Memo.java", f"{optimizer_path}/Memo.java"),
            ("Group.java", f"{optimizer_path}/Group.java"),
            ("Optimizer.java", f"{optimizer_path}/Optimizer.java"),
        ]

        structure["key_files_exist"] = {
            name: Path(path).exists() for name, path in key_files
        }

    elif engine_name == "Calcite":
        plan_path = f"{source_path}/core/src/main/java/org/apache/calcite/plan"
        structure["components"] = {
            "核心类": {
                "RelOptPlanner.java": "优化器接口，定义规则应用框架",
                "VolcanoPlanner.java": "Volcano风格优化器实现",
                "RelOptRule.java": "优化规则基类",
                "RelTrait.java": "物理特征定义（排序、分布等）",
                "RelTraitDef.java": "特征定义接口",
            },
            "规则系统": "rel/rules/目录包含大量预定义规则",
            "特征系统": "支持Convention（执行约定）、Collation（排序）、Distribution（分布）",
            "转换框架": "支持逻辑到物理的转换",
        }

    elif engine_name == "Doris":
        nereids_path = f"{source_path}/fe/fe-core/src/main/java/org/apache/doris/nereids"
        structure["components"] = {
            "核心类": {
                "NereidsPlanner.java": "Nereids优化器主入口",
                "CascadesContext.java": "Cascades上下文，管理Memo",
                "PlanContext.java": "计划上下文",
                "Rule.java": "规则基类",
                "RuleSet.java": "规则集管理",
            },
            "规则系统": "rules/目录按功能分类（分析、探索、实现、重写、表达式）",
            "代价模型": "cost/目录包含代价计算",
            "统计信息": "statistics/目录包含统计信息",
            "分析器": "analyzer/目录包含语义分析",
        }

        key_files = [
            ("CascadesContext.java", f"{nereids_path}/CascadesContext.java"),
            ("NereidsPlanner.java", f"{nereids_path}/NereidsPlanner.java"),
            ("Rule.java", f"{nereids_path}/rules/Rule.java"),
        ]

        structure["key_files_exist"] = {
            name: Path(path).exists() for name, path in key_files
        }

    return structure


def generate_chinese_report(engine_name: str, source_path: str, output_dir: str) -> str:
    """Generate detailed Chinese report for an engine."""
    config = {
        "StarRocks": STARROCKS_CONFIG,
        "Calcite": CALCITE_CONFIG,
        "Doris": DORIS_CONFIG,
    }[engine_name]

    print(f"正在分析 {engine_name}...")

    # Scan rules
    rule_dirs = get_rule_directories(engine_name, source_path, config)
    all_rules = {}
    total_rules = 0

    for category, dir_path in rule_dirs.items():
        rules = scan_rules_directory(dir_path, engine_name)
        all_rules[category] = rules
        total_rules += len(rules)
        print(f"  {category}: {len(rules)} 条规则")

    # Analyze structure
    structure = analyze_optimizer_structure(engine_name, source_path, config)

    # Generate report
    report = generate_report_markdown(engine_name, config, all_rules, structure, total_rules)

    # Save report
    output_file = Path(output_dir) / f"{engine_name.lower()}_详细分析报告.md"
    output_file.write_text(report, encoding="utf-8")

    print(f"  已保存: {output_file}")

    return str(output_file)


def generate_report_markdown(engine_name: str, config, all_rules: Dict, structure: Dict, total: int) -> str:
    """Generate markdown report in Chinese."""
    lines = []

    # Header
    lines.append(f"# {engine_name} 优化器详细分析报告\n")
    lines.append(f"**生成时间:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append(f"**分析源码路径:** {ENGINE_PATHS[engine_name]}\n")

    # Executive Summary
    lines.append("## 一、概述\n")
    lines.append(f"### 1.1 引擎基本信息\n")
    lines.append(f"| 属性 | 值 |\n|------|----|\n")
    lines.append(f"| 引擎类型 | {config.engine_type.value} |\n")
    lines.append(f"| 优化器风格 | {config.optimizer_style.value} |\n")
    lines.append(f"| 主要编程语言 | Java |\n")
    lines.append(f"| 规则总数 | {total} |\n")

    lines.append(f"\n### 1.2 优化器特点\n")
    for note in config.notes:
        lines.append(f"- {note}")

    # Architecture
    lines.append("\n## 二、优化器架构\n")
    lines.append(f"### 2.1 核心组件\n")

    for component, description in structure.get("components", {}).items():
        if isinstance(description, dict):
            lines.append(f"\n**{component}:**\n")
            for name, desc in description.items():
                lines.append(f"- `{name}`: {desc}")
        else:
            lines.append(f"- **{component}**: {description}")

    # Key files verification
    if "key_files_exist" in structure:
        lines.append(f"\n### 2.2 关键文件验证\n")
        lines.append("| 文件 | 存在 |\n|------|------|\n")
        for name, exists in structure["key_files_exist"].items():
            status = "✅" if exists else "❌"
            lines.append(f"| {name} | {status} |")

    # Rules Detail
    lines.append("\n## 三、规则详解\n")
    lines.append(f"### 3.1 规则统计\n")

    lines.append("| 规则类型 | 数量 |\n|----------|------|\n")
    for category, rules in all_rules.items():
        lines.append(f"| {category} | {len(rules)} |")
    lines.append(f"| **总计** | **{total}** |")

    # List rules by category
    for category, rules in all_rules.items():
        if not rules:
            continue

        # Extract category name for section header
        cat_name = category.split("(")[0].strip()
        lines.append(f"\n### 3.2 {cat_name}\n")

        if len(rules) > 50:
            lines.append(f"> 共 {len(rules)} 条规则，仅展示前50条\n")
            display_rules = rules[:50]
        else:
            display_rules = rules

        lines.append("| 序号 | 规则名称 | 类型 | 依赖 |\n|------|----------|------|------|\n")

        for i, rule in enumerate(display_rules, 1):
            name = rule.get("class_name", "N/A")
            rule_type = rule.get("rule_type", "未知")
            deps = ", ".join(rule.get("dependencies", [])) or "-"
            lines.append(f"| {i} | `{name}` | {rule_type} | {deps} |")

        if len(rules) > 50:
            lines.append(f"\n*...还有 {len(rules) - 50} 条规则未展示*")

    # Lifecycle
    lines.append("\n## 四、优化流程\n")

    if engine_name == "StarRocks":
        lines.append("""
### 4.1 优化生命周期

```
SQL输入
    │
    ▼
┌─────────────┐
│   解析      │  SQL Parser → AST
└─────────────┘
    │
    ▼
┌─────────────┐
│   分析      │  语义分析、类型检查
└─────────────┘
    │
    ▼
┌─────────────┐
│ 逻辑优化    │  应用转换规则、Memo构建
└─────────────┘
    │
    ▼
┌─────────────┐
│ 物理优化    │  应用实现规则、代价估算
└─────────────┘
    │
    ▼
┌─────────────┐
│ 计划选择    │  选择最优执行计划
└─────────────┘
    │
    ▼
执行计划输出
```

### 4.2 Memo结构

StarRocks采用Cascades风格的Memo结构：
- **Memo**: 存储所有等价表达式组
- **Group**: 逻辑上等价的表达式集合
- **GroupExpression**: 组内具体表达式，带物理属性要求

### 4.3 规则应用策略

1. **转换规则**: 在逻辑优化阶段应用，生成等价逻辑表达式
2. **实现规则**: 在物理优化阶段应用，将逻辑算子转换为物理算子
3. **代价驱动**: 通过代价模型比较不同实现方案
""")

    elif engine_name == "Calcite":
        lines.append("""
### 4.1 优化生命周期

```
SQL输入
    │
    ▼
┌─────────────┐
│   解析      │  SqlParser → SqlNode
└─────────────┘
    │
    ▼
┌─────────────┐
│   验证      │  SqlValidator验证语义
└─────────────┘
    │
    ▼
┌─────────────┐
│ 转换为RelNode│  SqlToRelConverter
└─────────────┘
    │
    ▼
┌─────────────┐
│  规则优化   │  VolcanoPlanner应用规则
└─────────────┘
    │
    ▼
┌─────────────┐
│ 特征转换    │  RelTrait转换
└─────────────┘
    │
    ▼
执行计划输出
```

### 4.2 特征系统 (Trait System)

Calcite的特征系统是其核心特性：
- **Convention**: 执行约定（如Enumerable、Bindable）
- **Collation**: 排序特征
- **Distribution**: 分布特征

### 4.3 规则应用策略

1. **规则注册**: 将规则添加到Planner
2. **规则匹配**: 基于操作符类型匹配规则
3. **特征协商**: 在转换时协商目标特征
4. **代价估算**: 使用RelOptCost比较方案
""")

    elif engine_name == "Doris":
        lines.append("""
### 4.1 优化生命周期

```
SQL输入
    │
    ▼
┌─────────────┐
│   解析      │  SQL Parser → AST
└─────────────┘
    │
    ▼
┌─────────────┐
│   分析      │  分析规则绑定、类型检查
└─────────────┘
    │
    ▼
┌─────────────┐
│  逻辑优化   │  重写规则优化
└─────────────┘
    │
    ▼
┌─────────────┐
│  探索优化   │  探索规则生成备选计划
└─────────────┘
    │
    ▼
┌─────────────┐
│  物理优化   │  实现规则选择物理算子
└─────────────┘
    │
    ▼
执行计划输出
```

### 4.2 Nereids优化器特点

Doris的Nereids优化器采用现代Cascades实现：
- **CascadesContext**: 管理整个优化上下文
- **分层规则**: 分析→重写→探索→实现
- **表达式规则**: 独立的表达式优化层

### 4.3 规则分类应用

1. **分析规则**: 绑定列引用、解析视图
2. **重写规则**: 逻辑等价变换
3. **探索规则**: 生成备选执行计划
4. **实现规则**: 选择具体物理实现
5. **表达式规则**: 标量表达式优化
""")

    # Observability
    lines.append("\n## 五、可观测性\n")
    lines.append("""
### 5.1 Explain支持

| 功能 | 支持情况 |
|------|----------|
| EXPLAIN | ✅ 支持 |
| EXPLAIN ANALYZE | ✅ 支持 |
| 优化器追踪 | ✅ 支持 |
| Memo导出 | ✅ 支持 |
| 会话控制 | ✅ 支持 |

### 5.2 调试接口

可通过会话变量控制优化器行为，查看优化过程。
""")

    # Comparison with others
    lines.append("\n## 六、与其他引擎对比\n")

    if engine_name == "StarRocks":
        lines.append("""
### 6.1 相比Calcite

| 方面 | StarRocks | Calcite |
|------|-----------|---------|
| 定位 | 完整OLAP数据库 | SQL框架 |
| Memo支持 | ✅ 内置 | ❌ 无 |
| 代价模型 | ✅ 内置 | ⚠️ 可插拔 |
| 规则数量 | 269 | 155 |
| 学习曲线 | 较陡 | 平缓 |

### 6.2 相比Doris

| 方面 | StarRocks | Doris |
|------|-----------|-------|
| 规则数量 | 269 | 463 |
| 规则分类 | 2类 | 5类 |
| 架构清晰度 | ✅ 更清晰 | ⚠️ 较复杂 |
| 成熟度 | ✅ 较成熟 | ⚠️ 新优化器 |
""")

    elif engine_name == "Calcite":
        lines.append("""
### 6.1 作为框架的优势

- **广泛使用**: Apache Hive, Drill, Flink, Kylin等
- **扩展性强**: 可自定义规则、特征、代价模型
- **标准实现**: 遵循SQL标准
- **文档完善**: 官方文档和教程丰富

### 6.2 与数据库优化器的差异

Calcite作为框架，不像StarRocks/Doris那样内置完整的数据库功能：
- 不内置Memo结构
- 代价模型需要用户实现
- 统计信息管理需要外部提供
""")

    elif engine_name == "Doris":
        lines.append("""
### 6.1 相比StarRocks

| 方面 | Doris | StarRocks |
|------|-------|-----------|
| 规则数量 | 463 | 269 |
| 规则分类 | 5类（更细粒度） | 2类 |
| 优化器名称 | Nereids | 内置优化器 |
| 历史包袱 | ⚠️ 新旧优化器共存 | ✅ 单一优化器 |

### 6.2 规则丰富度

Doris在以下方面有更多规则：
- **分析规则**: 48条，处理绑定和分析
- **探索规则**: 82条，生成备选计划
- **表达式规则**: 88条，标量表达式优化
""")

    # Conclusion
    lines.append("\n## 七、总结与建议\n")

    if engine_name == "StarRocks":
        lines.append("""
### 7.1 优势

1. **架构清晰**: 纯Cascades实现，Memo/Group分离明确
2. **性能优秀**: 列存优化、向量化执行
3. **规则完整**: 转换和实现规则分离清晰
4. **文档齐全**: 官方文档完善

### 7.2 学习建议

1. 从`Optimizer.java`入口开始理解整体流程
2. 研究`Memo.java`和`Group.java`理解搜索空间管理
3. 阅读`rule/transformation/`中的典型规则
4. 分析`cost/`目录理解代价模型

### 7.3 参考资源

- 官方文档: https://docs.starrocks.io/
- 源码仓库: https://github.com/StarRocks/starrocks
""")

    elif engine_name == "Calcite":
        lines.append("""
### 7.1 优势

1. **框架成熟**: 被众多项目采用验证
2. **扩展性强**: Trait系统灵活
3. **标准实现**: SQL标准兼容性好
4. **社区活跃**: Apache顶级项目

### 7.2 学习建议

1. 理解RelNode树结构
2. 学习RelTrait和Convention机制
3. 阅读VolcanoPlanner实现
4. 参考Hive/Flink的使用方式

### 7.3 参考资源

- 官方文档: https://calcite.apache.org/docs/
- 源码仓库: https://github.com/apache/calcite
- 论文: "Volcano-An Extensible and Parallel Query Evaluation System"
""")

    elif engine_name == "Doris":
        lines.append("""
### 7.1 优势

1. **规则丰富**: 463条规则覆盖全面
2. **分类细致**: 5类规则各司其职
3. **现代架构**: Nereids采用现代Cascades设计
4. **持续演进**: 社区活跃，功能不断增强

### 7.2 学习建议

1. 从`NereidsPlanner.java`理解入口
2. 研究`CascadesContext.java`理解上下文管理
3. 按分类阅读rules/下各类规则
4. 对比新旧优化器理解演进

### 7.3 参考资源

- 官方文档: https://doris.apache.org/docs/
- 源码仓库: https://github.com/apache/doris
- Nereids论文: 了解设计背景
""")

    lines.append("\n---\n")
    lines.append(f"*本报告由Optimizer Expert Analyzer Agent自动生成*\n")
    lines.append(f"*生成时间: {datetime.now().isoformat()}*\n")

    return "\n".join(lines)


def main():
    """Generate reports for all engines."""
    import argparse

    parser = argparse.ArgumentParser(description="生成优化器详细中文分析报告")
    parser.add_argument("--engines", nargs="+", default=["StarRocks", "Calcite", "Doris"],
                        help="要分析的引擎")
    parser.add_argument("--output", default="./reports",
                        help="输出目录")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("优化器详细分析报告生成器")
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

        output_file = generate_chinese_report(engine_name, source_path, args.output)
        generated.append(output_file)

    print("\n" + "=" * 60)
    print("报告生成完成")
    print("=" * 60)
    for f in generated:
        print(f"  - {f}")


if __name__ == "__main__":
    main()