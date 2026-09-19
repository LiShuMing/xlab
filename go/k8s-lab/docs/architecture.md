# Architecture — k8s-lab 迷你控制面

本文记录分层设计、关键决策与并发模型。读代码前先看这里；改并发相关代码前**必须**先读对应小节。

## 1. 总览：一次 `apply` 的完整旅程

以 `cmd/demo` 创建 3 副本 ReplicaSet 为例，跟踪状态如何流动：

```
1. 用户          api.Create("replicasets", rs)
                   │  校验 selector/replicas，默认 namespace/UID/TypeMeta
                   ▼
2. store         revision++ → rv=N，对象落库，事件写入保留日志
                   │  commit() 扇出给所有前缀匹配的 watcher
                   ▼
3. informer      Reflector 的 WATCH 收到 {MODIFIED, /replicasets/default/web, rv=N}
                   │  更新本地缓存（key = "default/web"）
                   │  依次回调 handlers
                   ▼
4. controller    handler 只做一件事：queue.Add("default/web")
                   │  workqueue 去重后交给 worker
                   ▼
5. worker        key := queue.Get()
                   │  reconcile(key):
                   │    a. 从 RS 缓存读期望：spec.replicas=3
                   │    b. expectations 检查：有未观察到的动作？→ 跳过本轮
                   │    c. 从 Pod 缓存扫实际：owned=0
                   │    d. diff：缺 3 → expectCreations(3) → 3×api.Create("pods",…)
                   │    e. status 变化了(0,0)→(0,0)? 否 → 不写
                   │  queue.Done(key)
                   ▼
6. kubelet       Pod Add 事件 → 入队 → syncPod: Pending→Running
                   │  通过 UpdateStatus 写回（status 子资源）
                   ▼
7. controller    Pod 事件 → creationObserved() 销账 + 重新入队 owner
                   │  reconcile: owned=3, ready=3 → status 变化 → 写一次
                   ▼
8. 收敛          期望=实际=3/3，之后所有 reconcile 都是 no-op
```

关键观察：**第 4 步 handlers 不传事件负载，只传 key**。事件是边沿（"变过了"），
reconcile 读的是水平（"现在是什么样"）。这一区分是整个 k8s 控制器模型的基石。

## 2. 分层与依赖方向

```
        cmd/demo ────────────────┐（组装层，可 import 一切）
            │                    │
   controller   kubelet          │
        │  └─────┴── informer ────┤
        │            │            │
        └──── apiserver ──────────┤
                 │                │
               store ─────────────┤
                 │                │
               apis ◀─────────────┘（被所有层引用的纯类型层）
   workqueue ◀── controller/kubelet（无内部依赖的独立工具）
```

规则（AGENTS.md 硬性约束）：
- 无反向依赖：controller/kubelet 不 import store；store 只认 apis。
- informer import apiserver 是为了 `ServerListWatch` 适配器；Reflector 本体
  只依赖 `ListWatch` 接口（测试用 fake 替换）。
- 状态修改唯一入口是 apiserver（校验/默认值/子资源语义在此收口）。

## 3. store：MVCC 与 watch 的并发模型

### 3.1 数据结构

```go
Store {
    mu       sync.RWMutex   // 保护下面一切
    revision uint64         // 全局单调，任何成功写 +1
    objects  map[string]entry
    events   []WatchEvent   // 有界保留日志（环形驱逐），支持 resume
    watchers map[uint64]*watcher
}
watcher {
    prefix, ch, done, closed,
    pending []WatchEvent,   // 两段式缓冲的"第一段"
    notify  chan struct{}   // size=1 的唤醒信号
}
```

### 3.2 为什么是"两段式缓冲 + pump goroutine"

朴素做法：commit 时直接 `w.ch <- ev`。问题：**ch 满时阻塞，而 commit 持有
store 写锁** → 一个慢消费者卡死整个存储。

朴素改进：commit 里非阻塞 send，失败就丢弃。问题：丢事件后 watcher 不知情，
缓存悄悄失真。

本实现：
1. `commit`（持锁）只把事件 append 到 `w.pending` 并置 notify 信号，**永不阻塞**；
2. 每个 watcher 一个 `pump` goroutine，把 pending 搬到 ch（可阻塞，但只阻塞
   自己）；搬运用完即释放锁，绝不在持锁时 send；
3. pending 超过 `maxPending`(1024) → 判定消费者已死，走关闭流程**强制其
   relist**——与 client-go "watch 缓冲溢出 → 410 Gone → relist" 同构。

### 3.3 关闭不变式（踩过竞态，勿破坏）

**`w.ch` 的唯一关闭者是 pump 的 `defer close(w.ch)`。**

所有取消路径（慢消费者驱逐 / stopWatcher / Store.Close）只做一件事：
`closeWatcher(w)` → 置 closed 标记 + close(w.done)（恰好一次，w.closed 防重）。
pump 在 select 中观察 done，退出时收口 ch。

为什么：如果 commit（持 store 锁）直接 close(ch)，而 pump 正在 `ch <- ev`，
就是 send-on-closed-channel panic。把"决定关闭"与"执行关闭"分离到不同
goroutine，靠 done 单向传递，是这类问题的标准解法。
`TestConcurrentWritesAndWatchers`（-race，8 writer × 400 事件）锁定此不变式。

### 3.4 resume-from-revision

`Watch(prefix, sinceRV)` 先从保留日志回放 `rv > sinceRV` 的事件（注册 watcher
**之前**灌入 pending，杜绝乱序），再接实时流。informer 的 LIST+WATCH 依赖此
语义做到"无缝、不重、不漏"。日志满时驱逐最老事件（compaction 类比）；回放
不到的旧 revision 意味着调用方必须 relist——informer 的行为正是如此。

### 3.5 深拷贝边界

Create/Update 存**入参的深拷贝**（防调用者事后改对象污染存储）；Get/List 出
**存储态的深拷贝**（防调用者改返回值污染存储）；commit 扇出前再拷一次，
每个 watcher 拿到独立快照。代价是每写 O(拷贝)，教学场景完全值得。

## 4. apiserver：为什么 status 是子资源

RS 上同时有两类写者：用户改 `spec.replicas`，控制器写 `status.*`。若共用
一个 PUT，控制器读-改-写会把用户刚改的 spec 回滚掉（反之亦然）。

本实现的 `UpdateStatus`：读当前存储态 → **只替换 Status 字段** → 条件写。
客户端副本里的 spec 改动被丢弃（`TestUpdateStatusOnlyTouchesStatus` 用
`Spec.Replicas=999` 的恶意副本验证）。这就是真实 k8s `/status` 子资源的
最小等价物。

同理，UID/creationTimestamp 在 Update 时以存储态为准——客户端伪造无效
（`TestUpdatePreservesServerOwnedIdentity`）。

## 5. informer：relist 是特性不是故障

`Run(ctx)` 就是一个死循环：`listAndWatch` → watch 断了（channel 关闭）→
再来一轮。正确性不依赖"每个事件恰好看到一次"，只依赖"缓存最终一致"。
两个细节：

- **cache 先更新，handler 后回调**（applyEvent 里 upsert → dispatch 的顺序）。
  这保证了 controller handler 入队 owner 时，触发该事件的 Pod 已在缓存里——
  下一次 reconcile 一定能看到它。顺序反了会制造窗口。
- **缓存 key 是 `namespace/name`**（keyOf，来自对象元数据），不是 store 的
  路径 key（`/pods/default/web-0`）。事件到达时用 `keyOf(ev.Object)` 归一化。
  混用两种 key 曾导致"LIST 种子和 WATCH 更新写进不同槽位"的 bug。

## 6. controller：expectations 与 status-on-change

### 6.1 缓存滞后 → 过量创建（真实 bug #2）

时间线：reconcile 创建 3 Pod（t0）→ Pod Add 事件到达缓存（t1）。t0~t1 之间
任何再入队（RS 心跳、别的 Pod 事件、甚至 status 写触发的 MODIFIED）都会让
reconcile 看到 owned=0 → 再创建 3 个。demo 实测删 1 个 Pod 后 observed=6。

解法（真实 k8s 的 ControllerExpectations 简化版）：

```
reconcile:
    if !exp.satisfied(key): return          # 有在途动作 → 本轮放弃
    diff → 缺 n 个 → exp.expectCreations(key, n) → 创建 n 个
pod handler:
    OnAdd    → exp.creationObserved(owner)  # 销账
    OnDelete → exp.deletionObserved(owner)
```

计数器下限为零（stray 事件不会把账目搞成负数而永久卡死）。
`TestReconcileSkipsWhileExpectationsPending` 用"故意不启动 pod informer"
制造缓存滞后窗口，验证 3 次额外 reconcile 一个 Pod 都不多建。

### 6.2 无条件写 status → 自激循环（真实 bug #3）

写 status → rv 变化 → RS MODIFIED 事件 → handler 入队自己 → reconcile →
又写 status……revision 实测飙到 48546，worker 永不空闲，还放大 6.1 的竞态。

解法：`rs.Status == 新计算值` 时直接 return。收敛后 reconcile 是**真 no-op**：
不写存储、rv 不动（`TestReconcileIdempotent` 锁定 rvBefore == rvAfter）。

### 6.3 Pod 命名序号

`podSeq[rsKey]` 只增不减：自愈重建的 Pod 拿新名字（web-3 顶替 web-0），
与真实 RS 的 generate-name 行为一致，也避免"删掉的名字立刻复用"造成的
事件歧义（watcher 分不清是复活还是新建）。

## 7. kubelet：节点侧也是控制器

kubelet 与 RS controller 结构同构（informer + workqueue + reconcile），
只是 reconcile 对象是单个 Pod、动作是"启动容器"（Pending→Running）。
它演示了三件事：

- **status 的属主是节点**：controller 创建 Pod 时故意不写 status，
  Running 只能由 kubelet 写——两类写者经 status 子资源互不踩踏。
- **调度被折叠**：`spec.nodeName` 为空即认领（demo 只有一个节点，
  scheduler 在 TODOS P3）。
- **conflict 即重试**：绑定 nodeName（spec 写）与写 Running（status 写）
  之间 rv 会变，syncPod 重读-重写，冲突走 requeue。

## 8. 测试策略

- **确定性优先**：时钟注入（apiserver.now）、可脚本化 fake（fakeListWatch
  控制每次 LIST 的快照与 WATCH 的生死）、直接驱动 reconcile（withoutWorkers）。
- **异步断言一律 waitFor 轮询**，sleep-then-assert 只用于"证明不发生"的
  反向断言（如 orphan 不被重建）。
- **-race 是门禁**：store 的并发测试（8 writers × 400 events + 顺序校验 +
  慢消费者驱逐 + 强杀 watcher）专为此设计。
- 已关闭 channel 会先吐缓冲事件再报关闭——断言 close 前先 drain
  （expectClosed 的语义）。

## 9. 与真实 k8s 的差距（诚实清单）

| 方面 | 真实 k8s | 本实现 |
|---|---|---|
| 存储 | etcd（Raft、持久化、mvcc 多版本读） | 单进程内存 map + 有界事件日志 |
| API 传输 | HTTP/JSON + protobuf、watch chunking | 进程内类型化调用 |
| 调度 | 独立 scheduler（filter/score/assume） | kubelet 直接认领 |
| 所有权 | ownerReferences + GC controller + finalizer | 单一 owner label，孤儿容忍 |
| 重试 | rate-limited queue（指数退避+桶） | requeue + 50ms 固定退避 |
| 校验 | OpenAPI schema + CEL + admission webhooks | 手写规则 |
| HA | 多副本 leader election | 单实例 |

这些差距是有意的：每一处都保留了**客户端/控制器可观察的语义**，砍掉了
分布式部署复杂度。学习控制面原理，语义才是本体。
