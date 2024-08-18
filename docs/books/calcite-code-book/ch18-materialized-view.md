# 第18章：物化视图与 Lattice

## 18.1 物化视图的本质

物化视图是预先计算并存储的查询结果。当用户查询匹配物化视图的定义时，优化器可以重写查询，直接从物化视图读取数据而非重新计算。

```sql
-- 物化视图定义
CREATE MATERIALIZED VIEW mv_dept_salary AS
SELECT dept_id, AVG(salary) AS avg_sal, COUNT(*) AS cnt
FROM emp GROUP BY dept_id;

-- 原始查询
SELECT dept_id, AVG(salary) FROM emp GROUP BY dept_id;
-- → 重写为
SELECT dept_id, avg_sal FROM mv_dept_salary;
```

## 18.2 MaterializationService 与 MaterializationActor

源码位置：`materialize/`（23 文件）

`MaterializationService` 管理物化视图的注册和查询：

```java
// materialize/MaterializationService.java
public class MaterializationService {
  // 注册物化视图
  public MaterializationKey defineMaterialization(RelOptSchema schema, String sql, ...);

  // 查询匹配的物化视图
  public List<Materialization> queryMaterializations(RelOptSchema schema);
}
```

`MaterializationActor` 跟踪物化视图的生命周期：

```java
// materialize/MaterializationActor.java
class MaterializationActor {
  // 记录物化视图的键、查询定义和物化表
}
```

## 18.3 Lattice 模型

Lattice 是 Calcite 的多维数据模型，定义了维度表和事实表之间的星型结构：

```java
// materialize/Lattice.java
public class Lattice {
  final LatticeRootNode root;        // 根节点（事实表）
  final List<LatticeNode> nodes;     // 所有节点
  final double rowCount;             // 估计行数
  final LatticeStatisticProvider statisticProvider;
}
```

### 18.3.1 Lattice 定义示例

```json
{
  "lattices": [{
    "name": "star",
    "sql": "SELECT * FROM sales JOIN product USING (product_id) JOIN time USING (time_id)",
    "auto": true,
    "algorithm": true,
    "rowCountEstimate": 1000000
  }]
}
```

### 18.3.2 Lattice 的用途

1. **自动推荐物化视图**：`LatticeSuggester` 分析查询模式，推荐 Tile
2. **Tile 自动选择**：根据查询的维度组合选择最优的 Tile
3. **增量维护**：基于 Lattice 结构计算增量更新

## 18.4 物化视图匹配算法

### 18.4.1 SubstitutionVisitor

`SubstitutionVisitor`（`plan/SubstitutionVisitor.java`，2438 行）是物化视图匹配的核心算法，使用 `MutableRel` 框架比较查询子树和物化视图定义的结构相似性：

```
1. 将查询和物化视图定义都转换为 MutableRel 树
2. 自顶向下匹配节点结构
3. 对齐投影表达式和过滤条件
4. 如果匹配成功，生成替换计划
```

### 18.4.2 基于规则的匹配

`rel/rules/materialize/` 提供了 6 条物化视图规则，它们通过优化规则机制匹配查询子树：

```
MaterializedViewFilterRule:         Filter + Scan → Scan(物化视图)
MaterializedViewProjectFilterRule:  Project + Filter + Scan → ...
MaterializedViewJoinRule:           Join → Join with 物化视图
MaterializedViewAggregateRule:      Aggregate → Aggregate on 物化视图
```

## 18.5 统计信息驱动

`LatticeStatisticProvider` 和 `SqlStatisticProvider` 提供基于统计信息的物化视图推荐：

```java
// materialize/SqlLatticeStatisticProvider.java
public class SqlLatticeStatisticProvider implements LatticeStatisticProvider {
  // 执行 SQL 查询获取统计信息
  // SELECT COUNT(*), COUNT(DISTINCT col1), ... FROM fact_table
}
```

---

## 本章小结

Calcite 的物化视图支持通过 SubstitutionVisitor 和规则匹配两种机制实现查询重写。Lattice 模型为多维数据提供了自动推荐物化视图的能力。统计信息驱动的 Tile 选择确保推荐的物化视图能最大化查询性能提升。
