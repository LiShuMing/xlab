# 第 22 章 · SQL Gateway、Materialized Table 与 Batch 模式

## 导读

- **一句话**：本章回答"Flink 怎样支持多用户通过 REST/JDBC 提交 SQL、以及 Materialized Table 这种增量物化视图怎么维护"。
- **前置知识**：第 18 章 SQL 架构。
- **读完本章你能回答**：
  - Session / Operation 的隔离模型与生命周期管理
  - Operation 状态机的转移规则
  - JDBC Driver 是 REST 客户端而非嵌入式
  - Continuous Refresh 与 Full Refresh 的源码路径差异
  - Batch 模式在 Materialized Table 刷新中的角色

---

## 22.1 — 设计动机：从"单次运行"到"多租户 SQL 服务"

默认 Flink SQL 的模式是一个 Job 一次运行。SQL Gateway 将其改为类似 MySQL Gateway 的"始终运行的服务"——支持多客户端并发提交 SQL，管理 Session 上下文。

```
SqlGateway (入口)
  ├── SqlGatewayServiceImpl (核心服务层)
  ├── SessionManager → SessionManagerImpl (Session 生命周期)
  │     └── Session → SessionContext → OperationManager → OperationExecutor
  └── SqlGatewayEndpoint (对外协议层)
        ├── SqlGatewayRestEndpoint (REST/HTTP, Netty)
        └── [扩展点] 自定义 Endpoint 实现
```

源码入口：`org.apache.flink.table.gateway.SqlGateway:L#47`

为什么这样设计：将 Endpoint（协议适配）和 Service（业务逻辑）解耦，解决多协议接入问题。放弃了类似 HiveServer2 统一用 Thrift 的方案——REST 更轻量，JDBC 作为 REST 的客户端封装，避免 Thrift 依赖的侵入性。

---

## 22.2 — 核心数据结构

### 22.2.1 SessionHandle 与 OperationHandle

两者结构对称——都是 `UUID identifier` 的薄封装：

```java
// org.apache.flink.table.gateway.api.session.SessionHandle:L#28
public class SessionHandle {
    private final UUID identifier;
    public static SessionHandle create() { return new SessionHandle(UUID.randomUUID()); }
}
// OperationHandle 结构完全同构，见 org.apache.flink.table.gateway.api.operation.OperationHandle:L#28
```

为什么这样设计：用 UUID 而非自增 ID，解决分布式场景下 ID 冲突问题，放弃 ID 可排序性。Handle 不携带业务数据，仅做索引——真正状态在 `Session` / `Operation` 对象内部。

### 22.2.2 Session 的生命周期管理

Session 由 `SessionManagerImpl` 统一管理，核心字段：

```java
// org.apache.flink.table.gateway.service.session.SessionManagerImpl:L#54
private final long idleTimeout;         // 默认 10min
private final long checkInterval;       // 默认 1min
private final int maxSessionCount;      // 默认 1,000,000
private final Map<SessionHandle, Session> sessions;  // ConcurrentHashMap
```

生命周期三阶段：

1. **创建**：`openSession()` 生成唯一 SessionHandle，构建 `SessionContext`（内含 CatalogManager、ModuleManager、FunctionCatalog、ResourceManager、OperationManager），包装为 `Session` 存入 Map，同时检查 `maxSessionCount`。
2. **存活**：每次 `getSession()` 触发 `session.touch()` 更新 `lastAccessTime`。定时器按 `checkInterval` 周期扫描，超 `idleTimeout` 未访问的 Session 自动关闭（`org.apache.flink.table.gateway.service.session.SessionManagerImpl:L#192`）。
3. **销毁**：`closeSession()` 从 Map 移除并调用 `session.close()`，级联释放 OperationManager、ResourceManager 等资源。

### 22.2.3 Operation 的状态机

Operation 是单条 SQL 的执行单元，状态转移由 `AtomicReference<OperationStatus>` + CAS 保证线程安全：

```
INITIALIZED ──→ PENDING ──→ RUNNING ──→ FINISHED
     │             │           │          ↓
     ├──→ CANCELED ├──→ CANCELED ├──→ CANCELED → CLOSED
     ├──→ CLOSED   ├──→ CLOSED   ├──→ TIMEOUT
     └──→ ERROR    └──→ ERROR    └──→ ERROR
```

```java
// org.apache.flink.table.gateway.api.operation.OperationStatus:L#30
public enum OperationStatus {
    INITIALIZED(false), PENDING(false), RUNNING(false),  // 非终态
    FINISHED(true), CANCELED(true), CLOSED(true), ERROR(true), TIMEOUT(true);  // 终态
}
```

关键设计：`OperationManager` 用 `Semaphore(1)` 控制 Operation 串行执行——因为 CatalogManager 等组件非线程安全。这放弃了并发执行能力，换来正确性保证（`org.apache.flink.table.gateway.service.operation.OperationManager:L#75`）。

### 22.2.4 SqlGatewayEndpoint 接口

Endpoint 是协议适配层，接口极简：

```java
// org.apache.flink.table.gateway.api.endpoint.SqlGatewayEndpoint:L#25
public interface SqlGatewayEndpoint {
    void start() throws Exception;
    void stop() throws Exception;
}
```

内置实现 `SqlGatewayRestEndpoint` 基于 Netty（继承 `RestServerEndpoint`），注册的 Handler 族包括：`OpenSessionHandler`、`CloseSessionHandler`、`ExecuteStatementHandler`、`FetchResultsHandler`、`RefreshMaterializedTableHandler` 等。

### 22.2.5 Materialized Table 的接口定义

`CatalogMaterializedTable` 定义物化表核心元数据：

```java
// org.apache.flink.table.catalog.CatalogMaterializedTable:L#51
public interface CatalogMaterializedTable extends CatalogBaseTable {
    String getExpandedQuery();                    // 展开后的定义查询
    IntervalFreshness getDefinitionFreshness();   // 数据新鲜度
    LogicalRefreshMode getLogicalRefreshMode();   // 逻辑刷新模式
    RefreshMode getRefreshMode();                 // 物理刷新模式
    RefreshStatus getRefreshStatus();             // 刷新状态
    byte[] getSerializedRefreshHandler();         // 序列化的刷新句柄
}
```

逻辑刷新模式映射规则：`CONTINUOUS` → `RefreshMode.CONTINUOUS`，`FULL` → `RefreshMode.FULL`，`AUTOMATIC` → 根据 freshness 阈值自动选择。刷新状态三态：`INITIALIZING` → `ACTIVATED` ↔ `SUSPENDED`。

### 22.2.6 RefreshHandler

`RefreshHandler` 是刷新管线元信息的抽象接口（`org.apache.flink.table.refresh.RefreshHandler:L#40`）。Continuous 模式的实现 `ContinuousRefreshHandler` 保存集群定位：`executionTarget`、`clusterId`、`jobId`、`restorePath`（Suspend 时的 savepoint）。Full 模式由用户通过 `WorkflowScheduler` 插件自定义实现。

`IntervalFreshness` 将用户声明的 `"1" MINUTE` 解析为结构化时间间隔，并能通过 `convertFreshnessToCron()` 转换为 Cron 表达式供 Full Refresh 调度。注意 Cron 转换有约束：秒级需 < 60 且整除 60，分/时级同理，日级只支持 1 天。这是因为 Cron 表达式与固定间隔并非等价映射，只能支持有限的 freshness 模式（`org.apache.flink.table.catalog.IntervalFreshness:L#250`）。

---

## 22.3 — 关键流程走读

### 22.3.1 SQL Gateway 处理请求的完整流程

以 `executeStatement` 为例：

```
REST Client → POST /v3/sessions/:handle/statements
  → ExecuteStatementHandler → SqlGatewayServiceImpl.executeStatement()
    → sessionManager.getSession(handle)  // touch() 更新访问时间
    → session.getOperationManager().submitOperation()
      → OperationHandle.create() → new Operation(handle, fetcherSupplier)
      → operation.run()  // Semaphore.acquire()
        → PENDING → RUNNING
        → session.createExecutor().executeStatement(handle, statement)
          → OperationExecutor: parse → 分发到 callXxxOperation()
        → RUNNING → FINISHED → Semaphore.release()
```

`OperationExecutor.executeStatement()` 是核心分发器（`org.apache.flink.table.gateway.service.operation.OperationExecutor:L#230`），`MaterializedTableOperation` 路由到 `MaterializedTableManager.callMaterializedTableOperation()`，`QueryOperation` 走 `ResultFetcher.fromTableResult(handle, result, true)` 支持流式持续拉取。

### 22.3.2 JDBC Driver 的工作原理

JDBC Driver 不是嵌入 Gateway 的薄层，而是独立的 REST 客户端：

```
JDBC Client → FlinkDriver.connect(url, props)
  → FlinkConnection(DriverUri)
    → Executor.create(defaultContext, address, sessionId, RowFormat.JSON)
      → ExecutorImpl (REST 客户端, 调用 Gateway REST API)
```

`FlinkDriver.jdbcCompliant()` 返回 `false`——事务方法（`setAutoCommit`、`setTransactionIsolation`）是空实现，仅为兼容 beeline 不抛异常。`FlinkConnection.close()` 底层调用 `executor.close()` 会关闭 Gateway Session，务必确保 close 被调用。

### 22.3.3 Materialized Table 的增量刷新流程

**Continuous Refresh**（源码：`MaterializedTableManager:L#536`）：

1. `createMaterializedTableInContinuousMode()` 先将表元数据写入 Catalog
2. `executeContinuousRefreshJob()` 构造 `INSERT INTO mt <definition_query>`，设置 `RUNTIME_MODE=STREAMING`、`checkpointing.interval=freshness`
3. 提交流式 Job → 获取 JobID → 构造 `ContinuousRefreshHandler(executionTarget, clusterId, jobId)`
4. RefreshHandler 序列化后存入 Catalog 表属性

**Full Refresh**（源码：`MaterializedTableManager:L#248`）：

1. `createMaterializedTableInFullMode()` 要求 `workflowScheduler != null`
2. `IntervalFreshness.convertFreshnessToCron()` 转换为 Cron 表达式
3. 通过 `workflowScheduler.createRefreshWorkflow()` 注册到 `EmbeddedQuartzScheduler`
4. 每次调度触发时，Quartz Job 通过 REST API 回调 `RefreshMaterializedTableHandler`，以 `RUNTIME_MODE=BATCH` 执行 `INSERT OVERWRITE`

### 22.3.4 Suspend/Resume 的源码路径

Continuous 模式的 Suspend 是 Stop with Savepoint（`MaterializedTableManager:L#330`）：`stopJobWithSavepoint()` 获取保存点路径，构造新的 `ContinuousRefreshHandler(..., savepointPath)` 存入 Catalog。Resume 时从 `restorePath` 恢复流式 Job，实现状态续传。

### 22.3.5 Session 的 Catalog 和 Database 切换

Session 内通过 `USE CATALOG` / `USE DATABASE` 切换上下文。JDBC Driver 的 `setCatalog()` 底层就是执行 `USE CATALOG` 语句：

```java
// org.apache.flink.table.jdbc.FlinkConnection:L#150
private void setSessionCatalog(String catalog) {
    executor.configureSession(String.format("USE CATALOG %s;", catalog));
}
```

这些切换操作通过 `OperationExecutor.configureSession()` 执行，仅允许 SET/RESET/DDL/USE 等元数据操作，不允许 DML。`configureSession()` 是同步阻塞的——会 `awaitOperationTermination()` 等待配置完成后再返回。

每个 Session 拥有独立的 `CatalogManager` 实例（通过 `SessionContext.create()` 构建），因此不同 Session 的 Catalog 切换互不影响。

---

## 22.4 — 横向对比（Spark / StarRocks / MaxCompute）

### vs Spark Thrift Server

| 维度 | Spark Thrift Server | Flink SQL Gateway |
|---|---|---|
| **协议** | HiveServer2 (Thrift) | REST + JDBC (REST 客户端) |
| **Session 隔离** | HiveConf per user，共享 SparkContext | CatalogManager per Session |
| **结果获取** | FetchSize N，批量 | token-based 游标，流式持续拉取 |
| **流支持** | 仅批 | 流+批同时支持 |
| **并发模型** | 共享 SparkContext 资源竞争 | Operation 串行（Semaphore），Session 间隔离 |

为什么 Flink 放弃 HiveServer2 协议：HiveServer2 为批查询设计，无法表达流式结果的持续推送。REST + token-based fetch 天然适配"结果可能无穷"的流场景。

### vs StarRocks FE

StarRocks 物化视图是"同步维护"——数据写入时自动更新视图，查询时自动改写路由。Flink Materialized Table 是"异步维护"——通过独立 Job 刷新。前者延迟更低但写入吞吐受限，后者解耦但存在刷新延迟。StarRocks 兼容 MySQL 协议，BI 工具直连；Flink 需专用 JDBC Driver，但支持流式结果持续返回——`fetchResults()` 可循环拉取无尽数据流，这是 StarRocks 的 MySQL 协议做不到的。

### vs MaxCompute ODPS JDBC

MaxCompute 有独立的调度层（Fuxi）和 Tunnel 服务，架构更重。Flink SQL Gateway 更轻量，直接复用 Flink Cluster 的 Dispatcher。多租户方面，MaxCompute 用 Project + Quota 管理，Flink 用 Session 级隔离 + maxSessionCount 限制。结果传输方面，MaxCompute 通过 HTTP Tunnel 分批拉取，Flink 通过 REST token-based 游标拉取，模型类似但 Flink 额外支持流式结果。

---

## 22.5 — 调优与实战陷阱

### 22.5.1 Session 泄漏

**现象**：Gateway 长时间运行后 Session 数达 `sql-gateway.session.max-num`（默认 100 万）后拒绝新连接。**根因**：客户端未调用 `closeSession()`。**调优**：合理设 `idle-timeout`（默认 10min），生产环境 30min；JDBC 连接池配 `maxIdleTime` 确保空闲连接回收。

### 22.5.2 大结果集的 OOM 风险

**现象**：`SELECT * FROM huge_table` 导致 Gateway OOM。**根因**：`ResultFetcher` 内存 buffer 无上限。**调优**：客户端分页拉取 `fetchResults(token, maxRows=1000)`；SQL 层加 LIMIT；Gateway JVM 堆 4GB+，降低 `worker.threads.max` 减少并发内存。

### 22.5.3 Materialized Table 的刷新延迟

**根因**：Cron 精度限制（`convertFreshnessToCron()` 只支持整除值）；Quartz 触发偏差；Batch Job 启动排队；Continuous 的 Checkpoint 间隔 > freshness。**调优**：Continuous 模式设 `checkpointing.interval` ≤ freshness；Full 模式必要时用外部 Airflow 替代 EmbeddedQuartzScheduler；用 `ALTER MATERIALIZED TABLE ... REFRESH` 手动补偿。

### 22.5.4 JDBC Driver 的连接池管理

`FlinkDriver.jdbcCompliant() == false`，部分连接池会校验 JDBC 兼容性——需关闭合规检查。`setAutoCommit()` 是空操作，不要依赖事务语义。`FlinkConnection.close()` 会关闭 Gateway Session——务必确保 close 被调用。

### 22.5.5 Operation 串行瓶颈

同一 Session 下 SQL 无法并发执行——`OperationManager.operationLock = Semaphore(1)`。**解决**：为高并发场景分配独立 Session；单 Session 内串行是设计决策（CatalogManager 非线程安全）。如需 Session 内并发，需等社区解决 CatalogManager 线程安全问题（FLINK-27838 相关）。

### 22.5.6 Continuous Refresh 的 Suspend 前置条件

Suspend Continuous Refresh Job 需要 `savepoint directory` 已配置，否则 `stopJobWithSavepoint()` 会抛 `ValidationException`（`MaterializedTableManager:L#1098`）。生产环境务必配置 `execution.checkpointing.savepoint-directory`，否则 Suspend 操作不可用。

---

## 本章要点回顾

1. SQL Gateway 让 Flink 变成多租户 SQL 服务——Session 隔离、Operation 串行（Semaphore）、REST+JDBC 双协议。
2. SessionHandle / OperationHandle 都是 UUID 封装，生命周期由 SessionManager（idleTimeout 回收）和 OperationManager（CAS 状态机）管理。
3. Materialized Table 双模式：Continuous 走 Streaming Job + Checkpoint，Full 走 Batch Job + Quartz Cron。
4. JDBC Driver 本质是 REST 客户端——`FlinkConnection` 通过 `ExecutorImpl` 调用 Gateway REST API。
5. RefreshHandler 是刷新管线元信息抽象——Continuous 保存 JobID/ClusterId/SavepointPath，Full 保存 WorkflowId，序列化后存 Catalog。
6. Operation 串行执行是正确性妥协——CatalogManager 非线程安全，高并发场景需分配独立 Session。

## 源码导航

- Gateway 入口：`org.apache.flink.table.gateway.SqlGateway`
- Service 接口：`org.apache.flink.table.gateway.api.SqlGatewayService`
- Service 实现：`org.apache.flink.table.gateway.service.SqlGatewayServiceImpl`
- Session 管理：`org.apache.flink.table.gateway.service.session.SessionManagerImpl`
- Session 对象：`org.apache.flink.table.gateway.service.session.Session`
- Session 上下文：`org.apache.flink.table.gateway.service.context.SessionContext`
- SessionHandle：`org.apache.flink.table.gateway.api.session.SessionHandle`
- Operation 状态机：`org.apache.flink.table.gateway.api.operation.OperationStatus`
- OperationManager：`org.apache.flink.table.gateway.service.operation.OperationManager`
- OperationExecutor：`org.apache.flink.table.gateway.service.operation.OperationExecutor`
- REST Endpoint：`org.apache.flink.table.gateway.rest.SqlGatewayRestEndpoint`
- Endpoint 接口：`org.apache.flink.table.gateway.api.endpoint.SqlGatewayEndpoint`
- JDBC Driver：`org.apache.flink.table.jdbc.FlinkDriver`
- JDBC Connection：`org.apache.flink.table.jdbc.FlinkConnection`
- MaterializedTableManager：`org.apache.flink.table.gateway.service.materializedtable.MaterializedTableManager`
- CatalogMaterializedTable：`org.apache.flink.table.catalog.CatalogMaterializedTable`
- RefreshHandler：`org.apache.flink.table.refresh.RefreshHandler`
- ContinuousRefreshHandler：`org.apache.flink.table.refresh.ContinuousRefreshHandler`
- IntervalFreshness：`org.apache.flink.table.catalog.IntervalFreshness`
- EmbeddedQuartzScheduler：`org.apache.flink.table.gateway.workflow.scheduler.EmbeddedQuartzScheduler`
- Service 配置：`org.apache.flink.table.gateway.api.config.SqlGatewayServiceConfigOptions`
