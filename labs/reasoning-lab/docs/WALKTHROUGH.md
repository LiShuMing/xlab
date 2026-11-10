# 从一道凑数题到一次可比较的 SFT

这份文档只走一条路：把一道题变成可判定对象，立 baseline，挂 LoRA，跑 SFT，
再用配对比较判断"是不是真的变好了"。每一步写清楚三件事：输入是什么、
产物落在哪个文件、什么现象算失败。

文中数字来自本机 MPS FP32 实际运行（`.local/` 被 git 忽略，正式引用以各 run 目录的
`summary.json` 为准）。任务选择凑数游戏，因为它的难点可以切成两部分：先"会不会按格式作答"，
再"算术搜不搜得出来"，这两件事必须分开度量。

## 0. 一页总览

| 阶段 | 命令 | 权重变化 | 主要产物 | 判定依据 |
| --- | --- | --- | --- | --- |
| 任务与数据 | `bash lab.sh data` | 无 | `train/dev/test/ood.jsonl`、`manifest.json` | solver 与 verifier 互拍 |
| 数值验收 | `bash lab.sh parity` | 无 | `parity/summary.json` | 与 HF 参考的 logits 差 |
| baseline | `bash lab.sh run --config configs/base.yaml` | 无 | `eval/dev/summary.json` | pass@1、pass@4、失败分类（定义见第 1 节） |
| LoRA 挂载 | 由 `rank`/`alpha` 决定 | 新增 392 个张量，B 全零 | 无 | 初始 forward 与 base 相等 |
| SFT | `bash lab.sh run --config configs/countdown-sft.yaml` | 只改 adapter | `checkpoints/{best,latest,final}.pt` | dev-quick 选模、loss、grad_norm |
| SFT 后评测 | 同一 base 配置加 `--adapter` | 无 | 新 run 的 `eval/dev/` | 与 baseline 同 protocol |
| 比较 | `bash lab.sh compare A B` | 无 | `comparison.json` | 配对 bootstrap 与 3pp 规则 |

一个 run 目录里各文件的用途互不重叠：`metrics.jsonl` 存每步训练记录，
`eval/step-*` 只是选模用的中间检查（不可用于比较），`eval/dev-full` 才是候选证据，
`checkpoints/best.pt` 是权重视图，`decision.md` 是人的结论。

## 1. 先认识三个任务、四个难度和几个名词

### 三个任务

三个任务共用同一套结构：“题目 + prompt 模板 + 程序验证器”，但考核的能力完全不同：

| 任务 | 题目形态 | prompt 要什么 | 验证方式 |
| --- | --- | --- | --- |
| countdown（凑数） | 给 2 到 4 个数字和一个目标值 | 只用这些数字和允许的运算符，输出一个等于目标值的表达式 | 解析成 AST、精确求值、检查数字用量与结果 |
| maze（迷宫） | 4×4 网格，`S` 起点、`G` 终点、`#` 是墙 | 只输出一串 `U/D/L/R` | 逐格模拟移动，检查越界、撞墙、是否停在终点 |
| sql | 表 `items(id, category, value)` 与一句自然语言条件 | 只输出一条 `SELECT` | 在 4 个独立内存库上执行，与参考 SQL 的结果多重集比较 |

- **countdown** 是主任务。难点可以切成两段：先“会不会只输出表达式”，再“算术搜不搜得出来”。
  同一道题往往有多个正确解，solver 给出其中一个，verifier 接受任意合法解。
- **maze** 是单轮动作序列，参考解由 BFS 给出。verifier 只判断“是否到达终点”，
  不判断路径是否最短，所以绕路也算对；它没有多轮 episode 状态。
- **sql** 是单表单聚合过滤，覆盖 `COUNT/SUM/MAX/MIN/AVG`、三类 category、六种比较符。
  验证在沙箱里做，四重限制：只读授权白名单（只允许 `SELECT`/`READ`/`FUNCTION`）、
  函数白名单、每 1000 条 VM 指令回调一次且累计超过 100 次即中止、结果最多 1000 行。
  数据里有 `NULL`、负数和重复值，避免“只按非空行算”也能蒙对。

### 四个难度等级

`L1` 到 `L4` **只属于 countdown**，是题目生成器里的课程分级；maze 与 sql 用另一种方式表达难度。

| 等级 | 数字个数 | 允许运算符 | 额外约束 |
| --- | --- | --- | --- |
| L1 | 2 | `+ -` | 无；最简单，主要验证“会输出表达式” |
| L2 | 3 | `+ - *` | 默认课程，数据快照的主力 |
| L3 | 4 | `+ - * /` | 除法会引入分数结果 |
| L4 | 4 | `+ - * /` | 解法必须经过分数中间值，纯整数中间解不算 |

L4 的实现方式是：先用 `integer_only=True` 求一遍“只用整数中间结果能到达的值”，
再把 target 限定在这个集合之外——于是任何正确解都必然出现分数中间量。

maze 的难度由网格尺寸表达：常规 4×4，OOD 5×5。sql 的难度由阈值区间表达：
常规在 -5 到 20，OOD 在 21 到 40。OOD（out-of-distribution，训练分布之外）
不改变任务形式，只检验“同一套规则能否外推到没见过的数值段”。

### 几个会反复出现的名词

| 名词 | 定义 | 为什么要单独看 |
| --- | --- | --- |
| pass@1（`single_success_rate`） | 每个样本单独判对的比例，正确样本数除以总样本数 | 主指标，也是配对比较的对象 |
| pass@4（`any_success_rate`） | 每题 4 个候选中至少有 1 个正确的题目比例 | 衡量采样预算带来的收益，不被训练直接优化 |
| 截断（`truncated_samples`） | 生成到 `max_new_tokens` 上限仍未输出 EOS 的样本数 | 几乎必然判错，会把“长度预算不足”混进“能力不足” |
| 失败分类（`failure_reasons`） | 验证器给出的结构化拒绝原因及计数 | 只有分类才能区分“格式不会”与“算不出来” |
| 每样本生成 token | `generated_tokens` 除以样本数 | 输出是否退化或膨胀，是格式习得的旁证 |
| `dev-quick` / `dev-full` | 前者是 `dev[:50]` 单候选，后者是 200 题 × 4 候选 | 前者选 checkpoint，后者才是比较证据 |

“截断”在本项目只有一个含义：`finish_reason == "max_tokens"`。countdown baseline 的
800 个样本里有 202 个截断，占 25.25%，所以那一轮的低分里至少有四分之一不是“答错”，
而是“没说完”。这正是后面要先用 SFT 修格式、再谈算术的原因。

## 2. 把"会做题"变成可判定对象

`tasks.py:make_task` 负责出题，`countdown_verdict` 负责判卷，两者在同一函数末尾就要对上。

出题时先用子集 DP 把所有可达值算出来（`solve`，按 bitmask 枚举所有二叉划分，
每个精确值只保留最短表达式），再从中挑一个 1 到 200 的整数当 target：

```python
count, ops = {"L1": (2, "+-"), "L2": (3, "+-*"), "L3": (4, "+-*/"), "L4": (4, "+-*/")}[difficulty]
numbers = tuple(sorted(rng.randint(1, 15) for _ in range(count)))
answers = solve(numbers, ops)
targets = sorted(v for v in answers if v.denominator == 1 and 1 <= v <= 200)
```

L4 的额外约束见第 1 节：target 只从“可达、但纯整数中间解到不了”的值里挑。
prompt 与 answer 都是纯文本：prompt 要求"只输出一个表达式，不要等号和解释"，
answer 是 solver 的最短见证，例如 `[6, 6, 15] -> 51` 的见证是 `(15+(6*6))`。

判卷不复用 solver，而是独立实现一遍（理由见本节末尾）：

- 长度超过 256 或 AST 节点超过 64 直接拒绝；
- 只允许 `+ - * /` 四类 `BinOp`，且运算符必须在本题 `payload["ops"]` 里；
- 整数常量绝对值不超过 9999，中间结果分子分母不超过 1e8，除零拒绝；
- 用 `Fraction` 精确比较，最后 `Counter(used) == Counter(payload["numbers"])` 保证每个数字
  恰好用一次，再判 `value == payload["target"]`。

最后一行是整条链的地基：

```python
if not verify(task, answer).correct:
    raise RuntimeError("Solver/verifier disagreement")
```

出题器与判卷器对不上就在生成数据时崩掉，而不是等训练完才发现标签是错的。
失败原因会被细分成可解释的标签，后面的诊断全部依赖这套标签：

| 标签 | 含义 |
| --- | --- |
| `parse_error` | 输出不是合法 Python 表达式，通常带了解释或 Markdown 围栏 |
| `number_mismatch` | 表达式合法，但数字使用与题目不一致 |
| `target` | 数字用对了、表达式也算得出来，但结果不等于 target |
| `illegal_operation` | 用了本题不允许的运算符 |
| `too_long` / `too_complex` | 超过长度或 AST 规模上限 |

`task_id` 是语义主键：`digest([kind, RULE_VERSION, identity])`，其中 identity 只含题目内容。
它不含随机种子、不含 prompt 文字，所以同一道题在任何 run 里 id 相同，配对比较才能对齐。

### 为什么 solver 和 verifier 都不走 `eval`

这两处方向相反，但都不用 Python 的 `eval`，原因不同。

solver 要做的是**反向求解**：回答“这些数字能凑出哪些值、每个值的最短表达式是什么”。
这是枚举问题，需要对所有二叉划分与运算符组合做子集 DP；`eval` 只能对一个已知字符串求值，
给不出可达值集合，结构上不适用。solver 里也不先生成字符串再 `eval`：值直接以 `Fraction`
运算，表达式字符串只是最后拼出来的产物。

verifier 做的是**正向验证**，形式上可以写成 `eval(output) == target`，但实际不能这么做：

- 安全性：输出是模型生成的不可信文本，`eval` 能执行任意代码，例如
  `__import__("os").system(...)`。`countdown_verdict` 只做白名单 AST 遍历，
  属性访问、函数调用、下标等节点一律不允许。
- 精确性：`eval` 里的 `/` 走浮点，`1/3*3` 未必等于 1；L3/L4 恰好要求分数中间值，
  浮点误差会把正确解判错。verifier 全程用 `Fraction`。
- 可诊断：判卷要给出 `parse_error`、`number_mismatch`、`target`、`illegal_operation`
  这些标签，`eval` 只能抛异常或返回一个值，无法区分“数字用错”和“算错”。
- 边界可控：长度 256、AST 节点 64、常量上限 9999、分子分母上限 1e8 都必须在求值过程中拦截；
  要能拦截就得自己写递归求值，那已经等于自己实现了 verifier。

同样的理由也适用于 SQL：不能把模型输出直接丢给数据库，verifier 用只读授权、函数白名单、
VM 指令上限和行数上限把它关进沙箱。

## 3. 把任务切成不可变快照

`data.py:generate_dataset` 一次生成四个 split 和一个固定子集：

- `train=1000`、`dev=200`、`test=400`、`ood=200`；
- 跨 split 用同一个 `seen` 集合做语义去重，同一道题不会同时出现在 train 和 dev；
- countdown 的 L2 快照里，前 10%（`count // 10`）强制用 L1，避免简单题空间被 L2 淹没；
- `ood` 只改参数范围（countdown 数字 16 到 25、maze 网格 5×5、sql 阈值 21 到 40），
  任务形式不变；
- `dev-quick` 就固定是 `dev[:50]`。

目录已存在时直接抛 `FileExistsError`，不覆盖、不静默重切。`manifest.json` 记下每个 split 的
`count` 与 `digest(rows)`，加载时再校验一次；手改任何一行 jsonl 都会在 `load_dataset` 阶段失败。

这一步的收益在协议层：`protocol_identity` 里 `data` 就是 `digest(data_manifest)`，
换数据等于换协议，resume 与 compare 都会立刻拒绝混用。

## 4. 先证明手写模型是对的，再谈能力

`model.py:load_model` 在 `torch.device("meta")` 上建结构，`to_empty` 之后按
`model.safetensors.index.json` 分片加载，并检查：

- 加载后的键集合必须等于 `state_dict` 去掉全部 `.A`/`.B`，多一个少一个都报错；
- 拒绝量化权重（`quantization_config`）、滑动窗口、`rope_scaling`；
- `tie_word_embeddings` 时把 `lm_head.weight` 绑到 embedding 上。

`parity`（对齐）指两套实现逐位对齐：`bash lab.sh parity` 在子进程里跑 HF 官方实现作为 FP32 参考，
进程退出后再加载手写模型，比较四件事：FP32 logits、cached 与 full、左 padding、eager 与 SDPA。
本机实测最大 logits 差 `9.73e-5`，cached/full 差为 0。

顺序不能反。手写 attention 一旦有 bug，baseline 的低分会被误读成"0.6B 本来就不会做题"，
后面所有调优都在错误前提上做。

## 5. 建立 baseline：不动任何权重

```bash
bash lab.sh run --config configs/base.yaml --split dev
```

`configs/base.yaml` 的关键字段：`stage=eval`、`samples=4`、`temperature=0.7`、
`max_new_tokens=64`、`max_length=256`、`dtype=float32`、`seed=42`。这几项加上题集哈希与
`split` 一起构成评测协议，改任何一项都必须重跑 baseline，不能与旧结果对比。

`evaluate` 对每一题、每个候选计算一个确定的种子：

```python
seed = (int(task["task_id"][:8], 16) + cfg.seed + candidate * 1000003) % 2**31
seed_all(seed)
```

评测开始前保存 RNG、结束后恢复，所以"评测"本身不扰动训练状态；
同一题在同一 seed 下换模型，diff 只来自权重。

四个判据一起看，缺一个就会误判：

| 任务 | pass@1 | pass@4 | 截断数 | 失败分布 | 每样本生成 token |
| --- | --- | --- | --- | --- | --- |
| countdown | 0.0000 | 0.0000 | 202/800 | `parse_error` 797、`number_mismatch` 3 | 31.6 |
| maze | 0.0000 | 0.0000 | 736/800 | `format` 800 | 62.0 |
| sql | 0.0375 | 0.1400 | 339/800 | `format` 770 | 43.7 |

countdown 的 800 个样本里 797 个不是合法表达式，只有 3 个是"表达式对了但数字不对"。
这说明 base 模型的瓶颈是**格式服从性**，不是算不出来；maze 连 800 个样本全是格式错误。
如果没有 `failure_reasons` 这一列，只看到 0.0000 会误以为模型完全没有任务能力。

两个容易踩的细节：

- `--limit` 会改变 `task_hash`，因为它进了评测协议的 `task_hash = digest(tasks)`；
  用 `--limit 50` 跑的 baseline 不能与 200 题的 dev-full 比较。要小规模试跑就用 `dev-quick` split。
- 截断数属于协议的一部分：它度量的是“模型有没有在 `max_new_tokens` 内说完”，
  而不是“算得对不对”。202/800 截断意味着四分之一样本连“说完”都没做到，
  这时讨论推理能力没有意义，先看长度预算与 prompt 格式。

## 6. 挂上 LoRA：先保证"等于没挂"

`model.py:LoRALinear` 直接继承 `nn.Linear`，在旁路加两个矩阵：

```python
self.A = nn.Parameter(torch.empty(rank, source))
self.B = nn.Parameter(torch.zeros(target, rank))
self.scale = alpha / rank
nn.init.kaiming_uniform_(self.A, a=math.sqrt(5))


def forward(self, x):
    base = F.linear(x, self.weight, self.bias)
    delta = F.linear(F.linear(x.float(), self.A), self.B) * self.scale
    return base + delta.to(base.dtype)
```

三个约定各有原因：

- `B` 置零：初始 `delta = B(Ax) = 0`，模型输出与 base 完全相同，加载 adapter 不会破坏能力；
- `A` 用 kaiming 初始化而不是零：若 `A`、`B` 同时为零，两边梯度都恒为零，是真正的死锁；
- `delta` 在 FP32 里算完再 cast 回 base dtype：base 用 BF16 时，低秩增量仍在 FP32 累积。

`Qwen3.freeze_base()` 只放行名字以 `.A`/`.B` 结尾的参数：

```python
for name, param in self.named_parameters():
    param.requires_grad_(name.endswith((".A", ".B")))
```

所以训练里那句 `RuntimeError("Frozen base received gradients")` 是有效断言，不是摆设。

0.6B、rank=16 时的参数面（hidden=1024，intermediate=3072，Q/KV heads=16/8，head_dim=128）：

| 模块 | in to out | A | B | 小计 |
| --- | --- | --- | --- | --- |
| `q_proj` | 1024 to 2048 | 16,384 | 32,768 | 49,152 |
| `k_proj` | 1024 to 1024 | 16,384 | 16,384 | 32,768 |
| `v_proj` | 1024 to 1024 | 16,384 | 16,384 | 32,768 |
| `o_proj` | 2048 to 1024 | 32,768 | 16,384 | 49,152 |
| `gate_proj` | 1024 to 3072 | 16,384 | 49,152 | 65,536 |
| `up_proj` | 1024 to 3072 | 16,384 | 49,152 | 65,536 |
| `down_proj` | 3072 to 1024 | 49,152 | 16,384 | 65,536 |

每层 360,448，28 层共 10,092,544 个可训练参数，占基础参数 596,049,920 的 1.69%。
日志里那行 `updating 392 LoRA tensors (10.09M parameters)` 就是 28 层乘 7 个模块再乘 2 个矩阵。

挂载后的第一个可验证性质：初始状态必须与 base 完全等价。实测 196 个 `B` 全零、196 个 `A` 非零、
可训练参数 10,092,544；`B` 精确为零意味着 `delta` 恒等于 0，首次 forward 与 base 逐位相同。
再用同一 seed 连跑两次评测，4 个样本的 `token_ids` 逐条一致，说明采样侧也是确定的。
如果不满足，说明 forward 或 RNG 被改动过，先修这个再训练。

## 7. SFT 到底在学什么

SFT 的损失只覆盖回答部分。`generation.py:sft_loss_sum` 是全部实现：

```python
ids = torch.tensor([prompt + response], device=device, dtype=torch.long)
logits, _ = model(ids[:, :-1])
answer_logits = logits[0, len(prompt) - 1 :]
targets = ids[0, len(prompt) :]
return F.cross_entropy(answer_logits.float(), targets, reduction="sum"), len(response)
```

- 位置 `t` 的 logits 预测位置 `t+1` 的 token，所以答案首 token 的预测来自
  `len(prompt) - 1` 这个位置，切片的 `-1` 不能省；
- targets 是 `answer` 加上 EOS，EOS 也参与监督，模型因此学会"说完就停"，
  这是截断数从 202 降到 0 的主要原因之一；
- prompt 里的 token 一个都不产生 loss，模型学的是"给定题目怎么作答"，不是"题目怎么表述"；
- `reduction="sum"` 返回的是总和，训练循环里再除以整批有效回答 token 数：

```python
target_tokens = sum(len(answer) for _, _, answer in examples)
(loss_sum / target_tokens).backward()
```

梯度累积时每个 microbatch 除的都是整批的 token 总数，所以累积后等价于把所有回答 token
放在一个 batch 里取平均，与 microbatch 怎么切无关。

把参数面和目标面放在一起就能预判 SFT 的性质：能改的只有 1.69% 的参数，监督信号只落在回答
token 上，所以 SFT 能改变的是**输出的形状与长度**，不能往权重里注入新知识。
后面 sql 的结果会精确印证这一点。

## 8. 第一次 SFT：命令、日志与判据

```bash
bash lab.sh run --config configs/countdown-sft.yaml --steps 2 --max-seconds 300
bash lab.sh run --config configs/countdown-sft.yaml
```

`configs/countdown-sft.yaml` 的关键字段：`stage=sft`、`rank=16`、`alpha=16`、
`learning_rate=1e-4`、`accumulation=1`、`steps=200`、`eval_every=50`、`save_every=50`、
`max_length=256`、`dtype=float32`。先用两到三步核对成本，再花完整预算，是硬性习惯。

每一步的流水固定为：取一个样本（或一段累积）→ forward/backward → 裁剪梯度 → optimizer step
→ 写 `metrics.jsonl` 与 stdout 一条 JSON → 每 `save_every` 存 checkpoint →
每 `eval_every` 在 `dev[:50]` 上跑单候选评测。两步探路的实测日志：

```text
INFO  reasoning_lab.train: encoded 1000/1000 train examples, filtered 0 over max_length=256
INFO  reasoning_lab.train: updating 392 LoRA tensors (10.09M parameters) lr=0.0001 accumulation=1 budget=2 updates
DEBUG reasoning_lab.train: step 1/2 loss=5.0646 grad_norm=33.819 update=0.608s
DEBUG reasoning_lab.train: step 2/2 loss=3.4243 grad_norm=29.416 update=0.146s
```

`loss=5.0646` 明显低于均匀分布的理论值 `ln(151936) = 11.9`，说明 base 的下一 token 分布
已经相当集中，SFT 的起点不是"随机猜"；`grad_norm=33.8` 主要来自 `B` 的第一步更新
（`A` 的梯度在 `B` 非零之前为零）。这两条曲线后面的走向决定这次训练是否有效：

| 现象 | 含义 |
| --- | --- |
| loss 下降到 1e-4 量级、grad_norm 降到 1e-4 | 模板习得，监督目标太窄，不是能力提升 |
| loss 缓慢下降、grad_norm 保持在个位数 | 在学新的搜索行为，继续加预算有意义 |
| loss 不降、dev-quick 不动 | 先查数据与标签，再查学习率 |

数据顺序不依赖 DataLoader：游标用 `divmod(cursor, len(encoded))` 拆成 epoch 与 offset，
每个 epoch 的排列由 `random.Random(cfg.seed + epoch).shuffle` 生成。这样 checkpoint 只要存
一个整数 `cursor` 就能精确重放，恢复后数据流与连续训练完全一致。

选模只用 `dev[:50]` 单候选，`best.pt` 只有在评测 `complete` 且成功率严格变大时才写；
`latest.pt`/`final.pt` 每个保存点都写。训练结束时如果还有预算，才用 `best.pt` 跑
`dev-full`（200 题乘 4 候选）作为候选证据。

停止原因有三种，都会带触发数值写进日志与 trace：

- `step_budget`：跑满 `steps`，正常结束，可以跑 full dev；
- `time_budget`：`max_seconds` 用尽；
- `paging_slowdown` / `memory_budget`：换页或显存超软阈值，**会跳过 full dev**，
  因为此时继续跑大规模评测只会放大本机压力。

本机 countdown 的三段实测（200 步预算被 `paging_slowdown` 切成三段，用 `--resume` 续跑）：

| 段 | 累计更新 | best dev-quick | 停止原因 |
| --- | --- | --- | --- |
| 1 | 39 | 0.06 | `paging_slowdown` |
| 2 | 101 | 0.40 | `paging_slowdown` |
| 3 | 200 | 0.42 | `step_budget` |

`best dev-quick` 从 0.06 到 0.40 主要发生在第 40 到 100 步之间，之后趋于平缓，这与"格式学会得很快、
算术提升很慢"的预期一致。逐次检查的完整曲线（39/50/100/150/200 步）记在那次 run 的 `decision.md` 里。

## 9. SFT 之后：重新评测，再做配对比较

训练出的 adapter 不能直接下结论，必须在**同一评测协议**下重新跑一遍。
下面假设 baseline 与 SFT 的目录分别在 `.local/baseline`、`.local/sft`（第 12 节给出完整顺序）：

```bash
BASE=$(ls -d .local/baseline/*)
SFT=$(ls -d .local/sft/*)
bash lab.sh run --config configs/base.yaml --split dev \
    --adapter "$SFT/checkpoints/best.pt" --output .local/candidate
CAND=$(ls -d .local/candidate/*)
bash lab.sh compare "$BASE/eval/dev" "$CAND/eval/dev"
```

为什么 `--adapter` 的评测可以与 baseline 比较：`protocol_identity` 明确把
`output`、`steps`、`max_seconds`、`limit`、`resume`、`adapter`、`hypothesis`、`change`
排除在协议之外。adapter 是"被测对象"，不是"实验条件"，所以 baseline 与候选共享协议。
反过来，改题集、温度、候选数或 dtype 都会改变协议，`compare` 会直接拒绝。

`compare` 的统计口径：

- 先按 `task_id` 聚簇，再按 `(candidate, seed)` 对齐左右两侧，保证比的是同一题同一候选；
- 每题算一个差值，2000 次对题目做有放回重采样（即配对 bootstrap），
  取 2.5% 与 97.5% 分位构成 95% 区间；
- 判定规则：`delta >= 0.03` 且区间下界大于 0 为 `accept`，区间上界小于 0 为 `reject`，
  其余为 `insufficient_evidence`。

以题目为聚类单位很关键：一题的 4 个候选高度相关，把它们当成 4 道独立题会把区间压得过窄。

两次真实比较（均为 200 题、每题 4 候选、2000 次重采样）：

| 任务 | baseline | SFT 后 | delta | 95% 区间 | 判定 |
| --- | --- | --- | --- | --- | --- |
| countdown | 0.0000 | 0.2350 | +0.2350 | [+0.1888, +0.2813] | accept |
| sql | 0.0375 | 1.0000 | +0.9625 | [+0.9488, +0.9750] | accept |

两个 `accept` 的含义完全不同，必须分开解释：

countdown 是真实学习。`parse_error` 从 797 降到 1，截断从 202 降到 0，每样本生成 token
从 31.6 降到 8.8，但 loss 只从 0.390 降到 0.338、grad_norm 仍在 2.5 附近——
格式被学会了，算术还在学。残余失败里 `target` 有 553 条（占 69.1%）：
数字全用对、表达式合法、结果不等于 target。分难度看，L1（两数字加减）单次成功率 0.9125，
L2（三数字加减乘）0.1597，是一条干净的能力梯度，不是随机噪声。

sql 是模板习得。loss 从 0.925 掉到 6e-05、grad_norm 从 11.5 掉到 2e-04，监督目标只有 17 到 19
个 token；题目空间是 5 种聚合乘 3 个 category 乘 6 个比较符乘 26 个阈值，共 2340 个规则点，
1000 条训练数据覆盖其中 43%，模板补全就能泛化到整个 dev。
dev 在 1.0 饱和，之后任何改动都无法再测出效果，所以这个任务只能证明流程通，不能当后续调优目标。

## 10. 把结论写回实验卡，决定下一轮

每个 run 目录里有一张 `decision.md`，六段固定内容：假设、唯一改动、预算与实际消耗、
可观察证据、结果、下一轮问题。三条硬规则：

1. **一次只改一个主要变量**。数据课程、学习率、rank、长度、缓存、attention 实现，
   同时改两项以上，配对比较的 delta 就没有归因。
2. **test/OOD 只在协议冻结后审计**。训练入口本身禁止用它们选 checkpoint；
   反复查看再改方案，等于把测试集变成了开发集。
3. **续训与分叉是两件事**。继续同一实验用 `--resume`（保留 optimizer、RNG、数据游标、
   GRPO 参考策略）；改超参或改代码属于新实验，只能用 `--adapter` 从同一权重分叉。

本机 countdown 的下一轮就是第 1 种：loss 仍在下降、grad_norm 仍在 2.5，
把预算从 200 提到 600 是合法的续训，前提是源码、依赖、数据、设备一个都没变。

## 11. 四个已经踩过的坑

- **改一行 .py 就断掉 resume**。`Run.protocol` 里含 `source_hash`（包内所有 `.py` 的哈希）；
  为引入日志改了模块，旧 checkpoint 的 `source_hash` 立刻对不上，`--resume` 被拒绝。
  只有权重语义没变（model hash 与 rank/alpha 相同）时，`--adapter` 仍然可用，
  但会失去 optimizer 与 RNG 连续性。真断点续训必须在改动前完成。
- **`paging_slowdown` 会跳过 full dev**。本机 22GB swap 已占用时，单步 0.38 秒对中位数
  0.15 秒触发阈值就会停训。此时 `summary.json` 里 `full_dev` 为 null，必须另起一个
  `eval` run 加 `--adapter` 补评测；sql 那次就是这样拿到 1.0000 的。
- **`dev[:50]` 有难度偏置**。数据集把 20 道 L1 放在 dev 的 0 到 19 位，所以 `dev[:50]`
  里 L1 占 40%，而完整 dev 只占 10%。0.42 的 dev-quick 与 0.235 的 full dev 不是同一口径，
  不能互相替代；checkpoint 选择因此偏向 L1 能力，本次 best 与 final 恰好重合才没出问题。
- **`--limit` 会改变协议**。它进了评测协议的 `task_hash`，用 `--limit 50` 跑出来的结果
  不能与 200 题结果比较；小规模试跑请用 `dev-quick` split，而不是给 dev 加 limit。

## 12. 从零到一次比较的完整命令

```bash
cd labs/reasoning-lab
bash lab.sh setup
bash lab.sh doctor
bash lab.sh fetch
bash lab.sh data
bash lab.sh parity --device mps

# baseline：给一个空输出目录，跑完取唯一子目录
bash lab.sh run --config configs/base.yaml --split dev --output .local/baseline
BASE=$(ls -d .local/baseline/*)

# 两三步探路，再跑满预算
bash lab.sh run --config configs/countdown-sft.yaml --steps 3 --max-seconds 300 \
    --output .local/sft-probe
bash lab.sh run --config configs/countdown-sft.yaml --output .local/sft
SFT=$(ls -d .local/sft/*)

# 同一协议下评测 adapter，然后配对比较
bash lab.sh run --config configs/base.yaml --split dev \
    --adapter "$SFT/checkpoints/best.pt" --output .local/candidate
CAND=$(ls -d .local/candidate/*)
bash lab.sh compare "$BASE/eval/dev" "$CAND/eval/dev"
bash lab.sh report "$CAND"
```

不要用 `| head -1` 从 stdout 抓 `Run:` 路径：管道提前关闭后，进程下一次写 metrics JSON 会抛
`BrokenPipeError`，整次 run 被标为 failed。用固定 `--output` 目录再取子目录更稳。

每一步都先看 `run.log`（人类叙事）与 `summary.json`（机器结果），再看 `trace.json`
确认时间花在哪个阶段。只有 `dev-full` 的结果与 `compare` 的区间才是候选证据，
中间的 `eval/step-*` 只用来回答"要不要继续加预算"。
