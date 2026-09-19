# TODOS.md — k8s-lab 迭代路线

状态标记：`[ ]` 未开始 · `[~]` 进行中 · `[x]` 完成

## 已完成（核心闭环 MVP）

- [x] `apis`：Pod/ReplicaSet 类型，Spec/Status 分离，DeepCopy，label selector
- [x] `store`：MVCC 全局 revision、乐观并发、watch 扇出、resume-from-revision、
      事件保留窗口（etcd compaction 类比）、慢消费者强制 relist、pump 单关闭者模型
- [x] `apiserver`：校验/默认值/服务端字段保护/status 子资源/LIST/WATCH 门面
- [x] `informer`：Reflector（LIST+WATCH）、本地缓存、断线 relist、HasSynced、
      AddHandler（运行期注册）
- [x] `workqueue`：dirty/processing 去重队列，同 key 不并发处理，ShutDown 排空语义
- [x] `controller`：ReplicaSet reconcile 闭环 + expectations + status-on-change
- [x] `kubelet`：节点模拟（认领未调度 Pod、Pending→Running、startup delay）
- [x] `cmd/demo`：apply/自愈/缩容/扩容全场景演示
- [x] 测试：全包 ≥86% 覆盖，-race 全绿

## 下一步（按教学价值排序）

### P1 — 补全控制器叙事

- [ ] **Deployment 控制器**：在 RS 之上加一层，教学滚动更新
      （maxSurge/maxUnavailable、revision 历史、rollback）。
      这是"控制器管理控制器"的最佳教材。
- [ ] **rate-limited workqueue**：指数退避 + bucket，替换现在的
      requeue+50ms sleep。教学点：为什么重试必须限速（热循环打爆 apiserver）。
- [ ] **GC（ownerReferences + 级联删除）**：删 RS 时回收其 Pod，
      替换现在的"孤儿 Pod 容忍"。教学点：finalizer 与级联语义。

### P2 — 让存储更像 etcd

- [ ] **事件保留窗口的显式 compaction**：watch resume 早于窗口时返回
      "too old" 错误，迫使 informer 走 relist 路径（现在只是静默少回放）。
      教学点：k8s 410 Gone 与 informer 的关系。
- [ ] **WAL + snapshot 持久化**：重启后恢复 revision 与对象。
      教学点：崩溃恢复、日志截断。
- [ ] **多 revision 历史读**（Get-at-revision）：教学 MVCC 读语义。

### P3 — 补全数据面

- [ ] **scheduler**：独立的调度控制器，把未绑定 Pod 按资源打分绑定到多个
      模拟节点。教学点：调度框架的 filter/score、assume-Pod 与乐观绑定。
- [ ] **多节点 kubelet + 节点心跳**：NodeReady 条件、节点失联后 Pod 驱逐。
      教学点：lease/心跳与 taint-based eviction。
- [ ] **Pod 失败注入**：按 image 名模拟 CrashLoopBackOff，观察控制器反应。

### P4 — 界面与可观测性

- [ ] **HTTP API + kubectl-lite CLI**：把 apiserver 暴露成 REST
      （GET/POST/PUT/DELETE + watch chunking），写一个最小 CLI。
      教学点：k8s API 的 HTTP 语义、watch 的 chunked 响应。
- [ ] **事件（Event 对象）**：控制器动作发 Event，demo 里 kubectl describe
      风格输出。教学点：为什么 k8s 把"发生过什么"做成一等对象。
- [ ] **metrics**：reconcile 时延/队列深度/冲突率，教学 controller-runtime
      的指标体系。

## 已评估、明确不做

- ~~接入 client-go~~：违背"自己造机器"的教学目标。
- ~~真实 etcd/gRPC~~：单进程内存实现足以覆盖客户端可见语义；引入进程间
  通信会把学习焦点从控制面原理移走。
- ~~envtest/kind~~：环境无 Docker、无法获取控制面二进制（已验证）。
