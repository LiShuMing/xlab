# Chapter 1: 架构全景 — 从 Server 启动到查询响应全链路

## 1.1 二进制入口：一个 `main`，二十个程序

### 源码导航

| 文件 | 作用 |
|------|------|
| `programs/main.cpp` | 统一入口，通过 symlink / argv[1] 分发到不同子程序 |
| `programs/server/Server.h` | `class Server : public BaseDaemon, public IServer` |
| `programs/server/Server.cpp` | Server 的完整初始化、运行、关闭流程（约 2000+ 行） |
| `programs/server/clickhouse-server.cpp` | 极简入口：`mainEntryClickHouseServer` → `Server app; app.run()` |

### 架构要点

ClickHouse 只有一个二进制文件 `clickhouse`，但承载了 20+ 个子程序（client、server、local、keeper、compressor、format、disks 等）。

**分发机制** (`programs/main.cpp:148-196`)：

```cpp
// programs/main.cpp:148 — 应用注册表（按优先级排列）
std::pair<std::string_view, MainFunc> clickhouse_applications[] =
{
    {"local", mainEntryClickHouseLocal},
    {"client", mainEntryClickHouseClient},
    {"server", mainEntryClickHouseServer},
    {"keeper", mainEntryClickHouseKeeper},
    {"format", mainEntryClickHouseFormat},
    // ... 共 20+ 项
};
```

**三种分发方式** (`programs/main.cpp:218-242`)：
1. **符号链接**：`clickhouse-server` → 实际指向 `clickhouse` 的 symlink，程序检测 `argv[0]` 是否为 `clickhouse-server`
2. **首参数模式**：`clickhouse server [args]` — 第一个参数匹配应用名即分发
3. **短名别名**：`chl` → `local`，`chc` → `client`（`programs/main.cpp:207-214`）

**关键设计决策**：
- **禁止 dlopen** (`programs/main.cpp:250-272`)：通过重写 `dlopen`/`dlmopen` 返回 `nullptr`，彻底阻止插件式动态加载。ClickHouse 哲学：单一二进制，编译时确定所有能力。
- **Sanitizer 默认选项** (`programs/main.cpp:28-76`)：在代码中硬编码 ASan/LSan/MSan/TSan/UBSan 的默认行为（`halt_on_error=1 abort_on_error=1`），保证开发构建的一致行为。
- **JeMalloc 消息抑制** (`programs/main.cpp:278-303`)：Release 构建中完全静默 JeMalloc 的 stderr 输出。

> **第一性原理**：为什么一个二进制包含所有功能？这和 BusyBox 的设计哲学一致——减少磁盘占用、简化部署、消除库版本不一致问题。对 ClickHouse 这种数据库系统来说，`clickhouse-local` 和 `clickhouse-server` 共享同一份 Storage/Function/AggregateFunction 代码路径至关重要，它保证了本地开发和服务器执行的行为一致性。

> **侧边栏 · 与 Spark 对比**：Spark 采用 `spark-submit` + 胖 JAR 的分发模式，运行时动态加载用户 JAR。ClickHouse 的反向选择（全静态链接 + 禁止 dlopen）带来更强的可重现性和更低的运维复杂度，但牺牲了扩展灵活性。UDF 通过 SQL 定义而非加载 .so，这正是这个约束的体现。

---

## 1.2 Server 初始化：三步启动法

### 源码导航

| 文件 | 行号 | 关键方法 |
|------|------|----------|
| `programs/server/Server.cpp` | 721 | `Server::initialize()` — 第一步：基础设置 |
| `programs/server/Server.cpp` | 1114 | `Server::main()` — 第二步：完整初始化（约 600 行） |
| `programs/server/Server.cpp` | 701 | `Server::run()` — 第三步：进入事件循环 |

### Server::initialize() — 轻量初始化

```cpp
// programs/server/Server.cpp:721-731
void Server::initialize(Poco::Util::Application & self)
{
    // 1. 注册嵌入的默认 config.xml（编译进二进制）
    ConfigProcessor::registerEmbeddedConfig("config.xml", ...);
    // 2. 调用父类 BaseDaemon::initialize
    BaseDaemon::initialize(self);
    // 3. 打印 OS 信息
    LOG_INFO(&logger(), "OS name: {}, version: {}, architecture: {}",
        Poco::Environment::osName(), ...);
}
```

这一步非常轻量，只做配置注册和日志初始化。真正的重活都在 `main()` 中。

### Server::main() — 完整初始化（关键阶段）

这是整个服务器启动的核心，约 600 行代码。按逻辑分为以下阶段：

**阶段 1: 硬件感知**

```cpp
// programs/server/Server.cpp:1125-1148
const size_t physical_server_memory = getMemoryAmount();
LOG_INFO(log, "Available RAM: {}; logical cores: {}; used cores: {}.",
    formatReadableSizeWithBinarySuffix(physical_server_memory),
    std::thread::hardware_concurrency(),
    getNumberOfCPUCoresToUse());

// x86_64 上枚举 CPU 指令集（SSE4.2 / AVX / AVX2 / AVX512 / POPCNT / BMI 等）
CPU_ID_ENUMERATE(COLLECT_FLAG)
```

ClickHouse 在启动时就摸清硬件底牌：多少内存、多少核、支持哪些 SIMD 指令集。这些信息影响后续的线程池大小和 SIMD 优化路径选择。

**阶段 2: 可执行文件锁定（Linux）**

```cpp
// programs/server/Server.cpp:1154-1206
// remap_executable: 重新映射可执行文件的内存布局（减少 TLB miss）
if (server_settings[ServerSetting::remap_executable])
    size_t size = remapExecutable();

// mlock_executable: 将代码段锁定在物理内存中，禁止换出
if (server_settings[ServerSetting::mlock_executable])
    mlock(addr, len);
```

`remapExecutable` 是一个相当底层的优化：利用 Linux 的 `mremap` 系统调用将分散加载的 .text 段合并为大页，减少 iTLB miss。`mlock_executable` 则直接禁止内核将代码页换出——对实时查询系统而言，等待磁盘 swap-in 是不可接受的延迟。

> **第一性原理**：这些操作体现了 ClickHouse 对 OS 的不信任——它不假设内核的页面管理策略能很好地适配 OLAP 负载（大量随机读、长时间运行的聚合查询）。通过显式控制内存布局，ClickHouse 保证了自己性能的确定性。

**阶段 3: 组件注册**

```cpp
// programs/server/Server.cpp:1282-1294
registerInterpreters();      // InterpreterSelectQuery 等
registerFunctions();          // 内建 SQL 函数
registerAggregateFunctions(); // 聚合函数
registerTableFunctions();     // 表函数 (file, url, s3 等)
registerDatabases();          // 数据库引擎
registerStorages();           // 存储引擎 (MergeTree, Memory 等)
registerDictionaries();       // 字典 (flat, hashed, cache 等)
registerDisks(false);         // 磁盘类型
registerFormats();            // 序列化格式
registerRemoteFileMetadatas();// 远程文件元数据
registerSchedulerNodes();     // 资源调度节点
QueryPlanStepRegistry::registerPlanSteps();
```

这些注册函数填充了全局的工厂注册表（Factory Registry Pattern）。每个 Storage/Function/Format 都有一个单例工厂，后续通过名字查找创建实例。

**阶段 4: Context 创建**

```cpp
// programs/server/Server.cpp:1302-1306
auto shared_context = Context::createShared();
global_context = Context::createGlobal(shared_context.get());
global_context->makeGlobalContext();
global_context->setApplicationType(Context::ApplicationType::SERVER);
```

Context 的三级结构：

```
SharedContext  — 跨 Global Context 共享（主要是后台线程池、配置缓存）
  └─ Context::Global  — 服务器全局唯一，所有查询从它 fork
       └─ Context::Query  — 每查询一个，从 Global 或 Session Context fork
```

这类似于 MaxCompute 的 JobContext → TaskContext 层级，但 ClickHouse 的分叉粒度更细——每次查询都是一个 Copy-on-Write Fork。

**阶段 5: 线程池初始化**

```cpp
// programs/server/Server.cpp:1377-1610
GlobalThreadPool::initialize(...);    // 全局 CPU 密集型线程池
getIOThreadPool().initialize(...);   // I/O 线程池（S3/HDFS 读）
getBackupsIOThreadPool().initialize(...);
getActivePartsLoadingThreadPool().initialize(...);
getOutdatedPartsLoadingThreadPool().initialize(...);
getPartsCleaningThreadPool().initialize(...);
```

ClickHouse 使用多个专用线程池（静态划分），而非动态线程池：

| 线程池 | 用途 |
|--------|------|
| `GlobalThreadPool` | 查询执行（Pipeline Executor 获取 worker） |
| `IOThreadPool` | 远程文件读取（S3/HDFS 的异步 I/O） |
| `BackupsIOThreadPool` | 备份/恢复的文件传输 |
| `ActivePartsLoadingThreadPool` | 启动时加载最新 data parts 的元数据 |
| `OutdatedPartsLoadingThreadPool` | 加载过期 data parts（合并/突变产生的旧 parts） |
| `PartsCleaningThreadPool` | 清理已过期 parts 的文件 |

**阶段 6: 元数据加载与后台任务启动**

在 Context 和线程池就绪后，Server 加载数据库元数据（DatabaseCatalog）、启动 MergeTree 后台任务调度、初始化异步指标采集器等。这些后台线程负责 ClickHouse 的核心自动化运维（merge、mutation、TTL）。

**阶段 7: 监听端口**

```cpp
// programs/server/Server.cpp:619-666
void Server::createServer(config, listen_host, port_name, listen_try, ...)
{
    // 创建 TCP/HTTP/Interserver 监听 socket
    servers.push_back(func(port));
    servers.back().start();
    LOG_INFO(&logger(), "Listening for {}", servers.back().getDescription());
}
```

Server 启动三类监听器：
- **HTTP**（默认 8123）：REST API、web UI、Grafana 数据源
- **TCP**（默认 9000）：native protocol，clickhouse-client 使用
- **Interserver HTTP**（默认 9009）：节点间数据交换（replication、distributed queries）

### Server::run() — 事件循环

```cpp
// programs/server/Server.cpp:701-719
int Server::run()
{
    if (config().hasOption("help")) { /* 打印帮助 */ return 0; }
    if (config().hasOption("version")) { /* 打印版本 */ return 0; }
    return Application::run(); // 进入 Poco::Application 的事件循环
}
```

与典型的网络服务器不同，ClickHouse 在 `main()` 中完成了所有初始化工作，`run()` 只是一个薄包装——进入 Poco 框架的事件循环等待信号（SIGTERM/SIGINT）或连接。

---

## 1.3 查询生命周期：一条 SQL 的完整旅程

### 源码导航

| 文件 | 作用 |
|------|------|
| `src/Server/TCPHandler.cpp` | Native 协议查询入口，整个请求/响应循环 |
| `src/Interpreters/executeQuery.cpp` | 查询执行的核心调度函数 |
| `src/Interpreters/InterpreterSelectQuery.cpp` | SELECT 语句的解释执行 |
| `src/Interpreters/InterpreterInsertQuery.cpp` | INSERT 语句的解释执行 |
| `src/Processors/Executors/` | Pipeline Executor 实现 |

### TCPHandler::runImpl() — 查询入口

TCPHandler 的生命周期是一个大循环（`programs/server/Server.cpp:466` `while (tcp_server.isOpen())`）：

```
[客户端连接]
    │
    ├── receiveHello()       ← 握手：用户名/密码/数据库/客户端版本
    ├── sendHello()          → 服务器信息、时区、协议版本
    ├── receiveAddendum()    ← 客户端附加配置
    │
    └── 查询循环:
         ├── receivePacketsExpectQuery()  ← 接收 SQL 文本
         ├── 设置 QueryScope（日志/超时/ProfileEvents）
         ├── executeQuery(...)            ← 解析 + 规划 + 执行
         │     ├── parseQuery()           → AST
         │     ├── InterpreterSelectQuery → QueryPipeline
         │     └── PipelineExecutor       → 执行
         └── sendEndOfStream()            → 发送结果
```

**协议状态机**（`src/Core/Protocol.h`）：

ClickHouse 的 Native TCP 协议是一个紧凑的二进制协议，Packet Type 枚举定义了所有消息类型：

```
Client → Server:
  Hello(0)             握手
  Query(1)             SQL 查询（普通查询：查询文本；初始查询：还包括 QueryStage）
  Data(2)              INSERT 数据块
  Cancel(3)            取消查询

Server → Client:
  Hello(0)             握手回应
  Data(1)              结果数据块
  Exception(2)         异常
  Progress(3)          查询进度
  EndOfStream(5)       查询完成
  Log(7)               服务器日志
  ProfileEvents(11)    ProfileEvents 增量
```

### executeQuery() — 核心调度

`src/Interpreters/executeQuery.cpp` 是整个查询执行的中心枢纽：

```cpp
// 伪代码：executeQuery 的调度逻辑
std::tuple<ASTPtr, BlockIO> executeQuery(
    const String & query,          // SQL 文本
    ContextMutablePtr context,     // 查询 Context
    QueryProcessingStage::Enum stage)
{
    // 1. 解析：SQL 文本 → AST
    auto ast = parseQuery(parser, query, query_begin, query_end);

    // 2. 选择 Interpreter：根据 AST 类型分派
    //    SELECT → InterpreterSelectQuery
    //    INSERT → InterpreterInsertQuery
    //    CREATE → InterpreterCreateQuery
    //    等等
    auto interpreter = chooseInterpreter(ast, context);

    // 3. 执行：Interpreter 生成 QueryPipeline
    auto res = interpreter->execute();

    // 4. 返回 BlockIO（包含 Pipeline 和 IO streams）
    return {ast, res};
}
```

**关键架构**：Interpreter 模式 — 每种 SQL 语句由一个专门的 Interpreter 类处理：

| Interpreter | 处理的语句 |
|-------------|-----------|
| `InterpreterSelectQuery` | SELECT 查询 |
| `InterpreterInsertQuery` | INSERT 语句 |
| `InterpreterCreateQuery` | CREATE TABLE/DATABASE 等 |
| `InterpreterAlterQuery` | ALTER TABLE |
| `InterpreterDropQuery` | DROP TABLE/DATABASE |
| `InterpreterSystemQuery` | SYSTEM 命令 |
| `InterpreterKillQueryQuery` | KILL QUERY |

### 从 Interpreter 到 Pipeline

以 `InterpreterSelectQuery` 为例：

```
InterpreterSelectQuery::execute()
    │
    ├── 1. 分析 AST（ExpressionAnalyzer / Analyzer v2）
    │       │
    │       ├── 解析表名 → StoragePtr
    │       ├── 解析表达式 → ActionsDAG
    │       ├── 解析 JOIN → JoinOperator + JoinStep
    │       └── 解析聚合 → AggregatingStep
    │
    ├── 2. 构建 QueryPlan（QueryPlanBuilder）
    │       │
    │       ├── ReadFromStorage (Source Step)
    │       ├── Filter (WHERE → FilterStep)
    │       ├── Join (JoinStepLogical → JoinStep)
    │       ├── Aggregating (AggregatingStep)
    │       ├── Sorting (SortingStep)
    │       └── Limit (LimitStep)
    │
    ├── 3. QueryPlan → QueryPlanOptimizer → 优化 QueryPlan
    │       (join reorder, predicate pushdown, etc.)
    │
    └── 4. QueryPlan::buildQueryPipeline() → QueryPipeline
            │
            └── 将 Plan Steps 转换为 Processors 链
```

**QueryPlan Step 类型**（`src/Processors/QueryPlan/`）：

| Step | 作用 | 关键文件 |
|------|------|----------|
| `ReadFromMergeTree` | 从 MergeTree 读取数据 | `ReadFromMergeTree.h` |
| `FilterStep` | WHERE 条件过滤 | `FilterStep.h` |
| `JoinStepLogical` → `JoinStep` | JOIN 操作 | `JoinStepLogical.h` |
| `AggregatingStep` | GROUP BY 聚合 | `AggregatingStep.h` |
| `SortingStep` | ORDER BY 排序 | `SortingStep.h` |
| `LimitStep` | LIMIT 限制行数 | `LimitStep.h` |
| `ExpressionStep` | 表达式求值/列变换 | `ExpressionStep.h` |

### Pipeline Executor — 执行引擎

Pipeline 构建完成后，由 Executor 驱动执行：

```
QueryPipeline
    │
    └── 一系列 IProcessor 组成的 DAG
         │
         ├── Source 层: ISource 子类（读数据）
         │      └── MergeTreeSource, NullSource, ...
         │
         ├── Transform 层: ITransformer 子类（处理数据）
         │      └── FilterTransform, AggregatingTransform, ...
         │
         └── Sink 层: ISink 子类（写结果）
                └── TCPHandler 的 sendData()

Executor 类型:
├── PipelineExecutor  — 同步单线程执行
├── PullingAsyncPipelineExecutor  — 异步拉取（服务器推给客户端）
├── PushingAsyncPipelineExecutor  — 异步推送（客户端推给服务器，INSERT）
└── CompletedPipelineExecutor     — 执行到完成（无交互）
```

**TCPHandler 使用 `PullingAsyncPipelineExecutor`**：服务器侧不断 pull 结果块，并通过 TCP socket 将其流式发送给客户端。这支持增量结果返回——客户端能在查询完成前就看到初步结果。

> **第一性原理**：ClickHouse 的执行模型本质上是一个 **多阶段向量化数据流 DAG**。每个 Processor 消费和产出 `Block`（列式数据批次），并暴露 `prepare()` / `work()` 两个方法。Executor 负责拓扑调度：当一个 Processor 的所有输入端就绪且有数据可读、输出端有空闲空间可以写时，调用其 `work()` 方法。这种模型天然支持并发：Pipeline 中多个分支可以被不同线程并行驱动。

> **侧边栏 · 与 StarRocks 对比**：StarRocks 使用 MPP 模型——查询被拆分为 Fragment，每个 Fragment 在多个 BE 节点上并行执行，Fragment 之间通过网络交换数据。ClickHouse 在单节点上也采用了类似的流水线并行模型（Processors），但多节点使用的是 Scatter/Gather（Distributed Table）而非 MPP 的全对全数据交换。两者的本质差异在于：StarRocks 假设 cross-node shuffle 是常态，ClickHouse 假设单节点 local 处理足矣——直到 Parallel Replicas 的出现才开始模糊这个边界。

---

## 1.4 关键数据结构速览

### Block — 列式数据批次

`src/Core/Block.h` — Block 是 ClickHouse 的核心数据单元，类似于 Spark 的 `InternalRow` 批次或 Arrow 的 `RecordBatch`。

```cpp
class Block
{
    using Container = ColumnsWithTypeAndName;  // 列数据 + 类型 + 列名
    Container data;
    BlockInfo info;  // bucket_num, is_overflows 等元信息
};
```

Block 包含：
- 一组 `ColumnWithTypeAndName`：每列有具体的 `IColumn` 数据、`DataTypePtr` 类型信息、列名字符串
- `BlockInfo`：用于分布式查询的装箱信息（murmurHash 分区桶号等）

### IColumn — 列抽象基类

`src/Columns/IColumn.h` — 所有列类型的基类，定义了列操作的标准接口：

```cpp
class IColumn
{
    virtual StringRef getDataAt(size_t n) const = 0;  // 取第 n 行字节
    virtual void insertFrom(const IColumn & src, size_t n) = 0;
    virtual void insertRangeFrom(const IColumn & src, size_t start, size_t length) = 0;
    virtual void filter(const Filter & filt, ssize_t result_size_hint) = 0;  // 按 mask 过滤
    virtual ColumnPtr permute(const Permutation & perm, size_t limit) const = 0; // 按序重排
    virtual size_t byteSize() const = 0;  // 内存占用
    // ... 30+ 个方法
};
```

典型列类型（`src/Columns/`）：
- `ColumnVector<UInt8>` / `<UInt64>` / `<Float64>` — 数值列
- `ColumnString` — 字符串列（带有 offset 数组）
- `ColumnArray` — 数组列（嵌套子列 + offset）
- `ColumnNullable` — Nullable 列（null bitmap + 嵌套列）
- `ColumnConst` — 常量列（只存一个值，所有行相同）
- `ColumnLowCardinality` — 低基数列（字典编码）
- `ColumnTuple` — 元组列（嵌套多个子列）

### Field — 单个值

`src/Core/Field.h` — `Field` 是 ClickHouse 的变体类型，存储单行单列的值：

```cpp
using Field = std::variant<
    Null,
    UInt64, Int64, Float64,
    String, Array, Tuple,
    DecimalField<Decimal32>, DecimalField<Decimal64>,  // ...
    AggregateFunctionStateData,
    CustomType,
    Dynamic
>;
```

它允许 `IColumn::operator[](n)` 返回一个 `Field`（便利但不高效——生产路径用 `getDataAt` 或原始指针）。

---

## 1.5 本章小结

ClickHouse 的架构可以用"单二进制、多子程序、列式内核、流水线执行"这十六个字概括。

**三个关键架构决策**：
1. **单二进制全静态** — 牺牲扩展灵活性，换取部署简单性和行为确定性
2. **工厂模式全局注册** — `registerFunctions()` 这样的注册表模式让新增组件只需添加注册和实现两个地方
3. **QueryPlan → Processor DAG 的分层模型** — 规划层（声明式 Step）和执行层（命令式 Processor）的解耦，让优化和执行可以独立演进

**关键文件地图**：
```
programs/main.cpp                    → 入口分发
programs/server/Server.cpp           → 服务器初始化 + 生命周期
src/Server/TCPHandler.cpp           → Native 协议查询处理
src/Interpreters/executeQuery.cpp   → 查询调度中心
src/Interpreters/InterpreterSelectQuery.cpp → SELECT 实现
src/Core/Block.h                     → 数据块
src/Columns/IColumn.h               → 列基类
src/Processors/                      → 流水线处理器
src/Processors/Executors/            → 执行器
```

**下一步阅读**：在理解了整体架构后，下一步深入 Part II — SQL 编译管线，跟随一条 SQL 从文本到 QueryPlan 的完整转换过程。
