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
cd go/k8s-lab
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

## 目录

```
go/k8s-lab/
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
