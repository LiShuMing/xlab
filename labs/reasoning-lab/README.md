# Reasoning Lab

面向 Apple Silicon / 24GB 统一内存的独立推理学习实验室。
Python 3.11+，PyTorch MPS（CPU 也可运行），无需 CUDA 或外部奖励 API。

本项目独立安装、独立运行，不读取其他 checkout，也不依赖同仓库的其他 lab。
目标是理解并反复验证「数据 → Base → LoRA SFT → GRPO → 评测 → 下一轮假设」，
同时测量内存、token 和墙钟成本。程序奖励无需 API key。

## 开始运行

在本目录执行以下命令。`lab.sh` 会切到自身目录，其他位置也可通过脚本路径运行。

```bash
bash lab.sh setup
bash lab.sh doctor
bash lab.sh test
bash lab.sh smoke --device cpu
bash lab.sh smoke --device mps
```

`setup` 使用 Python 3.11 与 `uv.lock` 建立项目 `.venv`，不修改全局环境。
`doctor` 实测 FP32/BF16 的 matmul、RMS、SDPA、cross entropy、反向传播与 AdamW。
`smoke` 不联网，用随机初始化的两层小模型完成数值检查、SFT、GRPO、保存和评测。
随机模型不应解对题；GRPO 全零奖励与零任务梯度是预期现象，不能当作能力结论。

正式模型与数据：

```bash
bash lab.sh fetch
bash lab.sh data
bash lab.sh parity --device mps
bash lab.sh run --config configs/base.yaml --split dev-quick --samples 1
```

完整真实模型接线验收可重复执行：

```bash
uv run --locked python scripts/validate_real.py
```

它在独立小数据快照上依次检查 Base、SFT 三更新、完整恢复到第四更新、GRPO 两更新、
两组配对比较和报告。每个模型实验最多 300 秒，子进程分时加载，日志保留在
`.local/acceptance/`。这是运行验收，不是正式训练成绩，也不会访问正式 test/OOD。

`fetch` 先把远端 revision 解析为不可变 commit，再下载官方原始权重与同源 tokenizer，
将 revision 写入模型目录的 `source.json`。已有本地模型可用 `--model PATH`。
不要传入 MLX 4-bit 目录；权重加载器会拒绝量化配置、缺失基础权重和异常张量键。
`parity` 先在独立进程生成 HF CPU FP32 参考，进程退出后再加载手写模型，
验证 FP32 logits、cached/full、左 padding 与 eager/SDPA，失败时返回非零退出码。

`data` 创建不可覆盖的数据快照：train=1000、dev=200、test=400、OOD=200；
`dev-quick` 是 dev 的固定前 50 题。首次主要题型为三数字加减乘，混入少量两数字题。
重复执行请显式指定新目录，不会覆盖或悄悄重切测试集。

## SFT 与 GRPO

先用几个真实模型更新核对成本，再执行正式预算：

```bash
bash lab.sh run --config configs/sft.yaml --steps 3 --max-seconds 300
bash lab.sh run --config configs/sft.yaml
```

默认 FP32，序列上限 256、回答上限 64、microbatch=1、rank=alpha=16。
SFT 只监督回答及 EOS；梯度累积按有效回答 token 总数归一化，并裁剪梯度。
确认本机 BF16 模型检查通过后可添加 `--dtype bfloat16`：基础权重 BF16、adapter FP32。
改精度属于新的实验协议，应新建 run。

每次命令打印 `Run:` 绝对路径。将选定 SFT run 的路径赋给 `SFT_RUN`，再继续：

```bash
bash lab.sh run --config configs/base.yaml --adapter "$SFT_RUN/checkpoints/best.pt"
bash lab.sh run --config configs/grpo.yaml --adapter "$SFT_RUN/checkpoints/best.pt"
```

GRPO 使用同一 PyTorch 模型完成 rollout 和评分：temperature=0.7，无 top-k/top-p 截断，
每题串行采样 4 个候选，程序奖励为 0/1。每组只更新一次，逐回答长度归一化。
旧策略概率由更新前 full forward 重算，记录 cached/full logprob 差异；
参考策略固定为本轮实际起始 adapter，恢复训练时继续使用原始参考。
同分组任务优势为零；如果几乎所有组都同分，应改课程或补 SFT，再考虑加步数。

本机 BF16/MPS 实测存在 no_grad 与可求导 forward 的数值差异。
旧策略/参考评分因此使用与当前策略相同的 grad-enabled 路径后立即 detach。
rollout 与评分的最大 logprob 差超过 `max_logprob_gap=0.05` 时拒绝更新，
更新前 current/old logprob 差超过 1e-4 也拒绝。首轮 GRPO 保持默认 FP32；
BF16 SFT 可用不等于 BF16 GRPO 已通过分布一致性检查。

每轮最多保留 best/latest/final 三个训练状态，不复制基础模型。
checkpoint 保存 adapter、AdamW、step、数据游标、Python/NumPy/CPU/MPS RNG、
原始参考 adapter、已消耗时间，以及模型/数据/训练协议/代码/依赖身份。
超参数消融用 `--adapter` 从同一权重分叉；原实验中断则用完整恢复：

```bash
bash lab.sh run --config configs/sft.yaml --resume "$SFT_RUN/checkpoints/latest.pt" --steps 300
```

`steps` 是恢复后的总更新上限，`max-seconds` 是包含已消耗时间的累计预算。
改变模型、数据、源码、依赖、设备或训练协议会拒绝完整 resume；需要时明确使用 warm start。
只在完整 optimizer step 边界保存。CPU 测试覆盖连续训练与恢复后的 adapter 精确一致；
MPS 不承诺跨版本或逐 bit 确定性。
恢复时保留 `latest/final` 所在目录的 sibling `best.pt`，它是已选候选的外部依赖；
新 run 会验证并继承该候选。只有单个移出的 checkpoint 时请明确使用 warm start。

训练中每隔指定步数评测固定 dev-quick 单候选，按其成功率保存 best。
结束时在剩余预算内对 best 进行 dev-full 四候选评测；没有足够预算时报告缺失或 incomplete，
不把不完整结果当作完整候选证据。最终权重始终另存为 final，best 的加载不会覆盖它。

## 评测与实验决定

```bash
bash lab.sh run --config configs/base.yaml --split dev
bash lab.sh run --config configs/base.yaml --split dev --adapter "$SFT_RUN/checkpoints/best.pt"
bash lab.sh compare "$BASE_RUN/eval/dev" "$CANDIDATE_RUN/eval/dev"
bash lab.sh report "$CANDIDATE_RUN"
```

`BASE_RUN`、`CANDIDATE_RUN` 同样来自对应命令打印的路径。
比较要求题集、种子、候选数、温度、长度预算完全一致。以题目为聚类单位做 2000 次
paired bootstrap；每题四候选不会被误当成四道独立题。报告单次成功率差值与 95% 区间，
四次至少一解率、输出长度、截断、失败原因和采样成本。

初始接受规则为提升至少 3 个百分点且区间下界大于零；这是开发阶段选模规则，
不能替代多训练 seed 的复核。决策仍需写入 run 的 `decision.md`。
训练入口禁止用 test/OOD 选 checkpoint；测试审计应在方案冻结后单独运行：

```bash
bash lab.sh run --config configs/base.yaml --split test --adapter "$SFT_RUN/checkpoints/best.pt"
bash lab.sh run --config configs/base.yaml --split ood --adapter "$SFT_RUN/checkpoints/best.pt"
```

不要根据 test/OOD 的具体失败题补训练数据。若反复查看它们并改变方案，需要新版本审计集。

## 推理效率与观测

```bash
bash lab.sh run --config configs/bench.yaml
bash lab.sh report "$BENCH_RUN"
```

固定同一 prompt 和输出 token 数，分别测 eager 全量重算、eager KV cache、SDPA KV cache，
各预热后重复三次。该实验忽略 EOS，属于固定计算量基准，不用于质量评分。
记录整段输出吞吐、引擎内 TTFT/ITL、同步阶段墙钟耗时；这些不是客户端延迟或纯 GPU 时间。
当前 KV 是 concat，后续可在这个稳定基线上增加预分配实验。

每个 run 写入：

```text
config.json / manifest.json / environment.json / load.json
metrics.jsonl / system.jsonl / trace.json / run.log
responses.jsonl / eval/*/responses.jsonl / eval/*/summary.json
checkpoints/{best,latest,final}.pt
summary.json / status.json / decision.md
index.html                         # report 命令生成，离线可打开
```

`trace.json` 是可导入 Chrome Trace 兼容查看器的阶段时间线。
每秒及阶段边界采样 RSS、MPS current/driver、全机 swap/pageout 增量。
采样高水位可能漏瞬时峰值；RSS 与 MPS 指标重叠，不能相加。
MPS driver 初始软阈值 10GiB，同时受 recommended memory 的 90% 限制；
完成当前更新后保存并停止。换页且步骤耗时显著上升时同样停止，OOM 以失败记录并退出进程。
时间预算在完整请求/更新边界检查，可能超出一个操作；没有后台无限重试。
正式实验不要启用自动 CPU fallback；诊断时启用则环境报告会标记。

### 日志与 trace

两个通道互不混用：stdout 是数据（每步一条 metrics JSON，命令结束一条结果对象），
stderr 是给人读的进度日志，级别由 `REASONING_LAB_LOG_LEVEL` 控制（默认 `INFO`）。

```bash
REASONING_LAB_LOG_LEVEL=DEBUG bash lab.sh run --config configs/countdown-sft.yaml
```

- `INFO`：run 身份与 provenance、数据编码过滤、debug/进度、`dev quick` 与 best 更新、
  停止原因及其触发数值、`full dev` 结论、evaluation 约十段进度（少于 10 题不打点）。
- `DEBUG`：每一步的 `loss / grad_norm / 耗时` 与 checkpoint 写入。
- 同一批记录另写入该 run 的 `run.log`，run 结束后单独看这一个文件即可还原全过程。

`trace.json` 的 span 带 `args.step`（GRPO 的 rollout/verification/old_reference/
policy_forward_backward/optimizer 以及 SFT 的 forward-backward），因此可以在时间线里
按步过滤；关键决策另以 instant 事件（`ph: "i"`）标记：`resume_loaded`、`dev_quick`、
`stop`、`full_dev`。span 的 `ts` 与 `system.jsonl` 的 `seconds` 共用同一时钟基准。

日志不进入 `Run.protocol`，也不写入 `config.json`：调日志级别不会改变 protocol 哈希，
因此不影响 `--resume` 与 `compare` 的可比性。

## 新课程与任务

```bash
# 新课程快照；正式比较也需要明确的新开发/审计协议。
bash lab.sh data --difficulty L3 --output .local/data/countdown-l3
# 小规模验证两个示例任务。
bash lab.sh data --task maze --train 40 --dev 10 --test 10 --ood 10 --output .local/data/maze-v1
bash lab.sh data --task sql --train 40 --dev 10 --test 10 --ood 10 --output .local/data/sql-v1
bash lab.sh run --config configs/base.yaml --task maze --data .local/data/maze-v1
```

最后一行的 `--task` 可通过配置设置；CLI 同样支持该参数。
L1=两数字加减，L2=三数字加减乘，L3=四数字四则，L4=必须使用分数中间值。
凑数验证器限制表达式长度/AST 节点/整数与分数规模，不使用 eval。
迷宫为单轮 UDLR 动作输出，由 BFS 提供解；尚无多轮 episode 状态。
SQL 为 SQLite 单表聚合过滤，包含 NULL/重复值，对四个独立数据实例比较结果多重集合，
限制只读授权、函数和 VM 步数；不是任意用户数据库的 SQL 执行服务。

## 学习顺序与来源

阅读 [WALKTHROUGH.md](docs/WALKTHROUGH.md)（从一道题到一次可比较 SFT 的完整走查）、
[DESIGN.md](docs/DESIGN.md)、[LEARNING.md](docs/LEARNING.md) 和
[VALIDATION.md](docs/VALIDATION.md)。已验证结果与后续研究项分开记录。

本项目参考公开 MIT 项目中的手写 Qwen3/LoRA/GRPO 和阶段观测思想。
未引入跨 checkout 导入、外部 LLM judge、CUDA kernel 或 mini-vllm 调度依赖。
来源与许可见 [NOTICE.md](NOTICE.md) 及 `licenses/`。
