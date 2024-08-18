# llm-wiki Gap-Closure Roadmap

- **状态**：Draft → 待用户确认
- **创建日期**：2026-05-16
- **作者**：Claude (Opus 4.7) + lism
- **关联**：`projects/llm-wiki/RFC-001-v2-personal-context-maintenance-system.md`
- **类型**：顶层 roadmap（非实现 spec）

## 1. 背景

2026-05-16 完成了一次 RFC 与代码的差距 audit（参见会话记录），结论是 RFC §7~§20 中相当一部分能力尚未落地或仅为 POC：

- Python eval 层（`python/{eval,experiments,providers,schemas,notebooks}/`）目录结构存在但全空
- `prompts/`、`contracts/`、`evals/golden/*`、`evals/cases`、`evals/fixtures`、`evals/reports` 目录均空
- Vision 抽取仅 MockProvider 实现，OpenAI-compatible 未实现
- ctx.yaml.example 存在但代码不加载 yaml
- Postgres schema 是 JSONB POC，未对齐 RFC §10 全部实体
- `cmd/ctx-web` + `internal/web/` 整体未提交，前端是 server.go 内联 HTML，无鉴权/CSRF
- DeleteContext 不级联，TTL 写入不清理
- 测试覆盖薄、错误静默吞、无结构化日志

本 roadmap 把这些缺口拆成 8 个相对独立的子项目，依次实现，最后一条 PR 合入 main。

## 2. 范围

**In scope**：仅 `projects/llm-wiki/` 内的 Go 代码、Python eval 层骨架、prompts/contracts/evals 目录、配置文件、相关文档。

**Out of scope**：

- 不改 `python/projects/py-ego/` 任何文件
- 不引入 OAuth、不做多用户协同（SP5 仅做单用户 token 鉴权）
- 不改 RFC-001 文档本身（除非发现规范矛盾时另开 errata）
- 不引入新 LLM 厂商（仅 OpenAI-compatible + Mock + Replay + Golden 四类 provider）
- 不重构 `internal/repository/postgres.go` 之外的存储后端（不引 sqlite/duckdb 等）
- 不做性能优化、不做 UI 美化（SP5 只把 inline HTML 拆出来，不重设计）

## 3. 8 个子项目

每个子项目会单独写一份 spec（`docs/superpowers/specs/2026-05-XX-llm-wiki-spXX-<topic>-design.md`）和 plan，再进入实现。本节只给一行级摘要。

### SP1 — 配置加载（ctx.yaml）

**目标**：用 viper 加载 `ctx.yaml`，统一 flag/env/yaml 三层优先级（flag > env > yaml > default）；`ctx.yaml.example` 与代码强制同步；CLI 与 web 共用 `internal/config` 包。

**依赖**：无。
**量级**：~0.5 d。
**关键交付**：`internal/config/loader.go`、`internal/config/loader_test.go`、`ctx.yaml.example` 校验。

### SP2 — Schema 真实化（Postgres + file）

**目标**：把 Postgres schema 从 JSONB POC 升级到 RFC §10 完整版。新增表：`entity / user_entity_edge / user_context_summary / extraction_job / match_result`（+ 索引）。Go domain 类型与 repo 接口同步扩展，file 后端 JSON 同步落地，迁移脚本进 `internal/repository/postgres/migrations/`。

**依赖**：SP1（配置）。
**量级**：~3 d。
**关键交付**：`internal/domain/{entity,summary,extraction_job}.go`、`internal/repository/store.go` 接口扩展、Postgres 迁移、file 后端实现、Postgres 集成测试新增 5 个用例。

### SP3 — 真实 LLM 集成（Vision + Replay + Golden）

**目标**：

- `OpenAICompatibleProvider.ExtractPhotoContext` 真实实现（OpenAI vision 协议，含 base64 图片编码与 system/user prompt）
- 新增 `ReplayProvider`（从录制 JSON 回放）和 `GoldenProvider`（针对固定测试输入返回固定输出）
- Provider 失败时的 fallback 显式标记：embedding 退回 hash 向量、bridge 退回模板文本两种情况都在 `match_result.metadata` 与 `audit.model_call.metadata` 中写 `provider_fallback=true` 与具体原因；eval suite 默认拒绝 fallback 命中
- `prompts/` 落实际文件：`extract_photo_context.md`、`bridge.md`、`summary.md`、`privacy_check.md`

**依赖**：SP1（配置）、SP2（match_result schema）。
**量级**：~2 d。
**关键交付**：`internal/provider/{vision_openai.go,replay.go,golden.go}` + 对应单测；`prompts/` 4 份；audit 与 eval 集成。

### SP4 — 删除 / TTL / 级联

**目标**：

- `DeleteContext` 真级联：vector、match_result、user_context_summary、extraction_job 均同步处理（保留 audit）
- `ctx asset delete --cascade-contexts` CLI 实现
- TTL 后台清理：goroutine（在 `cmd/ctx-web` 服务态）+ `ctx process --expire-ttl` 一次性命令（CLI 模式）
- privacy gate 在删除点二次校验

**依赖**：SP2（schema 决定级联范围）。
**量级**：~1 d。
**关键交付**：`internal/service/services.go` DeleteContext 重写、`internal/service/ttl.go` 新增、CLI 子命令扩展、删除链路集成测试。

### SP5 — Web 收尾

**目标**：提交并补齐目前未提交的 `cmd/ctx-web` + `internal/web`，达到可对外服务（单用户）的水准：

- HTML 拆到 `internal/web/templates/`，静态资源到 `internal/web/static/`，用 `embed.FS` 打包
- 单用户 token 鉴权（启动时生成或从 `ctx.yaml` 读取），保护所有 `/api/*`
- CSRF token（Cookie + header 校验）
- API 与 CLI 对齐：补 `reject / delete / intent / asset delete --cascade / cost / audit / privacy audit / eval run` 端点
- Photo 上传错误路径清理临时文件
- `server_test.go` 覆盖每个 API 至少一个 happy path + 一个鉴权失败路径

**依赖**：SP1~SP4。
**量级**：~2 d。
**关键交付**：`cmd/ctx-web/main.go`、`internal/web/{server.go,auth.go,csrf.go,templates/*}`、`internal/web/server_test.go` 扩展。

### SP6 — Python eval 层骨架

**目标**：把 RFC §9 描述的 Python eval 层落成可运行骨架（不强求完整指标，但必须能跑通 demo 数据）：

- `python/eval/{run_extraction_eval.py, run_privacy_eval.py, run_matching_eval.py, run_bridge_eval.py, report.py}`
- `python/providers/{qwen.py, doubao.py, local_model.py}`：mock 实现 + 对应配置入口
- `python/schemas/`：与 Go domain 对齐的 pydantic schema
- `evals/golden/{bridge, photo_extract, summary}/`：每个 1 份 case + 期望输出
- `evals/cases/`、`evals/fixtures/`：各 1 份 sample
- `Makefile` 增 `eval-py` 目标，`README.md` 增对应章节

**依赖**：SP2（schema/contracts）、SP3（prompts）。
**量级**：~2 d。
**关键交付**：以上目录全部填充并能 `make eval-py` 通过；输出落到 `evals/reports/2026-05-XX-*.md`。

### SP7 — 测试增强

**目标**：

- privacy 反例测试：构造 private context + bridge 流，断言私有内容不出现在输出且 audit 记录拒绝原因
- E2E demo flow 测试：从 `ctx demo run` 跑完整 ingest→extract→embed→match→bridge，断言关键产物存在
- Fallback 检测测试：embedding/bridge fallback 时 `match_result.metadata.provider_fallback=true`
- Postgres 集成测试覆盖 SP2 新表（CRUD + 级联）
- CLI golden output 测试（`testdata/cli_golden/*.txt`）

**依赖**：SP2~SP6。
**量级**：~1 d。
**关键交付**：`internal/{service,cli,web}/*_test.go` 增量、`testdata/cli_golden/`、`internal/repository/postgres_integration_test.go` 扩展。

### SP8 — 工程化

**目标**：

- 引入 `log/slog`，替换 `internal/{cli,service,web}/` 中所有 `fmt.Print*`、`log.Fatal`（CLI 输出保持人类可读，但用 slog handler 输出到 stderr）
- 抽取 `ensureDemoUser/ensureDemoNote/firstNonEmpty` 等重复实现到 `internal/demo`
- 给 `contracts/`、`prompts/`（剩余目录）、`python/notebooks/` 等保留空目录加 `README.md` 说明状态
- 删除 `.demo-data/` 与 `.web-demo-data/` 的二选一（保留一个，README 同步）
- Makefile lint 目标 `make vet test eval` 串通

**依赖**：SP1~SP7。
**量级**：~1 d。
**关键交付**：所有遗留 fmt.Print 替换、`internal/demo/` 新包、占位 README。

## 4. 时间与里程碑

| 里程碑 | 包含 | 累计 d |
|---|---|---|
| M1 — 地基 | SP1 + SP2 | 3.5 |
| M2 — 模型层 | SP3 + SP4 | 6.5 |
| M3 — 用户面 | SP5 | 8.5 |
| M4 — 评测面 | SP6 | 10.5 |
| M5 — 收尾 | SP7 + SP8 | 12.5 |

每个里程碑结束做一次完整 `go test ./... && make eval` 校验，并更新本 roadmap 的进度区。

## 5. 工作机制

- 全部 commit 到 `dev2` 分支，最后一条 PR 合到 main
- 每个子项目独立走 brainstorming → spec → writing-plans → 实现 → verification 全流程
- 子项目 spec 路径：`docs/superpowers/specs/2026-05-XX-llm-wiki-spXX-<topic>-design.md`
- 子项目内部的设计选择（鉴权细节、eval golden 规模等）留给子项目 spec 决策，不在本 roadmap 提前决定
- 每完成一个子项目，在本 roadmap 第 7 节勾选并附 commit 范围

## 6. 整体成功标准

1. `go build ./... && go test ./...` 通过
2. `make eval` 通过（Go 侧 eval suite）
3. `make eval-py` 通过（Python 侧）
4. `ctx demo run` 跑通完整 ingest → extract(vision via Replay) → embed → match → bridge，输出包含 `provider_fallback` 字段
5. RFC §9 / §10 / §17 主要表与服务在 file 与 postgres 后端均存在且一致（同一 demo 数据两种后端跑出等价结果）
6. Web UI 在 token 鉴权下，API 能力与 CLI 子命令一一对应（除明显不适合 Web 的 init/user create 外）
7. Python eval 四个 suite 在 demo 数据上能在 `evals/reports/` 产出 markdown 报告

## 7. 进度

- [ ] SP1 — 配置加载
- [ ] SP2 — Schema 真实化
- [ ] SP3 — 真实 LLM 集成
- [ ] SP4 — 删除 / TTL / 级联
- [ ] SP5 — Web 收尾
- [ ] SP6 — Python eval 骨架
- [ ] SP7 — 测试增强
- [ ] SP8 — 工程化

## 8. 风险与决策点

- **Postgres schema 漂移**：SP2 改完后，SP3~SP7 任何对 schema 的新需求都回头改 SP2 迁移文件并重跑集成测试，不在子项目内偷加列
- **Vision 厂商差异**：SP3 默认 OpenAI vision 协议；如 DashScope 兼容层不一致，子项目 spec 时再决定是否抽 `VisionEncoder` 接口
- **Web 鉴权方式**：SP5 spec 时确认 token 是 cookie 还是 header；CSRF 是 double-submit cookie 还是 SameSite=Strict 单 cookie
- **eval 跑得慢**：SP6 默认走 ReplayProvider 跑 golden；不在 CI 默认跑真实 LLM
- **`.demo-data/` vs `.web-demo-data/`**：SP8 收口时择一保留；规则是哪个被 demo skill 引用就保留哪个

## 9. 附录：当前文件参考

- 业务核心：`internal/service/services.go:30-540`
- 命令分发：`internal/cli/cli.go:36-100`
- Repository 接口：`internal/repository/store.go:50-70`
- Postgres：`internal/repository/postgres.go:26-80`
- LLM：`internal/provider/openai_compatible.go:27,80,123,252`
- Web（未提交）：`internal/web/server.go:26-310`、`server.go:434-768`
- 配置：`ctx.yaml.example`（未加载）
- RFC：`RFC-001-v2-personal-context-maintenance-system.md`（2380 行，§9/§17/§18 是最大未落地块）
