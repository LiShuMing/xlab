# k8s-lab — 从零实现迷你 Kubernetes 控制面

一个纯 Go（零外部依赖）实现的迷你 Kubernetes 控制面，用于学习 k8s 的**操作原理与实现机制**：声明式 API、MVCC 存储、LIST+WATCH、Informer 缓存、workqueue 去重、水平触发（level-triggered）reconcile 闭环。

> 学习方式：**不用 client-go，自己把机器造出来**。每个包对应真实 k8s 的一个组件，注释里写明"真实世界是怎么做的、为什么这么做"。

## 快速开始

```bash
cd go/k8s-lab
go run ./cmd/demo        # 端到端演示：apply -> 自愈 -> 缩容 -> 扩容
go test -race ./...      # 全部测试（race detector）
go test -cover ./...     # 覆盖率（各包 86%~100%）
```

`cmd/demo` 输出（节选）：

```
>>> kubectl apply: ReplicaSet web (replicas=3, image=nginx:1.25)
ReplicaSet/web  desired=3  observed=3  ready=3
  Pod/web-0    phase=Running  node=node-1

>>> kill -9 on pod web-0 (simulating a node/container failure)
ReplicaSet/web  desired=3  observed=3  ready=3   # 自动重建为 web-3
  Pod/web-3    phase=Running  node=node-1
```

## 架构：与真实 k8s 的对应关系

```
你 (kubectl apply)                ┌──────────────────────────────┐
    │ Create("replicasets", rs)   │  internal/  (每包一个组件)      │
    ▼                             │                              │
apiserver.Server ── 校验/默认值 ──▶│  apiserver ≈ kube-apiserver    │
    │  唯一存储入口                │      校验、默认值、status 子资源 │
    ▼                             │                              │
store.Store ── MVCC + watch ─────▶│  store      ≈ etcd            │
    ▲                             │      全局 revision、乐观并发、  │
    │ LIST+WATCH                  │      事件日志、慢消费者保护      │
    │                             │                              │
informer.Informer ── 本地缓存 ────▶│  informer   ≈ client-go        │
    │  事件回调(只入队 key)         │      Reflector、LIST+WATCH、   │
    ▼                             │      cache、断线 relist       │
workqueue.Queue ── 去重/重排队 ───▶│  workqueue  ≈ client-go        │
    │                             │      dirty/processing 双集合   │
    ▼                             │                              │
controller.ReplicaSetController ─▶│  controller ≈ kube-controller- │
    │  reconcile: 期望 vs 实际     │      manager  期望值(expectations)、│
    ▼                             │      状态只在变化时写回         │
kubelet.Kubelet ── Pending→Running│  kubelet    ≈ kubelet          │
                                  │      认领 Pod、写 status       │
                                  └──────────────────────────────┘
```

数据流一句话：**声明期望状态 → informer 更新缓存 → workqueue 入队 key → reconcile 对比期望/实际 → 通过 apiserver 行动 → kubelet 运行 Pod → status 写回 → 循环**。

## 包导览（按学习顺序）

| 包 | 真实对应 | 核心教学点 |
|---|---|---|
| `internal/apis` | k8s.io/api | Spec(期望)/Status(实际)分离；DeepCopy 隔离；label selector |
| `internal/store` | etcd | MVCC 全局 revision；乐观并发（resourceVersion 冲突）；watch 事件扇出；断点续传（resume-from-revision）；慢消费者强制 relist |
| `internal/apiserver` | kube-apiserver | 唯一存储入口；默认值与校验；**status 子资源**（Spec/Status 写路径分离）；服务端拥有的不可变字段（UID/creationTimestamp） |
| `internal/informer` | client-go informers | Reflector 的 LIST+WATCH；本地缓存；断线 relist 保正确性；handler 只当"门铃" |
| `internal/workqueue` | client-go workqueue | 事件是边沿触发、reconcile 是水平触发；去重；同一 key 不会被两个 worker 同时处理 |
| `internal/controller` | kube-controller-manager | reconcile 循环；**expectations 防止缓存滞后导致过量创建**；status 只在变化时写（防自激 busy-loop）；自愈 |
| `internal/kubelet` | kubelet | 节点侧也是控制器；Pending→Running；status 由节点写、不由控制器写 |
| `cmd/demo` | — | 全链路组装 + 场景演示 |

## 这个 lab 里最有价值的三个 bug（真实踩坑记录）

初版 controller 是"教科书式"的 diff-then-act，跑 demo 立刻暴露两个经典错误——这正是真实 kube-controller-manager 里那些"看起来多余"的机制存在的原因：

1. **过量创建（over-provisioning）**：reconcile 创建了 3 个 Pod，但 Pod Add 事件还没到达 informer 缓存，此时任何原因触发再次 reconcile，看到的还是旧计数 → 再创建 3 个。demo 里表现为删 1 个 Pod 后 `observed=6`。
   → 真实 k8s 的解法是 **ControllerExpectations**：行动前记账"我发起了 N 个创建"，观察到 N 个 Add 之后才允许下一次 diff。本实现在 `controller.expectations`。

2. **status 自激循环（busy-loop）**：reconcile 无条件写 status → 写触发 Modified 事件 → 事件重新入队自己 → 再写……revision 从 15 飙到 48546。
   → 解法：**只在 status 实际变化时才写**。收敛后的 reconcile 是真正的 no-op（连 resourceVersion 都不动，有测试锁定）。

3. **watch 通道关闭竞态**（store 层）：广播协程和 pump 协程都可能 close 同一个 channel → send-on-closed-channel panic。
   → 解法：**pump goroutine 是 channel 的唯一关闭者**（defer close），所有取消路径只关 done 信号。`-race` 下 8 写者 × 400 并发事件验证。

## 设计取舍（诚实声明）

- **单进程内存存储**，无 Raft、无持久化——etcd 的复制/压缩只建模了客户端可见语义（revision、watch、resume、事件保留窗口）。
- **无 scheduler**：kubelet 直接认领未调度 Pod（scope 决定：核心闭环优先）。
- **无 Deployment**（RS 之上再加一层滚动更新的控制器是练习方向，见 TODOS）。
- 所有权用 label（`k8s-lab.owner`）表达，而非 ownerReferences + GC。
- 错误重试是简单 requeue + 50ms 退避，没有 rate limiter / 指数退避。

## 文档

- `docs/architecture.md` — 分层设计与关键决策记录（含并发模型）
- `AGENTS.md` — 给 coding agent 的项目约定
- `RULES.md` — 工程规范
- `TODOS.md` — 迭代路线（Deployment、scheduler、rate limiter、持久化…）
- `CHANGELOG.md` — 版本记录

## 环境

- Go 1.26+（`go.mod` 声明 1.26.2），**零外部依赖**，纯标准库。
- 无需 Docker / 真实集群：所有组件进程内运行，`go test -race` 即为验证手段。
