"""Readable Qwen3, HF-compatible base names and FP32 LoRA adapters.

Architecture and low-rank adaptation follow the MIT reference recorded in NOTICE.md.
Training never retains KV caches. Inference can compare cached and full forwards.

一次 forward 的数据流（这是读整个仓库的主干）：

    token ids [batch, length]
      -> embed_tokens            查表 -> [batch, length, hidden_size]
      -> 28 x Layer              每层 = 注意力子层 + MLP 子层，各带一条残差
      -> RMSNorm                 把最后一层输出归一化
      -> lm_head                 [batch, length, vocab_size]，每个位置对全词表的打分

基座权重全程冻结，只有 LoRA 的 A/B 参与反向传播（见 ``freeze_base``）。
因此同一份代码既能跑 base 评测（B 为零，等价于原模型），也能跑 SFT/GRPO。

两个容易混淆的维度：``hidden_size`` 是残差流的宽度，``head_dim * num_heads``
是注意力内部的宽度，Qwen3 里两者不相等（1024 与 2048）。
"""

from __future__ import annotations

import contextlib
import json
import math
from dataclasses import asdict, dataclass, fields
from pathlib import Path

import torch
import torch.nn.functional as F
from safetensors.torch import load_file
from torch import nn
from torch.utils.checkpoint import checkpoint


@dataclass
class ModelConfig:
    """Qwen3-0.6B 的结构超参，字段名与 HF config.json 对齐以便直接加载。"""

    # 词表：分词器能切出的不同 token 个数，也是 lm_head 的输出维度
    vocab_size: int = 151936
    # 残差流宽度：每个位置始终用这么长的向量在层间传递
    hidden_size: int = 1024
    # SwiGLU 的中间宽度，约为 3 x hidden_size
    intermediate_size: int = 3072
    # 解码器层数：28 层相同结构串联
    num_hidden_layers: int = 28
    # 查询头数
    num_attention_heads: int = 16
    # K/V 头数。小于查询头数就是 GQA：多个查询头共享一组 K/V，
    # 推理时 KV cache 只需存 8 个头而不是 16 个，显存减半
    num_key_value_heads: int = 8
    # 每个头的维度。注意 head_dim * num_attention_heads = 2048 != hidden_size，
    # 所以 q_proj 是 1024 -> 2048 的升维投影，不是按 head 均分 hidden_size
    head_dim: int = 128
    # RMSNorm 分母里的平滑项，防止全零向量除零
    rms_norm_eps: float = 1e-6
    # RoPE 的基频。越大，不同位置的旋转角差异越小，长上下文外推更好
    rope_theta: float = 1000000.0
    # 输入 embedding 与输出 lm_head 共用同一张矩阵，省一半参数
    tie_word_embeddings: bool = True
    attention_bias: bool = False

    @classmethod
    def from_dict(cls, value: dict) -> ModelConfig:
        if value.get("hidden_act", "silu") != "silu":
            raise ValueError("Only SwiGLU/SiLU is supported")
        if value.get("model_type", "qwen3") != "qwen3":
            raise ValueError("Only dense Qwen3 is supported")
        if value.get("quantization") or value.get("quantization_config"):
            raise ValueError("Use original unquantized weights, not MLX/GPTQ/AWQ weights")
        if value.get("use_sliding_window") or value.get("rope_scaling"):
            raise ValueError("Sliding window/scaled RoPE are not implemented")
        names = {field.name for field in fields(cls)}
        result = {key: val for key, val in value.items() if key in names}
        if "rope_parameters" in value:
            rope = value["rope_parameters"]
            if rope.get("rope_type", "default") != "default":
                raise ValueError("Only default RoPE is supported")
            result["rope_theta"] = rope["rope_theta"]
        return cls(**result)


class RMSNorm(nn.Module):
    """RMSNorm：y = x / sqrt(mean(x^2) + eps) * weight。

    与 LayerNorm 的区别是**不减均值**，只按均方根缩放。少一次 reduce，也少一组 bias，
    而且不需要保存均值，因此更快。

    归一化在 FP32 里算完再 cast 回输入 dtype：BF16 下平方和容易溢出或丢精度，
    这一层是数值稳定性的关键点之一。
    """

    def __init__(self, width: int, eps: float):
        super().__init__()
        self.weight = nn.Parameter(torch.ones(width))
        self.eps = eps

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        normalized = x.float() * torch.rsqrt(x.float().square().mean(-1, keepdim=True) + self.eps)
        return normalized.to(x.dtype) * self.weight


class LoRALinear(nn.Linear):
    """线性层的 LoRA 旁路：y = W x + scale * B (A x)。

    形状约定（source = 输入维度，target = 输出维度，rank = r）：
        A: [r, source]   随机初始化
        B: [target, r]   零初始化
        W: [target, source]  基座权重，requires_grad=False

    B 为零的理由：训练开始那一刻 delta = B(Ax) = 0，模型输出与 base 完全一致；
    第一步梯度只更新 B（dL/dA 正比于 B，此时为零），B 离开零点后 A 才开始学。
    如果 A、B 同时置零，两边梯度都是零，旁路永远学不动。

    scale = alpha / r 把“秩”与“更新幅度”解耦：调大 r 不必同时调学习率。
    delta 一律在 FP32 里算再 cast 回基座 dtype，原因与 RMSNorm 相同。

    继承 nn.Linear 而不是包一层：state_dict 的键名保持 ``...weight``，
    可以直接加载 HF 权重，只在加载后补上 .A/.B。
    """

    def __init__(self, source: int, target: int, rank: int, alpha: float, bias: bool = False):
        super().__init__(source, target, bias=bias)
        self.A = nn.Parameter(torch.empty(rank, source))
        self.B = nn.Parameter(torch.zeros(target, rank))
        self.scale = alpha / rank
        nn.init.kaiming_uniform_(self.A, a=math.sqrt(5))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        base = F.linear(x, self.weight, self.bias)
        # 两次小矩阵乘法替代一次大矩阵乘法：r << source/target，参数量与计算量都大幅下降
        delta = F.linear(F.linear(x.float(), self.A), self.B) * self.scale
        return base + delta.to(base.dtype)


class Attention(nn.Module):
    """因果自注意力：GQA + RoPE + 可选 KV cache。

    输入 x: [batch, length, hidden_size]，输出同形状。内部四步：
      1. 四个投影把 x 变成 q/k/v（q 有 16 个头，k/v 只有 8 个）并做 per-head RMSNorm；
      2. 对 q/k 施加 RoPE，把“我在第几个位置”写成向量方向上的旋转；
      3. 有 past 时把历史 K/V 拼到当前 K/V 前面，这就是 KV cache；
      4. 按因果掩码做 attention，再投影回 hidden_size。
    """

    def __init__(self, cfg: ModelConfig, rank: int, alpha: float):
        super().__init__()
        self.cfg = cfg
        self.q_proj = LoRALinear(
            cfg.hidden_size, cfg.num_attention_heads * cfg.head_dim, rank, alpha, cfg.attention_bias
        )
        self.k_proj = LoRALinear(
            cfg.hidden_size, cfg.num_key_value_heads * cfg.head_dim, rank, alpha, cfg.attention_bias
        )
        self.v_proj = LoRALinear(
            cfg.hidden_size, cfg.num_key_value_heads * cfg.head_dim, rank, alpha, cfg.attention_bias
        )
        self.o_proj = LoRALinear(
            cfg.num_attention_heads * cfg.head_dim, cfg.hidden_size, rank, alpha
        )
        self.q_norm = RMSNorm(cfg.head_dim, cfg.rms_norm_eps)
        self.k_norm = RMSNorm(cfg.head_dim, cfg.rms_norm_eps)

    def forward(self, x, positions, mask, past, implementation):
        cfg = self.cfg
        batch, length, _ = x.shape
        # 投影后重排成 [batch, heads, length, head_dim]，让每个头独立做点积。
        # q_norm/k_norm 是 Qwen3 特有的“逐头归一化”，防止个别头的 logits 过大。
        q = self.q_norm(
            self.q_proj(x).view(batch, length, cfg.num_attention_heads, cfg.head_dim)
        ).transpose(1, 2)
        k = self.k_norm(
            self.k_proj(x).view(batch, length, cfg.num_key_value_heads, cfg.head_dim)
        ).transpose(1, 2)
        v = (
            self.v_proj(x)
            .view(batch, length, cfg.num_key_value_heads, cfg.head_dim)
            .transpose(1, 2)
        )
        # RoPE：每个二维子空间按位置旋转一个角度。freq 是各子空间的转速，
        # theta 越大转速越慢。相邻两维共享同一个角，所以把 angle 复制一份再拼。
        freq = 1.0 / cfg.rope_theta ** (
            torch.arange(0, cfg.head_dim, 2, device=x.device).float() / cfg.head_dim
        )
        angle = positions.float().unsqueeze(-1) * freq
        angle = torch.cat((angle, angle), -1).unsqueeze(1)
        cosine, sine = angle.cos().to(x.dtype), angle.sin().to(x.dtype)

        def rotate(tensor):
            # (x1, x2) -> (-x2, x1)，二维平面上的 90 度旋转；旋转不改变向量长度
            a, b = tensor.chunk(2, -1)
            return torch.cat((-b, a), -1)

        q, k = q * cosine + rotate(q) * sine, k * cosine + rotate(k) * sine
        # KV cache 只追加、不重算历史：decode 时每步只算 1 个新 token 的 K/V。
        if past is not None:
            k = torch.cat((past[0], k), 2)
            v = torch.cat((past[1], v), 2)
        # cache 存的是 repeat 之前的 8 个头，显存只有全量的一半；
        # 复制成 16 个头只发生在计算时，不进入缓存。
        cache = (k, v)
        copies = cfg.num_attention_heads // cfg.num_key_value_heads
        k, v = k.repeat_interleave(copies, 1), v.repeat_interleave(copies, 1)
        key_length = k.shape[2]
        # 因果掩码：第 i 个 query 只能看到位置 <= 自己的 key。
        # 再与 padding mask 相与，避免 attend 到左侧填充（左 padding 用于变长 batch）。
        causal = (
            torch.arange(key_length, device=x.device)[None, :]
            <= torch.arange(key_length - length, key_length, device=x.device)[:, None]
        )
        allowed = causal[None, None] & mask[:, None, None, :].bool()
        if implementation == "sdpa":
            # 融合算子：内部自动做 1/sqrt(d) 缩放，速度最快
            out = F.scaled_dot_product_attention(q, k, v, attn_mask=allowed, dropout_p=0.0)
        elif implementation == "eager":
            # 手写版本，用 FP32 算分数，专门用来和 HF 参考实现逐位对账；
            # nan_to_num 防御“整行都被掩掉”时 softmax 全 -inf 产生的 nan
            scores = (q.float() @ k.float().transpose(-1, -2)) / math.sqrt(cfg.head_dim)
            probs = scores.masked_fill(~allowed, -torch.inf).softmax(-1).nan_to_num(0.0)
            out = probs.to(v.dtype) @ v
        else:
            raise ValueError(f"Unknown attention implementation: {implementation}")
        return self.o_proj(out.transpose(1, 2).reshape(batch, length, -1)), cache


class MLP(nn.Module):
    """SwiGLU 前馈层：down( silu(gate(x)) * up(x) )。

    普通 Transformer 的 FFN 是“升维 -> 激活 -> 降维”两个矩阵；SwiGLU 用三个：
    gate 分支负责门控，up 分支提供内容，两路逐元素相乘后再降维。
    中间宽度因此取 3 x hidden（而不是普通实现的 4 x hidden）。
    """

    def __init__(self, cfg, rank, alpha):
        super().__init__()
        self.gate_proj = LoRALinear(cfg.hidden_size, cfg.intermediate_size, rank, alpha)
        self.up_proj = LoRALinear(cfg.hidden_size, cfg.intermediate_size, rank, alpha)
        self.down_proj = LoRALinear(cfg.intermediate_size, cfg.hidden_size, rank, alpha)

    def forward(self, x):
        return self.down_proj(F.silu(self.gate_proj(x)) * self.up_proj(x))


class Layer(nn.Module):
    """一个解码器层：pre-norm 残差结构。

        x = x + Attn(RMSNorm(x))
        x = x + MLP (RMSNorm(x))

    每个子层前先归一化、残差直连不经过归一化。这样 28 层堆叠时
    梯度沿着残差流原样回传，比“先子层后归一化”的 post-norm 好训很多。
    """

    def __init__(self, cfg, rank, alpha):
        super().__init__()
        self.input_layernorm = RMSNorm(cfg.hidden_size, cfg.rms_norm_eps)
        self.self_attn = Attention(cfg, rank, alpha)
        self.post_attention_layernorm = RMSNorm(cfg.hidden_size, cfg.rms_norm_eps)
        self.mlp = MLP(cfg, rank, alpha)

    def forward(self, x, positions, mask, past, implementation):
        attended, cache = self.self_attn(
            self.input_layernorm(x), positions, mask, past, implementation
        )
        x = x + attended
        return x + self.mlp(self.post_attention_layernorm(x)), cache


class Backbone(nn.Module):
    def __init__(self, cfg, rank, alpha):
        super().__init__()
        self.embed_tokens = nn.Embedding(cfg.vocab_size, cfg.hidden_size)
        self.layers = nn.ModuleList([Layer(cfg, rank, alpha) for _ in range(cfg.num_hidden_layers)])
        self.norm = RMSNorm(cfg.hidden_size, cfg.rms_norm_eps)


class Qwen3(nn.Module):
    """完整模型：embedding + 28 层 + final norm + lm_head。

    ``self.model`` 这层嵌套是沿用 HF 的命名前缀（权重键长成 ``model.layers.0...``），
    不是多余的包装层；改名会让 safetensors 加载全部对不上。
    """

    def __init__(self, cfg: ModelConfig, rank: int = 16, alpha: float = 16):
        super().__init__()
        if rank < 1 or cfg.num_attention_heads % cfg.num_key_value_heads:
            raise ValueError("Invalid rank or grouped-query head configuration")
        self.config, self.rank, self.alpha = cfg, rank, alpha
        self.model = Backbone(cfg, rank, alpha)
        self.lm_head = nn.Linear(cfg.hidden_size, cfg.vocab_size, bias=False)
        self.tie_weights()
        self.gradient_checkpointing = False
        self.attention_impl = "sdpa"
        self.freeze_base()

    def tie_weights(self):
        # 共享同一张矩阵：输入把 token 映射成向量，输出用同一张矩阵把向量映回词表分数。
        # 直接赋值而不是拷贝，所以 state_dict 里两处指向同一个 storage。
        if self.config.tie_word_embeddings:
            self.lm_head.weight = self.model.embed_tokens.weight

    def freeze_base(self):
        # 用“名字后缀”而不是 isinstance 判定可训练参数：
        # 只有 LoRALinear 会造出 .A/.B，其它权重（包括 embedding、norm）全部冻结。
        for name, param in self.named_parameters():
            param.requires_grad_(name.endswith((".A", ".B")))

    def forward(self, input_ids, attention_mask=None, past_key_values=None, use_cache=False):
        batch, length = input_ids.shape
        past_length = 0 if past_key_values is None else past_key_values[0][0].shape[2]
        if attention_mask is None:
            attention_mask = torch.ones(batch, past_length + length, device=input_ids.device)
        if attention_mask.shape != (batch, past_length + length):
            raise ValueError("attention_mask must cover past and current tokens")
        # 位置按“真实 token 数”编号，而不是按数组下标：
        # 左 padding 时 pad 位不计入，第一个有效 token 的位置永远是 0，RoPE 才不会错位。
        positions = (attention_mask.long().cumsum(-1) - 1).clamp_min(0)[:, -length:]
        x = self.model.embed_tokens(input_ids)
        caches = []
        for index, layer in enumerate(self.model.layers):
            past = None if past_key_values is None else past_key_values[index]
            if self.gradient_checkpointing and self.training:
                # 梯度检查点用“重算前向”换显存，所以不能同时保存 KV cache（两者目的相反）
                if use_cache or past is not None:
                    raise ValueError("Gradient checkpointing is incompatible with KV cache")

                def run(value, layer=layer):
                    return layer(value, positions, attention_mask, None, self.attention_impl)[0]

                x = checkpoint(run, x, use_reentrant=False)
            else:
                x, cache = layer(x, positions, attention_mask, past, self.attention_impl)
                if use_cache:
                    caches.append(cache)
        return self.lm_head(self.model.norm(x)), caches if use_cache else None

    def adapter_state(self) -> dict[str, torch.Tensor]:
        """把 392 张 A/B 张量快照成一份 CPU 副本，内部不共享存储。

        detach 断开计算图、cpu 搬出显卡、clone 防共享内存：这份快照后续会被当作
        GRPO 的参考策略，或者在 ``--adapter`` 时写进 checkpoint，不能被训练改到。
        """
        return {
            name: p.detach().cpu().clone()
            for name, p in self.named_parameters()
            if name.endswith((".A", ".B"))
        }

    def load_adapter(self, state: dict):
        """把一份快照装回模型。

        要求键集合**完全相等**，而不是“包含即可”：rank 不同时形状不同，
        多一个少一个都应该报错，而不是静默错位。
        """
        expected = {name: p for name, p in self.named_parameters() if p.requires_grad}
        if expected.keys() != state.keys():
            raise ValueError("Adapter key mismatch")
        with torch.no_grad():
            for name, value in state.items():
                if value.shape != expected[name].shape:
                    raise ValueError(f"Adapter shape mismatch: {name}")
                expected[name].copy_(value)

    @contextlib.contextmanager
    def adapters_as(self, state: dict):
        """在一个 with 块内临时换成另一套 A/B，退出时无条件换回。

        用途是 GRPO：同一时刻要同时算“当前策略”与“参考策略”的 logprob，
        但只能有一份参数在主模型上，于是用上下文管理器切开时间片。
        用 try/finally 而不是只写两次 load，是为了让块内抛异常也能恢复。
        """
        saved = self.adapter_state()
        self.load_adapter(state)
        try:
            yield
        finally:
            self.load_adapter(saved)


def load_model(
    path: Path, device: str, dtype: torch.dtype, rank: int = 16, alpha: float = 16
) -> tuple[Qwen3, dict]:
    """加载 HF 格式的基座权重，并挂上零初始化的 LoRA 旁路。

    步骤：读 config -> 在 meta device 上建空结构 -> to_empty 后填入真实权重 ->
    校验键集合 -> 重建 A/B（FP32）-> 冻结基座 -> 把冻结参数 cast 到目标 dtype。

    返回的 report 会写进 run 目录，用来核对参数量与结构，不参与训练。
    """
    cfg = ModelConfig.from_dict(json.loads((path / "config.json").read_text()))
    index = path / "model.safetensors.index.json"
    shards = (
        sorted(set(json.loads(index.read_text())["weight_map"].values()))
        if index.exists()
        else ["model.safetensors"]
    )
    # Meta construction avoids initializing 0.6B random parameters before loading.
    # （5.96 亿参数的随机初始化纯属浪费：每个权重马上会被文件内容覆盖）
    with torch.device("meta"):
        model = Qwen3(cfg, rank, alpha)
    model.to_empty(device="cpu")
    state = {}
    for shard in shards:
        if Path(shard).name != shard:
            raise ValueError("Shard names must be local filenames")
        values = load_file(path / shard, device="cpu")
        if state.keys() & values.keys():
            raise ValueError("Duplicate tensor keys across shards")
        state.update(values)
    if cfg.tie_word_embeddings:
        # 共享权重在两个文件里可能只存一份；两边都在时必须逐位相等，否则说明文件被改过
        embedding = state.get("model.embed_tokens.weight")
        head = state.get("lm_head.weight")
        if embedding is None and head is None:
            raise ValueError("Missing tied embeddings")
        if embedding is not None and head is not None and not torch.equal(embedding, head):
            raise ValueError("Tied embedding tensors disagree")
        state["model.embed_tokens.weight"] = embedding if embedding is not None else head
        state["lm_head.weight"] = state["model.embed_tokens.weight"]
    # 键集合必须精确相等（A/B 除外）：多一个少一个都意味着权重与结构不匹配，
    # 沉默加载会得到“能跑但全错”的模型，这类 bug 比直接报错贵得多
    expected = {key for key in model.state_dict() if not key.endswith((".A", ".B"))}
    if set(state) != expected:
        raise ValueError(
            f"Base weight keys differ: missing={expected - state.keys()}, "
            f"unexpected={state.keys() - expected}"
        )
    model.load_state_dict(state, strict=False, assign=True)
    del state, values
    model.tie_weights()
    # A/B 单独重建为 FP32：to_empty 之后它们是 meta 里的占位值；
    # 保持 FP32 才能让更新量在低精度基座上不丢信息
    for module in model.modules():
        if isinstance(module, LoRALinear):
            module.A = nn.Parameter(torch.empty(module.A.shape, dtype=torch.float32))
            module.B = nn.Parameter(torch.zeros(module.B.shape, dtype=torch.float32))
            nn.init.kaiming_uniform_(module.A, a=math.sqrt(5))
    model.freeze_base()
    for param in model.parameters():
        # 只把冻结参数 cast 到目标 dtype（如 bf16/fp16），可训练的 A/B 保持 FP32
        if not param.requires_grad:
            param.data = param.data.to(dtype)
    model.to(device)
    report = {
        "architecture": asdict(cfg),
        "rank": rank,
        "alpha": alpha,
        "parameters": sum(p.numel() for p in model.parameters()),
        "trainable_parameters": sum(p.numel() for p in model.parameters() if p.requires_grad),
        "base_parameters": sum(p.numel() for p in model.parameters() if not p.requires_grad),
        "dtype": str(dtype),
        "shards": shards,
        "tied_embeddings": model.lm_head.weight is model.model.embed_tokens.weight,
    }
    return model, report
