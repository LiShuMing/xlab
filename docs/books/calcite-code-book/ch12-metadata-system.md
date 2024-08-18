# 第12章：元数据系统 — 优化的情报中心

## 12.1 为什么元数据系统至关重要

优化器的每个决策都依赖元数据：

- **代价计算**需要行数估计（`getRowCount`）
- **选择率估计**需要谓词的选择率（`getSelectivity`）
- **Join 重排序**需要唯一键信息（`getUniqueKeys`）
- **列裁剪**需要列来源信息（`getColumnOrigins`）
- **排序消除**需要排序属性（`collations`）

如果元数据不准确，优化器可能做出错误决策——例如低估行数导致选择 Hash Join 而非 Broadcast Join。

## 12.2 RelMetadataProvider 体系

### 12.2.1 核心接口

```java
// rel/metadata/RelMetadataProvider.java
public interface RelMetadataProvider {
  // 为某种元数据类型和 RelNode 类型绑定处理器
  <M extends Metadata> UnboundMetadata<M> apply(Class<? extends RelNode> relClass,
      Class<? extends M> metadataClass);
}
```

### 12.2.2 提供者链

多个 RelMetadataProvider 可以链式组合：

```java
// DefaultRelMetadataProvider 是默认的实现
ChainedRelMetadataProvider.of(ImmutableList.of(
    customMetadataProvider,                    // 自定义（最高优先级）
    DefaultRelMetadataProvider.INSTANCE        // 内置默认
));
```

### 12.2.3 CachingRelMetadataProvider

为元数据查询结果添加缓存：

```java
CachingRelMetadataProvider.wrap(baseProvider, planner);
```

缓存避免了重复计算——同一次优化中，同一个 RelNode 的同一种元数据只计算一次。

## 12.3 Janino 运行时编译

`JaninoRelMetadataProvider` 是 Calcite 元数据系统最精妙的设计——它使用 Janino 编译器在运行时生成 Java 字节码，将元数据分发逻辑编译为高效的方法调用。

### 12.3.1 问题背景

最朴素的元数据分发是通过反射：

```java
// 朴素方式：每次元数据查询都通过反射
Method method = provider.getClass().getMethod("getRowCount", rel.getClass(), ...);
Double rowCount = (Double) method.invoke(provider, rel, ...);
```

反射的开销在优化过程中会累积——一个复杂查询的优化可能触发数千次元数据查询。

### 12.3.2 Janino 的解决方案

JaninoRelMetadataProvider 为每种元数据类型动态生成一个分发类：

```java
// 生成的代码（概念）
class GeneratedMetadataHandler_RowCount implements BuiltInMetadata.RowCount.Handler {
  @Override public Double getRowCount(RelNode rel, RelMetadataQuery mq) {
    if (rel instanceof LogicalTableScan) {
      return relMdRowCount.getRowCount((LogicalTableScan) rel, mq);
    } else if (rel instanceof LogicalFilter) {
      return relMdRowCount.getRowCount((LogicalFilter) rel, mq);
    } else if (rel instanceof LogicalJoin) {
      return relMdRowCount.getRowCount((LogicalJoin) rel, mq);
    }
    // ... 所有注册的 RelNode 类型
    return rel.estimateRowCount(mq);  // 兜底
  }
}
```

这个类被 Janino 编译为字节码后直接执行——与手写代码性能相同，远快于反射。

### 12.3.3 编译触发

元数据处理器在首次使用时编译，后续直接使用缓存：

```java
// JaninoRelMetadataProvider.java
private <M extends Metadata> MetadataHandler<M> compile(Class<M> metadataClass) {
  // 1. 收集所有注册的 (RelNode类型, 元数据类型) 对
  // 2. 生成 Java 源码
  // 3. 用 Janino 编译为字节码
  // 4. 实例化并缓存
}
```

## 12.4 内置元数据

`BuiltInMetadata` 定义了 20+ 种内置元数据接口，每种都有对应的 `Handler` 和实现类：

| 元数据 | 接口 | 实现类 | 估算内容 |
|--------|------|--------|---------|
| 行数 | `RowCount` | `RelMdRowCount` | 结果行数 |
| 选择率 | `Selectivity` | `RelMdSelectivity` | 谓词的过滤比例 |
| 去重行数 | `DistinctRowCount` | `RelMdDistinctRowCount` | 去重后的行数 |
| 列来源 | `ColumnOrigins` | `RelMdColumnOrigins` | 列从哪个表的哪列来 |
| 唯一键 | `UniqueKeys` | `RelMdUniqueKeys` | 哪些列组合唯一 |
| 列唯一性 | `ColumnUniqueness` | `RelMdColumnUniqueness` | 指定列是否唯一 |
| 排序属性 | `Collation` | `RelMdCollation` | 数据的排序保证 |
| 分布属性 | `Distribution` | `RelMdDistribution` | 数据的分布方式 |
| 谓词 | `Predicates` | `RelMdPredicates` | 可推导的谓词条件 |
| 代价 | `NonCumulativeCost` | 各算子自行实现 | 算子自身代价 |
| 表引用 | `TableReferences` | `RelMdTableReferences` | 引用了哪些表 |
| 表达式谱系 | `ExpressionLineage` | `RelMdExpressionLineage` | 表达式从哪些列推导 |
| 大小 | `Size` | `RelMdSize` | 平均行大小/列大小 |
| 并行度 | `Parallelism` | `RelMdParallelism` | 可用的并行度 |
| 函数依赖 | `FunctionalDependency` | `RelMdFunctionalDependency` | 列间函数依赖关系 |
| 使用的字段 | `InputFieldsUsed` | `RelMdInputFieldsUsed` | 实际使用的输入字段 |

### 12.4.1 RelMdRowCount — 行数估计

```java
// rel/metadata/RelMdRowCount.java
public class RelMdRowCount implements BuiltInMetadata.RowCount.Handler {
  // TableScan: 使用表的统计信息
  public Double getRowCount(TableScan scan, RelMetadataQuery mq) {
    return scan.getTable().getRowCount();
  }

  // Filter: 行数 = 输入行数 × 选择率
  public Double getRowCount(Filter filter, RelMetadataQuery mq) {
    return mq.getRowCount(filter.getInput()) * mq.getSelectivity(filter, null);
  }

  // Join: 行数 = 左行数 × 右行数 × 选择率
  public Double getRowCount(Join join, RelMetadataQuery mq) {
    double left = mq.getRowCount(join.getLeft());
    double right = mq.getRowCount(join.getRight());
    return left * right * mq.getSelectivity(join, join.getCondition());
  }

  // Aggregate: 行数 = 去重后的分组键组合数
  public Double getRowCount(Aggregate aggregate, RelMetadataQuery mq) {
    return mq.getDistinctRowCount(aggregate.getInput(), aggregate.getGroupSet(), null);
  }

  // Project: 行数 = 输入行数（投影不改行数）
  public Double getRowCount(Project project, RelMetadataQuery mq) {
    return mq.getRowCount(project.getInput());
  }
}
```

### 12.4.2 RelMdSelectivity — 选择率估计

```java
// rel/metadata/RelMdSelectivity.java
public class RelMdSelectivity implements BuiltInMetadata.Selectivity.Handler {
  // 等值条件: 选择率 = 1 / max(左NDV, 右NDV)
  // 范围条件: 选择率 ≈ 1/3（经验值）
  // AND: 各选择率相乘
  // OR: 1 - (1-sel1) * (1-sel2)
  // NOT: 1 - sel
}
```

### 12.4.3 RelMdCollation — 排序属性

排序属性传播是消除冗余 Sort 的关键：

```java
// 如果输入已经按 [dept_id] 排序
// Filter 不改变排序 → Filter 输出仍按 [dept_id] 排序
// Project 不改变排序 → Project 输出仍按 [dept_id] 排序
// Aggregate(group=[dept_id]) → 输出按 [dept_id] 排序
// Sort([dept_id]) → 冗余！可以消除
```

## 12.5 RelMetadataQuery — 元数据查询入口

`RelMetadataQuery` 是所有元数据查询的入口，提供类型安全的 API：

```java
// rel/metadata/RelMetadataQuery.java
public class RelMetadataQuery {
  public Double getRowCount(RelNode rel) { ... }
  public Double getSelectivity(RelNode rel, @Nullable RexNode predicate) { ... }
  public Double getDistinctRowCount(RelNode rel, ImmutableBitSet groupKey, @Nullable RexNode predicate) { ... }
  public Set<RelColumnOrigin> getColumnOrigins(RelNode rel, int column) { ... }
  public Set<ImmutableBitSet> getUniqueKeys(RelNode rel) { ... }
  public Boolean areColumnsUnique(RelNode rel, ImmutableBitSet columns) { ... }
  public ImmutableList<RelCollation> collations(RelNode rel) { ... }
  public RelDistribution distribution(RelNode rel) { ... }
  public RelOptCost getCumulativeCost(RelNode rel) { ... }
  public RelOptCost getNonCumulativeCost(RelNode rel) { ... }
  // ... 20+ 个查询方法
}
```

### 12.5.1 元数据缓存与失效

`RelMetadataQuery` 内部维护了查询缓存，避免重复计算。缓存的生命周期是单次元数据查询——当 RelNode 树变化时（如规则应用后），需要创建新的 `RelMetadataQuery` 实例。

VolcanoPlanner 在每次代价计算时使用 `cluster.getMetadataQuery()` 获取当前有效的 MQ 实例。

### 12.5.2 循环依赖检测

元数据查询可能产生循环——例如 `getRowCount(Aggregate)` 调用 `getDistinctRowCount(Input)`，后者又调用 `getRowCount(Input)`。`CyclicMetadataException` 用于检测和中断循环：

```java
// 循环检测机制
if (mq.isQueryInProgress(rel, metadataType)) {
  throw CyclicMetadataException.INSTANCE;
}
```

## 12.6 自定义元数据的完整流程

### 步骤 1：定义元数据接口

```java
// 自定义：数据倾斜度
public interface Skewness extends Metadata {
  interface Handler extends MetadataHandler<Skewness> {
    Double getSkewness(RelNode rel, RelMetadataQuery mq, int column);
  }
}
```

### 步骤 2：实现处理器

```java
public class RelMdSkewness implements Skewness.Handler {
  @Override public Double getSkewness(TableScan scan, RelMetadataQuery mq, int column) {
    // 从表的统计信息中获取倾斜度
    return scan.getTable().getStatistic().getSkewness(column);
  }

  @Override public Double getSkewness(Filter filter, RelMetadataQuery mq, int column) {
    // Filter 可能增加倾斜度
    Double inputSkew = mq.getSkewness(filter.getInput(), column);
    return inputSkew != null ? inputSkew * 1.2 : null;
  }

  // ... 为其他 RelNode 类型提供实现
}
```

### 步骤 3：注册

```java
RelMetadataProvider customProvider = ChainedRelMetadataProvider.of(
    ImmutableList.of(
        new ConstantSkewnessProvider(RelMdSkewness.class),
        DefaultRelMetadataProvider.INSTANCE));
```

### 步骤 4：在 RelMetadataQuery 中添加查询方法

```java
// 扩展 RelMetadataQuery
public class MyRelMetadataQuery extends RelMetadataQuery {
  public Double getSkewness(RelNode rel, int column) {
    return rel.metadata(Skewness.class, this).getSkewness(column);
  }
}
```

---

## 本章小结

Calcite 的元数据系统通过 Janino 运行时编译实现高效分发，避免了反射开销。20+ 种内置元数据覆盖了行数、选择率、唯一键、排序属性等优化所需的关键信息。`RelMdRowCount` 和 `RelMdSelectivity` 是代价计算的基础。自定义元数据只需定义接口、实现处理器、注册提供者三步。下一章将进入物理执行层——Convention 与代码生成。
