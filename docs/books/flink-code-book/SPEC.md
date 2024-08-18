# 《深入理解 Apache Flink 内核：从源码到本质》
## Book Specification & Master Index

---

### 元信息

- **代码基准**：Apache Flink 源码 `/Users/lism/work/flink`，当前 master 分支
- **目标读者**：具有查询引擎工程经验（Spark/StarRocks/MaxCompute），希望从第一性原理理解 Flink 内核设计
- **写作风格**：源码驱动、设计决策还原、横向对比；不写手册、不译注释、不堆代码
- **内容格式**：Markdown，每章一文件

---

### 写作约定

1. **源码入口**：每章标注关键类的全限定路径，可直接在 IDE 中定位
2. **设计追问**：每个核心模块以"为什么这样设计"开头，回答"解决什么问题、放弃什么替代方案"
3. **横向对比**：与 Spark/StarRocks/MaxCompute 的对应机制对比，挂在已有知识锚点上
4. **代码引用**：引用关键代码片段而非大量粘贴，行号标注 `<package.ClassName:L#起始行>`
5. **不写注释翻译**：代码片段的价值在于揭示控制流与数据流，不在逐行说明语法

---

### 章节索引

| 编号 | 章节 | 文件 | 状态 |
|------|------|------|------|
| P1 | 第一部分导论：基石 — 运行时核心与分布式架构 | - | 🟢 已完成 |
| 01 | Flink 的架构哲学：流优先的一体化引擎 | `ch-01-architecture-philosophy.md` | 🟢 已完成 |
| 02 | 自包含与类型系统：为什么 Flink 要自己管理一切 | `ch-02-self-contained-type-system.md` | 🟢 已完成 |
| 03 | RPC 与高可用：分布式协调的骨架 | `ch-03-rpc-high-availability.md` | 🟢 已完成 |
| 04 | 内存管理与 IO 子系统 | `ch-04-memory-management-io.md` | 🟢 已完成 |
| P2 | 第二部分导论：任务调度与图计算 | - | 🟢 已完成 |
| 05 | 逻辑图到物理图：JobGraph → ExecutionGraph | `ch-05-jobgraph-executiongraph.md` | 🟢 已完成 |
| 06 | 调度策略：从 Eager 到 Adaptive 的演进 | `ch-06-scheduling-strategies.md` | 🟢 已完成 |
| 07 | Slot 管理与资源调度 | `ch-07-slot-resource-scheduling.md` | 🟢 已完成 |
| P3 | 第三部分导论：流计算引擎 | - | - |
| 08 | Watermark、Event Time 与窗口计算 | `ch-08-watermark-window.md` | 🟢 已完成 |
| 09 | StreamOperator 与算子链 | `ch-09-streamoperator-chain.md` | 🟢 已完成 |
| 10 | StreamTask 执行引擎 | `ch-10-streamtask-execution.md` | 🟢 已完成 |
| 11 | 反压机制 | `ch-11-backpressure.md` | 🟢 已完成 |
| P4 | 第四部分导论：容错与状态管理 | - | - |
| 12 | Checkpoint 核心机制：Chandy-Lamport 的工业实现 | `ch-12-checkpoint-mechanism.md` | 🟢 已完成 |
| 13 | State Backend：可插拔的状态存储 | `ch-13-state-backend.md` | 🟢 已完成 |
| 14 | Savepoint 与 State 兼容性 | `ch-14-savepoint-state-compatibility.md` | 🟢 已完成 |
| 15 | Changelog State Backend 与 Restore 加速 | `ch-15-changelog-state-backend.md` | 🟢 已完成 |
| P5 | 第五部分导论：网络栈与数据传输 | - | - |
| 16 | 网络栈分层架构 | `ch-16-network-stack.md` | 🟢 已完成 |
| 17 | Shuffle 与数据分发策略 | `ch-17-shuffle-data-distribution.md` | 🟢 已完成 |
| P6 | 第六部分导论：Table/SQL — 声明式到执行式的桥梁 | - | - |
| 18 | Table API & SQL 的架构全景 | `ch-18-table-api-sql-architecture.md` | 🟢 已完成 |
| 19 | Calcite 集成与 Optimizer | `ch-19-calcite-optimizer.md` | 🟢 已完成 |
| 20 | CodeGen 与运行时算子 | `ch-20-codegen-runtime-operators.md` | 🟢 已完成 |
| 21 | Binary Row 与列式处理 | `ch-21-binary-row-columnar.md` | 🟢 已完成 |
| 22 | SQL Gateway、Materialized Table 与 Batch 模式 | `ch-22-sql-gateway-materialized.md` | 🟢 已完成 |
| P7 | 第七部分导论：连接器与生态 | - | - |
| 23 | Source / Sink 的设计演化 | `ch-23-source-sink-design.md` | 🟢 已完成 |
| 24 | 格式层与序列化加速 | `ch-24-format-serialization.md` | 🟢 已完成 |
| P8 | 第八部分导论：部署与运维 | - | - |
| 25 | 资源管理器的多平台适配 | `ch-25-resource-manager-multi-platform.md` | 🟢 已完成 |
| 26 | Metrics、REST API 与可观测性 | `ch-26-metrics-observability.md` | 🟢 已完成 |
| P9 | 第九部分导论：横向对比与第一性原理思考 | - | - |
| 27 | 计算引擎设计的本质追问 | `ch-27-essence-of-compute-engine.md` | 🟢 已完成 |
| 28 | AI 时代：Flink 与 LLM 推理、Agent 的碰撞 | `ch-28-flink-ai-era.md` | 🟢 已完成 |
| A | 附录 | - | - |
| A1 | 关键配置项速查 | `appendix-a-config.md` | 🟢 已完成 |
| A2 | 核心类图索引 | `appendix-b-class-index.md` | 🟢 已完成 |
| A3 | FLIP 索引 | `appendix-c-flip-index.md` | 🟢 已完成 |
| A4 | 术语对照表 | `appendix-d-glossary.md` | 🟢 已完成 |

---

### 每章模板结构

生成每章内容时遵循以下结构：

```markdown
# 第 N 章 · 章节标题

## 导读
- 一句话：本章回答什么问题
- 前置知识
- 读完后你应能回答的问题列表

## N.1 — 设计动机

## N.2 — 核心数据结构

## N.3 — 关键流程走读

## N.4 — 横向对比（Spark / StarRocks / MaxCompute）

## N.5 — 调优与实战陷阱

## 本章要点回顾

## 源码导航
```

---

### 生成进度

使用下方表格追踪每章生成状态：

- 🔴 待开始
- 🟡 进行中
- 🟢 已完成

---

**全书完成日期**: 2026-05-04
**总文件数**: 33 (28 章 + 4 附录 + 1 SPEC)

状态更新规则：开始某章时修改对应行状态为 🟡，完成时修改为 🟢 并记录完成日期。
