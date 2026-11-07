# 2026-09-19 本机验收

## 环境

Apple M4 Mac mini，16 GB 统一内存，macOS 26.3.2，arm64。项目本地 uv 0.12.17、Python 3.12.14、PyTorch 2.14.0，依赖固定在 uv.lock；没有修改系统 Python 或 shell 配置。

沙箱内 MPS 不可见，沙箱外实际 MPS 训练与生成成功。doctor 输出取决于执行环境，不将沙箱的 false 解读为机器没有 GPU。

## 训练验证

语料 builtin-synthetic-v1：64 个不同文档，训练 52 / 验证 12，seed 42。相同数据划分，FP32；Tiny 2 层、64 维、4 heads、FFN 256、context 64、batch 8。Tiny 有 136192 个参数。Bigram 是不同模型/学习率/步数的教学基线，不是公平算力预算对比。

| 运行 | 步数 | 初始验证 loss | 最终验证 loss |
| --- | --- | --- | --- |
| tiny | 300 | 5.845363 | 0.187129 |
| tiny-mps | 300 | 5.845363 | 0.187129 |
| bigram | 600 | 6.054964 | 1.311186 |

## 正确性

- `pytest -q`：9 passed。覆盖字节/中文往返、因果性与梯度、数据确定性、训练下降、精确恢复、过拟合、Bigram、数据变化拒绝、配置合法性、EOS 和容量边界（部分在同一测试中）。
- 连续训练 12 步与训练 6 步保存后恢复到 12 步，CPU 模型参数逐项完全一致。
- `ruff check src tests scripts` 和格式检查通过。
- GPU 权重在 CPU/MPS 上执行固定输入，最大绝对误差 `1.9073486328125e-06`，atol/rtol 均为 1e-4；完整 logits 校验通过。
- CPU/MPS 生成一致：prompt `Ada likes ` → completion `art. Ada reads every day.\n`，EOS 正常结束。

## 复现

从项目目录运行 README 中命令。GPU 对照额外运行：

```bash
.venv/bin/python scripts/check_mps.py
```

该脚本要求先生成 `runs/tiny-mps/last.pt`，且执行环境允许 Metal 访问。原始报告与权重保留在已忽略的 runs/，报告输出包含代码 commit 与 dirty 标记；当前实现尚未提交，不能仅凭基线 commit 复现本次代码。

## 验收边界

完成环境安装和端到端功能验证。训练时间是单次记录，部分任务并行执行，不能用于 CPU/GPU 性能排名。合成语料 loss 不能解释为通用语言能力。未完成 KV Cache、bundle 导出、Rust 数值对照、长时间压力测试或标准数据集评测。
