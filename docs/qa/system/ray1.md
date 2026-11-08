# 第 1 讲：资源总量够，为什么 GPU 任务仍然等待？

日期：2026-11-04（北京时间）。建议用时：60 分钟。

时间安排：场景与概念 5 分钟，源码精读 20 分钟，实验与分析 20 分钟，跨项目对照与设计取舍 10 分钟，自测复盘 5 分钟。

## 今日问题

两台机器各剩 1 张 GPU，一个进程请求 2 张 GPU，能不能运行？

如果这个进程要求同一台机器提供两张卡，就不能。集群剩余资源的总和没有描述资源分布，调度还要检查单个放置位置能否满足完整请求。

如果应用拆成两个各需 1 张卡的进程，调度问题就变了：还要考虑两个进程的协同启动与通信。这将连接到之后的成组调度与训练同步。

## 先分清三个问题

- **资源记账**：软件声明和占用多少额度。例如 Ray Actor 请求 `num_gpus=0.5`。
- **设备分配与隔离**：进程看见哪些设备，是否限制显存或计算份额。逻辑额度本身不能推出硬件隔离。
- **应用执行**：模型是否加载、CUDA 是否运行、吞吐是否达到目标。拿到额度不代表这些阶段已完成。

Actor 是可以常驻并保存状态的工作进程抽象；Task 是一次远程函数调用。Pod 是 Kubernetes 放置到节点上的工作负载单元；Worker 是执行应用任务的进程。这些对象不属于同一层。

当 Ray 部署在 Kubernetes 上时，可以同时存在 Pod 等待节点、Ray Actor 等待 Ray 资源、应用请求等待模型处理三种队列。单独看到“等待”二字不能定位原因。

## 源码阅读：约 20 分钟

以下路径与标识符在本次生成时已核验；对应 HEAD 见 [路线](README.md)。

### 1. Ray：计算应该申请多少节点

读 [ResourceDemandScheduler.schedule](/home/admin/xwork/ray/python/ray/autoscaler/v2/scheduler.py:1181)。

它接收 `SchedulingRequest`，结合当前实例、节点规格、节点数限制和资源请求计算 `SchedulingReply`。阅读顺序：

1. `_enforce_min_workers_per_type`、`_enforce_max_workers_per_type`、`_enforce_max_workers_global`：哪些上下限限制了候选容量。
2. `_sched_gang_resource_requests`：需要作为一组处理的资源请求。
3. `_sched_resource_requests`：普通请求如何匹配节点容量。
4. `to_launch`、`infeasible_resource_requests`：结果是什么。

再看 `SchedulingNode.try_schedule`：请求是否能放进某个候选节点。这里属于自动扩缩容的需求规划；返回 `to_launch` 只表示计算出的启动请求，之后还需要实例管理等组件推进到节点可用。

精读时画出 `SchedulingRequest → ScheduleContext → 约束处理 → 请求匹配 → SchedulingReply`，在每个箭头上标出传递的容量或请求。区分“规划中可满足”与“当前已能执行”：实验 06 的启动中实例可以减少新增节点规划，却没有证明该实例已能运行任务。

### 2. Kubernetes：给 Pod 选择节点

读 [Scheduler.ScheduleOne](/home/admin/xwork/kubernetes/pkg/scheduler/schedule_one.go:66) 与 [scheduleOnePod](/home/admin/xwork/kubernetes/pkg/scheduler/schedule_one.go:92)。后者进行调度流程，成功后异步进入绑定流程，将 Pod 与选中的节点关联。

再读 [Fit.Filter](/home/admin/xwork/kubernetes/pkg/scheduler/framework/plugins/noderesources/fit.go:657) 与 `fitsRequest`。找出 `Insufficient cpu`、`Insufficient memory` 与扩展资源不足的分支，观察“单节点可用量”如何参与判断。

这里阅读的是资源过滤的一部分。节点标签、污点、亲和性、设备分配等约束还可能影响结果，不能把所有 Pending 都归因为 GPU 总量不足。Kubernetes 的普通扩展资源请求通常采用整数；Ray 的 `0.5 GPU` 不能直接照搬成 Pod 的普通 GPU 请求语义。

### 3. 后续对照入口

今天只需知道这两条线的位置，无需全部读完：

- [Spark TaskSchedulerImpl.resourceOffers](/home/admin/xwork/spark/core/src/main/scala/org/apache/spark/scheduler/TaskSchedulerImpl.scala:488)：在已有执行进程提供的资源上安排任务；上面的 `DAGScheduler` 组织依赖阶段。
- [Daft RayRunner](/home/admin/xwork/Daft/daft/runners/ray_runner.py:538)：初始化或复用 Ray，生成分布式物理计划，交给 `FlotillaRunner.stream_plan`。再沿 `/home/admin/xwork/Daft/src/daft-distributed/src/scheduling/` 看 Daft 的任务调度。

Daft 的数据计划、Ray 的进程/资源、Kubernetes 的 Pod 放置需要分别追踪，不能用其中一层的资源指标解释所有等待。

## 小实验：先预测，再运行，约 20 分钟

本讲提供步骤，本次没有执行。使用已有虚拟环境和启动器；不要在共享环境运行全局 `ray stop`。

```bash
cd /home/admin/xwork/ray/raylab
./run.sh doctor
./run.sh run 02
./run.sh run 06
```

若环境检查失败，先记录缺失项，不自动重装。两个实验各自默认 180 秒超时；学习阅读时只需关注下面的预测。

**实验 02：逻辑 GPU 额度。** 阅读 [02_logical_gpu.py](/home/admin/xwork/ray/raylab/experiments/02_logical_gpu.py:7)。本地 Ray 声明 1 个逻辑 GPU，启动三个各请求 0.5 GPU 的 Actor。

- 预测：前两个可以取得同一逻辑设备的份额，第三个等待。
- 释放第一个 Actor 后，第三个应获得资源。
- 看 `result.json` 的 `third_waited`、设备 ID 与 PID；这些是资源调度证据，不能证明显存隔离或 CUDA 性能。
- 反证：第三个在额度未释放前完成，或释放后始终无法取得资源。应先核验实际资源声明和实验日志，而非修改断言。

**实验 06：扩容需求规划。** 阅读 [06_autoscaler.py](/home/admin/xwork/ray/raylab/experiments/06_autoscaler.py:11)。它直接调用源码算法，不申请云机器或 Pod。

| 输入 | 预测 |
| --- | --- |
| 三个各需 1 GPU 的请求；每种候选节点 1 GPU | 计划新增 3 个节点 |
| 一个请求；已有一个启动中的匹配实例 | 不重复新增节点 |
| 三个请求；节点总数上限为 2 | 新增 2 个节点，仍有请求无法满足 |
| 单个请求需 2 GPU；候选节点每台仅 1 GPU | 无法靠增加这种节点满足单个请求 |

结果文件写入本次启动器输出的独立 `results/<UTC时间>/` 目录。检查 `runner.json`、`result.json`、`cleanup.json`；文章中的预测与代码断言不能代替实际结果。

用剩余时间做一轮约束推演，无需修改现有实验：

| 场景 | 先写下预测，再解释理由 |
| --- | --- |
| 两个节点各有 4 CPU、1 GPU；一个请求需要 1 CPU、2 GPU | 即使集群 GPU 总量为 2，单节点也装不下 |
| 同样节点；改成两个各需 1 CPU、1 GPU 的独立请求 | 资源形状允许分别放置；不代表已经满足应用的协同启动和通信要求 |
| 单个请求仍需 2 GPU；增加一种 4 CPU、2 GPU 的候选节点 | 资源形状变得可满足；仍需检查节点数量等限制 |
| 保持每节点 1 GPU，只提高节点数量上限 | 不能解决单个 2 GPU 请求的放置问题 |

这些是基于给定条件的推演，不是新增场景已实测。记录表中每个结论依赖的前提，并把两次实际运行的观察单独写在旁边。

## 连到 AI 场景与设计取舍：约 10 分钟

面对“训练起不来”或“推理排队”，先画出等待位置，再选指标：

| 位置 | 首先要回答的问题 | 合适的证据 |
| --- | --- | --- |
| Kubernetes Pod | 是否有满足全部约束的节点？ | Pod 事件、资源请求、节点容量与调度失败原因 |
| Ray Actor / Task | 是否有符合资源和放置约束的 Ray 节点？ | 请求形状、Ray 资源状态、占用资源的 Actor |
| 节点启动链 | 新容量已经申请，还是已可运行？ | 实例状态转移、节点注册与就绪状态 |
| 模型服务内部 | 执行容量、批处理或内存预算是否限制接入？ | 服务队列、模型加载状态、批次、首 token 和后续执行时间 |

大模型使用多张卡还会引入卡间通信与拓扑约束。今天的逻辑资源实验没有验证这些因素，也没有测量训练或推理性能。

再考虑两个设计取舍：

- **单个大请求与多个小请求**：拆分可能更容易利用分散容量，但需要应用支持跨进程通信、同步与失败处理。不能只改资源声明，就把单进程模型变成分布式模型。
- **复用启动中容量与立即追加申请**：等待已有申请可能减少重复扩容，也可能延长排队；追加申请可能缩短等待，也可能浪费容量。设计时需要状态、超时和重试证据。试着列出“启动超过多久、依据什么信号，才应重新规划”的问题；本讲不假定固定阈值。

## 自测：约 5 分钟

1. 两台机器各有 1 GPU，什么情况下能满足“需要 2 GPU 的应用”，什么情况下不能？说明应用是否可拆成多个进程。
2. 一个空闲 Actor 没有正在执行方法，它占用的 GPU 额度是否已经归还？指出实验中真正触发归还的动作。
3. `to_launch=2` 可以证明什么？还缺哪些证据，才能说两个新 Worker 已可运行？

参考要点：单个放置请求与多个协同进程有不同约束；本例 Actor 生命周期内持续占用声明的资源，`ray.kill(..., no_restart=True)` 结束一个 Actor 后释放额度；启动规划还需要实际申请、启动、注册和可用性证据。

今日产出：一张请求到规划结果的调用图、一张资源约束推演表；如果运行了实验，再附实际观察与预测的差异。未执行的项保留为待验证。

下一讲：沿 Daft → Ray → Kubernetes 区分谁生成计算计划、谁安排任务、谁放置进程。
