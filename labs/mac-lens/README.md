# mac-lens：macOS 推理性能观察台

Rust 编写的只读 TUI（Terminal User Interface），把整机资源、候选推理进程和可选的
vLLM 服务指标放在同一屏。目标是帮助提出、验证瓶颈假设，不生成“整机性能分数”。

**环境：macOS，Rust 1.94+，UTF-8 交互终端；Apple GPU 指标需要 Apple Silicon。**
推荐 140×42，最低完整面板 90×30；较小窗口自动切换紧凑视图。
不需要 sudo，不修改系统配置、不安装推理框架、不启动模型或压测请求。

## 启动

在本目录：

```sh
cargo run --release --locked

# 500ms 采样；窗口耗时和实际数据年龄显示在标题中
cargo run --release --locked -- --interval-ms 500

# 指定候选推理进程；不会读取进程命令行或环境变量
cargo run --release --locked -- --pid 12345
cargo run --release --locked -- --process vllm,python,mlx,ollama,llama

# 显式接入已经运行的本地 vLLM /metrics；没有此参数就不发送 HTTP 请求
cargo run --release --locked -- --metrics-url http://127.0.0.1:8000/metrics

# 非交互：输出两行 JSON，不写文件；第二次采样开始才有字节速率
cargo run --release --locked -- --snapshot --samples 2

# GPU 原生接口不适用或初始化失败时，可禁用 GPU 采集
cargo run --release --locked -- --no-gpu
```

首次构建需下载依赖；`Cargo.lock` 固定依赖解析结果，缓存齐全后可使用 `--offline`。
编译产物在 `target/`。本例独立构建，不依赖其它 lab 或语言目录。

| 按键 | 动作 |
| --- | --- |
| `q` / `Ctrl-C` | 退出，恢复终端 |
| `Space` | 暂停/恢复显示；采集继续，冻结画面有 PAUSED 和数据年龄 |
| `Tab`、`1` / `2` | 总览 / 详细指标来源和解释 |
| `f` | 全部保留进程 / 候选名称或指定 PID |
| `m` | 对保留的进程按 CPU / RSS 排序 |
| `j/k` 或上下箭头 | 滚动详细页 |

## 能看到什么，不能据此断言什么

| 区域 | 数据与来源 | 解释边界 |
| --- | --- | --- |
| CPU | sysinfo / Mach：整机与每逻辑核 busy%、load；macmon CPU 功耗估计 | 整机 100% 表示所有核繁忙；单进程 100% 表示一个核，可超过 100% |
| GPU | macmon / IOReport：活跃驻留比例、活跃频率、功耗估计、温度 | 是整机 GPU，包含桌面和其它应用；不是某个 PID 的利用率，更不是 FLOPs 利用率 |
| 内存 | sysinfo：used/available/swap；sysctl：normal/warning/critical；Mach VM64：压缩器物理占用、swap in/out 字节速率 | 统一内存由 CPU/GPU 共享，不提供独立 VRAM 总量；不能将 RSS 与 GPU 分配简单相加 |
| 磁盘 | sysinfo：挂载卷容量、剩余空间、IOKit 设备字节计数差分 | APFS 多卷可能共用同一物理计数，不求和；没有测量设备 busy%、队列深度或 I/O 延迟 |
| 网络 | sysinfo：每接口 RX/TX 字节速率、累计错误数，保留 lo0 | VPN/桥接/物理接口可能重复经过同一流量；吞吐低不能证明网络不是瓶颈 |
| 进程 | sysinfo：PID、名称、CPU、RSS、进程读写计数差分 | 名称命中只是候选，python 不一定在推理；不读参数、环境、提示词或请求内容 |
| 推理服务 | 可选本地 Prometheus：running/waiting、KV cache、prompt/generation tok/s、TTFT/TPOT/ITL 区间均值 | 没有服务指标就显示 N/A，不能从整机 GPU% 推导 token/s 或请求延迟 |

主面板显示有限行，详细页可查看完整挂载卷、网络接口和来源状态。
快照保留前 40 个 CPU 进程及名称/PID 候选，总计最多 160 个；`m` 仅对这些保留行排序，
不是“全系统 RSS Top”。接口和文件系统数据不跨层相加。

缺失/首次速率/计数重置显示 **N/A**，不伪装成空闲 0。GPU 无有效频率驻留窗口时不报告
活跃比例；macmon 对部分缺失功耗返回零，本例保守地把零功耗显示为 N/A。
SIP、驱动与私有接口变化都可能影响可见性；权限不足时不自动提权。
进程读写计数始终为零时，无法区分“从未发生 I/O”和“计数不可访问”，保守显示 N/A；
CPU/RSS 则按 sysinfo 的 best-effort 结果展示，受保护进程的可见性不保证完整。

macmon 使用 Apple 私有 IOReport/SMC 等接口，不属于 Apple 的稳定指标契约；初始化可能
回退调用只读 `system_profiler`。这部分没有本程序可控制的硬超时；放在采集线程中，
界面仍可退出。`--no-gpu` 可绕过该依赖的初始化与采样。

## 与 vLLM、Metal 后端一起用

系统/进程观察与框架无关，可观察已安装的 vLLM-Metal、MLX、Ollama、llama.cpp 等实际进程。
Apple Silicon 的 vLLM GPU 路径应按 [vLLM-Metal 的当前说明](https://github.com/vllm-project/vllm-metal)
确认；本工具不会安装它，也不假设 CUDA 进程在使用 Metal。

应用指标只实现 vLLM Prometheus 适配，不假设其它 OpenAI 兼容 API 一定暴露相同指标。
具体指标来源见 [vLLM metrics 文档](https://docs.vllm.ai/en/latest/design/metrics/)。

- KV cache 优先 `vllm:kv_cache_usage_perc`，兼容旧 `vllm:gpu_cache_usage_perc`；展示各 engine 最大比例，不相加。
- running/waiting 汇总标签序列；token counter 对每个序列分别做差分，避免某 worker 重置被其它 worker 增长掩盖。
- TTFT 使用 `time_to_first_token_seconds` 的 `_sum` / `_count` 差分。
- TPOT 优先新 `request_time_per_output_token_seconds`，兼容旧 `time_per_output_token_seconds`。
- ITL 单独使用 `inter_token_latency_seconds`，不混同每请求 TPOT。
- 以上延迟是本次窗口内观察到的直方图区间均值，不是 p95/p99；没有新完成样本时显示 N/A。
- 模型/engine 标签只用于内存中的 counter 身份，不显示或导出标签内容。

只接受 `http://`、字面回环 IP（如 `127.0.0.1` / `[::1]`），拒绝 DNS、认证信息、query、
fragment 和重定向；显式关闭环境代理。每次请求全局上限 800ms，响应最多 512 KiB。
服务错误、连接失败、超时或无兼容指标时清空差分基线，下一次成功采样重新预热。
这是本机观察工具，不是远程 GPU 监控或企业指标网关。

## 怎样判断下一步查什么

1. **先固定工作负载**：模型、量化方式、上下文、输出长度、batch、并发和预热条件。
2. **内存 pressure 升级并伴随持续 swap**：优先检查模型/上下文/KV cache 与其它应用竞争。
3. **CPU 平均高，或单核满而 GPU 不忙**：检查 tokenizer、串行供给、CPU fallback；只是一种假设。
4. **GPU 活跃高但生成慢**：只说明 GPU 在忙。计算、内存带宽、量化和 kernel 效率仍需
   Metal System Trace / Instruments 或可复现实验区分；本版不测 DRAM 带宽和每 kernel 时间。
5. **waiting/KV cache 与 TTFT 一起上升**：检查并发、上下文长度、cache 容量和驱逐；不要仅调大 batch。
6. **加载阶段读盘多**：将模型加载与稳定解码分开；设备吞吐不等于设备饱和。
7. **网络慢**：结合 lo0/实际接口、请求分布与服务耗时；没有链路速率和 RTT 就不能认定网络饱和。

阈值提示是单次采样的线索，不是 RCA，也没有测得“热降频”。温度、频率和功耗是观测量，
不能仅因温度高就断言降频。标题显示采样窗口耗时及快照年龄；窗口包含设定的原生等待间隔、
系统采集及可选 HTTP 耗时，不代表监控自身的 CPU 开销。旧数据不会无标识地当成实时数据。

## 实现与隐私

```text
sysinfo + Mach/sysctl + macmon + optional loopback /metrics
       -> collection thread -> one latest completed snapshot -> TUI / JSON Lines
```

- `model.rs`：带缺失状态的数值模型、真实单调时间差分、计数重置与启发式线索。
- `native.rs`：Apple GPU 与 Mach VM 小边界；检查结构有效前缀，兼容不同 OS/SDK revision。
- `collect.rs`：持久化 sysinfo/原生采样器、PID+启动时间身份、有限快照；不在绘制线程采样。
- `inference.rs`：受限回环 HTTP、白名单 Prometheus 解析、逐序列差分与时延均值。
- `ui.rs`：总览、120 样本历史、进程筛选排序、可滚动来源说明及小终端降级。
- `main.rs`：选项校验、终端恢复、暂停视图、只读 JSON 快照。

依赖通过 Cargo 使用，不复制第三方源码：Ratatui/Crossterm/sysinfo/macmon（MIT），
ureq（MIT OR Apache-2.0），mach2（BSD-2-Clause OR MIT OR Apache-2.0），libc、Serde/serde_json
按各自 Cargo 元数据的开源许可使用；解析版本见 `Cargo.lock`。
macmon 源码及库接口：[项目](https://github.com/vladkens/macmon)、[库文档](https://docs.rs/macmon/)。

默认不写日志、不导出数据、不读 LLM API 配置、不向外部上传。JSON 输出包含当前机器的
进程名称、PID、接口名和挂载路径，属于本地运行数据，不能提交到公开仓库。
若需要保存，在忽略的 `.local/` 中自行创建私有文件；本工具不自动创建目录或覆盖已有文件。

## 验证

```sh
cargo fmt -- --check
cargo test --locked
cargo clippy --locked --all-targets -- -D warnings
cargo build --release --locked

# 可选：真实伪终端交互验收（需要先构建 debug binary）
cargo build --locked
python3 tests/terminal_smoke.py
python3 tests/terminal_smoke.py --ctrl-c
```

测试覆盖 counter 初次采样/重置/接口消失、Prometheus 标签与无效数值、版本别名、端点边界、
CLI 失败路径、无 GPU 的真实机器快照、小终端与完整面板的渲染和有限历史。
真实硬件指标、TTY 退出恢复及伪服务 HTTP 行为另做运行验证；不把合成夹具当成模型性能证据。
没有自动运行模型、下载权重或执行负载基准，实际推理瓶颈需使用自己的固定工作负载继续验证。

本次验收环境：macOS 15.5 / Apple Silicon / Rust 1.94.1。Release 构建、17 项 Rust 测试、
Clippy、格式检查及仓库 3 项 lab 独立性检查通过；真实 GPU/内存原生指标及第二窗口的
磁盘、网络、swap 差分可用。PTY 验证总览、暂停、详细页、导航，以及 `q` / `Ctrl-C`
退出后的 echo/canonical 模式恢复。HTTP 行为使用本地伪服务验证，未连接真实 vLLM 模型服务。
