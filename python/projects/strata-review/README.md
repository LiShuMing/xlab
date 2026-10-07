# Strata 本地只读代码审查

调用已经部署在 Windows 上的 Strata，从 WSL 审查 xlab 文件或指定路径的
Git diff。模型只返回报告，不自动应用补丁、不执行命令，也不扫描整个仓库。

## 开始使用

从 xlab 根目录执行。Python 3.11+，只使用标准库，不需要 pip 安装依赖。

```bash
python3 -m venv python/projects/strata-review/.venv
PYTHON=python/projects/strata-review/.venv/bin/python
REVIEW=python/projects/strata-review/strata_review.py

# 仅检查模型是否加载，不触发推理。
"$PYTHON" "$REVIEW" --check

# 单文件；可重复 --file，显式提供关联实现。
"$PYTHON" "$REVIEW" --file cc/cclab/src/utils/task_thread.h

# 只读取指定路径的未暂存改动。
"$PYTHON" "$REVIEW" --diff --path cc/cclab/test/common/enum_test.cc

# 显式提高思考等级，将报告写入一个尚不存在的文件。
"$PYTHON" "$REVIEW" --file cc/cclab/src/utils/task_thread.h \
  --effort low --max-tokens 4096 --output /tmp/task-thread-review.md
```

默认 API 为 `http://127.0.0.1:8080/v1`，模型名为
`qwen3.8-flash-next-coder-iq1_m`。客户端绕过环境代理，不修改任何代理配置。
本机服务没有鉴权，无需 Key；如以后启用鉴权，可设置 `STRATA_API_KEY`。
可用 `STRATA_BASE_URL`、`STRATA_MODEL` 或对应 CLI 参数覆盖服务地址和模型。
非 loopback 地址禁止使用明文 HTTP。

## 验证

```bash
cd python/projects/strata-review
.venv/bin/python -m unittest -v

# 10 个小样例：6 个已知缺陷、4 个正常实现，串行调用真实模型。
.venv/bin/python validate_live.py --output-dir results/my-validation

# 用 ASan 执行仓库中提供的两个确定性复现；需要 clang++ 和 ASan。
# 不执行模型生成的复现代码。
.venv/bin/python verify_repros.py --output-dir results/my-validation

# 再对真实 TaskThread 头文件做退出/重入回调的对照验证。
.venv/bin/python verify_repros.py --task-thread --output-dir results/my-reproductions
```

`validate_live.py` 在每次请求后保存源码和完整报告，最终保存 `summary.json`。
它先做 C++20 语法检查，期望标签不会发给模型。计分仅检查缺陷分类命中及
正常样例是否被误报，必须人工检查论证，不能作为通用模型能力基准。

## 边界

- 只允许仓库内的 C/C++/Rust/Python 文件，排除隐藏文件和 thirdparty。
  跨出仓库的符号链接被拒绝。仍应自行检查源码中是否含敏感信息。
- diff 必须指定 `--path`；默认未暂存，`--staged` 读取暂存改动。
  只处理新增/修改的 tracked 文件，不支持纯删除、未跟踪文件或子模块审查。
  暂存文件同时有未暂存修改时会拒绝，以免源码和补丁不一致。
- 累计输入上限 100 KB，是字节保护，不是 tokenizer 计数。
  服务的 32K 上下文还要容纳提示词、思考和输出；过长时应拆分。
- 默认 `--effort none`，便于先验证链路；可选择 low/medium/high。
  默认最多生成 2048 tokens，输出截断会报错，不当作完整审查。
- 默认超时 600 秒，服务当前串行处理请求。排队也计入时间；推理请求不自动重试，
  避免超时后重复提交。客户端超时不一定意味着服务端计算立即停止。
- JSON 报告逐项核验文件名、行号、原文引用、分类等字段。
  引用匹配不能证明缺陷成立；空 findings 也不能证明代码正确。
- 输出使用排他创建，不覆盖已有文件。results、.venv、缓存不纳入版本控制。

## 实测记录（2026-10-07）

使用本机 `qwen3.8-flash-next-coder-iq1_m`，不是模拟返回值。
初始 10 个样例全部返回通过引用检查的 JSON：6 个已知缺陷分类命中、4 个
正常样例无 findings。之后为正常求和样例加上最多 1000 项的明确上界，
避免把极大输入的整数溢出可能性漏出测试定义。最终复测仍为 10/10 有效响应、
6/6 缺陷分类命中、4/4 正常样例无 findings，保存在
`results/validation-20261007-final/summary.json`。

`cc/cclab/src/utils/task_thread.h` 使用 low 思考等级审查，耗时约 79 秒。
模型指出第 166 行：停止流程持有 mutex_ 执行 deferred task，若回调调用
add()，会再次获取同一把非递归锁。独立复现使用原始头文件：control 返回 0，
reentrant 进入回调后在 3 秒截止时间内未返回。
完整报告在 `results/validation-20261007-initial/task-thread-review.json`，
复现记录在 `results/reproductions-20261007/task-thread-summary.json`。
未修改该头文件，也未执行模型生成的代码。

限定路径 diff 模式也通过真实接口验证：审查 enum_test.cc 的未暂存改动，
约 8.9 秒返回有效报告，未报告引入的新缺陷。报告在
`results/validation-20261007-final/diff-enum-review.json`。

这仅说明链路及小样例可用，不是生产审查可靠率；需保留人工复核和真实测试。
