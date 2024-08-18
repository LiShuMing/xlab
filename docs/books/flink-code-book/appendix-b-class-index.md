# 附录 B · 核心类图索引

## 按功能模块快速定位代码

### 集群启动与提交

```
flink-runtime/entrypoint/
├── ClusterEntrypoint.java          — 集群启动基类(startCluster, runCluster, initializeServices)
├── SessionClusterEntrypoint.java   — Session 模式启动
└── StandaloneSessionClusterEntrypoint.java — Standalone 启动

flink-clients/src/main/java/.../CliFrontend.java  — 命令行入口

flink-runtime/entrypoint/component/
├── DispatcherResourceManagerComponent.java  — JM 顶层组件
└── DefaultDispatcherResourceManagerComponentFactory.java  — 创建 Dispatcher+RM+RestEndpoint
```

### RPC 层

```
flink-rpc/flink-rpc-core/
├── RpcGateway.java                 — RPC 网关接口(getAddress, getHostname)
├── FencedRpcGateway.java           — 带 fencing token 的网关
├── RpcEndpoint.java                — RPC 端点基类(生命周期管理, 主线程保证)
├── RpcService.java                 — RPC 服务接口(startServer, connect)
├── RpcServer.java                  — 自引用接口(StartStoppable + MainThreadExecutable)
└── MainThreadExecutable.java       — 主线程可执行接口(runAsync, callAsync)

flink-rpc/flink-rpc-akka/
├── PekkoRpcActor.java             — Actor 实现(四状态机, 反射调用 Endpoint 方法)
├── PekkoInvocationHandler.java    — 动态代理(tell vs ask, 本地零序列化)
├── PekkoRpcService.java           — Pekko RPC 服务实现
└── FencedPekkoRpcActor.java       — 带 fencing 的 Actor

### 核心运行时组件

```
flink-runtime/dispatcher/
├── Dispatcher.java                 — 提交接收、JobMaster 管理
├── DispatcherGateway.java          — 对外 RPC 接口
└── DispatcherRestEndpoint.java     — REST API 实现

flink-runtime/resourcemanager/
├── ResourceManager.java            — 资源管理基类
├── StandaloneResourceManager.java
└── resourcemanager/slotmanager/    — Slot 管理

flink-runtime/jobmaster/
├── JobMaster.java                  — 核心：持有 ExecutionGraph、Scheduler
├── jobmaster/slotpool/            — SlotPool 实现
└── JobMasterGateway.java           — 对外 RPC 接口

flink-runtime/taskexecutor/
├── TaskExecutor.java               — TM 核心
└── TaskExecutorGateway.java        — 对外 RPC 接口
```

### 图与调度

```
flink-streaming-java/api/graph/
├── StreamGraph.java                — 用户层图
├── StreamGraphGenerator.java       — StreamGraph 构建
└── StreamingJobGraphGenerator.java — JobGraph 转换

flink-runtime/jobgraph/
├── JobGraph.java                   — 优化后 IR
├── JobVertex.java
└── IntermediateDataSet.java

flink-runtime/executiongraph/
├── ExecutionGraph.java             — 物理执行图
├── Execution.java                  — 运行尝试
├── ExecutionVertex.java
├── IntermediateResult.java
└── IntermediateResultPartition.java

flink-runtime/scheduler/
├── SchedulerBase.java              — 调度器基类
├── scheduler/adaptive/            — Adaptive Scheduler
├── scheduler/adaptivebatch/       — Batch Adaptive Scheduler
├── scheduler/strategy/            — SchedulingStrategy 实现
└── scheduler/slowtaskdetector/    — 慢任务检测
```

### State & Checkpoint

```
flink-runtime/state/
├── StateBackend.java               — 主接口
├── heap/HeapKeyedStateBackend.java
├── KeyGroupRange.java              — KeyGroup 分片
├── ttl/                            — State TTL
├── changelog/                      — Changelog State Backend
├── v2/                             — 新版 State API
└── filemerging/                    — 文件合并 State

flink-state-backends/
├── flink-statebackend-rocksdb/     — RocksDB 实现
├── flink-statebackend-forst/      — ForSt 实现
└── flink-statebackend-changelog/  — Changelog 实现

flink-runtime/checkpoint/
├── CheckpointCoordinator.java      — 全局协调者
├── CheckpointBarrier.java          — Barrier 定义
├── CheckpointBarrierHandler.java   — Barrier 处理
├── CheckpointStorage.java          — Checkpoint 存储
└── channel/                        — Channel State
```

### 网络与 IO

```
flink-runtime/io/network/
├── buffer/
│   ├── NetworkBufferPool.java      — 全局 Buffer 池
│   ├── LocalBufferPool.java        — 本地 Buffer 池
│   └── NetworkBuffer.java
├── api/writer/
│   └── RecordWriter.java           — 算子输出写
├── api/serialization/
│   └── SpanningRecordSerializer.java
├── partition/
│   ├── ResultPartition.java
│   ├── ResultSubpartition.java
│   ├── consumer/InputGate.java
│   ├── consumer/InputChannel.java
│   └── hybrid/                     — Hybrid Shuffle
└── netty/
    └── NettyMessage.java           — Netty 协议

flink-runtime/io/disk/iomanager/
└── IOManager.java                  — 异步 IO / 磁盘溢写
```

### Stream 算子

```
flink-streaming-java/api/operators/
├── StreamOperator.java             — 接口
├── AbstractStreamOperator.java     — 基类
└── OneInputStreamOperator.java

flink-streaming-java/runtime/
├── tasks/
│   ├── StreamTask.java             — Task 运行循环
│   ├── SourceStreamTask.java
│   ├── OneInputStreamTask.java
│   └── TwoInputStreamTask.java
├── io/
│   ├── OperatorChain.java          — 算子链构建
│   ├── StreamOneInputProcessor.java
│   └── StreamTwoInputProcessor.java
└── operators/windowing/
    └── WindowOperator.java
```

### Table / SQL

```
flink-table/
├── flink-table-api-java/           — Table API 用户接口
├── flink-table-common/
│   ├── data/RowData.java           — 内部行接口
│   ├── data/binary/BinaryRowData.java
│   ├── data/columnar/              — 列式数据
│   ├── connector/source/DynamicTableSource.java
│   ├── catalog/Catalog.java
│   └── refresh/                    — Materialized Table
├── flink-table-planner/
│   ├── plan/nodes/logical/         — FlinkLogicalRel
│   ├── plan/nodes/physical/        — FlinkPhysicalRel
│   ├── plan/nodes/exec/            — ExecNode DAG
│   ├── plan/optimize/              — 优化器
│   ├── plan/metadata/              — 代价模型
│   ├── plan/rules/                 — 优化规则
│   ├── codegen/                    — CodeGen 生成器
│   └── calcite/                    — Calcite 集成
├── flink-table-runtime/
│   ├── data/binary/BinaryRowData.java
│   ├── operators/join/             — Join 算子实现
│   ├── operators/aggregate/        — Agg 算子实现
│   └── functions/                  — 内置函数
├── flink-sql-gateway/              — SQL Gateway
└── flink-sql-jdbc-driver/          — JDBC Driver
```

### RPC & HA

```
flink-rpc/
├── flink-rpc-core/                 — RPC 接口抽象
└── flink-rpc-akka/                 — Akka 实现

flink-runtime/highavailability/
├── HighAvailabilityServices.java   — HA 服务接口
├── zookeeper/ZooKeeperHaServices.java
└── nonha/standalone/               — Standalone 实现
```
