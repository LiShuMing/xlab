# LLM 可观测性实验平台

原生 Prometheus + Jaeger v2 + macOS host exporter，配套单次 SSE 诊断客户端与可选 vLLM ASGI middleware。
目标是把请求链路、推理指标与系统背景放在同一调查窗口中；host span 不冒充 GPU kernel 时间。

环境：Python 3.11+；开发与单测环境为 Apple Silicon macOS，平台验收状态见下方。
下载器同时提供 Darwin/Linux 的
arm64/amd64 固定版本资产，Linux 没有 Apple GPU 探针，其他平台尚未做运行验收。
不依赖同仓库的其他 lab，也不下载模型或第三方源码 checkout。

已验证固定 release 下载与 SHA256、Python/ASGI/生命周期单测、原生配置检查、
平台启动和合成 OTLP 查询，以及受支持模型的请求链路与固定 cache/KV 对照。
真实模型错误/取消和 collector 故障场景尚未验收，host timing 不表示 GPU kernel timing。

端口冲突时可使用 `--port-offset 1000`：Prometheus 为
`http://127.0.0.1:10090`，Jaeger 为 `http://127.0.0.1:17686`；其他端口相同偏移。

## 快速开始

```bash
cd labs/llm-observability
./scripts/bootstrap.sh       # 独立 .local/venv，不改已有模型环境
./scripts/download.sh        # 固定版本、SHA256 校验、只提取执行文件及许可
./scripts/check.sh           # 原生配置验证 + Git index/忽略规则检查
./scripts/start.sh           # 三个监控进程；只读取现有 :8000 的 /metrics
./scripts/status.sh
./scripts/smoke.sh           # 合成 trace + Prometheus 抓取验收；不调用模型
./scripts/stop.sh            # 仅关闭本 lab 启动且身份吻合的进程
```

`start`/`stop` 可重复执行。占用端口、配置错误、部分启动失败均返回非零；部分启动会回收
本次启动的子进程。不会使用 `pkill` 或按端口杀进程，不自动启动、重启或停止模型。
上述监控命令不管理模型。关闭保留数据库、日志与实验归档；Jaeger 内存中的 trace 会丢失，
重要 trace 由探针归档。模型的显式重启/关闭入口见下文。

```bash
./scripts/start.sh --model-url http://127.0.0.1:8100
# 或整套监控端口加偏移，适合避免冲突；同一 lab 同时管理一套实例。
./scripts/start.sh --port-offset 1000
```

| 入口 | 默认地址 |
| --- | --- |
| Prometheus UI / query | `http://127.0.0.1:9090` |
| Jaeger trace UI | `http://127.0.0.1:16686` |
| Host metrics / health | `http://127.0.0.1:9108/metrics`、`/healthz` |
| OTLP gRPC / HTTP | `127.0.0.1:4317`、`http://127.0.0.1:4318/v1/traces` |

所有监听绑定 loopback。服务与探针不需要 sudo；不会安装系统服务或登录自启动项。
代理不用于本地抓取；下载使用正常 HTTPS 网络配置，不依赖 GitHub API 配额。

### 完整启停顺序

首次使用先完成上面的环境、下载及配置检查，再按下文配置已有模型 Python 环境。
已有私有模型 profile 时，可以按以下顺序恢复和关闭整套服务：

```bash
# 先启动监控；每次都显式传入需要的模型地址和端口偏移。
./scripts/start.sh --model-url http://127.0.0.1:8000 --port-offset 1000
./scripts/restart-vllm.sh
./scripts/status.sh
./scripts/status-vllm.sh

# 完成验收后先关模型，在 Jaeger 仍运行时完成导出，再关三个监控进程。
./scripts/stop-vllm.sh
./scripts/stop.sh
```

这里的三个监控进程是 Prometheus、Jaeger 和 host exporter；`stop.sh` 会一起关闭。
前台 `serve-vllm.sh` 启动的模型由其终端 Ctrl-C 关闭，不属于后台模型 PID registry。
关闭命令可重复执行；状态命令在已停止、缺少 PID registry 或不健康时返回非零，
不会因此自动启动服务。关闭不删除下载、profile、数据库、日志或磁盘上的验收快照。

`stop.sh` 删除监控的运行 registry，后续 `start.sh` 需要重新指定 model URL/port offset；
模型 profile 则会保留。`restart-vllm.sh` 复用的是最后一次保存的模型参数，包括 KV、
prefix cache 和 async scheduling 选项，不会自动恢复实验前的配置；重启前应复核该 profile，
需要改参数时显式传入完整的 `MODEL ...` 参数列表。

## 文件与提交边界

```text
config/                    可提交的配置模板
src/llm_observe/            本实验自己的实现
scripts/                   下载、启动、关闭、状态与验收入口
tests/                     无模型单元测试
releases.json              固定版本和官方发布的 SHA256
.local/                    全部忽略：不进入正常 git add/commit
  venv/                    Python 环境
  downloads/               校验过的下载归档
  opt/                     执行文件、许可、安装收据
  run/                     PID 身份、实例参数、渲染后的配置
  logs/                    启动及配置校验日志
  data/prometheus/          TSDB / WAL
  artifacts/               原始 SSE、请求、响应、trace、验收记录
```

根目录和本目录均忽略 `.local/`，入口将新运行文件权限收紧为用户私有。只保存自有源码和公开
配置，不将第三方实现复制进源码树。实际命令行、机器路径、请求内容和模型指标中的本地标签
可能进入运行归档，所以它们一律留在 `.local/`，不要搬进 README、源码或提交说明。

`check.sh` 检查实际 Git index 中是否有该 lab 的下载/运行/未知类型文件，并验证典型产物
路径被忽略；不改变暂存区或 hooks。`.gitignore` 不能阻止 `git add -f`，因此提交前必须
运行检查并复核实际暂存内容。没有自动 commit/push，也没有修改已有 Git 身份或 hooks。
仅检查提交边界时运行 `./scripts/check-git.sh`，不需要下载监控二进制。
遇到执行问题时可运行 `./scripts/doctor.sh`，仅检查文件哈希和 macOS 评估，不修改系统设置。

## 接入模型 tracing

现有模型服务即使可抓 `/metrics`，如果未配置 OTel，也不会自动获得请求 trace。
监控启动命令不会隐式接管它。可在**已有 vLLM 0.33.0 环境**中前台启动：

```bash
VLLM_PYTHON="$HOME/path/to/vllm-venv/bin/python" \
  ./scripts/serve-vllm.sh MODEL \
  --max-model-len 4096 --max-num-batched-tokens 2048 \
  --gpu-memory-utilization 0.6
```

`VLLM_PYTHON` 必须指向已有模型运行环境；不向该环境安装依赖或复制模型源码。该环境需有
vLLM、模型插件及 vLLM tracing 所需的 OTel API/SDK、gRPC/HTTP exporters。启动器添加
本 lab 的 import 路径、OTLP endpoint、request ID header 与 ASGI middleware；在前台运行，
由所在终端的 Ctrl-C 关闭。它先检查模型端口，已有监听时直接退出，不打断旧服务。
它不固定模型、backend 或其他推理参数；重启时仍需记录实际 KV 容量与缓存状态。

### 后台重启与管理

首次配置可执行文件、工作目录和原有推理参数；如果已有非本模块管理的监听进程，必须用
`--adopt-pid` 指定已核实的 vLLM API PID。日志、启动配置、PID 身份和前后模型列表只写入
忽略的 `.local/`。示例中的 PID、MODEL 与路径需要替换：

```bash
./scripts/restart-vllm.sh \
  --python "$HOME/path/to/vllm-venv/bin/python" \
  --working-directory "$HOME/path/to/vllm-checkout" \
  -- MODEL \
  --max-model-len 4096 --max-num-batched-tokens 2048 --gpu-memory-utilization 0.6

# 此后复用已保存配置，并读取当前运行平台的 tracing endpoint：
./scripts/restart-vllm.sh
./scripts/status-vllm.sh
./scripts/stop-vllm.sh
```

如果该端口已有非本模块启动的 vLLM，需要在首次命令中另加 `--adopt-pid PID`；
PID 必须是已核实的 API 进程。已有模型环境缺少 OTel 依赖时预检失败，启动器不会替它安装。

重启先检查监控健康、模型环境版本与 OTel 依赖，再检查原服务 running/waiting 为 0。
模型繁忙、指标缺失或 PID 身份不符时不停止旧服务。通过预检后发送 TERM，等待旧进程与
已识别子进程退出，核对端口释放，再启动新服务。超时清理仅作用于已核实身份的进程；
不按名称批量杀进程。新服务启动失败时清理本次进程、保留日志并返回非零，不自动无 tracing
回退。`--timeout` 控制 readiness 等待，默认 180 秒。

默认使用已缓存模型（`HF_HUB_OFFLINE=1`），可显式使用 `--no-offline`；仅保存这个受控选项，
不快照整个环境。子进程设置 `PYTORCH_ENABLE_MPS_FALLBACK=0`，不修改父终端或原有模型环境。
推理参数保存在私有 profile 中；新版启动自动追加 loopback host/port、当前 OTLP endpoint、
request ID header 和 ASGI middleware。`stop.sh` 仍只关闭监控，`stop-vllm.sh` 显式关闭模型。

默认 `--instrument` 同时启用本模块的 Core/Scheduler/Metal host 埋点；
`restart-vllm.sh --no-instrument` 可关闭这些 adapter，保留基础 API/vLLM tracing。
启动预检记录目标模块的源码 SHA256 与函数签名，子进程导入时核对源码未变；
当前只验收 vLLM 0.33.0、Metal paged text 路径与 UniProcExecutor。
启动钩子通过子进程的 `PYTHONPATH` 加载，不改模型 checkout 或 site-packages。

Core 请求记录 enqueue/queued/scheduled/first output/finished/KV 引用释放；full 模式的每轮共享 batch
独立建 trace，并用 Links 关联请求。Metal/MLX 覆盖 graph build、异步提交、实际采样与
pending resolve；API 记录接收及共享输出处理。批次用实际 SchedulerOutput 关联，
deferred resolve 使用 pending 的批次，不能归到下一轮当前 batch。没有新增 `mx.eval`
或 GPU synchronize；这些 span 均为 host 边界，不是纯 GPU kernel 耗时。
详细埋点的 provider 使用独立系统随机源生成 ID，避免模型重设 Python seed 后重复 trace ID，
也不消耗模型的 Python PRNG 状态；验收同时核对 batch 的 run/进程实例，拒绝跨运行混入。

接入后，**显式**发送一条自然结束的诊断请求：

```bash
./scripts/probe.sh --model MODEL \
  --prompt '只用两句中文解释数据库索引，并给出一个适用场景。' --require-server-traces
```

探针只尝试一次，不重试生成；保存原始 SSE、事件接收时间、IDs、usage、结束原因与 trace，
输出校验摘要和私有归档路径，不打印完整答案。默认关闭 thinking、greedy、上限 256 tokens。
此探针不是吞吐基准。若服务没有 tracing/middleware，摘要会分别显示对应 span 缺失，不能
将 client-only trace 当作模型端到端通过。`--require-server-traces` 等待客户端、API、
`llm_request` 全部导出，并验证父子关系；只轮询 trace，不重发生成。探针不替代 checkpoint
parity 或语义质量评测。

API middleware 覆盖 headers 到最终 body send、SSE DONE、异常与取消，并将 server context
传给内置 `llm_request`；发送边界不等于客户端接收边界。默认不把完整 prompt/答案放进 spans。
ASGI 错误/取消由合成应用测试覆盖；真实模型成功链路已完成 B=1/B=4 验收。
真实模型错误/取消与 exporter 故障场景仍待验收。

### 链路验收与延迟调查

```bash
./scripts/restart-vllm.sh --instrument
./scripts/investigate.sh --model MODEL
```

调查入口要求重启后尚无成功请求，不会隐式重启或清空缓存。它只发 13 条生成请求：
重启后首请求、8 条暖缓存 B=1 交错 full/minimal 对照，以及 4 条并发请求。
每条只生成一次，轮询仅用于等待 trace 导出。完整生命周期、所有关联 batch、
共享 Links、MLX deferred 路径、跨进程时钟偏移、usage/IDs 与原始指标均留在私有归档。
首请求同时包含模型/驱动热身，不能解释为单独的缓存效应。

`probe.sh --minimal-trace ...` 用 `tracestate: llmobs=off` 跳过逐阶段 span，
基础 client/API/vLLM tracing 仍开启；它衡量详细埋点的增量，不是完全关闭所有监控。
开销对照仅比较输入 IDs、输出 IDs、cache/workload 指标相同的暖缓存请求。
冷/暖和不同 batch 形状可能出现不同 greedy 输出 IDs，分别记录，不作为开销对照，
也不能以此验收模型数值 parity。小样本结果不能证明零开销或当作吞吐基准。
本机验收已观测到详细 tracing 对短请求 E2E 的可见成本，尚未界定稳定开销上限；
性能基线应单独记录 minimal/adapter 关闭状态，不能混用两种模式的数据。
host 采样覆盖整个调查窗口，包含生成间的 trace 查询；系统 swap 不能归因给某条请求。

### Compact 与固定 KV 对照

未指定 `llmobs` tracestate 的请求及 `probe.sh` 默认使用 compact。该模式保留请求生命周期，
只追踪首输出发布前进入流水线的 batch；后续 decode 不再逐轮创建执行/API 输出 span。
batch 内的阶段先记录单调时钟与线程 CPU 数值，等请求终止后再作为 batch span 的事件导出。
共享 batch 仍用 Links 关联；不会复制执行耗时给每个请求，也没有增加 GPU 同步。

```bash
./scripts/probe.sh --model MODEL --prompt '诊断输入' --trace-mode compact --require-server-traces
./scripts/probe.sh --model MODEL --prompt '诊断输入' --trace-mode full --require-server-traces
./scripts/probe.sh --model MODEL --prompt '诊断输入' --trace-mode off --require-server-traces
```

`off` 与原 `--minimal-trace` 等价；基础 client/API/vLLM tracing 和 host 监控仍存在。
full 用于完整 decode/deferred 路径调查，compact 用于 prefill/TTFT 的较低开销观察。
当前对照不能证明 compact 零成本；完整模式与 compact 也不提供相同的逐 token 明细。
compact 额外分开原生 `mx.async_eval` 调用、线程 CPU、进程 fault/switch 增量、MLX active/peak
和 memory limit。进程 fault counters 包含其他线程，且不能代替 GPU 驻留/分页证据。

为隔离 prefix 命中与 KV 自动定容，先显式启动固定条件。下面的预算/block 数是小模型的
实验示例；其他模型需核实能容纳 max-model-len，启动和验收会检查实际容量：

```bash
./scripts/restart-vllm.sh --instrument -- MODEL \
  --max-model-len 4096 --max-num-batched-tokens 2048 --gpu-memory-utilization 0.6 \
  --kv-cache-memory-bytes 1073741824 --num-gpu-blocks-override 512 \
  --no-enable-prefix-caching --async-scheduling

./scripts/controlled.sh --model MODEL --label async-on \
  --rounds 12 --kv-blocks 512 --queue-depth 2
```

此入口不重启模型或清空缓存；要求 prefix cache 已关闭，先做 3 次相同形状的热身，再按
模式的不同排列交错比较。它验证逐请求指标窗口、实际 KV/队列深度、相同输入/输出 IDs、
原生 prefill 与事件边界、host 探针新鲜度，并保存原始数据。`--modes off compact` 可只比较
两种模式。用于流水线对照时，显式重启为相同参数加 `--no-async-scheduling`，然后传
`--queue-depth 1`；该选项同时改变队列和 decode pipeline gate，不能把整个 E2E 差额只归给队列。
恢复 async 后再复测，避免用一次跨重启比较推断因果。

macOS 的 controlled 脚本在运行期间使用 `caffeinate -is`，退出即释放，不改全局电源设置。
若请求 wall-clock span 与 monotonic E2E 差超过 50 ms，验收失败并保留归档，不自动重发。
系统 sleep/resume 会使两种时钟分离，不能把受影响请求解释为驱动或模型长尾。

## 观测范围与阶段状态

| 阶段 | 本版实现 | 验收方式 |
| --- | --- | --- |
| M1 平台底座 | 下载校验、原生配置校验、进程管理、host exporter、Prometheus、Jaeger | `check.sh`、`smoke.sh` |
| M2 客户端 / API | 单次 SSE 客户端、ASGI span、llm_request context、显式后台模型重启 | 单元测试与真实成功请求的三层 trace 验收；真实错误/取消待验收 |
| M3 Core / Metal | 外置 import adapter、request/batch Links、MLX host 阶段与 API 输出 join | B=1/B=4 成功链路及 deferred resolve 已验证 |
| M4 观测开销 | full/compact/off、固定 cache/KV 交错对照 | IDs、指标窗口和时钟校验；背景波动仍限制成本上限判断 |
| M5 根因分析 | native async_eval 的 wall/CPU/内存数据、栈采样、队列前瞻对照 | 报告留在私有归档；历史无 trace 时不反推确定根因 |

Prometheus 2 秒抓取；短请求可能完全落在两次 running/KV gauge 之间，累计直方图仍能在结算后
保存工作量。1 秒系统采样不能解释 6 ms 内的逐 token 活动。GPU 利用率是整机设备值；
swap counters 是系统累计值，进程 RSS 也不代表完整 Metal/共享内存成本。

进程指标中的 `vllm_engine_candidate` 只是通过进程名找到的候选；不要把它当作已完成请求关联。
探针失败时发布 success=0 和最近成功时间，失效用量被移除，不用 0 伪造空闲。scrape 不运行
子进程；host 采样由后台线程缓存。进程、系统 CPU、swap 存量和内存压力每 5 轮采集一次。
memory_pressure 的 free ratio 是系统压力口径，不等于物理空闲页比例。

Prometheus 保留目标为 48h / 512MB；磁盘保留目标不限制 RSS。Jaeger 最多缓存 1000 traces，
memory limiter/Go 内存目标也不是进程 RSS 的硬上限。监控可能改变系统分页，重启模型后也
可能改变自动 KV 定容；必须记录并控制，不能用监控开启后的速度直接对比旧基线。

## 开发与验证

先进行不启动服务、不调用模型的检查：

```bash
.local/venv/bin/python -m pytest -q
.local/venv/bin/ruff check src tests
.local/venv/bin/ruff format --check src tests
./scripts/check.sh
```

各入口的验收边界如下；运行命令本身不会替代尚未覆盖的场景：

| 命令 | 前置条件 | 通过说明 |
| --- | --- | --- |
| `check-git.sh` | Git 仓库 | 实际 index 无禁止产物，典型运行路径被忽略；不修改暂存区 |
| `check.sh` | 已下载监控二进制 | 原生配置可读、Git 排除有效；不启动监控或模型 |
| `smoke.sh` | 监控已启动 | 合成 OTLP trace 的父子/Links、监控 targets 与 host sample；不生成模型请求 |
| `probe.sh --require-server-traces` | 模型已接入 tracing | 单次自然结束、SSE/usage/IDs、client/API/llm_request 关联；不保证所有 Core/Metal 阶段齐全 |
| `investigate.sh --model MODEL` | 显式重启后尚无成功请求 | full 模式的 Core 生命周期、B=1/B=4 共享 batch 和 deferred 路径；首请求不混入暖对照 |
| `controlled.sh ...` | prefix cache 关闭、固定实际 KV/队列条件 | 热身后交错比较模式，核验 IDs、指标窗口、阶段边界、host 新鲜度和时钟差 |

`smoke.sh` 的 `vllm_metrics_connected` 独立报告模型 target；平台通过不等于模型接入通过。
真实请求验收失败会返回非零并保留 `.local/artifacts/`；只轮询导出，不自动重试生成。
Jaeger 使用有界内存，停止或淘汰后 UI 中可能没有旧 trace，应从每条请求的磁盘 JSON 复核。
验收摘要、原始指标、SSE 和栈采样均不属于提交内容。

测试聚焦 SSE 分帧、span 生命周期、错误/取消、并发 context、缺失指标与 PID 复用保护；
运行中组件的 native check、启动、合成 trace、抓取和关闭另行执行。当前没有修改上游模型代码。

## 排查结论与限制

- prefill 指标从 Core 首次调度到首个输出对象创建，TTFT 还包含 API 到客户端的不同边界。
  async 队列优先补充下一批次，因此首 batch 已采样后，首输出仍可能等待下一轮 host 提交。
  关闭 async 同时改变 decode pipeline，不能仅凭 TTFT 降低认定整体生成更快。
- native `mx.async_eval` 不只是收集 Python 输出：它处理计算图、编码 Metal 命令，并可能在
  活动任务或内存达到阈值时等待已有任务。调用名中的 async 不表示 host 调用必定立即返回。
  [MLX 0.32.4 对应实现](https://github.com/ml-explore/mlx/blob/v0.32.4/mlx/transforms.cpp#L260)
- compact 将逐轮 SDK 操作收敛到首输出窗口，降低 decode 路径上的观测工作量；对照没有
  建立稳定的零开销保证。full 用于完整路径调查，性能比较应显式记录模式与缓存/KV 条件。
- sleep/resume 会使 wall 和 monotonic 分离，必须隔离受影响的实验。进程 fault counters、
  MLX active memory 和整机 swap 也都不能单独证明模型或 GPU 分页。
- 历史缺少逐阶段 trace 的 prefill 长尾仍未唯一确定根因。尚未采集纯 GPU kernel 时间，
  也未完成真实模型错误/取消、collector 故障或全监控关闭对照。

这里保留机制结论和复核方法；具体 prompt/答案、请求/trace ID、机器路径、测量值和原始
报告只留在被忽略的 `.local/`，不把实验数据或第三方实现复制进仓库。

## 公开来源

- [Prometheus 3.7.3 release](https://github.com/prometheus/prometheus/releases/tag/v3.7.3)，
  [官方 SHA256](https://github.com/prometheus/prometheus/releases/download/v3.7.3/sha256sums.txt)。
- [Jaeger 2.23.0 release](https://github.com/jaegertracing/jaeger/releases/tag/v2.23.0)，
  [官方 SHA256](https://github.com/jaegertracing/jaeger/releases/download/v2.23.0/jaeger-2.23.0.sha256sum.txt)，
  [固定版本配置样例](https://github.com/jaegertracing/jaeger/blob/v2.23.0/cmd/jaeger/config.yaml)。
- 两个上游均为 Apache-2.0；下载器保留归档中随附的 LICENSE/NOTICE（如有），归档保存在私有目录。
- [OTel trace 模型](https://opentelemetry.io/docs/specs/otel/trace/api/)、
  [Prometheus 配置](https://prometheus.io/docs/prometheus/latest/configuration/configuration/)。
