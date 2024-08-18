# 第9章：优化器框架

> DuckDB 的优化器不是一座不可逾越的黑盒——它是一条精心排序的流水线，33 个优化步骤依次执行，每步做一件事。理解这个顺序，就理解了 DuckDB 的优化哲学：先简化表达式，再调整结构，最后精打细算。

## 9.1 优化器的完整流水线

```cpp
// src/optimizer/optimizer.cpp:120-346
void Optimizer::RunBuiltInOptimizers() {
    // Phase 1: 表达式重写（不改变计划结构）
    EXPRESSION_REWRITER           // 23 条表达式简化规则

    // Phase 2: CTE 与聚合改写
    CTE_INLINING                  // CTE 内联替代物化
    AGGREGATE_FUNCTION_REWRITER   // AVG→SUM/COUNT, SUM(x+C)→SUM(x)+C*COUNT(x)

    // Phase 3: 过滤器移动
    FILTER_PULLUP                 // 过滤上拉（为下推做准备）
    FILTER_PUSHDOWN               // 过滤下推到最接近数据源的位置
    CTE_FILTER_PUSHER             // 过滤推入 CTE

    // Phase 4: 专用重写
    REGEX_RANGE                   // 正则表达式→范围过滤
    IN_CLAUSE                     // IN 子句重写
    DELIMINATOR                   // 消除冗余 DelimGet/DelimJoin
    CTE_INLINING                  // 二次 CTE 内联
    EMPTY_RESULT_PULLUP           // 空结果上拉
    WINDOW_SELF_JOIN              // 窗口函数→自连接
    PROJECTION_PULLUP             // 投影上拉

    // Phase 5: Join 优化
    OUTER_JOIN_SIMPLIFICATION     // FULL→LEFT→INNER 简化
    JOIN_ORDER                    // Join 排序（DP + Greedy）
    JOIN_ELIMINATION              // Join 消除
    UNNEST_REWRITER               // UNNEST 重写

    // Phase 6: 列生命周期
    UNUSED_COLUMNS                // 列裁剪
    DUPLICATE_GROUPS              // 消除重复分组键
    COMMON_SUBEXPRESSIONS         // 公共子表达式消除
    COLUMN_LIFETIME               // 列生命周期分析→投影映射
    BUILD_SIDE_PROBE_SIDE         // 构建/探测端选择

    // Phase 7: 后期优化
    COMMON_SUBPLAN                // 公共子计划→物化 CTE
    LIMIT_PUSHDOWN                // LIMIT 下推
    ROW_GROUP_PRUNER              // RowGroup 裁剪
    SAMPLING_PUSHDOWN             // 采样下推
    TOP_N                         // ORDER BY+LIMIT→TopN
    LATE_MATERIALIZATION          // 延迟物化
    STATISTICS_PROPAGATION        // 统计信息传播
    TOP_N_WINDOW_ELIMINATION      // ROW_NUMBER→聚合
    COMMON_AGGREGATE              // 消除重复聚合
    COLUMN_LIFETIME               // 二次列生命周期分析
    REORDER_FILTER                // 过滤条件重排序
    JOIN_FILTER_PUSHDOWN          // Join 过滤下推
    ROW_NUMBER_REWRITER           // ROW_NUMBER→虚拟列
}
```

### 顺序的重要性

优化步骤的顺序不是随意的。几个关键依赖：

- **FILTER_PULLUP 必须在 FILTER_PUSHDOWN 之前**：先把嵌入在 Join/Projection 中的过滤器"拉"出来，才能统一"推"到最底层的 Scan 位置
- **JOIN_ORDER 必须在 UNUSED_COLUMNS 之后**：Join 排序需要知道哪些列被下游使用，列裁剪提前执行可以减少 Join 排序的搜索空间
- **STATISTICS_PROPAGATION 必须在 TOP_N_WINDOW_ELIMINATION 之前**：TopN 窗口消除需要准确的基数统计来判断是否值得转换
- **COLUMN_LIFETIME 执行两次**：第一次在 Join 排序后建立投影映射，第二次在所有重写完成后更新映射

### RunOptimizer 的安全网

```cpp
// src/optimizer/optimizer.cpp:98-114
void Optimizer::RunOptimizer(OptimizerType type, const std::function<void()> &callback) {
    if (context.IsInterrupted()) {
        throw InterruptException();  // 支持查询中断
    }
    if (OptimizerDisabled(type)) {
        return;  // 用户可以通过 SET disabled_optimizers 跳过特定优化
    }
    auto &profiler = QueryProfiler::Get(context);
    profiler.StartPhase(MetricsUtils::GetOptimizerMetricByType(type));
    callback();
    profiler.EndPhase();
    if (plan) {
        Verify(*plan);  // 每步后验证 ColumnBinding 一致性
    }
}
```

每个优化步骤执行后，`Verify` 检查 ColumnBinding 的一致性——确保没有任何优化规则破坏了列引用的正确性。这是 DuckDB 优化器可靠性的关键保障。

## 9.2 ExpressionRewriter：23 条表达式简化规则

```cpp
// src/optimizer/optimizer.cpp:52-76
Optimizer::Optimizer(Binder &binder, ClientContext &context) : context(context), binder(binder), rewriter(context) {
    rewriter.rules.push_back(make_uniq<ConstantOrderNormalizationRule>(rewriter));
    rewriter.rules.push_back(make_uniq<ConstantFoldingRule>(rewriter));
    rewriter.rules.push_back(make_uniq<DistributivityRule>(rewriter));
    rewriter.rules.push_back(make_uniq<ArithmeticSimplificationRule>(rewriter));
    rewriter.rules.push_back(make_uniq<CaseSimplificationRule>(rewriter));
    rewriter.rules.push_back(make_uniq<ConjunctionSimplificationRule>(rewriter));
    rewriter.rules.push_back(make_uniq<DatePartSimplificationRule>(rewriter));
    rewriter.rules.push_back(make_uniq<DateTruncSimplificationRule>(rewriter));
    rewriter.rules.push_back(make_uniq<ComparisonSimplificationRule>(rewriter));
    rewriter.rules.push_back(make_uniq<InClauseSimplificationRule>(rewriter));
    rewriter.rules.push_back(make_uniq<EqualOrNullSimplification>(rewriter));
    rewriter.rules.push_back(make_uniq<MoveConstantsRule>(rewriter));
    rewriter.rules.push_back(make_uniq<LikeOptimizationRule>(rewriter));
    rewriter.rules.push_back(make_uniq<OrderedAggregateOptimizer>(rewriter));
    rewriter.rules.push_back(make_uniq<DistinctAggregateOptimizer>(rewriter));
    rewriter.rules.push_back(make_uniq<DistinctWindowedOptimizer>(rewriter));
    rewriter.rules.push_back(make_uniq<RegexOptimizationRule>(rewriter));
    rewriter.rules.push_back(make_uniq<EmptyNeedleRemovalRule>(rewriter));
    rewriter.rules.push_back(make_uniq<EnumComparisonRule>(rewriter));
    rewriter.rules.push_back(make_uniq<JoinDependentFilterRule>(rewriter));
    rewriter.rules.push_back(make_uniq<TimeStampComparison>(rewriter));
    rewriter.rules.push_back(make_uniq<PredicateFactoringRule>(rewriter));
    rewriter.rules.push_back(make_uniq<ListComprehensionRewriteRule>(rewriter));
}
```

### 规则匹配引擎：ExpressionMatcher

每条规则定义一个**模式树**（Pattern Tree），描述它要匹配的表达式结构。`ExpressionRewriter` 遍历逻辑计划中的所有表达式，对每个表达式尝试所有规则的模式匹配。

```cpp
// src/optimizer/matcher/expression_matcher.cpp
// 模式匹配的核心是递归比较表达式结构和类型
// 例如 ConstantFoldingRule 匹配：FunctionExpression(常量参数...)
//   → 如果所有参数都是常量，直接计算结果替换
```

典型的规则实现：

```cpp
// 伪代码：ConstantFoldingRule
class ConstantFoldingRule : public Rule {
    // 模式：任意函数调用，所有参数为常量
    ConstantFoldingRule(ExpressionRewriter &rewriter) : Rule(rewriter) {
        root = make_uniq<ExpressionMatcher>(ExpressionType::FUNCTION);
        root->policy = SetMatcher::Policy::UNORDERED;  // 参数顺序无关
        // 子匹配器：每个参数必须是常量
        auto constant_matcher = make_uniq<ExpressionMatcher>(ExpressionType::VALUE_CONSTANT);
        root->matchers.push_back(std::move(constant_matcher));
    }

    unique_ptr<Expression> Apply(LogicalOperator &op, vector<Expression *> &bindings) override {
        auto &func = bindings[0]->Cast<BoundFunctionExpression>();
        // 检查所有参数是否为常量
        for (auto &child : func.children) {
            if (child->type != ExpressionType::VALUE_CONSTANT) return nullptr;
        }
        // 执行函数计算，替换整个函数调用为常量结果
        auto result = ExpressionExecutor::EvaluateScalar(context, func);
        return make_uniq<BoundConstantExpression>(result);
    }
};
```

`ConstantFoldingRule` 的效果：`2 + 3` → `5`，`UPPER('hello')` → `'HELLO'`。这些在编译期就能确定的值不需要在运行时计算。

### 规则迭代：固定点收敛

`ExpressionRewriter` 重复遍历计划树，直到**没有任何规则产生新的改写**为止：

```
Round 1: a + 0 → a (ArithmeticSimplification)
         1 + 2 → 3 (ConstantFolding)
Round 2: CASE WHEN true THEN x ELSE y → x (CaseSimplification)
Round 3: 无新改写 → 收敛，退出
```

这保证了组合效果——`CASE WHEN 1+1=2 THEN a+0 ELSE b` 会在第一轮折叠 `1+1→2`，第二轮简化 `CASE WHEN true`，第三轮消除 `a+0→a`。

## 9.3 OptimizerExtension：可插拔的优化扩展

```cpp
// src/optimizer/optimizer.cpp:348-376
unique_ptr<LogicalOperator> Optimizer::Optimize(unique_ptr<LogicalOperator> plan_p) {
    this->plan = std::move(plan_p);

    // 前置优化扩展（在内建优化之前执行）
    for (auto &ext : OptimizerExtension::Iterate(context)) {
        RunOptimizer(OptimizerType::EXTENSION, [&]() {
            if (ext.pre_optimize_function) {
                ext.pre_optimize_function(input, plan);
            }
        });
    }

    // 内建优化流水线
    RunBuiltInOptimizers();

    // 后置优化扩展（在内建优化之后执行）
    for (auto &ext : OptimizerExtension::Iterate(context)) {
        RunOptimizer(OptimizerType::EXTENSION, [&]() {
            if (ext.optimize_function) {
                ext.optimize_function(input, plan);
            }
        });
    }

    Planner::VerifyPlan(context, plan);
    return std::move(plan);
}
```

扩展可以在两个位置注入：

1. **pre_optimize_function**：在内建优化之前运行——适合需要"原始"逻辑计划的场景（如自定义的 Join 排序策略）
2. **optimize_function**：在内建优化之后运行——适合基于优化后计划的进一步调整（如基于代价模型的物理算子选择）

## 9.4 禁用优化器的调试方法

```sql
-- 禁用特定优化步骤
SET disabled_optimizers='join_order';

-- 禁用所有优化（通过禁用各步骤）
SET disabled_optimizers='expression_rewriter,filter_pushdown,join_order,...';

-- 查看优化前后的计划差异
SET explain_output=all;  -- 显示优化前、优化后、物理计划
EXPLAIN SELECT ...;
```

这是一个对数据库内核开发者非常有用的功能——当怀疑某个优化步骤引入了 bug 时，可以逐步禁用各步骤来定位问题。

---

## 本章小结

DuckDB 优化器的核心设计：

1. **33 步有序流水线**：先简化表达式→再调整结构→最后精打细算，每步只做一件事
2. **ExpressionRewriter 的 23 条规则**：基于模式匹配的固定点迭代，支持组合效果
3. **每步后验证**：ColumnBinding 一致性检查保证优化不破坏语义
4. **可插拔扩展**：前置/后置优化钩子，支持自定义优化逻辑
5. **可调试性**：支持按步骤禁用优化，便于定位问题

下一章深入其中最核心的几条优化规则。