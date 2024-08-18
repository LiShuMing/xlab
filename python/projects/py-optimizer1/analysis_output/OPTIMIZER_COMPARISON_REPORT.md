# Optimizer Analysis Report

## StarRocks vs Calcite vs Doris

**Generated:** 2026-04-06

---

## Executive Summary

This report compares the optimizer architectures of three systems:
- **StarRocks** - Columnar OLAP database with Cascades-style optimizer
- **Apache Calcite** - SQL parser and optimizer framework
- **Apache Doris** - Columnar OLAP database with Nereids optimizer (Cascades-style)

---

## 1. Engine Classification

| Dimension | StarRocks | Calcite | Doris |
|-----------|-----------|---------|-------|
| **Type** | Columnar OLAP | Framework | Columnar OLAP |
| **Optimizer Style** | Cascades | Volcano | Cascades |
| **Language** | Java (FE) | Java | Java (FE) |
| **Source Path** | `/home/lism/work/starrocks` | `/home/lism/work/calcite` | `/home/lism/work/doris` |

---

## 2. Optimizer Structure

### StarRocks
```
fe/fe-core/src/main/java/com/starrocks/sql/optimizer/
├── Optimizer.java          # Main entry
├── Memo.java               # Memoization structure
├── Group.java              # Expression groups
├── GroupExpression.java    # Group expressions
├── rule/
│   ├── transformation/     # 224 rules
│   └── implementation/     # 45 rules
├── cost/                   # Cost model
├── statistics/             # Statistics
└── property/               # Physical properties
```

### Calcite
```
core/src/main/java/org/apache/calcite/
├── rel/rules/              # 155 rules
├── plan/                   # Planner infrastructure
│   ├── RelOptPlanner.java
│   ├── RelOptRule.java
│   └── RelTrait.java
└── tools/
    └── Planner.java        # Main entry
```

### Doris (Nereids)
```
fe/fe-core/src/main/java/org/apache/doris/nereids/
├── NereidsPlanner.java     # Main entry
├── CascadesContext.java    # Memo management
├── rules/
│   ├── analysis/           # 48 rules
│   ├── exploration/        # 82 rules
│   ├── implementation/     # 54 rules
│   ├── rewrite/            # 191 rules
│   └── expression/         # 88 rules
├── cost/                   # Cost model
└── statistics/             # Statistics
```

---

## 3. Rule Coverage

| Rule Type | StarRocks | Calcite | Doris |
|-----------|-----------|---------|-------|
| **Transformation/Logical** | 224 | 155 | 191 (rewrite) |
| **Implementation/Physical** | 45 | - | 54 |
| **Exploration** | - | - | 82 |
| **Analysis** | - | - | 48 |
| **Expression** | - | - | 88 |
| **Total** | **269** | **155** | **463** |

### Key Observations:
1. **Doris has the most comprehensive rule set** (463 rules vs StarRocks 269)
2. **StarRocks has cleaner separation** between transformation and implementation
3. **Calcite provides framework rules** that users extend
4. **Doris categorizes rules more finely** (5 categories vs 2)

---

## 4. Optimizer Style Comparison

### Cascades-style (StarRocks, Doris)
- Top-down search with memoization
- Groups and GroupExpressions
- Explicit property enforcement
- Cost-based pruning

### Volcano-style (Calcite)
- Bottom-up or top-down search
- Trait-based optimization
- Convention conversion
- Pluggable rule system

---

## 5. Lifecycle Phases

### StarRocks Lifecycle
```
SQL Input → Parsing → Analysis → LogicalPlanning → PhysicalPlanning → Execution
                              ↑                       ↑
                        Logical/Physical Boundary    Cost-based Selection
```

### Calcite Lifecycle
```
SQL Input → Parsing → Validation → Logical Planning → Physical Planning → Execution
                                    ↑                    ↑
                              RelNode tree          RelTrait conversion
```

### Doris (Nereids) Lifecycle
```
SQL Input → Parsing → Analysis → LogicalPlanning → Exploration → Implementation → Execution
                              ↑                    ↑              ↑
                        Bind/Analyze         Memo search    Physical plan
```

---

## 6. Key Architectural Differences

### StarRocks
- ✅ Clear Cascades implementation with Memo
- ✅ Separate transformation and implementation rules
- ✅ Integrated cost model with CPU/IO/Network factors
- ✅ Statistics integration with histogram support
- ✅ Physical properties (distribution, ordering)

### Calcite
- ✅ Framework design - highly extensible
- ✅ Trait-based optimization (convention, collation, distribution)
- ✅ Large ecosystem (Hive, Drill, Flink use it)
- ⚠️ No built-in memoization
- ⚠️ Cost model is pluggable, not built-in

### Doris
- ✅ Most comprehensive rule set
- ✅ Fine-grained rule categorization
- ✅ Modern Nereids optimizer (Cascades)
- ✅ Integrated statistics and cost model
- ✅ Support for both legacy and new optimizer

---

## 7. Observability

| Feature | StarRocks | Calcite | Doris |
|---------|-----------|---------|-------|
| **EXPLAIN** | ✅ | ✅ | ✅ |
| **EXPLAIN ANALYZE** | ✅ | ⚠️ | ✅ |
| **Optimizer Trace** | ✅ | ⚠️ | ✅ |
| **Memo Dump** | ✅ | ❌ | ✅ |
| **Session Controls** | ✅ | ✅ | ✅ |

---

## 8. Recommendations

### For Learning Optimizer Design
1. **Start with Calcite** - well-documented, simpler trait system
2. **Study StarRocks** - clean Cascades implementation
3. **Explore Doris** - comprehensive rule coverage

### For Building a New Optimizer
1. **Use Calcite as foundation** if building on JVM
2. **Copy StarRocks structure** for Cascades-style
3. **Reference Doris rules** for comprehensive coverage

### For OLAP Workloads
- **StarRocks or Doris** are better suited
- Both have columnar-aware optimizations
- Both support distributed execution

---

## 9. Source References

### StarRocks Key Files
- `fe/fe-core/src/main/java/com/starrocks/sql/optimizer/Optimizer.java`
- `fe/fe-core/src/main/java/com/starrocks/sql/optimizer/Memo.java`
- `fe/fe-core/src/main/java/com/starrocks/sql/optimizer/rule/transformation/`

### Calcite Key Files
- `core/src/main/java/org/apache/calcite/tools/Planner.java`
- `core/src/main/java/org/apache/calcite/plan/RelOptPlanner.java`
- `core/src/main/java/org/apache/calcite/rel/rules/`

### Doris Key Files
- `fe/fe-core/src/main/java/org/apache/doris/nereids/NereidsPlanner.java`
- `fe/fe-core/src/main/java/org/apache/doris/nereids/CascadesContext.java`
- `fe/fe-core/src/main/java/org/apache/doris/nereids/rules/`

---

## 10. Analysis Confidence

| Engine | Structure | Rules | Lifecycle | Cost | Overall |
|--------|-----------|-------|-----------|------|---------|
| StarRocks | High | High | Medium | Medium | **Medium** |
| Calcite | High | High | High | Low | **Medium** |
| Doris | High | High | Medium | Medium | **Medium** |

---

*Generated by Optimizer Expert Analyzer Agent*