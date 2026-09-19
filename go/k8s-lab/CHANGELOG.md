# Changelog — k8s-lab

All notable changes to this project are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versions follow the repo's
`go/k8s-lab` subtree (not independently tagged yet).

## [Unreleased]

### Added — 核心闭环 MVP

从零实现的迷你 Kubernetes 控制面，纯 Go、零外部依赖。分层对应真实组件：

- **`internal/apis`**：Pod / ReplicaSet 类型定义，Spec(期望)/Status(实际)分离，
  `DeepCopyObject`，`LabelSelector`。覆盖率 94.6%。
- **`internal/store`**：etcd-like MVCC 存储。全局单调 revision、乐观并发
  （`ErrConflict`）、watch 事件扇出、resume-from-revision 回放、有界事件日志
  （compaction 类比）、慢消费者强制关闭。覆盖率 90.9%。
- **`internal/apiserver`**：类型化门面。默认值、校验、服务端字段保护
  （UID/creationTimestamp 不可被客户端覆盖）、status 子资源写路径、LIST/WATCH。
  覆盖率 91.3%。
- **`internal/informer`**：Reflector（LIST+WATCH）、线程安全本地缓存、断线 relist、
  `HasSynced`/`WaitForSync`、运行期 `AddHandler`。覆盖率 93.8%。
- **`internal/workqueue`**：去重工作队列（dirty/processing 双集合），同一 key
  绝不被两个 worker 并发处理，ShutDown 排空语义。覆盖率 100%。
- **`internal/controller`**：ReplicaSet reconcile 闭环，含 expectations 与
  status-on-change 写入。覆盖率 86.2%。
- **`internal/kubelet`**：节点模拟器，认领未调度 Pod，Pending→Running，
  可注入启动延迟。覆盖率 82.4%。
- **`cmd/demo`**：apply → 自愈 → 缩容 → 扩容 全场景端到端演示。

### Fixed — 实现过程中修复的三个经典并发/控制器 bug

1. **watch channel 关闭竞态（store）**：广播路径与 pump 都可能 close 同一
   channel，导致 send-on-closed panic。重构为 **pump goroutine 是唯一关闭者**
   （`defer close`），所有取消路径只 close done。`-race` 下 8 写者并发验证。
2. **过量创建 over-provisioning（controller）**：缓存滞后时再次 reconcile 会
   重复创建 Pod（demo 表现为删 1 个 Pod 后 observed=6）。引入 **expectations**
   记账机制：行动前登记，观察到对应 Add/Delete 后才允许下一次 diff。
3. **status 自激 busy-loop（controller）**：无条件写 status → 触发 Modified →
   重新入队自己 → 无限循环，revision 飙到 4 万+。改为 **仅在 status 变化时写**，
   收敛后 reconcile 成为真正的 no-op（rv 不变，有测试锁定）。

### 验证

- `gofmt -l .` 无输出；`go vet ./...` 通过。
- `go test -race -count=1 ./...` 连续 3 次全绿，无 flakiness。
- 各包覆盖率 82%~100%，均 ≥ 80% 目标。
