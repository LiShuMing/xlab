# RULES.md — k8s-lab 工程规范

## 构建与验证

```bash
cd go/k8s-lab

# 格式（提交前必须无输出）
gofmt -l .

# 静态检查
go vet ./...

# 测试：-race 是硬要求（本项目大量并发原语，race 是唯一可靠的守门员）
go test -race -count=1 ./...

# 覆盖率（每包 ≥ 80%）
go test -cover ./...

# 端到端冒烟
go run ./cmd/demo
```

## 语言与依赖

- Go 1.26+，**仅标准库**。`go.mod` require 块为空是项目不变式；引入任何外部模块都违背教学目标，需要先讨论。
- 不使用 `unsafe`、不使用 `panic` 做控制流（测试断言除外）。

## 并发规范

- 每个含 `sync.Mutex/RWMutex` 的类型，注释必须写明**锁保护的字段与不变式**（参考 `store.Store`、`watcher`）。
- channel 关闭权唯一化：谁创建谁关闭，或指定单一 closer（store 的 pump 模式）。多个 goroutine 都可能触发关闭时，用 done-channel 广播取消，由 closer 收口。
- 持有锁时禁止阻塞在 channel send / 网络 / 磁盘上（store.pump 的两段式 pending 队列是范本）。
- 新增长驻 goroutine 必须响应 `context.Context` 取消，并有测试覆盖退出路径（防泄漏）。
- 测试并发行为时提供确定性钩子（注入时钟、可脚本化的 fake ListWatch），禁止纯 sleep 断言。

## API/存储规范

- resourceVersion 语义：字符串形态、单调、任何写都推进；客户端必须用读到的 rv 做条件写，冲突（`ErrConflict`）时重读重试。
- DeepCopy 边界：store/apiserver/informer cache 交出的对象一律是深拷贝，调用方可自由修改。新增 API 类型必须实现 `DeepCopyObject` 并覆盖指针与 map 字段（参考 Pod/ReplicaSet 及其测试）。
- 服务端拥有字段：UID、creationTimestamp、resourceVersion、TypeMeta。客户端写入这些字段的值一律被丢弃或拒绝。
- Spec/Status 写路径分离：控制面组件只写 Status（`UpdateStatus`），用户只写 Spec（`Create`/`Update`）。

## 控制器规范

- reconcile 输入只有 key，不传事件负载（事件会过期，状态不会）。
- 幂等：同一 key 连续 reconcile N 次，世界状态与 rv 均不变（有测试锁定）。
- 任何创建/删除子对象前检查 expectations；发起动作前记账，观察到回调后销账。
- 失败即 requeue + 短暂退避；禁止在 reconcile 里做无界重试。
- handler 回调里只允许入队，禁止读写业务状态。

## 测试规范

- 表驱动优先；异步收敛用 `waitFor(t, desc, cond)`（轮询 + 超时 Fatal），超时上限 3–5s。
- 涉及 goroutine 生命周期的测试必须验证**退出**（context cancel 后 Run 返回、channel 关闭），不允许只测 happy path。
- 直接驱动 `reconcile` 的测试必须隔离 worker（`withoutWorkers()`）并显式控制 informer 启动顺序。

## Git 约定

- 提交信息：`feat(k8s-lab): …` / `fix(k8s-lab): …` / `docs(k8s-lab): …`。
- 二进制、测试缓存产物一律不入库（根 `.gitignore` 已覆盖常见模式）。

## 文档规范

- 每个包必须有 package doc：这个包对应真实 k8s 的什么、教什么、简化了什么。
- README 面向学习者：先跑 demo，再按包导览顺序读代码。
- 设计决策（尤其并发模型与踩坑修复）写入 `docs/architecture.md`，不散落在聊天记录里。
