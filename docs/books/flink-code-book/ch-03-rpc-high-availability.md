# 第 3 章 · RPC 与高可用：分布式协调的骨架

## 导读

- **一句话**：本章回答"Flink 的 JobManager 和 TaskManager 之间怎么通信，以及一个节点挂了另一个怎么自动接手"。
- **前置知识**：Actor 模型基础概念、ZooKeeper 基础、Java 动态代理。
- **读完本章你能回答**：
  - Flink 为什么不直接用 Netty 做 RPC，而要在其上加 Pekko（原 Akka）？
  - `flink-rpc-core` 的三层抽象——`RpcGateway` / `RpcEndpoint` / `RpcService` 如何做到不绑定任何具体 RPC 框架？
  - `PekkoRpcActor` 的四状态机（STOPPED → STARTED → TERMINATING → TERMINATED）如何驱动 RpcEndpoint 生命周期？
  - `PekkoInvocationHandler` 的动态代理如何区分本地调用和远程调用？
  - `FencedRpcGateway` 的 fencing token 机制防止什么问题？
  - 心跳怎样发现 TaskManager 死掉？`DefaultHeartbeatMonitor` 的四状态机是什么？
  - HA 模式下 ZooKeeper 存了哪些关键信息，Dispatcher/JM failover 全流程是怎样的？

---

## 3.1 — 设计动机：RPC 是控制平面，Netty 是数据平面

Flink 有两条完全分离的通信信道：

| 信道 | 用途 | 传输内容 | 实现 |
|------|------|---------|------|
| **控制平面** | 组件间协调 | RPC 请求/响应（deploy task, ack checkpoint） | Pekko（原 Akka） |
| **数据平面** | 算子间数据传输 | Buffer（序列化后的记录） | Netty |

**为什么控制平面不直接用 Netty？** Netty 处理的是无连接的 byte stream——要做 request-response 模式需要自己实现 pairing、timeout、重试。Pekko Actor 模式天然提供 `ask()` 的 request-response 抽象——发 `ask(msg)` 返回 `Future`，超时自动失败，无需手工管理连接状态。

### 从 Akka 到 Pekko：许可变更的应对

Akka 在 2022 年宣布许可变更——从 Apache 2.0 切换到 BSL（Business Source License）。Flink 社区的应对是把 `akka` 包名全部替换为 `pekko`（Apache Pekko 是 Akka 的社区分支，保持 Apache 2.0 许可）。在源码中你会看到：

```java
// PekkoRpcActor.java:42-46
import org.apache.pekko.actor.AbstractActor;
import org.apache.pekko.actor.ActorRef;
import org.apache.pekko.pattern.Patterns;
```

但整个 RPC 架构的设计没有变化——仍然是 Actor 模型 + 动态代理。

### 为什么要抽象 `flink-rpc-core`

```
flink-rpc/
├── flink-rpc-core/          ← 纯接口：RpcGateway, RpcEndpoint, RpcService, RpcServer
├── flink-rpc-akka/           ← Pekko 实现：PekkoRpcActor, PekkoRpcService, PekkoInvocationHandler
└── flink-rpc-akka-loader/    ← Java SPI 加载入口
```

`flink-rpc-core` 的存在意义：**整个 Flink 代码库只看到 `RpcGateway`、`RpcEndpoint`、`RpcService` 这些接口，不出现任何 Pekko 导入**。`loader` 层用 Java SPI 加载具体的 `RpcSystem` 实现——将来如果有 `flink-rpc-grpc`，只需要换 META-INF/services 配置。

---

## 3.2 — RPC 核心抽象：三层接口源码走读

### RpcGateway：每种角色的"可调用方法"合集

`RpcGateway` 是最基础的接口（`flink-rpc-core/.../rpc/RpcGateway.java:22`）：

```java
public interface RpcGateway {
    String getAddress();    // RPC 地址（host:port）
    String getHostname();   // 主机名
}
```

Flink 中每种服务角色对外暴露一个继承自 `RpcGateway` 的接口：

```java
// TaskExecutorGateway 继承 RpcGateway
public interface TaskExecutorGateway extends RpcGateway {
    CompletableFuture<Acknowledge> submitTask(TaskDeploymentDescriptor, ...);
    CompletableFuture<Acknowledge> cancelTask(ExecutionAttemptID, ...);
    CompletableFuture<Acknowledge> triggerCheckpoint(ExecutionAttemptID, ...);
    ...
}
```

Dispatcher、JobMaster、ResourceManager、TaskExecutor 各有自己的 Gateway 接口。这跟 OS 中的 "capability-based security" 思路一致——调用一个组件时，你只能调用它 Gateway 上声明的方法。

**Gateway 的关键约定**：所有方法的返回类型必须是 `CompletableFuture`——这是 Flink 的 RPC 层不阻塞调用方线程、天然适合异步调度的基础。

### FencedRpcGateway：fencing token 防旧主干政

```java
// flink-rpc-core/.../rpc/FencedRpcGateway.java:28
public interface FencedRpcGateway<F extends Serializable> extends RpcGateway {
    F getFencingToken();
}
```

`FencedRpcGateway` 在 `RpcGateway` 基础上增加了一个 `fencingToken`——这是分布式系统中经典的 "fencing" 机制。JobMaster 在 failover 后会获得一个新的 fencing token（UUID），旧主即使没死透继续发 RPC，接收方发现 fencing token 不匹配会拒绝请求。这防止了"脑裂"场景下旧主和新主同时操作同一个 Job 的状态。

### RpcServer：RpcEndpoint 的自引用接口

```java
// flink-rpc-core/.../rpc/RpcServer.java:24
public interface RpcServer extends StartStoppable, MainThreadExecutable, RpcGateway {
    CompletableFuture<Void> getTerminationFuture();
}
```

`RpcServer` 是 `RpcEndpoint` 的自引用——`RpcEndpoint` 构造时调用 `rpcService.startServer(this)` 返回一个 `RpcServer` 对象，这个对象同时扮演三个角色：
1. **StartStoppable**：控制 Endpoint 的启动/停止
2. **MainThreadExecutable**：可以向主线程投递 Runnable/Callable
3. **RpcGateway**：可以获取地址信息

### MainThreadExecutable：向主线程投递任务

```java
// flink-rpc-core/.../rpc/MainThreadExecutable.java:34
public interface MainThreadExecutable {
    void runAsync(Runnable runnable);
    <V> CompletableFuture<V> callAsync(Callable<V> callable, Duration callTimeout);
    void scheduleRunAsync(Runnable runnable, long delay);
}
```

这三个方法是将"执行"投递到 Endpoint 的主线程中——这是 Actor 模型的核心：所有状态变更操作必须在主线程中串行执行。

### RpcService：RPC 基础设施接口

```java
// flink-rpc-core/.../rpc/RpcService.java:34
public interface RpcService extends AutoCloseableAsync {
    String getAddress();
    int getPort();
    <C extends RpcGateway> C getSelfGateway(Class<C> selfGatewayType, RpcServer rpcServer);
    <C extends RpcGateway> CompletableFuture<C> connect(String address, Class<C> clazz);
    <F extends Serializable, C extends FencedRpcGateway<F>> CompletableFuture<C> connect(
            String address, F fencingToken, Class<C> clazz);
    <C extends RpcEndpoint & RpcGateway> RpcServer startServer(
            C rpcEndpoint, Map<String, String> loggingContext);
    void stopServer(RpcServer selfGateway);
    ScheduledExecutor getScheduledExecutor();
}
```

`RpcService` 的核心职责：
- `startServer()`：将 `RpcEndpoint` 注册为一个 RPC 服务，返回 `RpcServer`
- `connect()`：连接到远程 RPC 服务，返回对应 `RpcGateway` 类型的代理
- `getSelfGateway()`：获取自身的 Gateway 代理（用于内部异步调用自身方法）

注意 `connect()` 有两个重载：一个普通连接，一个带 fencing token 的连接。带 fencing token 的连接返回 `FencedRpcGateway`，所有 RPC 调用都会附带 fencing token。

### RpcEndpoint：服务的生命周期容器

`RpcEndpoint` 是所有 RPC 服务组件的基类（`flink-rpc-core/.../rpc/RpcEndpoint.java:95`）：

```java
public abstract class RpcEndpoint implements RpcGateway, AutoCloseableAsync {
    private final RpcService rpcService;         // RPC 服务
    private final String endpointId;             // 唯一标识
    protected final RpcServer rpcServer;          // 自引用（构造时由 rpcService.startServer(this) 创建）
    final AtomicReference<Thread> currentMainThread; // 主线程引用
    private final MainThreadExecutor mainThreadExecutor; // 主线程执行器
    private final CloseableRegistry resourceRegistry;   // 资源注册表
    private boolean isRunning;                   // 运行状态（仅主线程可访问）
}
```

**关键设计点**：`rpcServer` 在构造函数中被创建（`RpcEndpoint.java:147`）：

```java
protected RpcEndpoint(RpcService rpcService, String endpointId, Map<String, String> loggingContext) {
    this.rpcService = checkNotNull(rpcService, "rpcService");
    this.endpointId = checkNotNull(endpointId, "endpointId");
    this.rpcServer = rpcService.startServer(this, loggingContext);  // ← 创建 Pekko Actor
    this.resourceRegistry = new CloseableRegistry();
    this.mainThreadExecutor = new MainThreadExecutor(rpcServer, this::validateRunsInMainThread, endpointId);
    registerResource(this.mainThreadExecutor);
}
```

#### 生命周期：onStart() → running → onStop()

```java
// RpcEndpoint.java:201-229
public final void start() { rpcServer.start(); }

public final void internalCallOnStart() throws Exception {
    validateRunsInMainThread();  // 确保在主线程
    isRunning = true;
    onStart();                  // 用户覆写此方法
}

protected void onStart() throws Exception {}  // 空实现，子类覆写
```

生命周期严格有序：`start()` → `internalCallOnStart()` → `onStart()` → `isRunning=true`。关闭同理：`closeAsync()` → `internalCallOnStop()` → `onStop()` → `isRunning=false`。

#### 主线程保证：所有 RPC 调用串行执行

```java
// RpcEndpoint.java:402-404
protected void runAsync(Runnable runnable) {
    rpcServer.runAsync(runnable);  // 投递到主线程的 mailbox
}
```

每个 RPC Endpoint 内部持有一个专属的 Actor，Actor 的 mailbox 提供"每个 endpoint 单线程处理"的保证——所有对它的 RPC 调用都排队在这个 mailbox 中逐一执行。这意味着 **RpcEndpoint 的实现不需要自己写锁**——这是 Actor 模型最大的优势。

#### getSelfGateway：内部异步调用自身

```java
// RpcEndpoint.java:326-328
public <C extends RpcGateway> C getSelfGateway(Class<C> selfGatewayType) {
    return rpcService.getSelfGateway(selfGatewayType, rpcServer);
}
```

这允许 Endpoint 内部代码通过 Gateway 接口异步调用自身的方法——调用仍然经过 mailbox 排队，保证串行执行。这是 Flink 中常见的模式：在异步回调中需要修改 Endpoint 状态时，通过 `getSelfGateway()` 把操作投递回主线程。

---

## 3.3 — Pekko 实现：从 Actor 到动态代理

### PekkoRpcActor：四状态机驱动生命周期

`PekkoRpcActor` 是 Flink RPC 的核心实现（`flink-rpc-akka/.../rpc/pekko/PekkoRpcActor.java:86`）：

```java
class PekkoRpcActor<T extends RpcEndpoint & RpcGateway> extends AbstractActor {
    protected final T rpcEndpoint;           // 被代理的 RpcEndpoint
    private final ClassLoader flinkClassLoader;
    private final MainThreadValidatorUtil mainThreadValidator;
    private final CompletableFuture<Boolean> terminationFuture;
    private final int version;               // RPC 协议版本
    private final long maximumFramesize;     // 最大帧大小
    private final AtomicBoolean rpcEndpointStopped;
    @Nonnull private State state;            // 当前状态
}
```

**四状态机**：

```
STOPPED ──start()──→ STARTED ──terminate()──→ TERMINATING ──postStop()──→ TERMINATED
   │                    │
   │                    └──stop()──→ STOPPED
   │
   └──terminate()──→ TERMINATING
```

状态定义在 `PekkoRpcActor.java:532-673`：

| 状态 | isRunning() | 行为 |
|------|------------|------|
| `STOPPED` | false | 丢弃所有消息，等待 START |
| `STARTED` | true | 正常处理 RPC 调用 |
| `TERMINATING` | true | 正在关闭，仍接受消息 |
| `TERMINATED` | false | 终止完成 |

#### 消息分发：createReceive()

```java
// PekkoRpcActor.java:160-166
@Override
public Receive createReceive() {
    return ReceiveBuilder.create()
            .match(RemoteHandshakeMessage.class, this::handleHandshakeMessage)
            .match(ControlMessages.class, this::handleControlMessage)
            .matchAny(this::handleMessage)      // ← 所有其他消息（包括 RpcInvocation）
            .build();
}
```

消息类型有三类：
1. **RemoteHandshakeMessage**：连接握手（版本号 + Gateway 类型检查）
2. **ControlMessages**：START / STOP / TERMINATE 控制
3. **其他**：RpcInvocation / RunAsync / CallAsync

#### handleMessage：主线程守卫

```java
// PekkoRpcActor.java:168-191
private void handleMessage(final Object message) {
    if (state.isRunning()) {
        mainThreadValidator.enterMainThread();   // ← 标记当前线程为"主线程"
        try {
            handleRpcMessage(message);
        } finally {
            mainThreadValidator.exitMainThread(); // ← 退出主线程标记
        }
    } else {
        sendErrorIfSender(new EndpointNotStartedException(...));
    }
}
```

`mainThreadValidator` 是关键——它在 Actor 处理消息时将当前线程标记为 Endpoint 的主线程。这样 `RpcEndpoint.validateRunsInMainThread()` 才能通过。Pekko Actor 的单线程 mailbox 保证了同一时刻只有一个线程在处理消息——这就是 Actor 模型提供"无锁并发"的机制。

#### handleRpcMessage：三种消息类型

```java
// PekkoRpcActor.java:223-244
protected void handleRpcMessage(Object message) {
    if (message instanceof RunAsync) {
        handleRunAsync((RunAsync) message);      // 异步 Runnable
    } else if (message instanceof CallAsync) {
        handleCallAsync((CallAsync) message);    // 异步 Callable（有返回值）
    } else if (message instanceof RpcInvocation) {
        handleRpcInvocation((RpcInvocation) message);  // RPC 方法调用
    }
}
```

#### handleRpcInvocation：反射调用 Endpoint 方法

这是最核心的 RPC 调用处理（`PekkoRpcActor.java:285-347`）：

```java
private void handleRpcInvocation(RpcInvocation rpcInvocation) {
    String methodName = rpcInvocation.getMethodName();
    Class<?>[] parameterTypes = rpcInvocation.getParameterTypes();
    rpcMethod = lookupRpcMethod(methodName, parameterTypes);  // ← 反射查找方法

    if (rpcMethod != null) {
        rpcMethod.setAccessible(true);
        if (rpcMethod.getReturnType().equals(Void.TYPE)) {
            // void 返回 → fire-and-forget（tell 模式）
            runWithContextClassLoader(
                () -> capturedRpcMethod.invoke(rpcEndpoint, rpcInvocation.getArgs()),
                flinkClassLoader);
        } else {
            // 有返回值 → 需要回送结果
            Object result = runWithContextClassLoader(
                () -> capturedRpcMethod.invoke(rpcEndpoint, rpcInvocation.getArgs()),
                flinkClassLoader);

            if (result instanceof CompletableFuture) {
                sendAsyncResponse((CompletableFuture<?>) result, methodName, isLocalRpcInvocation);
            } else {
                sendSyncResponse(result, methodName, isLocalRpcInvocation);
            }
        }
    }
}
```

**关键设计**：`lookupRpcMethod()` 直接用反射在 `rpcEndpoint` 上查找方法——这意味着 RPC 调用与 `RpcEndpoint` 子类的方法定义是 1:1 对应的。子类只需要正常写方法，不需要额外的序列化/反序列化代码。

#### 远程 vs 本地：序列化优化

```java
// PekkoRpcActor.java:349-363
private void sendSyncResponse(Object response, String methodName, boolean isLocalRpcInvocation) {
    if (isRemoteSender(getSender()) || (forceSerialization && !isLocalRpcInvocation)) {
        // 远程发送 → 序列化 + 帧大小检查
        Either<RpcSerializedValue, RpcException> serializedResult =
                serializeRemoteResultAndVerifySize(response, methodName);
        getSender().tell(new Status.Success(serializedResult.left()), getSelf());
    } else {
        // 本地发送 → 直接传引用（零拷贝）
        getSender().tell(new Status.Success(response), getSelf());
    }
}
```

本地 Actor 之间的消息传递不需要序列化——直接传 Java 对象引用。远程则必须序列化并检查帧大小（`maximumFramesize`）。这是 Actor 模型在单 JVM 内的性能优势。

### PekkoInvocationHandler：调用方的动态代理

`PekkoInvocationHandler` 是调用方的代理（`flink-rpc-akka/.../rpc/pekko/PekkoInvocationHandler.java:71`）：

```java
class PekkoInvocationHandler implements InvocationHandler, PekkoBasedEndpoint, RpcServer {
    private final String address;
    private final String hostname;
    private final ActorRef rpcEndpoint;    // 远端 Actor 引用
    private final boolean isLocal;         // 是否同一 ActorSystem
    private final Duration timeout;        // ask 超时
    private final long maximumFramesize;
}
```

#### invoke()：所有 RPC 调用的入口

```java
// PekkoInvocationHandler.java:125-149
@Override
public Object invoke(Object proxy, Method method, Object[] args) throws Throwable {
    Class<?> declaringClass = method.getDeclaringClass();

    if (declaringClass.equals(PekkoBasedEndpoint.class)
            || declaringClass.equals(Object.class)
            || declaringClass.equals(RpcGateway.class)
            || declaringClass.equals(StartStoppable.class)
            || declaringClass.equals(MainThreadExecutable.class)
            || declaringClass.equals(RpcServer.class)) {
        result = method.invoke(this, args);   // ← 本地方法，直接调用
    } else if (declaringClass.equals(FencedRpcGateway.class)) {
        throw new UnsupportedOperationException(...);  // ← 必须用 fencing token 连接
    } else {
        result = invokeRpc(method, args);     // ← 真正的 RPC 调用
    }
}
```

#### invokeRpc()：tell vs ask

```java
// PekkoInvocationHandler.java:217-286
private Object invokeRpc(Method method, Object[] args) throws Exception {
    RpcInvocation rpcInvocation = createRpcInvocationMessage(
            method.getDeclaringClass().getSimpleName(),
            methodName, isLocalRpcInvocation, parameterTypes, args);

    if (Objects.equals(returnType, Void.TYPE)) {
        tell(rpcInvocation);                  // ← fire-and-forget
        result = null;
    } else {
        CompletableFuture<?> resultFuture = ask(rpcInvocation, futureTimeout)  // ← ask 模式
                .thenApply(resultValue -> deserializeValueIfNeeded(resultValue, method, flinkClassLoader));
        // ...
    }
}
```

**tell vs ask**：
- `tell`：单向发送，不等回应。用于 void 返回类型的方法（如 `cancelTask`）
- `ask`：发送后等回应，超时自动失败。用于有返回值的方法（如 `submitTask` → `Acknowledge`）

```java
// PekkoInvocationHandler.java:340-344
protected CompletableFuture<?> ask(Object message, Duration timeout) {
    final CompletableFuture<?> response =
            ScalaFutureUtils.toJava(Patterns.ask(rpcEndpoint, message, timeout.toMillis()));
    return guardCompletionWithContextClassLoader(response, flinkClassLoader);
}
```

`Patterns.ask()` 是 Pekko 的 ask 模式——它创建一个临时 Actor 作为回复目标，超时后自动返回 `AskTimeoutException`。

#### Local vs Remote RpcInvocation

```java
// PekkoInvocationHandler.java:299-317
private RpcInvocation createRpcInvocationMessage(...) {
    if (isLocal && (!forceRpcInvocationSerialization || isLocalRpcInvocation)) {
        rpcInvocation = new LocalRpcInvocation(...);  // ← 本地：不序列化参数
    } else {
        rpcInvocation = new RemoteRpcInvocation(...);  // ← 远程：序列化参数
    }
}
```

`@Local` 注解标记的方法即使在远程调用时也不强制序列化——用于性能敏感的内部方法。

### 调用链路全景

```
调用方线程:
  gateway.submitTask(tdd)
    → PekkoInvocationHandler.invoke()
      → invokeRpc()
        → createRpcInvocationMessage() → LocalRpcInvocation / RemoteRpcInvocation
        → ask(rpcInvocation, timeout)   → Patterns.ask(actorRef, msg, timeoutMs)
          → Pekko Actor mailbox 排队
          → CompletableFuture 等待响应

被调用方 Actor 线程:
  PekkoRpcActor.handleMessage()
    → mainThreadValidator.enterMainThread()
    → handleRpcMessage()
      → handleRpcInvocation()
        → lookupRpcMethod() → 反射找到 RpcEndpoint 子类的方法
        → rpcMethod.invoke(rpcEndpoint, args)  ← 实际执行
        → sendSyncResponse() / sendAsyncResponse() → 回送结果
    → mainThreadValidator.exitMainThread()

调用方线程（回调）:
  ask() 返回的 CompletableFuture 完成
    → deserializeValueIfNeeded()  ← 远程调用需要反序列化
    → 用户拿到结果
```

---

## 3.4 — 双层心跳：故障发现的基石

### 为什么需要两层

```
ResourceManager ←──心跳──→ TaskExecutor
              ←──心跳──→ JobMaster
JobMaster      ←──心跳──→ TaskExecutor   (间接，通过 Slot)
```

- **RM ↔ TM 心跳**：检测"这个 TM 进程还活着吗"。断线 → TM 被标记为不可用，其所有 Slot 被回收
- **JM ↔ TM 心跳**：检测"这个 Job 在这个 TM 上的 Slot 还好吗"。断线 → 对应 Execution 被 fail

每层心跳是独立计时的——RM 层面的心跳周期可以与 JM 面的不同。

### HeartbeatManagerImpl：心跳管理器源码

`HeartbeatManagerImpl` 是心跳管理的核心实现（`flink-runtime/.../heartbeat/HeartbeatManagerImpl.java:49`）：

```java
@ThreadSafe
class HeartbeatManagerImpl<I, O> implements HeartbeatManager<I, O> {
    private final long heartbeatTimeoutIntervalMs;           // 超时时间
    private final int failedRpcRequestsUntilUnreachable;     // 连续失败次数阈值
    private final ResourceID ownResourceID;                   // 自身资源 ID
    private final HeartbeatListener<I, O> heartbeatListener;  // 超时回调
    private final ScheduledExecutor mainThreadExecutor;       // 主线程执行器
    private final ConcurrentHashMap<ResourceID, HeartbeatMonitor<O>> heartbeatTargets; // 监控目标表
}
```

**两种心跳模式**：

```java
// HeartbeatManagerImpl.java:207-219
// 模式1：接收心跳（被监控方主动汇报）
public CompletableFuture<Void> receiveHeartbeat(ResourceID heartbeatOrigin, I heartbeatPayload) {
    reportHeartbeat(heartbeatOrigin);  // ← 重置超时计时器
    if (heartbeatPayload != null) {
        heartbeatListener.reportPayload(heartbeatOrigin, heartbeatPayload);
    }
    return FutureUtils.completedVoidFuture();
}

// HeartbeatManagerImpl.java:222-243
// 模式2：请求心跳（监控方主动探测）
public CompletableFuture<Void> requestHeartbeat(ResourceID requestOrigin, I heartbeatPayload) {
    HeartbeatTarget<O> heartbeatTarget = reportHeartbeat(requestOrigin);
    if (heartbeatTarget != null) {
        heartbeatTarget.receiveHeartbeat(getOwnResourceID(),
                heartbeatListener.retrievePayload(requestOrigin))   // ← 携带负载回送
            .whenCompleteAsync(handleHeartbeatRpc(requestOrigin), mainThreadExecutor);
    }
}
```

**心跳携带负载**：`I` 和 `O` 是泛型参数，分别代表"入站心跳负载"和"出站心跳负载"。例如：
- RM → TM 心跳中，TM 可以汇报 Slot 使用情况作为负载
- JM → TM 心跳中，TM 可以汇报当前 Execution 状态

### DefaultHeartbeatMonitor：四状态超时检测器

`DefaultHeartbeatMonitor` 是每个被监控目标的超时检测器（`flink-runtime/.../heartbeat/DefaultHeartbeatMonitor.java:39`）：

```java
public class DefaultHeartbeatMonitor<O> implements HeartbeatMonitor<O>, Runnable {
    private final long heartbeatTimeoutIntervalMs;
    private final int failedRpcRequestsUntilUnreachable;
    private volatile ScheduledFuture<?> futureTimeout;                        // 超时定时器
    private final AtomicReference<State> state = new AtomicReference<>(State.RUNNING);
    private final AtomicInteger numberFailedRpcRequestsSinceLastSuccess = new AtomicInteger(0);
    private volatile long lastHeartbeat;
}
```

**四状态机**：

```
RUNNING ──超时──→ TIMEOUT ──→ 通知 heartbeatListener.notifyHeartbeatTimeout()
  │
  ├──连续N次RPC失败──→ UNREACHABLE ──→ 通知 heartbeatListener.notifyTargetUnreachable()
  │
  └──cancel()──→ CANCELED
```

```java
// DefaultHeartbeatMonitor.java:155-160
@Override
public void run() {  // ScheduledExecutor 超时后执行此方法
    if (state.compareAndSet(State.RUNNING, State.TIMEOUT)) {
        heartbeatListener.notifyHeartbeatTimeout(resourceID);  // ← 通知超时
    }
}
```

超时重置机制（`DefaultHeartbeatMonitor.java:166-178`）：

```java
void resetHeartbeatTimeout(long heartbeatTimeout) {
    if (state.get() == State.RUNNING) {
        cancelTimeout();  // ← 取消旧的定时器
        futureTimeout = scheduledExecutor.schedule(this, heartbeatTimeout, TimeUnit.MILLISECONDS);  // ← 重新调度
        if (state.get() != State.RUNNING) {  // ← double-check 并发问题
            cancelTimeout();
        }
    }
}
```

每次收到心跳就重置定时器——如果 `heartbeatTimeoutIntervalMs` 内没有心跳，定时器触发 `run()` → 通知 `HeartbeatListener`。

### RPC 失败检测：与超时检测的互补

```java
// DefaultHeartbeatMonitor.java:113-129
@Override
public void reportHeartbeatRpcFailure() {
    int failedRpcRequestsSinceLastSuccess = numberFailedRpcRequestsSinceLastSuccess.incrementAndGet();
    if (isHeartbeatRpcFailureDetectionEnabled()
            && failedRpcRequestsSinceLastSuccess >= failedRpcRequestsUntilUnreachable) {
        if (state.compareAndSet(State.RUNNING, State.UNREACHABLE)) {
            cancelTimeout();
            heartbeatListener.notifyTargetUnreachable(resourceID);  // ← 标记为不可达
        }
    }
}
```

`failedRpcRequestsUntilUnreachable` 由 `heartbeat.rpc-failure-threshold` 控制。连续 N 次 RPC 失败就直接标记为 UNREACHABLE——这比等超时更快地发现对端已经不可达（例如进程已死但网络未断，TCP 连接还没超时）。

常见调优参数：
```yaml
heartbeat.interval: 10000          # 10s 发一次
heartbeat.timeout: 50000           # 50s 没回应 = 超时
heartbeat.rpc-failure-threshold: 2 # 连续 2 次超时就认为挂了
```

---

## 3.5 — High Availability：Leader 选举与状态持久化

### HighAvailabilityServices 接口

`HighAvailabilityServices` 是 HA 的顶层抽象（`flink-runtime/.../highavailability/HighAvailabilityServices.java:52`）：

```java
public interface HighAvailabilityServices extends ClientHighAvailabilityServices, GloballyCleanableResource {
    // Leader 选举
    LeaderElection getResourceManagerLeaderElection();
    LeaderElection getDispatcherLeaderElection();
    LeaderElection getJobManagerLeaderElection(JobID jobID);
    LeaderElection getClusterRestEndpointLeaderElection();

    // Leader 检索
    LeaderRetrievalService getResourceManagerLeaderRetriever();
    LeaderRetrievalService getDispatcherLeaderRetriever();
    LeaderRetrievalService getJobManagerLeaderRetriever(JobID jobID, String defaultJobManagerAddress);

    // 持久化存储
    CheckpointRecoveryFactory getCheckpointRecoveryFactory();
    ExecutionPlanStore getExecutionPlanStore();
    JobResultStore getJobResultStore();
    BlobStore createBlobStore();

    // 生命周期
    void close() throws Exception;
    void cleanupAllData() throws Exception;
}
```

**关键设计**：HA 接口为每种组件（RM、Dispatcher、JobMaster、REST Endpoint）提供独立的 Leader 选举和检索服务。每个 Job 有自己的 `JobManagerLeaderElection`——这是 per-job 故障隔离的基础。

### 实现层次

```
HighAvailabilityServices (接口)
  ├── AbstractHaServices (抽象基类，处理共享逻辑)
  │     ├── ZooKeeperLeaderElectionHaServices  ← ZK 实现
  │     └── KubernetesLeaderElectionHaServices ← K8s 实现
  ├── EmbeddedHaServices       ← 单进程模式
  └── StandaloneHaServices     ← 无 HA 模式
```

### ZooKeeper 上存什么

HA 模式下（`high-availability: zookeeper`），ZK 的目录结构如下：

```
/flink/
  ├── /leader/                          ← Dispatcher 的 Leader Latch
  ├── /leader/resourcemanager/          ← ResourceManager 的 Leader Latch
  ├── /leader/<job-id>/                 ← 每个 Job 的 JobMaster Leader Latch
  ├── /jobgraphs/<job-id>               ← 序列化的 JobGraph 数据
  ├── /checkpoints/<job-id>/<operator>  ← 完成的 checkpoint 指针
  └── /running_job_registry/<job-id>    ← 运行中 Job 的状态标记
```

### Leader 选举机制

`AbstractHaServices` 使用 `DefaultLeaderElectionService` 作为统一的选举服务入口，底层通过 `LeaderElectionDriverFactory` 适配不同的存储后端：

- ZK：`ZooKeeperLeaderElectionDriver`（基于 Ephemeral Sequential ZNode）
- K8s：`KubernetesLeaderElectionDriver`（基于 ConfigMap 的 leader 标记）
- Standalone：直接指定 Leader

ZK 选举流程：
```
1. 所有候选者创建 /leader/latch-000000001, latch-000000002, latch-000000003
2. 编号最小的自动成为 Leader
3. 其他注册 watcher 监控前序节点
4. Leader 故障 → Ephemeral ZNode 自动删除 → 下一位接手
```

### Dispatcher Failover 全流程

Dispatcher 挂掉后：

```
1. ZK 检测 Dispatcher session 超时 → 删除其 ephemeral znode
2. Standby Dispatcher 抢到 latch → 成为新 Leader
3. 新 Leader 从 ZK /leadergraphs/ 恢复所有活跃 JobGraph
4. 为每个 JobGraph 创建 JobMasterServiceLeadershipRunner
5. 新 Runner 选举该 Job 的 Master → 启动 JobMaster
6. JobMaster 从 ZK /checkpoints/ 读取最近 checkpoint 指针
7. 从 checkpoint 恢复 ExecutionGraph
8. 重新部署 Task 到可用的 TaskManager
```

关键是步骤 3：**如果 ZK 上没有 JobGraph，恢复链路就断了**——这也是为什么 `jobmanager.execution.failover-strategy: region` 的环境中，ZK 上必须在 Submit 时立刻写入 JobGraph。

### Standalone 模式的伪-HA

Standalone 模式下没有 ZK，Flink 内部走本地实现：

```
StandaloneHaServices → 什么都不存
StandaloneLeaderElectionService → 永远"我是 Leader"
```

恢复数据只能从本地文件系统上的 checkpoint metadata 读取。如果 TaskManager 挂了就靠 state backend 上的 checkpoint 恢复。

---

## 3.6 — JobMaster 的 Per-Job Leader Election

每个 Job 有一个独立的 Leader Election——即使在 Standalone 单 Dispatcher 下也是如此：

```
JobMasterServiceLeadershipRunner
  ├── LeaderElectionService      ← 选举"这个 Job 的 Master"
  ├── LeaderRetrievalService     ← 可以读取当前谁是这个 Job 的 Master
  ├── JobMaster                  ← 若当选，它启动
  └── 丢失 Leader → 关掉 JM → 重新选举 → 恢复
```

这保证了多 Job 的故障隔离：Job A 的 Master 挂了不影响 Job B。每个 Job 的 ZK election 路径独立 `/flink/leader/<job-id>`。

---

## 3.7 — 组件注册连接建立

### TaskExecutor 如何"加入集群"

```
TM 启动 → TaskExecutorToResourceManagerConnection
  → 通过 ZK / RM REST 发现 RM 地址
  → TM.registerTaskExecutor(TaskExecutorRegistration)
  → RM 做以下检查：
    - TM 的 ResourceID 是否冲突
    - RM 是否正在踢掉旧的同名 TM
  → 返回 TaskExecutorRegistrationSuccess
  → RM 把 TM 纳入 SlotManager
  → 通知活跃的 JobMaster "有新的计算资源可用"
```

源码入口：`flink-runtime/.../taskexecutor/TaskExecutorToResourceManagerConnection.java`

### Dispatch→JobMaster 的关联

Dispatch 创建 `JobMasterServiceLeadershipRunner` 并根据 ZK leader latch 控制 JobMaster 的实际启动。JobMaster 启动后立即连接 RM 申请 Slot 开始调度。这与 Spark Driver 中 DAGScheduler 一通到底不同——Flink 显式分开了"提交"和"执行/容错"的边界。

---

## 3.8 — 横向对比

### vs Spark RPC

Spark 在 2.x+ 版本自己做了一个基于 Netty 的 `RpcEnv` 替代 Akka。两者思路相同（分离地址/通道和上层业务逻辑），但 Spark 的 RPC 不考虑多 RPC 框架的 SPI 可插拔性——它绑定了 Netty。Flink 多了一层 `RpcGateway` 聚合和 `RpcEndpoint` 的生命周期管理，更接近于"微服务框架中的 RPC"思路。

Flink 的 `FencedRpcGateway` 机制是 Spark RPC 没有的——Spark Driver failover 后不防旧主干政（因为 Spark 批处理任务 failover 通常是直接重跑，不需要状态恢复）。

### vs StarRocks BE/FE RPC

StarRocks 用 BRPC + Thrift。BRPC 是百度自研的单线程 Reactor 模型 RPC，性能极高。Flink+Pekko 的 RPC 路径对于吞吐敏感的场景（如 Buffered 数据）远不如 BRPC，所以 Flink 严格地把数据平面甩给 Netty。

### vs MaxCompute

MaxCompute 的 Worker/Master 通信都是 REST-based——不是高性能 RPC 模式。这对手动作业（几秒到几小时）足够了——对比 Flink 流处理对 sub-second 级别的 RPC 调用有需求。

---

## 3.9 — 调优与实战陷阱

### 心跳 + GC 的死亡组合

最常见事故：`heartbeat.timeout: 30s` + GC 一次停了 35s → RM 错误地开掉 TM → 所有 Slot 被回收 → 整个 Job fail。

**解法**：观察 GC 日志中最大 pause + 15s 作为 heartbeat.timeout。或者把数据路径全部堆外（Direct Memory Network Buffer + Off-Heap State），大幅减少 Full GC 概率。

### ZK Session Timeout vs Heartbeat Timeout

ZK session timeout 应该 **≥ 2x heartbeat.timeout**。否则：RM 心跳偶尔超时一次被错误标记 → ZK session 先于心跳判定断连 → ZK 删掉 RM 的 ephemeral node → 另一个 RM 抢 Leader → 原 RM 恢复后发现已经不是 Leader → 整个集群抖动。

### Pekko Ask Timeout 默认配置

Pekko 的 `pekko.ask.timeout`（原 `akka.ask.timeout`）决定 RPC 调用方最多等多长时间。如果 JVM 压力大导致 Pekko mailbox 处理不过来，`ask()` 可能超时返回 timeout。这不是业务逻辑 bug，是 Pekko 线程池饿死。监控 `pekko.actor.default-dispatcher` 线程池的排队深度是 Flink 运维的关键。

### Oversized RPC Response

`PekkoRpcActor` 的 `maximumFramesize` 限制了 RPC 响应的大小（`PekkoRpcActor.java:402-427`）。如果一个 RPC 返回的结果超过帧大小限制，会抛出 `RpcException`。这在返回大的 State 快照、大量 Metric 数据时可能触发。调优参数：`rpc.ask.timeout` 和内部帧大小配置。

---

## 本章要点回顾

1. Flink 控制平面 RPC 与数据平面 Netty 严格分路——RPC 用 Pekko Actor 的 `ask/response` 模式，天然 request-response 配对和超时。
2. `flink-rpc-core` 的三层抽象——`RpcGateway`（接口契约）/ `RpcEndpoint`（生命周期）/ `RpcService`（基础设施）——让整个代码库不碰 Pekko 具体类型，随时可换 RPC 实现。
3. `PekkoRpcActor` 四状态机（STOPPED/STARTED/TERMINATING/TERMINATED）驱动 `RpcEndpoint` 生命周期，Actor mailbox 保证单线程处理。
4. `PekkoInvocationHandler` 是动态代理——`tell` 用于 fire-and-forget，`ask` 用于 request-response；本地调用走 `LocalRpcInvocation` 零序列化。
5. `FencedRpcGateway` 的 fencing token 防止旧主 failover 后继续操作。
6. `DefaultHeartbeatMonitor` 四状态机（RUNNING/TIMEOUT/UNREACHABLE/CANCELED）提供超时检测和 RPC 失败检测双重保障。
7. `HighAvailabilityServices` 为每种组件提供独立的 Leader 选举——per-job 选举是故障隔离的核心。

## 源码导航

- RPC 核心接口：`flink-rpc/flink-rpc-core/.../rpc/RpcGateway.java`（L22）
- FencedRpcGateway：`flink-rpc/flink-rpc-core/.../rpc/FencedRpcGateway.java`（L28）
- RpcServer：`flink-rpc/flink-rpc-core/.../rpc/RpcServer.java`（L24）
- MainThreadExecutable：`flink-rpc/flink-rpc-core/.../rpc/MainThreadExecutable.java`（L34）
- RpcEndpoint：`flink-rpc/flink-rpc-core/.../rpc/RpcEndpoint.java`（L95，构造 L142，生命周期 L201-258）
- RpcService：`flink-rpc/flink-rpc-core/.../rpc/RpcService.java`（L34）
- PekkoRpcActor：`flink-rpc/flink-rpc-akka/.../rpc/pekko/PekkoRpcActor.java`（L86，消息分发 L160，状态机 L532-673）
- PekkoInvocationHandler：`flink-rpc/flink-rpc-akka/.../rpc/pekko/PekkoInvocationHandler.java`（L71，invoke L125，invokeRpc L217）
- HeartbeatManagerImpl：`flink-runtime/.../heartbeat/HeartbeatManagerImpl.java`（L49）
- DefaultHeartbeatMonitor：`flink-runtime/.../heartbeat/DefaultHeartbeatMonitor.java`（L39，状态机 L186-191）
- HighAvailabilityServices：`flink-runtime/.../highavailability/HighAvailabilityServices.java`（L52）
- AbstractHaServices：`flink-runtime/.../highavailability/AbstractHaServices.java`（L56）
- ZooKeeperLeaderElectionHaServices：`flink-runtime/.../highavailability/zookeeper/ZooKeeperLeaderElectionHaServices.java`
- StandaloneHaServices：`flink-runtime/.../highavailability/nonha/standalone/StandaloneHaServices.java`
- TM 注册连接：`flink-runtime/.../taskexecutor/TaskExecutorToResourceManagerConnection.java`
- JobMaster 选举：`flink-runtime/.../dispatcher/JobMasterServiceLeadershipRunner.java`
