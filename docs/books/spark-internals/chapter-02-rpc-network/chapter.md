# 第 2 章：RPC 与网络传输层 — Spark 的神经系统

## 设计动机

分布式系统的第一行代码不是"怎么算"，而是"怎么通信"。Driver 要把 Task 发给 Executor，Executor 要把结果返回 Driver，Shuffle 期间节点间要互传数据， BlockManager 要跨节点复制缓存——这一切都依赖于一个可靠的、高性能的 RPC 层。

Spark 2014 年从 Akka 迁移到自研 Netty RPC（SPARK-5290），核心动机有三：

1. **用户代码与 Akka 版本冲突**：Akka 的 actor 模型依赖特定版本，与用户的业务代码冲突频繁。Spark 只需要一个通信层，不需要完整的 actor framework。
2. **Netty 是事实标准**：Hadoop 生态（YARN、HDFS DataNode）已大量使用 Netty。一个基于 Netty 的薄封装层足以覆盖 Spark 的全部通信需求。
3. **精细控制**：Spark 需要管理序列化格式（JavaSerializer）、连接认证（SASL/AES 加解密）、文件下载通道等定制行为——用 Akka 反而需要绕过其抽象。

自研 RPC 层的代价是 ~2000 行 Scala/Java 代码，换来了完全自主的连接管理、消息路由、超时失败处理。这 2000 行代码构成了 Spark 的**神经系统**——Driver 和 Executor 之间的所有交互都通过它。

从第一性原理看，分布式 RPC 的本质是**异步消息路由**：发送方不直接调用接收方的方法，而是把消息交给一个"路由系统"——该路由系统保证消息可靠到达目标、处理连接失败、支持同步和异步两种应答模式。Spark 的 RPC 层以 **RpcEnv → Dispatcher → Inbox/Outbox → TransportContext** 四级抽象实现了这个模型。

## 核心原理

### 2.1 全局视图 — 一条消息的完整旅程

在深入每个组件前，先理解一条消息从发送到处理的完整链路：

```
Sender (RpcEndpointRef.askSync)
  │
  ├── 1. RpcEndpointRef.serialize message → RequestMessage
  │      receiver=RpcEndpointAddress(host:port, endpointName)
  │      content=序列化后的消息体
  │
  ├── 2. NettyRpcEnv.askAbortable()
  │      ├── 本地消息: remoteAddr == self.address
  │      │     → Dispatcher.postLocalMessage → Inbox.post → active.offer(inbox)
  │      │
  │      └── 远端消息: remoteAddr != self.address
  │            → RpcOutboxMessage → Outbox.send → drainOutbox
  │              → TransportClient.sendRpc → Netty Channel → 网络
  │
  │  远端: Netty Channel → MessageDecoder → TransportRequestHandler
  │    → RpcHandler.receive → NettyRpcHandler.receive → Dispatcher.postRemoteMessage
  │      → Inbox.post → active.offer(inbox)
  │
  ├── MessageLoop.receiveLoop:
  │     active.take() → Inbox.process()
  │       → endpoint.receiveAndReply(context)
  │       → context.reply(result)
  │
  └── 3. Result → RpcResponse → Netty → TransportResponseHandler
       → RpcOutboxMessage.onSuccess → Promise.complete
       → askSync 返回结果
```

核心洞见：**Inbox 和 Outbox 解决了不同的问题**。Inbox 是"消息到了以后怎么安全地交给端点处理"——生产者-消费者 + 背压。Outbox 是"还没有连接怎么办？消息先排队"——连接管理 + 重连语义。

### 2.2 RpcEnv — RPC 环境的总控

`RpcEnv` 是 RPC 层的门面抽象。一个 JVM 进程只有一个 `RpcEnv` 实例：

```
RpcEnv 的两面:
  服务端: 监听端口, 接收远端连接, 路由消息到本地 Endpoint
    ├── TransportServer (Netty server bootstrap)
    └── TransportContext → NettyRpcHandler → Dispatcher

  客户端: 连接到远端, 发送消息
    ├── TransportClientFactory → TransportClient (复用连接)
    └── outboxes: Map[RpcAddress → Outbox] (每个远端地址一个 Outbox)
```

```scala
// RpcEnv 的工厂创建（RpcEnv.scala:37-59）:
RpcEnv.create(name, host, port, conf, securityManager)
  → RpcEnvConfig(conf, name, bindAddress, advertiseAddress, port, ...)
  → new NettyRpcEnvFactory().create(config)
  → new NettyRpcEnv(conf, serializer, host, securityManager, numUsableCores)
```

创建后的 `NettyRpcEnv` 内部持有：
- `dispatcher: Dispatcher` — 消息路由中枢
- `transportContext: TransportContext` — Netty Channel 工厂
- `clientFactory: TransportClientFactory` — 复用远端连接
- `outboxes: ConcurrentHashMap[RpcAddress, Outbox]` — 每个远端地址的出站队列
- `server: TransportServer` — 监听端口，接收远端连接
- `timeoutScheduler` — 管理 ask RPC 的超时

### 2.3 RpcEndpoint — 消息处理单元的生命周期

`RpcEndpoint` 和 `RpcEndpointRef` 是 RPC 层的"演员"和"地址簿"。每个分布式角色（Driver 上的 DAGScheduler、Executor 上的 CoarseGrainedExecutorBackend、BlockManagerMaster 等）都是一个 `RpcEndpoint`：

```
RpcEndpoint 生命周期 (RpcEndpoint.scala:38):
  constructor → onStart → receive* → onStop

端点类型:
  RpcEndpoint               → 默认: 共享线程池, 消息可并发
  ThreadSafeRpcEndpoint     → 共享线程池, 同一端点消息串行
  IsolatedRpcEndpoint       → 专用线程池, 可并发
  IsolatedThreadSafeRpcEndpoint → 专用单线程池, 线程安全
```

`RpcEndpointRef` 是对端点的远程引用——类似一个"电话号"。它提供两种通信模式：

```
RpcEndpointRef 的三种调用模式:
  send(message)          → fire-and-forget, 单向, 无返回值
  ask[T](message)        → 返回 Future[T], 异步等待回复
  askSync[T](message)    → 阻塞等待回复, 调用线程 blocked
  askAbortable[T](msg)   → 返回 AbortableRpcFuture, 可中途取消
```

**send vs ask 的根本区别**：
- `send`：消息放入 Outbox/Inbox，发送方立即返回。无法感知接收方是否收到、是否处理成功。适合状态报告（Task 进度、Executor 心跳）。
- `ask`：消息序列化 → 发送 → 返回 Future → 远端处理后回复 → Future complete。适合需要返回值的操作（查找 Shuffle 数据位置、检查 Executor 状态）。

**AbortableRpcFuture** 是 Spark 对长耗时 RPC 的特殊处理——如果 ask 在超时前被取消（如 Stage 被 abort），可以调用 `abort()` 来通知远端不再需要结果，避免远端继续计算一个无人等待的结果。

### 2.4 Dispatcher — 消息路由器

`Dispatcher` 是 RPC 层的核心路由引擎。它解决的问题是："一个消息到达时，怎么找到处理它的 Endpoint，然后把消息交给它？"

```
Dispatcher 的内部结构 (Dispatcher.scala:39-92):
  endpoints: ConcurrentMap[String, MessageLoop]
    → 将端点名称映射到消息循环（共享或专用）
  endpointRefs: ConcurrentMap[RpcEndpoint, RpcEndpointRef]
    → RpcEndpoint → 其 NettyRpcEndpointRef 的反向映射

注册端点:
  registerRpcEndpoint(name, endpoint)
    → 检查: name 是否已存在
    → 判断: endpoint 是 IsolatedRpcEndpoint?
        是 → DedicatedMessageLoop(name, endpoint, this)
        否 → sharedLoop.register(name, endpoint)
    → 创建 NettyRpcEndpointRef → 存入 endpointRefs
    → 返回 endpointRef

消息路由 (postMessage):
  1. 从 endpoints 找到 name 对应的 MessageLoop
  2. loop.post(name, message)         ← 将消息放入 Inbox
  3. messageLoop 将 Inbox 放入 active 队列 (setActive)
  4. 线程池中的线程捡起 Inbox → inbox.process(dispatcher)
```

三种消息入口对应三种场景：

```
postRemoteMessage  → 远端发来的 RPC → RemoteNettyRpcCallContext
postLocalMessage   → 本地 ask → LocalNettyRpcCallContext (Promise-based)
postOneWayMessage  → 本地 send → OneWayMessage (无 context)
```

**RpcCallContext 的双重人格**：`RemoteNettyRpcCallContext` 的 `reply()` 方法通过 Netty callback 将回复写回网络通道；`LocalNettyRpcCallContext` 的 `reply()` 方法直接 complete 一个 Promise。上层代码（Inbox.process）不需要知道这个区别——它只调用 `context.reply(result)`。

### 2.5 Inbox — 入站消息队列

`Inbox` 是挂靠在每个 Endpoint 上的**线程安全消息队列**。它的设计非常巧妙——不是简单地"有消息就处理"，而是同时支持串行和并发两种处理模式：

```
Inbox 的核心状态:
  messages: LinkedList[InboxMessage]   ← 消息队列
  stopped: boolean                     ← 是否已停止
  enableConcurrent: boolean            ← 是否允许多线程并发处理
  numActiveThreads: int                ← 当前激活的线程数

消息类型:
  OnStart          ← 构造函数中自动添加 (第一条消息)
  OnStop           ← stop() 时添加 (最后一条消息)
  RpcMessage       ← ask 消息 (带 RpcCallContext, 用于回复)
  OneWayMessage    ← send 消息 (无需回复)
  RemoteProcessConnected    ← 远端节点上线 (广播到所有端点)
  RemoteProcessDisconnected ← 远端节点下线
  RemoteProcessConnectionError ← 网络连接异常
```

`Inbox.process()` 的处理循环：

```
process(dispatcher):
  1. 取一条消息 (synchronized)
     - 如果是 ThreadSafeRpcEndpoint 或 串行模式且已有活跃线程 → return
     - 否则: poll() → numActiveThreads++
  
  2. 处理循环:
     匹配消息类型:
       OnStart  → endpoint.onStart()
                   如果 endpoint 不是 ThreadSafe → enableConcurrent = true
                   意味着: OnStart 后允许多线程并发处理消息
       OnStop   → dispatcher.removeRpcEndpointRef(endpoint)
                   endpoint.onStop()
       RpcMessage → endpoint.receiveAndReply(context)
                    context.reply/get/sendFailure
       OneWayMessage → endpoint.receive()
  
  3. 取下一消息:
     - 如果 enableConcurrent=false 且 numActiveThreads != 1 → 退出
     - 如果队列为空 → numActiveThreads-- → 退出
     - 否则继续循环
```

并发控制的精妙之处：`ThreadSafeRpcEndpoint` 的 `enableConcurrent` 始终为 false，因此同时只有一个线程处理该端点消息——消息间的 happened-before 由 `synchronized` 保证。非 ThreadSafe 端点在 `OnStart` 完成后设置 `enableConcurrent=true`，允许多线程并发处理——这在低消息量场景下减少了线程上下文切换。

`Inbox.stop()` 的执行不立即清理 `messages`——而是先设 `stopped=true`，然后把 `OnStop` 加入队列。正在处理的线程会发现 `messages` 中其他消息然后继续处理，最终处理 `OnStop`。这个设计避免了"强行终止正在处理中的消息"的并发问题。

### 2.6 Outbox — 出站消息队列与连接管理

`Outbox` 解决的是"对方可能还没上线、连接可能断开、消息需要排队"的发送端问题：

```
Outbox 的核心状态:
  messages: LinkedList[OutboxMessage]
  client: TransportClient?          ← 到远端的 Netty 连接
  connectFuture: Future[Unit]?      ← 正在进行的连接任务
  draining: boolean                 ← 是否有线程在 drain 消息
  stopped: boolean

消息类型:
  OneWayOutboxMessage → client.send(content) [fire-and-forget]
  RpcOutboxMessage    → client.sendRpc(content, callback) [带 onSuccess/onFailure]
```

`Outbox.drainOutbox()` 的发送循环：

```
drainOutbox():
  1. 检查:
     如果 stopped → return
     如果 connectFuture != null → 正在连接中, return
     如果 client == null → launchConnectTask() (异步创建连接)
     如果 draining → return (已有线程在 drain)
  
  2. poll 一条消息
  
  3. 发送循环:
     message.sendWith(client)
       对于 OneWayOutboxMessage → client.send(content) (无 callback)
       对于 RpcOutboxMessage    → client.sendRpc(content, this)
                                  (this 同时是 RpcResponseCallback)
     继续 poll 下一条
  
  4. 如果 poll 不到消息 → draining = false → 退出
```

`launchConnectTask()` 是连接管理的核心：

```
launchConnectTask():
  connectFuture = executor.submit {
    client = nettyEnv.createClient(address)   ← 阻塞: 创建 TCP 连接 + 认证
    synchronized {
      outbox.client = client
      if (stopped) closeClient()
    }
    connectFuture = null  (在 synchronized 内)
    drainOutbox()         ← 连接建立后, 立即 drain 排队的消息
  }
```

`handleNetworkFailure()` 的故障处理：

```
handleNetworkFailure(e):
  synchronized:
    stopped = true
    closeClient()           ← 设为 null, 不实际关闭 (复用)
  nettyEnv.removeOutbox(address)  ← 删除 Outbox, 下次发消息时重建
  
  // 通知所有排队消息: 连接失败
  while (messages.poll != null):
    message.onFailure(e)
```

这个设计的一个微妙之处：`closeClient()` 只是把 `client` 设为 null——不关闭底层连接。这是因为 TransportClient 的连接是复用的（多个 Outbox 可能共享同一个 TransportClient），而且"连接失败"通常是网络故障——关闭一个坏掉的连接意义不大。

**Outbox 的"每次故障重建"策略**：`handleNetworkFailure` 中调用 `nettyEnv.removeOutbox(address)` 删除整个 Outbox。这意味着下次向同一地址发消息时，`postToOutbox` 会创建一个全新的 Outbox——新的队列、新的连接。这是 Spark 的"连接重试"策略：不是立即重连，而是"下次发消息时自然重连"。

### 2.7 TransportContext — Netty Channel 的制造工厂

`TransportContext` 是 Spark RPC 的最底层——它封装了 Netty 的 Channel Pipeline 配置：

```
TransportContext 工厂方法:
  createServer(host, port, bootstraps) → TransportServer
    内部: new ServerBootstrap
      → group(bossGroup, workerGroup)
      → channel(NioServerSocketChannel)
      → childHandler(TransportChannelHandler)
      → bind(host, port)

  createClientFactory(bootstraps) → TransportClientFactory
    内部: new TransportClientFactory
      → 创建 TransportClient 时:
          创建 channel → pipeline:
            TransportFrameDecoder (Length-based framing)
            MessageDecoder (ByteBuf → RequestMessage/ResponseMessage)
            MessageEncoder (Message → ByteBuf, with 8-byte frame header)
            TransportRequestHandler (写回 response)
            TransportResponseHandler (匹配 requestId → callback)
            TransportChannelHandler (exception handling, channel inactive)
```

关键的 pipeline 设计：

```
入站路径 (接收):
  ByteBuf → TransportFrameDecoder (识别帧边界) → MessageDecoder (解码消息)
    → TransportRequestHandler
      → handle(RpcRequest):
          rpcHandler.receive(client, message, callback)
          → NettyRpcHandler.receive
            → dispatcher.postRemoteMessage(message, callback)
              → Inbox.post → active.offer

出站路径 (发送):
  TransportClient.sendRpc(content, callback):
    1. 分配 requestId
    2. handler.addRpcRequest(requestId, callback)   ← 注册 callback
    3. channel.writeAndFlush(new RpcRequest(requestId, content))

  远端回复后:
    入站: RpcResponse(requestId, body)
    → TransportResponseHandler.handle(RpcResponse)
      → 查找 requestId → callback.onSuccess(body)
        → RpcOutboxMessage.onSuccess → Promise.complete
```

**TransportFrameDecoder** 是帧边界的守护者：TCP 是字节流，没有消息边界。TransportFrameDecoder 通过 8 字节帧头（frame size + message type + body size）来切分消息。这是防止"粘包"和"半包"的标准方案——没有它，MessageDecoder 无法正常工作。

### 2.8 RPC 架构的设计取舍

| 设计选择 | 替代方案 | 选择的理由 |
|---------|--------|----------|
| 自研 Netty RPC | 继续用 Akka | 消除版本冲突 + 精细控制序列化/加密/文件传输 |
| Inbox/Outbox 队 列模式 | Netty Channel 直接回调 | 解耦线程模型——处理线程与 Netty I/O 线程分离 |
| SharedMessageLoop + DedicatedMessageLoop | 线程池 per endpoint | 减少线程数（共享 loop） + 隔离关键端点（专用 loop） |
| Length-based framing (8B header) | 分隔符协议 (e.g. `\r\n`) | 二进制安全（消息体可包含任意字节） + 零拷贝-friendly |
| JavaSerializer | Protobuf / Avro | 内置在 Spark 的 Serializer 体系中，避免引入新依赖 |
| 单连接 per peer | 多连接 (connection pool) | 减少服务端连接数; shuffle 数据走独立通道 |

## 关键代码片段

### 示例：Dispatcher 的端点注册

```scala
// Dispatcher.scala:56-89
def registerRpcEndpoint(name: String, endpoint: RpcEndpoint): NettyRpcEndpointRef = {
  val addr = RpcEndpointAddress(nettyEnv.address, name)
  val endpointRef = new NettyRpcEndpointRef(nettyEnv.conf, addr, nettyEnv)
  synchronized {
    if (stopped) {
      throw new IllegalStateException("RpcEnv has been stopped")
    }
    if (endpoints.containsKey(name)) {
      throw new IllegalArgumentException(s"There is already an RpcEndpoint called $name")
    }
    endpointRefs.put(endpoint, endpointRef)
    var messageLoop: MessageLoop = null
    try {
      messageLoop = endpoint match {
        case e: IsolatedRpcEndpoint =>
          new DedicatedMessageLoop(name, e, this)
        case _ =>
          sharedLoop.register(name, endpoint)
          sharedLoop
      }
      endpoints.put(name, messageLoop)
    } catch {
      case NonFatal(e) =>
        endpointRefs.remove(endpoint)
        throw e
    }
  }
  endpointRef
}
```

### 示例：Inbox 的消息处理调度

```scala
// Inbox.scala:86-164 (简化)
def process(dispatcher: Dispatcher): Unit = {
  var message: InboxMessage = null
  inbox.synchronized {
    if (!enableConcurrent && numActiveThreads != 0) return
    message = messages.poll()
    if (message != null) numActiveThreads += 1 else return
  }
  while (true) {
    safelyCall(endpoint) {
      message match {
        case RpcMessage(_sender, content, context) =>
          endpoint.receiveAndReply(context).applyOrElse[Any, Unit](content, { msg =>
            throw new SparkException(s"Unsupported message $message from ${_sender}")
          })
        case OneWayMessage(_sender, content) =>
          endpoint.receive.applyOrElse[Any, Unit](content, { msg =>
            throw new SparkException(s"Unsupported message $message from ${_sender}")
          })
        case OnStart =>
          endpoint.onStart()
          if (!endpoint.isInstanceOf[ThreadSafeRpcEndpoint]) {
            inbox.synchronized { if (!stopped) enableConcurrent = true }
          }
        case OnStop =>
          dispatcher.removeRpcEndpointRef(endpoint)
          endpoint.onStop()
      }
    }
    inbox.synchronized {
      if (!enableConcurrent && numActiveThreads != 1) {
        numActiveThreads -= 1; return
      }
      message = messages.poll()
      if (message == null) { numActiveThreads -= 1; return }
    }
  }
}
```

### 示例：Outbox 的异步连接与发送

```scala
// Outbox.scala:197-224 (简化)
private def launchConnectTask(): Unit = {
  connectFuture = nettyEnv.clientConnectionExecutor.submit(new Callable[Unit] {
    override def call(): Unit = {
      try {
        val _client = nettyEnv.createClient(address)
        outbox.synchronized {
          client = _client
          if (stopped) closeClient()
        }
      } catch {
        case ie: InterruptedException => return
        case NonFatal(e) =>
          outbox.synchronized { connectFuture = null }
          handleNetworkFailure(e)
          return
      }
      outbox.synchronized { connectFuture = null }
      drainOutbox()
    }
  })
}
```

## 硬件视角

**RDMA/InfiniBand 为何未成标配**：

RDMA（Remote Direct Memory Access）允许一台机器的 NIC 直接写另一台机器的物理内存——跳过 CPU、跳过内核网络栈、跳过数据拷贝。InfiniBand 网络的端到端延迟可以低至 1-2μs，吞吐可达 100Gb/s+（与 100GbE 相当），但 CPU 占用仅 ~5%（100GbE 的 TCP/IP 栈占 ~30-50%）。

Spark 从未原生支持 RDMA 的原因有三个层次：

第一层：**Java/NETTY 生态限制**。Netty 基于 Java NIO（SocketChannel/ServerSocketChannel），而 RDMA 的 API（libibverbs：`ibv_post_send`、`ibv_post_recv`、`ibv_poll_cq`）是完全不同的编程模型——不是"stream of bytes"，而是"post work request → poll completion queue"。要在 Netty 上支持 RDMA 需要重写 TransportContext 的全部 Channel 抽象。

第二层：**RDMA 的跨网络可靠性的代价**。InfiniBand 需要专用交换机、专用线缆，不支持标准 Ethernet 的 Spanning Tree / LACP。RoCE（RDMA over Converged Ethernet）可以在以太网上跑，但 PFC（Priority Flow Control）极易引起"拥塞树扩散"（congestion spreading）——一个 slow receiver 拖慢上游所有 sender。在大规模生产集群中，RoCE 的运维成本（配置 PFC、排查 pause frame 风暴）很高。

第三层：**收益不如预期**。Spark 的 RPC 消息主要是短消息（LaunchTask、StatusUpdate，几百 bytes 到几 KB）——这种场景下 RDMA 的"大块 DMA"优势不显著。Spark 的大数据传输（Shuffle）走的是 Chunk Fetch（第 4 章的 `ChunkFetchRequest`）——这个阶段理论上受益于 RDMA，但目前 Celeborn/Uniffle（第 29 章）对 RDMA 的支持仍在实验阶段。

**实际案例**：某云厂商在 2024 年做过 Spark + RDMA（RoCE v2）的 PoC。Shuffle 大数据块场景下，端到端 latency 下降了 30%（12GB/s → 18GB/s 有效吞吐），但在小 RPC 消息场景下降了 < 5%。综合考虑 RoCE 的运维复杂度（每台机器额外 bond 一个 RDMA NIC + 配置 PFC 参数 + 升级内核），投入产出比不足以推动生产落地。结论：**Spark 的 RPC 层不是瓶颈——Shuffle 磁盘 I/O 是瓶颈，而 RDMA 解决的是网络传输问题。**

## AI 时代反思

**gRPC vs Netty RPC 的本质差异**：

Spark 4.0 引入 Spark Connect（第 26 章）使用 gRPC，而内部 RPC 层使用 Netty。这不是"现代 vs 过时"的选择——两个协议服务于**不同范式**：

```
Netty RPC (Spark 内部):
  - 消息格式: Java/Kryo 序列化后的 ByteBuffer
  - 路由: name → Dispatcher → Inbox → Endpoint
  - 类型安全性: 编译期无保证 (Any → PartialFunction match)
  - 跨语言: 否 (JVM-only)
  - 设计目标: 高性能二进制交互, 与 Spark 序列化框架深度耦合

gRPC (Spark Connect):
  - 消息格式: Protobuf (Plan, ExecutePlanRequest, ...)
  - 路由: method → service handler
  - 类型安全性: 编译期强类型, proto schema 保证
  - 跨语言: 是 (Python/Go/Rust/Kotlin 都有 gRPC client)
  - 设计目标: 标准化接口, 跨语言, HTTP/2 生态, 云原生
```

**AI Agent 视角**：LLM Agent 天然偏向 gRPC/protobuf——因为 proto schema 是可读的、可类型检查的、可验证的。Agent 可以读取 `base.proto` 中的 `Plan` 消息定义，然后生成符合 schema 的查询——不需要理解 Spark 内部 RPC 的序列化格式。

但 gRPC 的代价是 protobuf 序列化的开销高于 JavaSerializer（对简单数据类型约 1.3-1.5×），HTTP/2 的帧开销也高于纯 Netty Channel。这就是为什么 Spark Connect 用 gRPC 做客户端接口，而 Spark 内部 RPC 仍然用 Netty——**一个是"开放协议"，一个是"性能协议"**。

这种"双协议栈"的模式可能成为分布式系统的新常态：内部通信走高效专有协议（Netty RPC），外部接口走标准化协议（gRPC）。AI Agent 和外部工具对接标准化接口，内核组件间用专有协议保持性能。

## 源码导航

| 文件 | 关键内容 | 行号参考 |
|------|---------|---------|
| `core/src/main/scala/org/apache/spark/rpc/RpcEnv.scala` | RpcEnv 抽象类，RpcEnv.create 工厂方法，RpcEnvFileServer trait | ~36 (object RpcEnv), ~72 (abstract class RpcEnv) |
| `core/src/main/scala/org/apache/spark/rpc/RpcEndpoint.scala` | RpcEndpoint trait（生命周期），ThreadSafeRpcEndpoint，IsolatedRpcEndpoint，RpcEnvFactory | ~26 (RpcEnvFactory), ~46 (RpcEndpoint), ~148 (ThreadSafeRpcEndpoint) |
| `core/src/main/scala/org/apache/spark/rpc/RpcEndpointRef.scala` | RpcEndpointRef 抽象（send/ask/askSync），AbortableRpcFuture | ~30 (abstract class RpcEndpointRef) |
| `core/src/main/scala/org/apache/spark/rpc/RpcAddress.scala` | RpcAddress (host, port)，RpcEndpointAddress (address, name)，toURI 格式 `spark://name@host:port` | |
| `core/src/main/scala/org/apache/spark/rpc/RpcCallContext.scala` | RpcCallContext trait（reply/sendFailure/senderAddress） | |
| `core/src/main/scala/org/apache/spark/rpc/netty/NettyRpcEnv.scala` | NettyRpcEnv — setupEndpoint, send, askAbortable, postToOutbox, createClient, startServer | ~46 (class NettyRpcEnv) |
| `core/src/main/scala/org/apache/spark/rpc/netty/Dispatcher.scala` | Dispatcher — registerRpcEndpoint, postRemoteMessage, postLocalMessage, postOneWayMessage, stop | ~39 (class Dispatcher) |
| `core/src/main/scala/org/apache/spark/rpc/netty/Inbox.scala` | Inbox — process (消息处理调度), stop, InboxMessage 类型（OnStart, OnStop, RpcMessage, OneWayMessage, RemoteProcessConnected 等） | ~30 (sealed trait InboxMessage), ~58 (class Inbox) |
| `core/src/main/scala/org/apache/spark/rpc/netty/Outbox.scala` | Outbox — send, drainOutbox, launchConnectTask, handleNetworkFailure; OutboxMessage（OneWayOutboxMessage, RpcOutboxMessage） | ~31 (sealed trait OutboxMessage), ~95 (class Outbox) |
| `core/src/main/scala/org/apache/spark/rpc/netty/MessageLoop.scala` | MessageLoop — receiveLoop, PoisonPill; SharedMessageLoop, DedicatedMessageLoop | ~35 (sealed abstract class MessageLoop), ~103 (SharedMessageLoop), ~160 (DedicatedMessageLoop) |
| `core/src/main/scala/org/apache/spark/rpc/netty/NettyRpcCallContext.scala` | LocalNettyRpcCallContext (Promise-based), RemoteNettyRpcCallContext (Netty callback-based) | |
| `core/src/main/scala/org/apache/spark/rpc/netty/RpcEndpointVerifier.scala` | RpcEndpointVerifier — CheckExistence, 端点存在性验证 | |
| `common/network-common/src/main/java/org/apache/spark/network/TransportContext.java` | TransportContext — createServer, createClientFactory, Channel Pipeline 配置 | ~75 (class TransportContext) |
| `common/network-common/src/main/java/org/apache/spark/network/client/TransportClient.java` | TransportClient — send (one-way), sendRpc (带 callback), fetchChunk (数据块拉取) | ~73 (class TransportClient) |
| `common/network-common/src/main/java/org/apache/spark/network/client/TransportClientFactory.java` | TransportClientFactory — createClient (连接复用, 通过 ClientPool) | |
| `common/network-common/src/main/java/org/apache/spark/network/server/TransportServer.java` | TransportServer — init (Netty ServerBootstrap, bind), close | ~45 (class TransportServer) |
| `common/network-common/src/main/java/org/apache/spark/network/server/TransportRequestHandler.java` | TransportRequestHandler — handle(RpcRequest/OneWayMessage/ChunkFetchRequest/StreamRequest) | |
| `common/network-common/src/main/java/org/apache/spark/network/client/TransportResponseHandler.java` | TransportResponseHandler — handle(RpcResponse/ChunkFetchSuccess/StreamResponse), requestId → callback 映射 | |
| `common/network-common/src/main/java/org/apache/spark/network/server/RpcHandler.java` | RpcHandler — receive, getStreamManager (抽象; NettyRpcHandler 是 Spark 的实现) | |
| `common/network-common/src/main/java/org/apache/spark/network/protocol/RpcRequest.java` | RpcRequest — requestId, body | |
| `common/network-common/src/main/java/org/apache/spark/network/protocol/MessageDecoder.java` | MessageDecoder — Frame → Message 解码 | |
| `common/network-common/src/main/java/org/apache/spark/network/protocol/MessageEncoder.java` | MessageEncoder — Message → ByteBuf, 8-byte frame header (length + type + body size) | |
| `common/network-common/src/main/java/org/apache/spark/network/util/TransportFrameDecoder.java` | TransportFrameDecoder — 帧边界检测, 粘包/半包处理 | |
