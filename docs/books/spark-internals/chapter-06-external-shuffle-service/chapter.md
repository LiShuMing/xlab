# 第 6 章：External Shuffle Service — 独立进程的数据服务

## 设计动机

Spark Executor 的本质是"计算 + 存储"的耦合——同一个 JVM 既要执行 Task（CPU/内存），又要对外提供 Shuffle 数据（网络/磁盘）。这种耦合带来了一个分布式系统的经典问题：**Executor 退出后，它写的 Shuffle 数据就不可访问了**。

考虑以下场景：

```
Executor-3 运行一个 Mapper Task，写了 20GB 的 Shuffle 数据到本地磁盘。
Executor-3 随后因为以下原因退出：
  - YARN preemption（集群资源紧张时强制回收 Container）
  - 节点 Decommission（运维维护下线）
  - 内存超限被 NodeManager kill
  - GC 停顿导致心跳超时
  - 硬件故障

此时，下游 Stage 的所有 Reducer 无法拉取这 20GB 数据 → Stage 重算 → 所有 Mapper 重新执行。
```

在 YARN 集群中，这种场景的发生频率不低——一个 200 节点的集群每天可能有 10-50 次 Executor 退出事件。如果每次退出都触发 Stage 重算，生产环境的稳定性会显著降低。

**External Shuffle Service 给出了一个优雅的设计**：将 Shuffle 数据服务从 Executor JVM 中剥离到独立的守护进程。这个守护进程运行在 NodeManager（YARN）或 Pod（Kubernetes）中，生命周期与节点绑定，不随 Executor 的创建/销毁而变动。

```
传统模型:
  NodeManager
    └── Container(Executor JVM)
          ├── Task 执行
          ├── Shuffle Write (写本地磁盘)
          └── Shuffle Serve (从本地磁盘读 + 网络发送)
          ↑ Executor 退出 → Shuffle 数据不可访问

External Shuffle Service 模型:
  NodeManager
    ├── Container(Executor JVM)
    │     ├── Task 执行
    │     └── Shuffle Write (写本地磁盘)
    └── External Shuffle Service (独立守护进程)
          └── Shuffle Serve (读本地磁盘 + 网络发送)
          ↑ Executor 退出 → 数据仍然可读
```

External Shuffle Service 的核心价值来自两个洞察：

1. **Shuffle Serve 不消耗 CPU**：它只是"定位文件 + 网络发送"。一把 `sendfile` 系统调用 + 少量元数据查找，CPU 开销几乎为零。把它独立出来不会造成额外的计算资源浪费。

2. **磁盘不属于 Executor**：Shuffle 数据存在本地磁盘上，而本地磁盘的生命周期与节点相同（不是与 Container 相同）。只要节点还在，磁盘数据就在——只需要一个进程来读取它。

## 核心原理

### 6.1 架构全景

External Shuffle Service 作为 YARN `AuxiliaryService` 运行，生命周期由 NodeManager 管理。每个 NodeManager 运行一个 Shuffle Service 实例，为该节点上所有 Spark Executor 提供 Shuffle 数据服务。

```
架构全景:

YARN ResourceManager
  └── NodeManager (per node)
        ├── External Shuffle Service (YarnShuffleService)
        │     ├── TransportServer (Netty, 默认 port=7337)
        │     │     └── 提供: fetch shuffle blocks, RDD blocks
        │     ├── ExternalBlockHandler (RPC 消息分发)
        │     │     ├── ExternalShuffleBlockResolver (executor 注册 + block 定位)
        │     │     └── MergedShuffleFileManager (push-based merge 管理)
        │     ├── ShuffleSecretManager (可选: SASL 认证)
        │     └── Recovery DB (RocksDB/LevelDB, NM 重启恢复)
        │
        ├── Container-1 (Spark Executor)
        │     ├── BlockManager → ExternalBlockStoreClient.registerShuffle()
        │     └── Shuffle Write → data + index → 本地磁盘
        │
        └── Container-2 (Spark Executor)
              └── ...

远端 Reducer (在另一节点的 Executor):
  ExternalBlockStoreClient.fetchBlocks()
    → TCP → TransportServer(port=7337) → ExternalBlockHandler
    → ShuffleManagedBufferIterator → ExternalShuffleBlockResolver.getBlockData()
    → FileSegmentManagedBuffer → sendfile() 发送磁盘数据
```

### 6.2 启动流程 — 作为 YARN AuxiliaryService

`YarnShuffleService` 继承 Hadoop YARN 的 `AuxiliaryService` 抽象类。NodeManager 根据 `yarn.nodemanager.aux-services` 配置加载它：

```xml
<!-- yarn-site.xml -->
<property>
  <name>yarn.nodemanager.aux-services</name>
  <value>spark_shuffle</value>
</property>
<property>
  <name>yarn.nodemanager.aux-services.spark_shuffle.class</name>
  <value>org.apache.spark.network.yarn.YarnShuffleService</value>
</property>
```

YARN NodeManager 的启动流程会调用 `serviceInit`：

```
NodeManager.serviceInit()
  → initialize AuxiliaryServices
    → YarnShuffleService.serviceInit(Configuration)
      1. 加载 spark-shuffle-site.xml (classpath overlay, 可选)
      2. 如果有 recovery path → 初始化恢复文件:
         - registeredExecutorFile: executor 注册信息
         - secretsFile: 应用认证密钥 (如果启用 auth)
         - mergeManagerFile: push-based merge 恢复信息
      3. 创建 ExternalBlockHandler:
         - MergedShuffleFileManager (mergeManager): RemoteBlockPushResolver 实例
         - ExternalShuffleBlockResolver (blockManager): 管理 executor→localDir 映射
      4. 如果启用认证 → 初始化 ShuffleSecretManager
      5. 创建 TransportServer 监听端口 (默认 7337)
      6. 注册 Metrics 到 Hadoop Metrics2 系统
```

核心启动代码：

```java
// YarnShuffleService.java:234
protected void serviceInit(Configuration externalConf) throws Exception {
  // TransportConf 从 Hadoop Configuration 读取 Spark 配置
  TransportConf transportConf = new TransportConf("shuffle", new HadoopConfigProvider(_conf));

  // 创建 shuffle merge manager (用于 push-based shuffle)
  if (shuffleMergeManager == null) {
    shuffleMergeManager = newMergedShuffleFileManagerInstance(transportConf, mergeManagerFile);
  }

  // 创建 block handler — 核心请求处理引擎
  blockHandler = new ExternalBlockHandler(
    transportConf, registeredExecutorFile, shuffleMergeManager);

  // 可选: 认证
  if (authEnabled) {
    secretManager = new ShuffleSecretManager();
    bootstraps.add(new AuthServerBootstrap(transportConf, secretManager));
  }

  // 启动 Netty Transport Server
  int port = _conf.getInt(SPARK_SHUFFLE_SERVICE_PORT_KEY, DEFAULT_SPARK_SHUFFLE_SERVICE_PORT);
  transportContext = new ShuffleTransportContext(transportConf, blockHandler, true);
  shuffleServer = transportContext.createServer(port, bootstraps);
}
```

**ShuffleTransportContext** 是 `TransportContext` 的子类，它在 Netty Pipeline 中添加了一个特殊的处理器 `FinalizedHandler`——将 `FINALIZE_SHUFFLE_MERGE` 请求路由到独立的 EventLoopGroup 执行。这是因为 Finalize 操作涉及文件 flush + 元数据写入，可能比较耗时，不应阻塞普通的 fetch 请求。

### 6.3 Executor 注册 — 建立元数据映射

Executor 启动后，`BlockManager` 通过 `ExternalBlockStoreClient` 向 Shuffle Service 发送 `RegisterExecutor` 消息：

```
Executor 启动:
  BlockManager.initialize()
    → externalBlockStoreClient.register()
      → RegisterExecutor(appId, execId, ExecutorShuffleInfo)
        → TCP → Shuffle Service:7337

ExecutorShuffleInfo 包含:
  - localDirs: Executor 本地磁盘目录列表
  - subDirsPerLocalDir: 每个目录下的子目录数
  - shuffleManager: SortShuffleManager 的类名
```

`ExternalShuffleBlockResolver.registerExecutor` 将 (appId, execId) → `ExecutorShuffleInfo` 的映射存入 `ConcurrentHashMap`。同时，如果启用了恢复机制（NM recovery），写入 RocksDB：

```java
// ExternalShuffleBlockResolver.java:149
public void registerExecutor(String appId, String execId, ExecutorShuffleInfo executorInfo) {
  AppExecId fullId = new AppExecId(appId, execId);
  if (db != null) {
    byte[] key = dbAppExecKey(fullId);
    byte[] value = mapper.writeValueAsString(executorInfo).getBytes(StandardCharsets.UTF_8);
    db.put(key, value);
  }
  executors.put(fullId, executorInfo);
}
```

这个注册映射非常精简——Shuffle Service 只需要"Executor 的本地目录在哪"就能完成所有的 block 定位。它不需要知道 Task 的执行状态、不需要知道 Shuffle 的 partition 分布——这些信息通过 `MapOutputTracker` 在 Driver 端管理。

### 6.4 Block 定位 — 从 BlockId 到磁盘文件

Reducer 发起 Shuffle Read 时，对每个 Block 请求，Shuffle Service 需要找到对应的本地文件并发送正确的区间。

**请求协议**：

Reducer → TransportServer: `FetchShuffleBlocks(appId, execId, shuffleId, mapIds, reduceIds, batchFetchEnabled)`

- 对于单 block 拉取：`mapIds=[3], reduceIds=[[5]]` → 拉取 `shuffle_0_3_0.data` 中 partition 5 的数据
- 对于 batch fetch：`mapIds=[3], reduceIds=[[0,5]]` → 拉取 partition [0, 5) 的连续段

**文件定位过程**：

```
1. 根据 (appId, execId) → 查找 ExecutorShuffleInfo
2. 根据 ExecutorShuffleInfo.localDirs → 找到目录列表
3. 根据 shuffleId, mapId → 构建文件名:
   data file:  "shuffle_{shuffleId}_{mapId}_0.data"
   index file: "shuffle_{shuffleId}_{mapId}_0.index"
4. 从 index cache (LoadingCache) 中获取 ShuffleIndexInformation:
   → 如果缓存未命中 → 读取 index file, 解析所有 partition 的 (offset, length) 对
5. 根据 startReduceId, endReduceId → 计算要发送的 offset + length
6. 创建 FileSegmentManagedBuffer(file, offset, length)
   → 内部使用 FileChannel.transferTo 或 sendfile 零拷贝发送
```

```java
// ExternalShuffleBlockResolver.java:322
private ManagedBuffer getSortBasedShuffleBlockData(
  ExecutorShuffleInfo executor, int shuffleId, long mapId, int startReduceId, int endReduceId) {

  String indexFilePath = ExecutorDiskUtils.getFilePath(
    executor.localDirs, executor.subDirsPerLocalDir,
    "shuffle_" + shuffleId + "_" + mapId + "_0.index");

  ShuffleIndexInformation shuffleIndexInformation = shuffleIndexCache.get(indexFilePath);
  ShuffleIndexRecord shuffleIndexRecord = shuffleIndexInformation.getIndex(
    startReduceId, endReduceId);

  return new FileSegmentManagedBuffer(
    conf,
    new File(ExecutorDiskUtils.getFilePath(
      executor.localDirs, executor.subDirsPerLocalDir,
      "shuffle_" + shuffleId + "_" + mapId + "_0.data")),
    shuffleIndexRecord.offset(),
    shuffleIndexRecord.length());
}
```

**Index File Cache** 是一个 Guava `LoadingCache`，按文件路径作为 key，`ShuffleIndexInformation`（所有 partition offset/length 的二进制数组）作为 value。容量由 `spark.shuffle.service.index.cache.size` 控制（默认 100MB），驱逐策略基于 entry 的内存占用（weigher = `ShuffleIndexInformation.getRetainedMemorySize()`）。

这个 cache 非常必要——对于一个 Executor 上 5000 个 Map Task、200 个 Reducer 的 Shuffle，index files 可能被读取上万次。没有 cache，每次 block fetch 都要 open/read/close index file → 磁盘随机 I/O 成为瓶颈。有了 cache，index 信息保持在内存 → block 定位是纯内存操作。

### 6.5 安全模型 — 应用间隔离

External Shuffle Service 是一个多租户服务——同一个节点的多个 Spark Application 的 Executor 使用同一个 Shuffle Service。必须隔离不同 App 的数据访问。

Spark 提供了两种认证机制：

1. **无认证模式（默认）**：通过 `TransportClient.clientId` 与请求中的 `appId` 匹配。Executor 连接服务时设置 `clientId = appId`，后续请求中的 appId 必须与 clientId 一致。

2. **SASL 认证模式**：通过 `spark.authenticate=true` 启用。ApplicationMaster 在 `initializeApplication` 中将 shuffle secret 传给 Shuffle Service 的 `ShuffleSecretManager`。Executor 连接时使用相同的 secret 做 SASL 握手。认证失败 → 连接被拒绝。

```java
// ExternalBlockHandler.java:304
private void checkAuth(TransportClient client, String appId) {
  if (client.getClientId() != null && !client.getClientId().equals(appId)) {
    throw new SecurityException(String.format(
      "Client for %s not authorized for application %s.", client.getClientId(), appId));
  }
}
```

### 6.6 恢复机制 — NodeManager 重启后重建状态

External Shuffle Service 面临的一个关键可靠性挑战是 **NodeManager 重启**——如果 NodeManager 崩溃并重启，Shuffle Service 重新启动，它必须恢复之前注册的所有 Executor 的信息，否则这些 Executor 的 Shuffle 数据不可读。

恢复机制通过 Key-Value Database（RocksDB 或 LevelDB，由 `spark.shuffle.service.db.backend` 配置）实现：

```
恢复数据三要素:
  1. registeredExecutorFile: AppExecId → ExecutorShuffleInfo
     → 告诉 Shuffle Service 去哪里找每个 Executor 的 Shuffle 文件
  2. secretsFile: AppId → Secret
     → 认证密钥，重启后仍需验证请求的合法性
  3. mergeManagerFile: push-based merge 的中间状态
     → 未 finalize 的 merged shuffle files

NodeManager 重启:
  serviceInit() → initRecoveryDb()
    → 如果恢复路径存在 → 读取 RocksDB 中的记录
    → 重建内存中的 executors Map
    → 重建 secretManager 的注册信息
```

恢复文件的存储位置由 YARN 的 NM Recovery 路径决定（`yarn.nodemanager.recovery.dir`）。如果旧版本的 Shuffle Service 将恢复文件存在 NM 本地目录而非 Recovery 路径，`initRecoveryDb` 会自动将其移动到新位置。

**恢复的局限性**：恢复只保证"NM 重启后 Shuffle 数据可读"。如果磁盘故障或节点宕机，恢复无法解决问题——这需要 Celeborn/Uniffle 这种独立存储集群的多副本机制。

### 6.7 集成 Push-based Shuffle

External Shuffle Service 不仅是传统 pull 模型的数据提供者，还是 push-based shuffle 的 **合并引擎**。`ExternalBlockHandler` 持有 `MergedShuffleFileManager` 引用，默认实现是 `RemoteBlockPushResolver`（第 5 章详细覆盖）。

集成点有三个：

1. **注册阶段**：`blockHandler.registerExecutor` 同时调 `mergeManager.registerExecutor`——告诉 merge manager 该 executor 的本地目录（存放未完全合并的 push blocks）

2. **Push 阶段**：`receiveStream` 将 `PushBlockStream` 消息直接路由到 `mergeManager.receiveBlockDataAsStream`——跳过 `blockManager` 的 block 定位路径

3. **Fetch 阶段**：当 blockId prefix 为 `shuffleChunk`（而非 `shuffle`）时，`ManagedBufferIterator` 走 `mergeManager.getMergedBlockData` 路径——读取已合并的 shuffle chunks

### 6.8 K8s 环境下的 External Shuffle Service

在 Kubernetes 环境下，External Shuffle Service 的思路与 YARN 不同。由于 K8s Pod 的临时存储生命周期与 Pod 绑定，传统的"守护进程读本地磁盘"模式不可行——Pod 删除后，Pod 的本地磁盘也被回收。

Spark on K8s 使用 **KubernetesLocalDiskShuffleExecutorComponents** 来管理 K8s 环境下的 Shuffle 存储。本质上是通过 HostPath 或 Local PV 将节点磁盘挂载到 Executor Pod 中，利用 shuffle 数据重分级的机制保障数据可靠性。不过从 Spark 4.0 开始，社区更推荐使用独立的 Shuffle 集群（Celeborn/Uniffle）而非 External Shuffle Service 来解决 K8s 下的 Shuffle 数据持久化问题。

## 关键代码片段

### 示例：Shuffle Service 处理的完整请求生命周期

```
Remote Reducer 请求 fetch partition 5 的数据:

1. ExternalBlockStoreClient (Reducer 侧):
   blocksByAddress = [(BlockManagerId("node-1", 7337), [ShuffleBlockId(0, 3, 5)])]
   → fetchBlocks("node-1", 7337, FetchShuffleBlocks(appId, execId, shuffleId=0, mapIds=[3], reduceIds=[[5]]))

2. TransportServer (Shuffle Service 侧, node-1:7337):
   接收 TCP 连接 → 反序列化消息 → 路由到 ExternalBlockHandler.receive()

3. ExternalBlockHandler.handleMessage():
   → 匹配 FetchShuffleBlocks
   → checkAuth(client, appId)  // 安全校验
   → streamManager.registerStream(clientId,
       ShuffleManagedBufferIterator(appId, execId, shuffleId=0, mapIds=[3], reduceIds=[[5]]))

4. ShuffleManagedBufferIterator.next():
   → blockManager.getBlockData(appId, execId, shuffleId=0, mapId=3, reduceId=5)
   → ExternalShuffleBlockResolver.getBlockData():
     → AppExecId("app-001", "exec-3") → ExecutorShuffleInfo
     → index file: "/data/yarn/local/usercache/.../shuffle_0_3_0.index"
     → 从 cache 读取 partition 5: offset=20480, length=5120
     → FileSegmentManagedBuffer("/data/.../shuffle_0_3_0.data", 20480, 5120)

5. Netty 使用 FileRegion(FileChannel, 20480, 5120) 发送:
   → sendfile64(fd, socket_fd, 20480, 5120)
   → 内核态 DMA: page cache → socket buffer → NIC
   → 零拷贝, CPU 仅参与控制面
```

## 硬件视角

**sendfile 的零拷贝路径**：

External Shuffle Service 最重要的硬件特性是 **发送路径的零拷贝**。当 `FileSegmentManagedBuffer` 被转换为 Netty 的 `FileRegion` 时，底层使用 Linux 的 `sendfile64` 系统调用：

```
传统 4 次拷贝 (read + write):
  disk → kernel page cache → user space buffer → kernel socket buffer → NIC

sendfile (1 次拷贝):
  disk → kernel page cache ──────────→ kernel socket buffer → NIC
                    (DMA scatter-gather)
```

在 40GbE（5GB/s）网络上，Shuffle Service 单次 block 传输可能是 50MB-500MB。如果用传统 read+write，这 50MB 要走 4 次内存总线——50MB × 4 = 200MB 的内存带宽消耗。sendfile 只需 1 次→50MB。对于同时处理 20 个连接的 Shuffle Service（聚合 1000MB/s 输出），sendfile 节省的内存带宽是 ~900MB/s——这条带宽留给其他进程（或本计算节点的 Executor）。

**Index Cache 的内存效益**：

对于一个运行 50 个 Spark Application 的节点，每个 App 有 100 个 Executor，每个 Executor 产生 500 个 Map 的 Shuffle：

- 总 index files 数：50 × 100 × 500 = 2,500,000 个
- 每个 index file 约 80KB（200 个 partition × 8 字节/对 + overhead）
- 2,500,000 × 80KB = 200GB 的 index 数据

显然无法全部 cache。但现实是：只有当前活跃的 Stage 的 Reducer 在读取数据。同一时刻只有 ~100 个 Stage 的 Shuffle data 在被读取：

- 100 × 500 map × 80KB = 4GB index data
- 100MB 的 cache 容量可以 hold 住最热的那部分 index files
- 带来 ~90% cache 命中率

Miss 时回退到磁盘读取 index file——单次 cost ≈ 0.1ms（NVMe 随机读）vs Cache hit 的 <1μs（内存访问）。

## AI 时代反思

External Shuffle Service 的设计非常"计算机系统化"——它做"最少的事情"，只负责"文件→网络"的桥梁工作。这种简单的语义使得 LLM Agent 在这个上下文中可以发挥一个有意思的作用：**健康检查与异常诊断**。

一个部署在 Shuffle Service 旁边的 Agent（sidecar 模式或节点级守护进程）可以执行几个高价值的诊断：

1. **passive 指标异常检测**：`openBlockRequestLatencyMillis` 从 5ms 飙升到 500ms → 磁盘故障或 index cache miss 率异常高。`blockTransferRateBytes` 突然降为 0 → 网络断了或客户端全部退出了

2. **active 冒烟测试**：Agent 可以做"模拟 Reducer"——向本地的 Shuffle Service 发送一个 `FetchShuffleBlocks`（请求一个不存在的 block）→ 测量延迟和错误响应 → 建立 network health baseline

3. **容量规划**：Agent 收集一周的 `blockTransferRateBytes` → 用简单的趋势预测做"下周这个 Shuffle Service 带宽峰值是否会超过 NIC 80%"→ 提前扩容

更有趣的是**配置决策的 LLM 辅助**。像 `spark.shuffle.service.index.cache.size` 这种参数，默认 100MB，但最优值完全依赖于工作负载：
- 大量小 Shuffle 场景 → 需要更多 cache（每次 miss 都是磁盘随机 I/O）
- 少量大 Shuffle 场景 → cache 收益低（一次 batch fetch 拉几十 MB，index 读占比微小）
- HDD 节点 = cache miss 代价 10ms；NVMe 节点 = cache miss 代价 0.1ms

LLM 可以通过读取 YARN 节点的磁盘类型、Spark 历史查询的 Shuffle 大小分布，给出合理的 cache size 建议——不需要精确建模，只需要"分类决策"（小/中/大/超大）。

## 源码导航

| 文件 | 关键内容 | 行号参考 |
|------|---------|---------|
| `common/network-yarn/src/main/java/org/apache/spark/network/yarn/YarnShuffleService.java` | YarnShuffleService 主类，AuxiliaryService 生命周期，serviceInit 启动 TransportServer，application/executor 生命周期回调，RocksDB 恢复，安全初始化 | 101 (class), 234 (serviceInit), 419 (initializeApplication), 462 (stopApplication), 502 (serviceStop) |
| `common/network-shuffle/src/main/java/org/apache/spark/network/shuffle/ExternalBlockHandler.java` | ExternalBlockHandler，RPC 消息分发（fetch blocks, register executor, finalize merge, remove blocks），ShuffleMetrics 指标体系，线程安全的 stream 注册，ShuffleManagedBufferIterator | 68 (class), 123 (receive), 142 (handleMessage), 315 (ShuffleMetrics), 500 (ShuffleManagedBufferIterator) |
| `common/network-shuffle/src/main/java/org/apache/spark/network/shuffle/ExternalShuffleBlockResolver.java` | ExternalShuffleBlockResolver，executor 注册元数据管理，index file cache (LoadingCache)，getSortBasedShuffleBlockData 文件定位，RocksDB 恢复加载，清理线程 | 64 (class), 149 (registerExecutor), 185 (getContinuousBlocksData), 322 (getSortBasedShuffleBlockData), 473 (reloadRegisteredExecutors) |
| `common/network-shuffle/src/main/java/org/apache/spark/network/shuffle/ExternalBlockStoreClient.java` | ExternalBlockStoreClient，客户端连接管理，init 初始化 TransportClientFactory，SASL bootstrap，fetchBlocks 远程调用 | 51 (class), 81 (init) |
| `common/network-shuffle/src/main/java/org/apache/spark/network/shuffle/ShuffleTransportContext.java` | ShuffleTransportContext，自定义 Netty Pipeline，FinalizedHandler 独立 EventLoop 处理 FINALIZE_SHUFFLE_MERGE，ShuffleMessageDecoder 消息拦截 | 53 (class), 103 (addHandlerToPipeline), 160 (FinalizedHandler) |
| `common/network-shuffle/src/main/java/org/apache/spark/network/shuffle/Constants.java` | SHUFFLE_SERVICE_FETCH_RDD_ENABLED, SHUFFLE_SERVICE_DB_BACKEND 常量定义 | 22 |
| `common/network-shuffle/src/main/java/org/apache/spark/network/shuffle/protocol/RegisterExecutor.java` | RegisterExecutor 消息格式，appId + execId + ExecutorShuffleInfo | 33 (class) |
| `resource-managers/kubernetes/core/src/main/scala/org/apache/spark/shuffle/KubernetesLocalDiskShuffleDataIO.scala` | K8s 环境下的 Shuffle 存储管理 | |
