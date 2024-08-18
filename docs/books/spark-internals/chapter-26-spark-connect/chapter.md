# 第 26 章：Spark Connect — gRPC 上的 Spark 会话解耦

## 设计动机

自 Spark 诞生以来，"用 Spark"这件事就有一个隐含的前提：**你的代码运行在同一个 JVM 进程中**，或者是它的旁边（PySpark 的 sidecar 模式）。这种紧耦合产生了三个连锁难题：

1. **版本耦合**：Client 需要与 Server 相同的 Spark 版本。升级 Server → 必须升级所有 Client 环境。在一个有数百个 Jupyter notebook 的组织中，这意味着"Spark 升级 = 全员重装环境"。

2. **语言绑定困难**：如果你想从 Go 或 Rust 程序调用 Spark，你需要实现整个 Py4J socket 协议 + 管理 JVM sidecar 进程。这阻挡了 Spark 连接所有语言的愿景。

3. **资源隔离脆弱**：Client 的任何 bug（如内存泄漏、死循环）直接影响 Driver JVM 的稳定性。一个用户的 notebook crash 可能拖累整个 Spark Driver。

Spark Connect（Spark 3.4+）的解决方案是：**把 Spark 的 DataFrame API 翻译为一套 gRPC 协议**。客户端只负责构建"逻辑计划"的 proto 消息，通过网络发给 Server——Server 运行真正的 Spark Driver，解析 proto plan → 转为 Catalyst 逻辑计划 → 规划+执行 → 通过 Arrow 返回结果。

```
传统 PySpark 模式:
  Python Client ──Py4J TCP──→ JVM Driver ──→ Executors
  (同一主机/容器)

Spark Connect 模式:
  Python/Go/Rust Client ──gRPC(HTTP/2+TLS)──→ Spark Connect Server(Different Host)
                                                └── Spark Driver ──→ Executors
```

这是一种"把 DataFrame API 变成 REST/gRPC API"的设计——类似 Snowflake 的 JDBC Driver 或 BigQuery 的 REST API，但 Spark Connect 走得更远：它不只是 SQL，而是可以表达完整的 DataFrame 操作链。

## 核心原理

### 26.1 Proto 协议 — Relation/Expression/Plan 的三层定义

Spark Connect 的核心协议定义在 Proto 文件中。与 PySpark 的 `df.filter().groupBy().count()` 的每步都是一次 Py4J 调用不同，Spark Connect 客户端将整个操作链序列化为一个 `Plan` proto 消息——在客户端构建完成后再一次性发送：

```protobuf
// spark/connect/base.proto
message Plan {
  oneof op_type {
    Relation root = 1;                   // 完整的数据流 DAG
    Command command = 2;                 // 命令 (SQL, WriteStream, etc.)
    CompressedOperation compressed_operation = 3;  // zstd 压缩
  }
}

// spark/connect/relations.proto
message Relation {
  RelationCommon common = 1;  // source_info (用于 plan id mapping), plan_id
  oneof rel_type {
    Read read = 2;           // 数据源 (表、文件、Kafka)
    Project project = 3;     // SELECT 列
    Filter filter = 4;       // WHERE
    Join join = 5;           // JOIN
    Aggregate aggregate = 9; // GROUP BY + aggregate
    SQL sql = 10;            // 原始 SQL (退回 safe mode)
    Sort sort = 7;
    Limit limit = 8;
    LocalRelation local_relation = 11;  // 本地数据 (如 from pandas → spark)
    Deduplicate deduplicate = 14;       // dropDuplicates
    // ... 40+ relation types
  }
}

// spark/connect/expressions.proto
message Expression {
  oneof expr_type {
    Literal literal = 1;
    UnresolvedAttribute unresolved_attribute = 2;   // 'col_name'
    UnresolvedFunction unresolved_function = 3;     // count(), sum(), etc.
    Alias alias = 4;
    Cast cast = 5;  // CAST
    // ... 40+ expression types
  }
}
```

这个设计的关键是：**Proto `Relation` 组成了一个 DAG**——`Relation.filter.input.plan_id` 指向其子 Relation，从而重建整个操作链。这与 Catalyst 的 `TreeNode` 树结构等价，但用 proto `oneof` + `plan_id` 引用实现。

```python
# Python 客户端: DataFrame.filter() 不调用服务器, 只构建 proto
df = spark.read.table("orders")
df2 = df.filter(df.amount > 1000).select("customer_id", "amount")

# df2 内部的 proto Plan:
# Plan(root=Relation(
#   rel_type=Project(columns=[customer_id, amount])
#     input=Relation(
#       rel_type=Filter(condition=Expression(amount > 1000))
#         input=Relation(
#           rel_type=Read(data_source=table, name="orders"))))))
```

### 26.2 gRPC 服务 — 14 个 RPC 的职责划分

SparkConnectService proto 定义了 14 个 RPC：

```
核心 RPC:
  ExecutePlan(ExecutePlanRequest) → stream ExecutePlanResponse
    主执行入口: 提交 Plan → 返回 Arrow 的 stream
    返回 stream 允许逐批拉取结果 (不一次性全量)

  AnalyzePlan(AnalyzePlanRequest) → AnalyzePlanResponse
    分析计划: schema/explan/input_files/is_local/is_streaming

会话管理 RPC:
  Config(ConfigRequest) → ConfigResponse
    GET/SET SparkSession configurations

  AddArtifacts(stream AddArtifactsRequest) → AddArtifactsResponse
    上传 jar/py 文件到 Server (UDF 依赖)

  CloneSession(CloneSessionRequest) → CloneSessionResponse
    克隆一个有状态的 session (临时视图、UDF 注册、配置)

  ReleaseSession(ReleaseSessionRequest) → ReleaseSessionResponse
    显式释放 session

执行管理 RPC:
  Interrupt(InterruptRequest) → InterruptResponse
    中断正运行的查询

  ReattachExecute(ReattachExecuteRequest) → stream ExecutePlanResponse
    重新附加到之前的执行 (client 断开后从 Server cache 恢复)

  ReleaseExecute(ReleaseExecuteRequest) → ReleaseExecuteResponse
    释放一个 reattachable 执行

状态查询 RPC:
  FetchErrorDetails(FetchErrorDetailsRequest) → FetchErrorDetailsResponse
  GetStatus(GetStatusRequest) → GetStatusResponse
  ArtifactStatus(ArtifactStatusesRequest) → ArtifactStatusesResponse
```

**ExecutePlan 的流式响应模式**：

```
ExecutePlan(request) → Server
  → Server 分配 ExecuteHolder + ExecuteThreadRunner
  → Server 执行查询:
      SparkConnectPlanner.transform(proto.Relation) → Catalyst LogicalPlan
      → Catalyst Optimizer → PhysicalPlan → execute
  → 结果通过 Arrow IPC 编码 → 逐个响应给 client stream
  → Server 流式发送 ExecutePlanResponse:
      1. ARROW_BATCH (schema + data batch)
      2. ARROW_BATCH (more data)
      ...
      N. RESULT_COMPLETE (metrics + observed_metrics + num_rows)
  → 流关闭
```

每条响应包含一个 `response_type`：`ARROW_BATCH` (数据)，`SQL_COMMAND_RESULT`（SQL 命令的返回值），`REATTACHABLE_EXECUTE`（执行可用于后续 reattach），或 `RESULT_COMPLETE`（执行完成，带指标和行数）。

### 26.3 SparkConnectPlanner — Proto → Catalyst 的翻译器

`SparkConnectPlanner` 是 Server 端将 proto `Relation` 翻译为 Catalyst `LogicalPlan` 的核心。它在结构上与 PySpark 的 `DataFrame._jdf` 调用链对应，但做的是**批量式翻译**（一次翻译整个 DAG）而非**逐步式代理**：

```scala
// SparkConnectPlanner.transformRelation(proto.Relation):
proto.Relation.rel_type match {
  case Read(read)         => transformRead(read)            // → UnresolvedRelation
  case Project(project)   => transformProject(project)       // → logical.Project
  case Filter(filter)     => transformFilter(filter)         // → logical.Filter
  case Aggregate(agg)     => transformAggregate(agg)         // → logical.Aggregate
  case Join(join)         => transformJoin(join)             // → logical.Join
  case SQL(sql)           => transformSql(sql)               // → 直接解析 SQL
  case LocalRelation(lr)  => transformLocalRelation(lr)      // → LocalRelation
  case RelationCommon(plan_id) => resolvePlanId(plan_id)     // → 查找已翻译的节点
  // ... etc
}

// 关键的 transformExpression:
// Expression.UnresolvedFunction("count", [Expression.UnresolvedAttribute("*")])
// → catalyst.expressions.UnresolvedFunction("count", [UnresolvedStar])
```

`SparkConnectPlanner` 也处理 Command（`SqlCommand`、`WriteStreamOperationStart`、`StreamingQueryCommand` 等）—这些通过 `processCommand()` 方法分发。

一个重要概念是 **plan_id 引用**：`RelationCommon` 包含 `plan_id: int64`。如果一个 `Filter` 引用 `input = Relation(common={plan_id=3})`，则 planner 会从 LPB（Logical Plan Builder）中查找 plan_id=3 对应的已翻译节点。这种"引用"避免了 proto 中的深度嵌套——相当于 `TreeNode` 中 child 的指针等效物。

### 26.4 客户端 — 语言无关的 DataFrame API 包装

客户端（Python 为例）的实现模式是"惰性构建 proto + 显式 execute"：

```python
# python/pyspark/sql/connect/dataframe.py
class DataFrame:
    def __init__(self, plan: proto.Relation, session: SparkSession):
        self._plan = plan           # proto.Relation (尚未发送)
        self._session = session
    
    def filter(self, condition: Column) -> "DataFrame":
        # 不发送 RPC! 只创建一个新的 proto.Relation(Filter)
        plan = proto.Relation(
            filter=proto.Filter(
                input=self._plan,
                condition=condition._expr  # proto.Expression
            )
        )
        return DataFrame(plan, self._session)
    
    def collect(self) -> List[Row]:
        # 这时才真正发送 executePlan RPC
        return self._session.client.execute(self._plan)
    
    def show(self, n=20, truncate=True):
        # show 也是走了 execute (不是 analyze)
        ...
```

客户端的职责是**只构建 plan，不执行**。这对 SQL 和 DataFrame 都是同一种模式——甚至 `spark.sql("SELECT ...")` 也是构建一个 `Relation(sql=...)` proto 消息。

当结果返回时，Python 客户端处理两种数据格式：
1. **ArrowTable**（默认）：Server 通过 gRPC `ExecutePlanResponse` stream 发送 ArrowRecordBatch → 客户端转为 `pa.Table` → 转为 `pandas.DataFrame` 或 `Row` list
2. **JSON**（fallback，通过 `spark.sql.execution.arrow.enabled=false` 触发）：每行转为 JSON → 文本流

`ReattachExecute` 机制处理 grpc 连接中断：如果执行被标记为 `reattachable=true`，Server 缓存执行结果（在 `ExecuteHolder` 中）。如果客户端断连，可以用 `ReattachExecute(execute_id, last_response_id)` 重新连接并从上次中断的位置继续接收结果——这对长时间运行的 streaming 或大结果集至关重要。

### 26.5 Session 管理 — 多租户隔离与生命周期

`SparkConnectSessionManager` 维护一个 `ConcurrentHashMap[UserId → SessionHolder]`。每个 Session：
- 有一个独立的 `SparkSession`（带隔离的 config、temp views、registered UDFs）
- 有自己的 `ExecuteHolder` 集（跟踪正运行的执行）
- 通过 `session_id`（UUID）关联

```
Session 生命周期:
  创建: 第一个 ExecutePlan/AnalyzePlan/Config 请求 (lazy)
  Active: 通过周期性 RPC 保持 alive
  过期: 默认 3600 秒无 RPC → 自动移除
  克隆: CloneSession → 拷贝临时视图+UDF+配置 → 获得新 session_id
  释放: ReleaseSession 显式释放 / Server shutdown
```

`CloneSession` 特别有趣——它支持"Branch a session"的使用模式。比如数据科学家想在 Session A 中建一张临时视图，然后在 Session B 中在此基础上测试不同的聚合逻辑而不影响 A。

### 26.6 与传统 PySpark 的对比

| 维度 | 传统 PySpark (Py4J) | Spark Connect |
|------|-------------------|---------------|
| 通信协议 | Py4J TCP Socket (端口回顾) | gRPC (HTTP/2, 端口 15002) |
| 客户端语言 | Python, R | Python, Go, Rust, Java, Scala, Kotlin |
| 升级依赖 | Client 和 Server 同一 Spark 版本 | Client 和 Server 版本解耦 |
| 驱动程序 | Python 进程 + JVM sidecar | 独立 Server, 纯客户端库 |
| 交互模式 | 逐次调用 (df.filter() → Py4J call) | 惰性构建 (df.filter() → 修改 proto) |
| 大结果传输 | Arrow (Socket) | Arrow (gRPC message) |
| UDF 支持 | Python UDF 直接在 sidecar 中执行 | Python UDF 在当前进程执行 (client-side) |
| 适用场景 | Local development, 传统 ETL | Remote IDE, 云服务, 多语言生态 |

### 26.7 安全与认证 — gRPC 拦截器链

Spark Connect Server 使用 gRPC 拦截器（Interceptor）链实现认证和中间件：

```
Client Request → RequestDecompressionInterceptor (解压zstd)
    → PreSharedKeyAuthenticationInterceptor (可选, 预共享密钥验证)
    → LoggingInterceptor (请求日志)
    → SparkConnectService (业务处理)
    → LocalPropertiesCleanupInterceptor (清理线程本地 props)
```

认证是灵活的：通过 `spark.authenticate` 和 `spark.authenticate.secret` 配置，`PreSharedKeyAuthenticationInterceptor` 基于 HTTP "Authorization: Bearer <token>" Header 进行验证。这比 Py4J 的本地 socket 权限控制更成熟——Spark Connect 默认设计为"可以跨越网络"，所以安全性是设计伊始就内置的。

## 关键代码片段

### 示例：ExecutePlan 请求-响应流

```
Python Client:
  df.filter(df.age > 30).collect()
  
  → 构造 ExecutePlanRequest {
      session_id="a1b2c3d4-...",
      user_context={user_id="user123", user_name="Alice"},
      client_type="_SPARK_CONNECT_PYTHON",
      plan=Plan {
        root=Relation {
          filter=Filter {
            input=Relation { read=Read { table="people" } },
            condition=Expression {
              unresolved_function=UnresolvedFunction {
                function_name="gt",
                arguments=[
                  Expression { unresolved_attribute="age" },
                  Expression { literal=Literal { long=30 } }
                ]
              }
            }
          }
        }
      }
    }

Server Response Stream:
  → ExecutePlanResponse { arrow_batch=Batch1 (schema + 1000 rows) }
  → ExecutePlanResponse { arrow_batch=Batch2 (1000 rows) }
  → ExecutePlanResponse { arrow_batch=Batch3 (250 rows) }
  → ExecutePlanResponse { result_complete={
        metrics=[{name:"numOutputRows", value:2250}],
        num_rows=2250
      }}
```

### 示例：Python Client 的 execute 方法

```python
# python/pyspark/sql/connect/client/core.py (简化)
class SparkConnectClient:
    def execute(self, plan: proto.Plan) -> List[Row]:
        req = proto.ExecutePlanRequest(
            session_id=self._session_id,
            user_context=self._user_context,
            plan=plan,
            client_type="_SPARK_CONNECT_PYTHON"
        )
        
        # 发起 gRPC unary-stream call
        for response in self._stub.ExecutePlan(req):
            if response.HasField("arrow_batch"):
                # 累加 Arrow 数据
                self._accumulate_batch(response.arrow_batch)
            elif response.HasField("result_complete"):
                # 执行完成
                break
        
        # Arrow → pandas → list[Row]
        return self._to_rows(self._collected_data)
```

## 硬件视角

**gRPC 批量传输 vs Py4J 逐步调用的网络效应**：

传统 PySpark 的 `df.filter().groupBy().count()` 产生 ~4 次 Py4J TCP 往返。Spark Connect 只有 **1 次 gRPC 调用**。网络延迟的影响因子完全不同：

```
LAN 场景 (延迟 0.1ms): Py4J 往返 = 4×0.1ms = 0.4ms overhead
WAN 场景 (延迟 50ms):  Py4J 往返 = 4×50ms = 200ms overhead

Spark Connect: 1 次 gRPC server 执行 = 网络延迟只发生 1 次
→ 对远程 IDE 或云端调用场景，Connect 有 10-100× 的延迟节约
```

**Arrow Batch Size 与 gRPC Message Size 的 trade-off**：

`spark.connect.grpc.arrow.maxBatchSize` 控制单次 gRPC 响应的最大 Arrow 数据量。gRPC 默认最大消息大小为 4MB (`CONNECT_GRPC_MAX_INBOUND_MESSAGE_SIZE`)。如果在 10GbE 链路上 batch size=256MB，单次 gRPC 响应传输本身就会因为 TCP 窗口增长、流控而占据大量时间。理想的 batch size = min(BDP (bandwidth-delay-product), gRPC max_message_size)。

## AI 时代反思

Spark Connect 将 DataFrame API 从一个"进程内的类库"变成了一个"网络上的协议"——这与 AI Agent 在 2025 年面临的"Function Calling"转变有惊人的相似之处。当 LLM Agent 要通过 Spark Connect 调用 Spark 时，用户代码不再是"一段在 Server 本地执行的 Python/Scala 脚本"——而是"Client 端构建 Plan 消息 + 发送 + 等待结果"。Agent 不再需要 "import pyspark and run shell"——它只需要一个 gRPC client。

这种解耦改变了一切：
- 一个 Python LLM Agent 可以在 1 台机器上运行，而 100 个 Spark Connect Servers 在数据中心里不休不眠
- Agent 可以创建 session、注册临时视图、运行查询、clone session、释放 session——全部通过 gRPC API 完成
- 如果 Agent 生成了一个错误的 filter（`df.filter(df.age > "")`），错误发生在 Server 端——Agent 只需要处理 gRPC Status 而非 Spark 内部异常

更进一步，`AnalyzePlan` RPC 特别适合 AI Agent 的"先验证再执行"模式——Agent 可以先生成一个 plan → 发送 AnalyzePlan 请求 → 获取 schema 和 explain → 确认正确后再发送 ExecutePlan。这比"直接执行 + 看错误"更高效——因为 schema 验证不需要读取任何实际数据。

## 源码导航

| 文件 | 关键内容 | 行号参考 |
|------|---------|---------|
| `sql/connect/common/src/main/protobuf/spark/connect/base.proto` | SparkConnectService 定义，ExecutePlan/AnalyzePlan/Config 等 14 个 RPC，Plan/UserContext/ExecutePlanRequest/ExecutePlanResponse | ~1311 (service SparkConnectService) |
| `sql/connect/common/src/main/protobuf/spark/connect/relations.proto` | Relation 定义，oneof rel_type (Read/Project/Filter/Join/Aggregate/SQL 等 40+ 类型)，RelationCommon (plan_id 引用) | ~37 (message Relation) |
| `sql/connect/common/src/main/protobuf/spark/connect/expressions.proto` | Expression 定义，Literal/UnresolvedAttribute/ UnresolvedFunction/Alias 等 | |
| `sql/connect/server/src/main/scala/.../service/SparkConnectService.scala` | SparkConnectService 主类，executePlan/analyzePlan/config 请求分发 | ~59 (class) |
| `sql/connect/server/src/main/scala/.../planner/SparkConnectPlanner.scala` | Proto Plan → Catalyst LogicalPlan 翻译，transformRelation/transformExpression 方法族 | |
| `sql/connect/server/src/main/scala/.../service/SparkConnectExecutePlanHandler.scala` | ExecutePlanHandler，单次执行处理，PlanCompressionUtils | |
| `sql/connect/server/src/main/scala/.../service/SessionHolder.scala` | SessionHolder，单个 session 的 SparkSession + ExecuteHolder 管理 | |
| `sql/connect/server/src/main/scala/.../service/SparkConnectSessionManager.scala` | SessionManager，UserId → SessionHolder 映射，session 过期 | |
| `sql/connect/server/src/main/scala/.../service/ExecuteHolder.scala` | ExecuteHolder，正运行的执行 + ReattachExecute 支持 | |
| `sql/connect/server/src/main/scala/.../execution/ExecuteThreadRunner.scala` | ExecuteThreadRunner，异步执行线程，ExecuteGrpcResponseSender 交互 | |
| `sql/connect/server/src/main/scala/.../execution/ExecuteGrpcResponseSender.scala` | ExecuteGrpcResponseSender，执行结果 → gRPC StreamObserver | |
| `python/pyspark/sql/connect/dataframe.py` | Python Connect DataFrame，惰性 proto Plan 构建 | |
| `python/pyspark/sql/connect/client/core.py` | SparkConnectClient，gRPC channel 管理，execute/analyze/config 调用 | |
| `sql/connect/common/src/main/protobuf/spark/connect/commands.proto` | Command 定义 (SqlCommand, WriteStreamOperationStart 等) | |
| `sql/connect/common/src/main/protobuf/spark/connect/types.proto` | DataType 的 proto 表示 | |
