# v0.4.1 · 接入既有 LLM API

2026-10-07。盘铭现在可以读取用户指定的 `~/.env` 中 `LLM_*` 配置，通过真实模型生成带版本引用的 Digest，再由用户更新 Report。沿用原有 Job、SourceRef 与人工正文保护。

## 配置与接口

参考了仓库中的 [Liminalis 共享 LLM 客户端](../../liminalis/backend/_shared/llm.py) 和 [刻白 LLM 配置设计](../../swift/projects/daylog/docs/llm-configuration.md)：使用 OpenAI-compatible Chat Completions，按 API 根路径追加 `/chat/completions`，保留网关前缀。

实现位于 [llm.py](../src/panming/llm.py)，只读取四个白名单字段：

| 字段 | 用途 |
| --- | --- |
| `LLM_BASE_URL` | API 根地址，要求 HTTPS，保留现有路径 |
| `LLM_API_KEY` | 内存中的 Bearer 凭据 |
| `LLM_MODEL` | 使用配置中的模型名称 |
| `LLM_TIMEOUT` | 整个请求的秒级时限，允许 0–600 秒之间的正数 |

配置优先级是完整的进程环境配置组，再到 `~/.env`。高优先级配置缺项时显示错误，不与文件中的地址或密钥拼接。`LLM_TIMEOUT` 缺省为 45 秒；已配置时保留原值。文件作为文本解析，支持 BOM、CRLF、引号和行内注释；重复白名单项、未闭合引号、展开语法和非法 URL 会产生脱敏错误。

可通过 `PANMING_LLM_ENV_FILE` 指定另一个文件，通过 `PANMING_LLM_DISABLED=1` 禁用真实 API。配置在 Server 启动时加载；修改后重启服务。现有 `.env` 不复制到项目，密钥不进入公开 profile、对象历史或备份。

请求为非流式 JSON，包含系统规则与固定版本的 source_chunks。Qwen 配置显式关闭 thinking。每任务最多 12 份素材 / 12,000 Unicode 字符，输出最多 4,096 tokens；超限返回说明。机械校验要求 claim 引用输入中的 chunk，quote 必须逐字出现在片段中。

## Web 使用

1. 打开“消化任务”，选择“已配置 API”。界面显示当前模型与目标服务。
2. 打开所选素材的“处理策略 / 原文”，将当前正文授权给该服务。策略改变会保存一个新 revision。
3. 回到任务页选择素材，确认所选版本的发送范围后提交。Server 完成后可展开证据、查看 usage 和导出结果。
4. 到 Report 手动更新，把符合其输入 manifest 的已完成结果纳入新版本。

默认素材策略为 `local_only`。API 授权绑定服务/模型 profile；修改正文会撤销授权并取消该素材未完成的云端任务。配置中的服务或模型改变后，旧任务不会转交新目标。已发出的数据无法通过取消撤回。

## CLI 使用

```bash
cd /Users/lism/xwork/xlab/panming
./scripts/run.sh
.venv/bin/panming llm status

# material_id / job_id 使用实际 ID；策略更新返回新 revision。
.venv/bin/panming material policy material_id --revision 1 --policy cloud_allowed --confirm-cloud
.venv/bin/panming digest material_id --provider openai_compatible --allow-cloud
.venv/bin/panming jobs list
.venv/bin/panming jobs cancel job_id
.venv/bin/panming jobs retry job_id --allow-cloud
```

策略授权本身不发送请求。重复提交相同版本、模型和协议返回已有 Job；失败或取消后需显式重试。

## 请求、用量与恢复

- API 调用在数据库事务外执行。后台每 5 秒续租；任务取消、策略撤回或服务停止会中止网络等待，旧 fence 的结果不能交付。
- 每个实际请求持久记录 call_id、开始时间、fence、usage 与结算状态。取消后迟到的 usage 仍可结算，避免丢失已发生的调用。
- 默认每日 20 请求 / 100,000 token 额度，分别由 `PANMING_LLM_DAILY_REQUESTS` 与 `PANMING_LLM_DAILY_TOKENS` 设置。发出请求前预留；正常返回按服务的实际 usage 结算。
- 无 usage、超时、进程中断等情况保留保守额度占用，并显示用量不确定。真实 API 没有自动付费重试；过期租约也不自动重发云端请求。
- 未配置价格，金额显示未估价。token 额度是应用内部限制，不能替代 API 服务的账单或订阅额度。
- 备份 schema 3 包含公开模型 profile 和调用账本，继续兼容 schema 1 / 2。恢复时未完成任务先暂停，原先未结算的调用保留为不确定记录。

## 本轮证据

`./scripts/check.sh` 通过：180 个 Python 用例、5 个草稿单测、Ruff、TypeScript 与 Vite 构建。API 用例使用虚构配置和 HTTP stub，覆盖路径、认证、输入策略、超时、取消、重定向拒绝、usage、迟到结算、配置整组选择和备份恢复。

随后用既有配置做了一次真实请求，输入为脚本内固定的 Join/Spill 合成材料，保存在临时独立 schema。服务返回 5 条归纳与 5 处有效引用，usage 为输入 704 / 输出 705 / 总计 1,409 tokens。旧 Report v1 保持原样，手动更新后的 v2 包含真实模型 Digest；导出与备份校验成功。

实际界面确认了 API 模型选择、调用用量、来源陈述/模型推断、证据展开以及素材 v2 跳转。验收导出和截图保存在忽略目录 `data/v041-verification/`，其中的 summary、Markdown 和 ZIP 均不含凭据。正式工作空间仍保留原有 12 对象 / 17 修订 / 6 原件，已另存升级前备份。

复现一次真实请求：

```bash
.venv/bin/python scripts/verify_llm.py
# 可选 --serve，在 5178 查看该次隔离结果；Ctrl+C 后清理临时 schema。
```

该脚本会消耗既有 API 的额度，素材固定为脚本中的合成文本。常规自动测试不会执行它。

这一轮验证了接口、任务和引用流程。摘要支持性、遗漏率、Topic Delta 的新增/重复/冲突，以及真实研究中节省的时间，还需要授权语料与人工评估。自动订阅与图书馆重构继续按 v0.5 / v0.6 顺序推进。
