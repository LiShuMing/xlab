# AGENTS.md — k8s-lab 项目约定

给 coding agent 的项目级指南。仓库根 `AGENTS.md` 仍然适用；本文件只写 k8s-lab 特有的规则，冲突时以本文件为准。

## 项目定位

纯 Go、零依赖的迷你 Kubernetes 控制面，**教学优先于功能**。每个包的注释承担"教材"职责：解释对应真实 k8s 组件的行为、为什么这样设计、我们简化了什么。

## 硬性规则

1. **零外部依赖**。`go.mod` 的 require 块必须为空。不许引入 client-go、logr、testify——用标准库实现等价机制本身就是教学目标。
2. **依赖方向固定**：`apis` ← `store` ← `apiserver` ← `informer`/`workqueue` ← `controller`/`kubelet` ← `cmd/demo`。禁止反向引用（例如 controller/kubelet 不得 import store）。
3. **写路径只有一条**：任何组件修改状态必须走 `apiserver.Server`；store 的 `Storage()` 逃生门只允许 informer 做 LIST/WATCH 只读访问。
4. **controller 不写 Pod status，kubelet 不写 Spec**。status 一律走 `UpdateStatus`（status 子资源语义）。
5. **reconcile 必须幂等且水平触发**：不信任事件内容，每次从缓存重读状态。新增动作前先过 `expectations` 检查。
6. **收敛即 no-op**：状态没有变化就不写存储（不许无条件 UpdateStatus），否则会自激 busy-loop——这是修过的真 bug，别改回去。
7. **watch channel 只能由 pump goroutine 关闭**（store 层不变式）；取消路径只 close done。改动 store 并发模型前先读 `store.go` 的 watcher/pump 注释。

## 验证命令（改完必跑）

```bash
cd labs/k8s-lab
gofmt -l .                  # 必须无输出
go vet ./...
go test -race -count=1 ./...   # 必须全绿；-race 是硬要求
go run ./cmd/demo              # 目测收敛：rv 应为两位数量级，observed==desired
```

覆盖率目标：每个包 ≥ 80%（现状 86%~100%）。新代码带测试。

## 代码风格

- gofmt；注释写"为什么"，尤其要写与真实 k8s 的对应关系和简化点。
- 错误：显式 error 返回，sentinel 错误 + `errors.Is`，不 panic。
- 并发：优先 mutex + 明确不变式；每个带锁结构体的注释要写清锁保护什么。
- 测试：并发/异步行为用 `waitFor(t, desc, cond)` 轮询模式，不要 sleep-then-assert；时间相关行为通过注入（如 `Server.now`）保持确定性。

## 常见陷阱（都踩过）

- 缓存 key 统一用 `namespace/name`（informer keyOf），store 路径 key 是 `/resource/ns/name`——两者不可混用。
- 标签值不能含 `/`（会与 key 解析冲突），OwnerLabel 用 `k8s-lab.owner`。
- 测试里直接调 `reconcile` 会绕过事件驱动时序，必须用 `withoutWorkers()` 并自己控制 informer 启动时机（参考 `TestReconcileSkipsWhileExpectationsPending`）。
- 已关闭的 channel 仍会吐出缓冲事件：断言 close 前要先 drain（store 测试的 `expectClosed`）。
- RS 的 resourceVersion 会被 controller 的 status 写推进——测试里 Update RS 前必须重新 Get。

## 补充工程规范

以下条款原先独立成 `RULES.md`，已并入本文件；与上面「硬性规则」同级，都是约束。

- **语言边界**：Go 1.26+，仅标准库；不使用 `unsafe`，不用 `panic` 做控制流（测试断言除外）。
- **锁内禁止阻塞**：持有 `sync.Mutex/RWMutex` 时不得阻塞在 channel send、网络或磁盘上；
  `store.pump` 的两段式 pending 队列是范本。channel 关闭权唯一化：谁创建谁关闭，或指定
  单一 closer；多个 goroutine 都可能触发关闭时用 done-channel 广播，由 closer 收口。
- **长驻 goroutine**：必须响应 `context.Context` 取消，且有测试覆盖退出路径（防泄漏）。
- **并发测试确定性**：注入时钟、可脚本化 fake ListWatch，禁止纯 sleep 断言；异步收敛统一用
  `waitFor(t, desc, cond)`（轮询 + 超时 Fatal，超时上限 3–5s）；表驱动优先。
  涉及 goroutine 生命周期的测试必须断言**退出**（cancel 后 Run 返回、channel 关闭），
  不允许只测 happy path。
- **resourceVersion 语义**：字符串形态、单调、任何写都推进；客户端必须用读到的 rv 做条件写，
  冲突（`ErrConflict`）时重读重试。
- **DeepCopy 边界**：store/apiserver/informer cache 交出的对象一律深拷贝，调用方可自由修改；
  新增 API 类型必须实现 `DeepCopyObject` 并覆盖指针与 map 字段。
- **服务端拥有字段**：UID、creationTimestamp、resourceVersion、TypeMeta 由服务端填写，
  客户端写入的值一律丢弃或拒绝。
- **reconcile 纪律**：输入只有 key（不传事件负载：事件会过期，状态不会）；失败即 requeue +
  短暂退避，禁止无界重试；handler 回调里只允许入队，禁止读写业务状态。
- **提交信息**：`feat(k8s-lab): …` / `fix(k8s-lab): …` / `docs(k8s-lab): …`。
- **文档**：每个包必须有 package doc（对应真实 k8s 的什么、教什么、简化了什么）；README 面向
  学习者（先跑 demo，再按包导览顺序读代码）；并发模型与踩坑修复写入 `docs/architecture.md`。

## 目录

```
labs/k8s-lab/
├── cmd/demo/            # 端到端演示（唯一 main）
├── internal/
│   ├── apis/            # 类型：Pod/ReplicaSet，Spec/Status 分离
│   ├── store/           # etcd-like MVCC + watch
│   ├── apiserver/       # 校验/默认值/status 子资源
│   ├── informer/        # Reflector：LIST+WATCH+cache+relist
│   ├── workqueue/       # 去重队列（dirty/processing）
│   ├── controller/      # ReplicaSet reconcile 循环 + expectations
│   └── kubelet/         # 节点模拟器：Pending→Running
└── docs/architecture.md # 架构决策记录
```

## 迭代路线（原 TODOS.md）

按教学价值排序，均未开始。

**P1 控制器叙事**

- [ ] Deployment 控制器：在 RS 之上加一层，教学滚动更新（maxSurge/maxUnavailable、
      revision 历史、rollback）——“控制器管理控制器”的最佳教材。
- [ ] rate-limited workqueue：指数退避 + bucket，替掉现在的 requeue + 50ms sleep；
      教学点：为什么重试必须限速（热循环打爆 apiserver）。
- [ ] GC（ownerReferences + 级联删除）：删 RS 时回收其 Pod，替掉现在的孤儿 Pod 容忍；
      教学点：finalizer 与级联语义。

**P2 存储更像 etcd**

- [ ] 事件保留窗口的显式 compaction：watch resume 早于窗口时返回 too old，迫使 informer
      relist（现在只是静默少回放）；教学点：k8s 410 Gone 与 informer 的关系。
- [ ] WAL + snapshot 持久化：重启后恢复 revision 与对象；教学点：崩溃恢复与日志截断。
- [ ] 多 revision 历史读（Get-at-revision）：教学 MVCC 读语义。

**P3 补全数据面**

- [ ] scheduler：独立调度控制器，按资源打分把未绑定 Pod 绑到多个模拟节点；
      教学点：filter/score、assume-Pod 与乐观绑定。
- [ ] 多节点 kubelet + 节点心跳：NodeReady 条件、失联后 Pod 驱逐；教学点：lease/心跳
      与 taint-based eviction。
- [ ] Pod 失败注入：按 image 名模拟 CrashLoopBackOff，观察控制器反应。

**P4 界面与可观测性**

- [ ] HTTP API + kubectl-lite CLI：把 apiserver 暴露成 REST（GET/POST/PUT/DELETE + watch
      chunking），教学 k8s API 的 HTTP 语义与 chunked watch。
- [ ] Event 对象：控制器动作发 Event，demo 输出 describe 风格视图；教学为何把“发生过什么”
      做成一等对象。
- [ ] metrics：reconcile 时延/队列深度/冲突率，对标 controller-runtime 指标体系。

**已评估、明确不做**：接入 client-go（违背“自己造机器”）、真实 etcd/gRPC（会转移学习焦点）、
`envtest`/`kind`（本机无 Docker、拿不到控制面二进制）。
