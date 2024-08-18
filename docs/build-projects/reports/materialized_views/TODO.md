- MV 的 Plan 缓存在 MTMVCache 中，与 MTMV 解耦（AsyncMaterializationContext 持有缓存引用），避免 MV 定义 SQL 每次查询都重新 parse/optimize
- Rewrite框架改进

```
Doris 改写框架基于 SPJG（Select-Project-Join-GroupBy） 模式，算法本质是 Subgraph Isomorphism：

View Normalization：MV 创建时 parse + 提取 Join 拓扑、列 lineage、聚合语义，缓存于 MTMVCache
Query StructInfo 提取：InitMaterializationContextHook 在 Cascades 优化开始前从 query plan tree 提取 StructInfo（Join order、predicates、output expressions）
映射匹配：RelationMapping 执行 Query-View 关系的子图同构匹配，生成 SlotMapping（列映射）
等价性验证：

谓词补偿（view predicates 是 query predicates 的超集时可补偿）
列 lineage 验证（输出列可否从 MV 列推导）
分区时效性检查（grace_period 控制允许的 staleness）



基于规则，非基于代价：当前 Doris 的 MV 改写是 exploration rule（注入 Cascades 的 exploration phase），本身不做 CBO cost 比较——命中 MV 后直接替换，cost 比较由后续 Cascades 阶段完成。这与 StarRocks 的处理方式基本一致。
```