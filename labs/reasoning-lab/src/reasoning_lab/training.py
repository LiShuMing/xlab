"""Small, explicit SFT and GRPO loops with optimizer-boundary checkpoints.

两条训练分支共用同一套 LoRA 参数：

    stage=sft    把 solver 的答案当监督信号，逐 token 做交叉熵（教师强制）
    stage=grpo   让模型自己采样一组答案，用程序化 reward 算出组内优势再更新

两者都在同一个 ``optimizer`` 上、同一个 ``step()`` 里落地；区别只在“监督信号从哪里来”。
基座权重始终冻结（见 model.freeze_base），所以一次 run 的产物只是一个 10M 的 adapter 增量。

每个 step 的顺序固定：前向 -> 反向 -> 断言门禁 -> 裁剪 -> step() -> 写 metrics。
门禁（梯度有限、基座无梯度、新旧策略一致）都是“出错即崩”而不是警告：
训练脚本静默地跑偏，比直接失败贵得多。
"""

from __future__ import annotations

import json
import shutil
import statistics
import time
from pathlib import Path

import torch

from .evaluation import evaluate
from .generation import answer_text, encode_prompt, generate, response_log_probs, sft_loss_sum
from .logging import duration, get_logger
from .runs import load_checkpoint, save_checkpoint
from .tasks import verify

log = get_logger("train")


def normalized_advantages(rewards: torch.Tensor) -> torch.Tensor:
    """组内标准化：a_i = (r_i - mean(r)) / std(r)。

    GRPO 不需要价值网络（critic），而是用“同一道题的 group_size 个答案”彼此比较：
    高于组均值的答案得到正优势，低于的得到负优势。标准化后 advantage 与 reward 的
    绝对尺度无关，0/1 奖励和连续奖励可以共用同一套学习率。

    clamp_min(1e-6) 处理“整组全对或全错”的退化情况：此时 std=0，不 clamp 会得到 nan。
    这种组本身没有学习信号，归一化后梯度为 0，自然跳过。
    """
    if not torch.isfinite(rewards).all():
        raise ValueError("Non-finite reward is an infrastructure failure")
    return (rewards - rewards.mean()) / rewards.std(unbiased=False).clamp_min(1e-6)


def grpo_loss(current, old, reference, advantage, beta: float, epsilon: float):
    """PPO 风格的裁剪目标，外加一项对参考策略的 KL 惩罚。

    三个 logprob 的含义必须分清：
        old        采样那一刻的策略（detach 的常量）
        reference  训练开始前的策略快照（也 detach），用来防止模型跑得太远
        current    当前正在更新的策略，带计算图

    ratio = exp(current - old)，理想情况下初始恰为 1。
    min(ratio*a, clip(ratio)*a) 是“悲观估计”：优势为正时不让 ratio 涨过 1+eps，
    优势为负时不让它跌过 1-eps，一次更新不会把某个 token 的概率推得太极端。

    KL 项用 k3 估计：kl = p/ref - log(p/ref) - 1，恒非负且无偏；
    beta 控制“允许离参考策略多远”，太大则学不动，太小则容易崩。
    """
    ratio = (current - old).exp()
    clipped = ratio.clamp(1 - epsilon, 1 + epsilon)
    log_ref_ratio = reference - current
    kl = log_ref_ratio.exp() - log_ref_ratio - 1
    loss = -(torch.minimum(ratio * advantage, clipped * advantage) - beta * kl).mean()
    return loss, {
        "kl": kl.detach().mean().item(),
        "ratio_min": ratio.detach().min().item(),
        "ratio_max": ratio.detach().max().item(),
        "clip_fraction": ((ratio.detach() - 1).abs() > epsilon).float().mean().item(),
    }


def train(
    model,
    tokenizer,
    train_tasks: list[dict],
    dev_tasks: list[dict],
    cfg,
    run,
    monitor,
    start_time: float,
) -> dict:
    params = [p for p in model.parameters() if p.requires_grad]
    # 只有 A/B 会进优化器；基座参数连 .grad 都不会有（requires_grad=False），
    # 所以“LoRA 微调”不是一种训练阶段，而是这个参数集合决定的更新范围
    optimizer = torch.optim.AdamW(
        params,
        lr=cfg.learning_rate,
        betas=tuple(cfg.betas),
        eps=cfg.eps,
        weight_decay=cfg.weight_decay,
    )
    encoded = []
    for task in train_tasks:
        prompt = encode_prompt(tokenizer, task["prompt"])
        # 答案后面拼一个 EOS：让模型学会“说完了要停”，这是降低截断率的关键一步
        answer = tokenizer.encode(task["answer"], add_special_tokens=False) + [
            tokenizer.eos_token_id
        ]
        # SFT 只需容纳 prompt+answer；GRPO 还要留出 max_new_tokens 的生成空间
        needed = len(answer) if cfg.stage == "sft" else cfg.max_new_tokens
        if len(prompt) + needed <= cfg.max_length:
            encoded.append((task, prompt, answer))
    if not encoded:
        raise ValueError("No training examples fit max_length")
    log.info(
        "encoded %d/%d train examples, filtered %d over max_length=%d",
        len(encoded),
        len(train_tasks),
        len(train_tasks) - len(encoded),
        cfg.max_length,
    )
    log.info(
        "updating %d LoRA tensors (%.2fM parameters) lr=%g accumulation=%d budget=%d updates",
        len(params),
        sum(p.numel() for p in params) / 1e6,
        cfg.learning_rate,
        cfg.accumulation,
        cfg.steps,
    )
    # An explicit seed-per-epoch permutation supports exact cursor replay without a loader process.
    # 不用 DataLoader：loader 的迭代器状态无法写入 checkpoint，resume 时无法精确复现
    # “下一步该喂哪道题”。这里用 (epoch, offset) 加每轮固定种子洗牌代替，
    # 只要给出 cursor 就能算出同样的样本，断点续训才真正等价
    import random

    order_cache = {}

    def at(cursor):
        epoch, offset = divmod(cursor, len(encoded))
        if epoch not in order_cache:
            order_cache.clear()
            order = list(range(len(encoded)))
            random.Random(cfg.seed + epoch).shuffle(order)
            order_cache[epoch] = order
        return encoded[order_cache[epoch][offset]]

    cursor, step, elapsed_prior, best = 0, 0, 0.0, -1.0
    # GRPO 需要一份“训练开始前”的 adapter 快照当参考策略；SFT 不需要
    reference = model.adapter_state() if cfg.stage == "grpo" else None
    if cfg.resume:
        saved = load_checkpoint(Path(cfg.resume), model, run.protocol, optimizer, run.device)
        cursor, step = saved["cursor"], saved["step"]
        elapsed_prior, best, reference = (
            saved["elapsed_seconds"],
            saved["best_dev"],
            saved["reference"],
        )
        if cfg.stage == "grpo" and reference is None:
            raise ValueError("GRPO resume checkpoint lacks its original reference adapter")
        log.info(
            "resumed step=%d cursor=%d best_dev=%.4f elapsed_prior=%s",
            step,
            cursor,
            best,
            duration(elapsed_prior),
        )
        monitor.event("resume_loaded", step=step, cursor=cursor, best_dev=best)
    deadline = start_time + max(0.0, cfg.max_seconds - elapsed_prior)
    log.info("deadline in %s", duration(max(0.0, deadline - time.monotonic())))
    step_times = []
    reason = "step_budget"
    checkpoints = run.path / "checkpoints"
    if cfg.resume and best >= 0:
        # Preserve the previously selected candidate even when no resumed step beats it.
        prior_best = Path(cfg.resume).parent / "best.pt"
        if not prior_best.exists():
            raise ValueError("Full resume requires the sibling best.pt; otherwise use warm start")
        candidate = torch.load(prior_best, map_location="cpu", weights_only=True)
        if candidate["protocol"] != run.protocol or candidate["best_dev"] != best:
            raise ValueError("Resume best checkpoint provenance mismatch")
        checkpoints.mkdir(parents=True, exist_ok=True)
        shutil.copy2(prior_best, checkpoints / "best.pt")
    evaluated_step = None

    def save(name):
        save_checkpoint(
            checkpoints / f"{name}.pt",
            model,
            optimizer,
            step,
            cursor,
            run.protocol,
            run.device,
            elapsed_prior + time.monotonic() - start_time,
            reference,
            best,
        )
        log.debug("checkpoint %s.pt step=%d cursor=%d", name, step, cursor)

    def dev_eval():
        nonlocal best, evaluated_step
        with monitor.phase("evaluation", {}, origin="dev_quick", step=step):
            # A fixed seed per question makes repeated dev checks comparable and RNG-neutral.
            # 只跑 dev 前 50 题、每题 1 个候选：这一步是“选 checkpoint”，不是产出证据，
            # 所以只看 single_success_rate，且绝不能拿去和 full dev 的结果比
            report = evaluate(
                model,
                tokenizer,
                dev_tasks[:50],
                cfg,
                run.path / "eval" / f"step-{step:06d}",
                deadline,
                samples=1,
            )
        evaluated_step = step
        rate = report["single_success_rate"] or 0.0
        # 必须 complete 才能参与比较：超预算的半成品评测里成功率的含义不确定
        improved = report["complete"] and rate > best
        log.info(
            "dev quick step=%d complete=%s samples=%d single=%.4f%s",
            step,
            report["complete"],
            report["samples"],
            rate,
            " new best" if improved else "",
        )
        monitor.event("dev_quick", step=step, single=rate, improved=improved)
        if improved:
            best = report["single_success_rate"]
            save("best")
        return report

    try:
        while step < cfg.steps:
            if time.monotonic() >= deadline:
                reason = "time_budget"
                log.warning("stopping at step %d: time budget exhausted", step)
                monitor.event("stop", reason=reason, step=step)
                break
            metrics = {"step": step + 1, "stage": cfg.stage}
            started = time.monotonic()
            model.train()
            optimizer.zero_grad(set_to_none=True)
            if cfg.stage == "sft":
                # 梯度累积：显存里一次只放 accumulation 个样本，但把梯度攒到一起再更新。
                # 每个样本先除以“全批 target token 数”再 backward，
                # 效果等价于一次大 batch 的按 token 平均损失
                examples = [at(cursor + i) for i in range(cfg.accumulation)]
                target_tokens = sum(len(answer) for _, _, answer in examples)
                total_loss = 0.0
                with monitor.phase("sft_forward_backward", metrics, step=step + 1):
                    for task, prompt, answer in examples:
                        loss_sum, _ = sft_loss_sum(model, prompt, answer)
                        (loss_sum / target_tokens).backward()
                        total_loss += loss_sum.detach().item()
                cursor += cfg.accumulation
                metrics.update(
                    loss=total_loss / target_tokens,
                    supervised_tokens=target_tokens,
                    input_tokens=sum(len(p) + len(a) - 1 for _, p, a in examples),
                )
            else:
                # GRPO 一步：同一个 prompt 采样一组答案 -> 用程序化验证器打分 ->
                # 组内标准化得到 advantage -> 计算三份 logprob（old/reference/current）后更新
                task, prompt, _answer = at(cursor)
                samples, rewards = [], []
                with monitor.phase("rollout", metrics, step=step + 1):
                    for candidate in range(cfg.group_size):
                        sample = generate(
                            model,
                            prompt,
                            cfg.max_new_tokens,
                            cfg.temperature,
                            tokenizer.eos_token_id,
                        )
                        samples.append(sample)
                with monitor.phase("verification", metrics, step=step + 1):
                    for candidate, sample in enumerate(samples):
                        text = answer_text(tokenizer, sample.token_ids)
                        # reward 就是 0/1：程序化验证器判对为 1，判错为 0。
                        # 不要把失败分类当成部分分，否则模型会学“接近正确”的中间形态
                        verdict = verify(task, text)
                        rewards.append(float(verdict.correct))
                        run.log(
                            "responses",
                            {
                                "step": step + 1,
                                "task_id": task["task_id"],
                                "candidate": candidate,
                                "prompt": task["prompt"],
                                "output": text,
                                "tokens": len(sample.token_ids),
                                "finish_reason": sample.finish_reason,
                                **verdict.to_dict(),
                            },
                        )
                advantages = normalized_advantages(torch.tensor(rewards, device=run.device))
                # MPS BF16 may dispatch different kernels with autograd disabled. Use the
                # same grad-enabled forward as the live policy, then immediately detach.
                # old 是“采样时那一刻”的策略：它必须与本步更新用的前向路径完全一致，
                # 否则 ratio 一开始就不是 1，后续裁剪失去意义
                with monitor.phase("old_reference", metrics, step=step + 1), torch.enable_grad():
                    model.eval()
                    old = [
                        response_log_probs(model, prompt, s.token_ids, cfg.temperature).detach()
                        for s in samples
                    ]
                    # 采样时记下的 logprob vs 重算的 logprob：两者应逐位接近。
                    # 差值超限说明 cache 路径或精度有问题，训练停止而不是带着偏差继续
                    gaps = torch.cat([(o - s.log_probs).abs() for o, s in zip(old, samples)])
                    if gaps.max().item() > cfg.max_logprob_gap:
                        run.log(
                            "metrics",
                            {
                                "step": step + 1,
                                "event": "logprob_gap_rejected",
                                "gap_max": gaps.max().item(),
                            },
                        )
                        raise FloatingPointError(
                            "Rollout/scoring logprob gap exceeds the protocol limit; "
                            "use FP32 or investigate precision/cache paths before training"
                        )
                    with model.adapters_as(reference):
                        # 参考策略的 logprob 在“训练开始时的 A/B”下计算；
                        # 上下文管理器退出后自动恢复当前权重
                        ref = [
                            response_log_probs(model, prompt, s.token_ids, cfg.temperature).detach()
                            for s in samples
                        ]
                details, total_loss = [], 0.0
                model.train()
                with monitor.phase("policy_forward_backward", metrics, step=step + 1):
                    for sample, previous, anchor, advantage in zip(samples, old, ref, advantages):
                        current = response_log_probs(
                            model, prompt, sample.token_ids, cfg.temperature
                        )
                        # 更新前必须校验 ratio 为 1：current 与 old 若不一致，
                        # 说明两次前向的条件（精度/缓存路径）不同，训练无效
                        if (current.detach() - previous).abs().max().item() > 1e-4:
                            raise FloatingPointError("Initial current/old policy ratio is not one")
                        loss, detail = grpo_loss(
                            current, previous, anchor, advantage, cfg.kl_beta, cfg.clip_eps
                        )
                        (loss / cfg.group_size).backward()
                        total_loss += loss.detach().item() / cfg.group_size
                        details.append(detail)
                metrics.update(
                    loss=total_loss,
                    reward_mean=statistics.mean(rewards),
                    rewards=rewards,
                    mixed_reward_group=len(set(rewards)) > 1,
                    generated_tokens=sum(len(s.token_ids) for s in samples),
                    cached_full_logprob_gap_mean=gaps.mean().item(),
                    cached_full_logprob_gap_max=gaps.max().item(),
                    kl=statistics.mean(d["kl"] for d in details),
                    ratio_min=min(d["ratio_min"] for d in details),
                    ratio_max=max(d["ratio_max"] for d in details),
                    clip_fraction=statistics.mean(d["clip_fraction"] for d in details),
                )
                cursor += 1
            finite = torch.stack(
                [torch.isfinite(p.grad).all() for p in params if p.grad is not None]
            )
            if not bool(finite.all()):
                raise FloatingPointError("Non-finite adapter gradient")
            # 关键不变量：任何一次 step 都不能让基座拿到梯度，否则“只训 LoRA”就成了假话
            if any(p.grad is not None for p in model.parameters() if not p.requires_grad):
                raise RuntimeError("Frozen base received gradients")
            with monitor.phase("optimizer", metrics, step=step + 1):
                # 按范数裁剪，防止单个异常批次把 adapter 推飞；
                # 只传 params，因为只有它有梯度
                grad_norm = torch.nn.utils.clip_grad_norm_(params, cfg.max_grad_norm)
                optimizer.step()
            step += 1
            seconds = time.monotonic() - started
            step_times.append(seconds)
            metrics.update(
                step=step,
                cursor=cursor,
                grad_norm=float(grad_norm),
                learning_rate=cfg.learning_rate,
                update_seconds=seconds,
                elapsed_seconds=elapsed_prior + time.monotonic() - start_time,
            )
            run.log("metrics", metrics)
            print(json.dumps(metrics), flush=True)
            reward = f" reward={metrics['reward_mean']:.3f}" if "reward_mean" in metrics else ""
            log.debug(
                "step %d/%d loss=%.4f grad_norm=%.3f update=%s%s",
                step,
                cfg.steps,
                metrics["loss"],
                metrics["grad_norm"],
                duration(seconds),
                reward,
            )
            if step % cfg.save_every == 0:
                save("latest")
            if step % cfg.eval_every == 0:
                dev_eval()
            memory = monitor.snapshot()
            # 硬限额取“配置上限”与“系统建议值的 90%”中更小的那个，
            # 提前停比被系统强杀好，至少能把 latest/final 写下来
            limit = min(
                cfg.memory_soft_limit_gib * 2**30,
                memory.get("mps_recommended_bytes", float("inf")) * 0.9,
            )
            if memory.get("mps_driver_bytes", 0) > limit:
                reason = "memory_budget"
                log.warning(
                    "stopping after step %d: MPS driver %.2f GiB exceeds the %.2f GiB limit",
                    step,
                    memory["mps_driver_bytes"] / 2**30,
                    limit / 2**30,
                )
                monitor.event("stop", reason=reason, step=step)
                break
            # 换页降速：本次 step 耗时超过近 6 步中位数的 2 倍，且系统正在换页。
            # 这是“内存不够但还没爆”的信号，继续跑下去每一步都在变慢且不稳定
            if (
                len(step_times) >= 6
                and memory["pageout_growth_bytes"] > 0
                and seconds > 2 * statistics.median(step_times[-6:-1])
            ):
                reason = "paging_slowdown"
                log.warning(
                    "stopping after step %d: update took %s against a %s median while pageout "
                    "grew %d bytes",
                    step,
                    duration(seconds),
                    duration(statistics.median(step_times[-6:-1])),
                    memory["pageout_growth_bytes"],
                )
                monitor.event("stop", reason=reason, step=step)
                break
        if reason == "step_budget":
            log.info("stopping at step %d: update budget reached", step)
        save("latest")
        save("final")
        if evaluated_step != step and time.monotonic() < deadline:
            dev_eval()
    except BaseException:
        # A partial optimizer step is not a resumable checkpoint boundary.
        run.status("failed", last_completed_step=step, cursor=cursor)
        raise
    full_dev = None
    candidate = checkpoints / "best.pt"
    # 只在预算内且环境健康时跑完整评测：内存/换页停止意味着机器已不稳定，
    # 这时测出的一列数字不可信，不如如实报告“本轮没有可比证据”
    if (
        candidate.exists()
        and time.monotonic() < deadline
        and reason
        not in {
            "memory_budget",
            "paging_slowdown",
        }
    ):
        # Weights-only candidate selection must not rewind the final optimizer/RNG checkpoint.
        # 只临时换权重跑评测（with 退块自动恢复），不去回滚 optimizer 与 RNG：
        # 选模是“看哪个权重更好”，不是“把训练退回那一步”
        selected = torch.load(candidate, map_location="cpu", weights_only=True)
        with model.adapters_as(selected["adapter"]), monitor.phase("full_dev", {}, step=step):
            full_dev = evaluate(
                model, tokenizer, dev_tasks, cfg, run.path / "eval" / "dev-full", deadline
            )
        log.info(
            "full dev complete=%s samples=%d single=%s any=%s failures=%s",
            full_dev["complete"],
            full_dev["samples"],
            full_dev["single_success_rate"],
            full_dev["any_success_rate"],
            full_dev["failure_reasons"],
        )
        monitor.event("full_dev", step=step, single=full_dev["single_success_rate"])
    else:
        # A stop reason that skips selection leaves the run without a comparable evaluation.
        log.warning(
            "skipping full dev: stop reason=%s candidate=%s budget_left=%s",
            reason,
            candidate.exists(),
            duration(max(0.0, deadline - time.monotonic())),
        )
    # Include final evaluation cost in resume budgets, preserving final policy/optimizer pairing.
    save("latest")
    save("final")
    summary = {
        "stop_reason": reason,
        "updates": step,
        "cursor": cursor,
        "training_examples_available": len(encoded),
        "filtered_examples": len(train_tasks) - len(encoded),
        "distinct_examples_seen_upper_bound": min(cursor, len(encoded)),
        "best_dev_quick": best if best >= 0 else None,
        "candidate_checkpoint": str(candidate) if candidate.exists() else None,
        "full_dev": full_dev,
        "elapsed_seconds": elapsed_prior + time.monotonic() - start_time,
        "observed_memory_high_water": monitor.high_water,
        "monitor_error": monitor.error,
        # 单次 run 永远不构成“训练已收敛”的证据：接受与否只能由 compare 的三态输出决定
        "convergence_established": False,
    }
    run.status("complete", **summary)
    log.info(
        "run complete stop_reason=%s updates=%d cursor=%d elapsed=%s",
        reason,
        step,
        cursor,
        duration(summary["elapsed_seconds"]),
    )
    return summary
