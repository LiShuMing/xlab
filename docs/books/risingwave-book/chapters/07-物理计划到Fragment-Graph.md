# 第 7 章 · 物理计划到 Fragment Graph

> **核心源码**：
> - `src/frontend/src/handler/` — DDL Handler，Frontend 侧入口
> - `src/meta/src/stream/stream_graph/` — Fragment 构建、Actor 生成、调度
> - `src/meta/src/stream/stream_manager.rs` — 流作业全局管理
> **关键数据结构**：`StreamFragmentGraph`、`BuildingFragment`、`ActorGraphBuilder`、`Locations`

---

## 7.1 从计划树到可执行拓扑

第 6 章结束时，Optimizer 产出的流物理计划仍然是一棵树——它以 `StreamMaterialize` 为根，内部包含 `StreamHashJoin`、`StreamHashAgg`、`StreamExchange`、`StreamTableScan` 等节点。这张图还缺少两样东西才能执行：

1. **并行度信息**：每个算子需要多少个并行实例？
2. **物理位置**：每个实例部署在哪台机器上？

本章跟踪从物理计划到最终下发执行的 Actor 拓扑的全过程。这条链路跨越两个进程：

```
Frontend (Handler)                         Meta (StreamManager)
══════════════════                         ═════════════════════
StreamPhysical Plan                        StreamFragmentGraph Proto
       │                                          │
       ▼                                          ▼
StreamFragmentGraph  ───gRPC──►           BuildingFragment { fill internal tables, fill job }
       │                                          │
                                               ActorGraphBuilder
                                               { rewrite Exchange→Merge, build edges }
                                                      │
                                               Locations { schedule to workers }
                                                      │
                                               Barrier 注入 → 所有 Compute Node
```

> **第一性原理思考**：为什么需要 Fragment？物理计划中不同算子有不同并行度——Source 取决于 Kafka partition 数，Agg 由用户配置决定，Materialize 必须是单例。Fragment 的切分边界恰好是 **数据分布发生变化的地方**：即 `Exchange` 算子。Fragment = Exchange 包围的子图，每个 Fragment 内所有算子有相同的并行度。这个设计直接来自 Flink 的 ExecutionGraph 思想。

---

## 7.2 Handler——Frontend 侧的 DDL 总入口

`handler/` 目录包含 80+ 个文件，每个文件处理一类 SQL 语句。以 `CREATE MATERIALIZED VIEW` 为例（`handler/create_mv.rs`）：

```rust
pub async fn handle_create_mv(
    handler_args: HandlerArgs,
    stmt: Statement,
) -> Result<RwPgResponse> {
    // 1. Binder → BoundStatement
    let bound = {
        let mut binder = Binder::new_for_stream(&session);
        binder.bind(stmt)?
    };

    // 2. Planner → LogicalPlanRoot
    let plan_root = Planner::new_for_stream(ctx).plan(bound)?;

    // 3. Optimizer → StreamMaterialize
    let materialize = plan_root.gen_materialize_plan(
        database_id, schema_id, mv_name, definition, emit_on_window_close
    )?;

    // 4. 转换为 Fragment Graph（Frontend 侧完成切分）
    let table_fragments = materialize.to_table_fragments()?;

    // 5. RPC → Meta Service
    meta_client.create_materialized_view(table_fragments).await
}
```

所有 DDL 操作遵循统一模式：**Bind → Plan → Optimize → Fragmentize → RPC to Meta**。

---

## 7.3 Fragment 的切分原理

Fragment 切分的核心规则只有一条：

> **Exchange 是 Fragment 的边界**

```
  StreamMaterialize     ─┐
  StreamHashAgg         ─┤ Fragment 2 (Singleton)
  StreamExchange(Single) ─┘
  ═══════════════════════════
  StreamHashJoin        ─┐
  StreamExchange(Hash)  ─┤ Fragment 1 (N-way parallel)
  StreamFilter          ─┤
  StreamTableScan       ─┘
  ═══════════════════════════
  StreamSource(Kafka)   ── Fragment 0 (N-way parallel)
```

Exchange 的 `DispatchStrategy` 决定了分发模式，对应不同的 `DispatcherType`（protobuf 枚举）：

| 策略 | DispatcherType | 用途 |
|------|---------------|------|
| Simple | Round-Robin | 无状态算子（Filter/Project） |
| Hash | Hash by distribution keys | Agg / Join |
| Broadcast | 广播到所有下游 | Broadcast Join |
| NoShuffle | 保持上游分区 | 紧随 Source 的分区 |

Fragment 在 Frontend 侧的 `to_table_fragments()` 阶段完成切分，打包为 protobuf 结构发给 Meta。

---

## 7.4 StreamFragmentGraph——Meta 侧的接收与构建

Meta 收到的是 protobuf 版的 Fragment Graph：

```protobuf
message StreamFragmentGraphProto {
    repeated StreamFragment fragments = 1;
    repeated StreamFragmentEdge edges = 2;
    // ...
}

message StreamFragment {
    uint32 fragment_id = 1;
    StreamNode node = 2;        // 根算子（物理计划子树）
    uint32 parallelism = 3;     // 并行度
    // ...
}
```

Meta 的 `BuildingFragment`（`fragment.rs:63-75`）是对 protobuf Fragment 的封装：

```rust
pub(super) struct BuildingFragment {
    inner: StreamFragment,
    job_id: Option<JobId>,
    upstream_job_columns: HashMap<JobId, Vec<PbColumnDesc>>,
}
```

`BuildingFragment::new()` 阶段有两个关键任务：

### 7.4.1 fill_internal_tables——为有状态算子分配存储

```rust
fn fill_internal_tables(fragment: &mut StreamFragment, job: &StreamingJob, table_id_gen: GlobalTableIdGen) {
    let fragment_id = fragment.fragment_id;
    stream_graph_visitor::visit_internal_tables(fragment, |table, table_type_name| {
        table.id = table_id_gen.to_global_id(table.id.as_raw_id()).as_global_id();
        table.schema_id = job.schema_id();
        table.database_id = job.database_id();
        table.name = generate_internal_table_name_with_type(
            &job.name(), fragment_id, table.id, table_type_name,
        );
        table.owner = job.owner();
    });
}
```

`visit_internal_tables` 遍历 Fragment 的每个节点，为有状态算子提取内部表：

| 算子 | 内部表类型 | 命名模式 |
|------|-----------|---------|
| HashJoin | Join State Table | `__internal_<job>_<frag>_<id>_HashJoinState` |
| HashAgg | Agg State Table | `__internal_<job>_<frag>_<id>_HashAggState` |
| Materialize | Materialize Table | 使用作业名 |
| TopN | TopN State Table | 类似 HashAgg |
| VectorIndexWrite | Vector Index Table | 使用作业名 |

### 7.4.2 fill_job——注入作业级元数据

```rust
fn fill_job(fragment: &mut StreamFragment, job: &StreamingJob) -> bool {
    stream_graph_visitor::visit_fragment_mut(fragment, |node_body| match node_body {
        NodeBody::Materialize(m) => {
            m.table_id = job.id().as_mv_table_id();
            m.table.insert(job.table().unwrap().clone());
            has_job = true;
        }
        NodeBody::Sink(s) => {
            s.sink_desc.as_mut().unwrap().id = job.id().as_sink_id();
            has_job = true;
        }
        NodeBody::Source(source_node) => {
            // Table with connector: source_id != table_id
            // Source job: source_id == job_id
            // Other jobs: refer to existing source, no need to fill
        }
        // ...
    })
}
```

---

## 7.5 Actor Graph Builder——从 Fragment 到 Actor

`ActorGraphBuilder`（`actor.rs`）执行四个关键步骤：

### Step 1: 计算每个 Fragment 的 Actor 数量

```
Fragment 0 (Source, parallelism=4) → 4 actors
Fragment 1 (Join,   parallelism=8) → 8 actors
Fragment 2 (MView,  parallelism=1) → 1 actor
```

### Step 2: 建立 Actor 间的边

```
Fragment 0 (4 actors) ──Hash──► Fragment 1 (8 actors) ──Single──► Fragment 2 (1 actor)
   A0.0 ──────────────► A1.0, A1.1
   A0.1 ──────────────► A1.2, A1.3
   A0.2 ──────────────► A1.4, A1.5
   A0.3 ──────────────► A1.6, A1.7
                                │
                            全部 A1.x ──► A2.0
```

### Step 3: Rewrite——Exchange 变为 Merge

这是 Actor 构建中最关键的变换（`actor.rs:45-80`）：

```rust
fn rewrite_inner(&self, stream_node: &StreamNode, depth: usize) -> MetaResult<StreamNode> {
    match stream_node.get_node_body()? {
        NodeBody::Exchange(exchange) => {
            // Exchange → Merge，指向上游 Fragment
            let (upstream_fragment_id, _) = &self.upstreams[&EdgeId::Internal {
                link_id: stream_node.get_operator_id().as_raw_id(),
            }];
            Ok(StreamNode {
                node_body: Some(NodeBody::Merge(Box::new(MergeNode {
                    upstream_fragment_id: upstream_fragment_id.as_global_id(),
                    upstream_dispatcher_type: exchange.get_strategy()?.r#type,
                    ..Default::default()
                }))),
                identity: "MergeExecutor".to_owned(),
                ..stream_node.clone()
            })
        }
        _ => { /* 递归处理子节点 */ }
    }
}
```

逻辑 `Exchange` 被替换为物理 `Merge` 节点，记录上游 Fragment ID 和分发策略类型。在 Compute Node 上，`MergeExecutor` 根据这些信息建立到上游 Actor 的 gRPC 连接。

### Step 4: 分配全局 ID 和确定部署位置

```rust
pub struct Locations {
    pub actor_locations: HashMap<ActorId, WorkerId>,
    pub worker_locations: HashMap<WorkerId, WorkerLocation>,
}
```

`schedule.rs` 根据各 Worker 的负载信息，将 Actor 分配到具体的 Compute Node 上。

---

## 7.6 流作业的五种类型

Meta 端通过 `StreamingJob` 区分流作业类型：

```rust
pub enum StreamingJob {
    MaterializedView(StreamJob),
    Sink(StreamJob),
    Table(Option<Source>, Option<Table>, TableJobType),
    Source(Source),
}
```

每种类型在 Fragment 构建中的差异：

| 类型 | fill_job 中的特殊处理 |
|------|---------------------|
| MaterializedView | MaterializeNode 的 table_id → job_id |
| Sink | SinkNode 的 sink_desc.id → job_id |
| Table + Source | SourceNode → 外部 Source ID |
| Table (no Source) | 保留 dummy Source（`CreateTable`） |
| Table + RowId | 需注入 `StreamRowIdGen` 节点 |
| Source | SourceNode 的 source_id → job_id |
| DML | DmlNode 的 table_id + table_version_id → job |

---

## 7.7 DDL Handler 全链路示例

以 `CREATE MATERIALIZED VIEW mv1 AS SELECT count(*) FROM orders GROUP BY region` 为例：

```
Frontend                            Meta
───────                             ────
① Parser  → AST
② Binder  → BoundStatement
③ Planner → LogicalPlanRoot
④ Optimizer → gen_optimized_logical_plan_for_stream()
    ├─ Predicate Pushdown
    ├─ Column Pruning
    └─ ...
⑤ StreamMaterialize::create()
    ├─ to_stream_with_dist_required()
    │   TableScan → StreamTableScan (Backfill)
    │   Agg → StreamHashAgg (Agg State Table)
    │   Exchange → StreamExchange (Single)
    └─ StreamMaterialize 包装
⑥ to_table_fragments()
    切分 Fragment:
    ┌── Fragment 2 (Singleton) ──┐
    │ StreamMaterialize           │
    │ StreamHashAgg               │
    │ StreamExchange (Single)     │
    └─────────────────────────────┘
    ┌── Fragment 0 (N-way) ──────┐
    │ StreamTableScan + Backfill  │
    └─────────────────────────────┘
⑦ gRPC → create_materialized_view(TableFragments)
                                    │
                                ⑧ StreamManager.create_materialized_view()
                                ⑨ BuildingFragment → fill_internal_tables + fill_job
                                ⑩ ActorGraphBuilder:
                                    Fragment 0 (p=4) → A0..A3
                                    Fragment 2 (p=1) → A4
                                    边: A0..A3 → A4 (Merge, Single)
                                ⑪ 全局 ID 分配 + Locations 调度
                                ⑫ Barrier 注入 → 所有 Compute Node 开始执行
```

---

## 7.8 重建与恢复场景

Fragment Graph 不仅用于初始创建，还用于：

1. **Scale（扩缩容）**：增加/减少并行度时重建部分 Fragment 的 Actor 图
2. **Failover（故障恢复）**：Compute Node 故障后，Meta 根据 Fragment Graph 重建丢失的 Actor 并重新分配
3. **Schema Change**：修改 Source Schema 时更新相关 Fragment 的字段映射
4. **Configuration Change**：`ALTER STREAMING CONFIG` 涉及 Fragment 并行度调整

这些操作的关键在于 Meta 始终持有完整的 Fragment Graph，可以随时重新运行 Actor Graph Builder。

---

## 7.9 小结

本章完成了从物理计划到可执行拓扑的最后一段路程：

- **Handler** 是 Frontend 侧所有 DDL 的统一入口，遵循 Bind → Plan → Optimize → Fragmentize → RPC 的固定管线
- **Fragment** 以 Exchange 为边界切分物理计划，每个 Fragment 内所有算子有相同的并行度
- **BuildingFragment** 在 Meta 侧完成内部状态表的 ID 分配和元数据注入（`fill_internal_tables` + `fill_job`）
- **ActorGraphBuilder** 将 Fragment 展开为 Actor 拓扑，关键变换是 `Exchange → Merge`（将逻辑交换替换为需建立物理连接的合并节点）
- **Locations** 负责将 Actor 调度到具体的 Worker 上

至此，SQL 的编译之旅完成了全链路：**SQL 文本 → AST → BoundStatement → LogicalPlan → Optimized Plan → Fragment Graph → Actor Graph**。

下一部分开始，我们将进入 RisingWave 最核心的领域——流计算引擎。从 Message/Barrier 抽象开始，逐步深入到每个算子的内部实现。

---

*本章完成。下一章：[第 8 章 · 核心抽象：Message / Barrier / Executor](../chapters/08-核心抽象-Message-Barrier-Executor.md)*
