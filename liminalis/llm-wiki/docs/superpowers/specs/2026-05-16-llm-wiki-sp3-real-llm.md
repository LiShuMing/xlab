# SP3 — 真实 LLM 集成（Vision + Replay + Golden + Prompts）

- **状态**: Draft
- **创建**: 2026-05-16
- **关联**: RFC-001-v2 §7.4/§8.3/§13; SP1, SP2

## 当前状态

| 方法 | 真实实现 | 问题 |
|------|----------|------|
| ExtractPhotoContext | **无（直接走 MockProvider）** | OpenAICompatibleProvider 嵌入 MockProvider，未 override ExtractPhotoContext |
| EmbedTexts | 有 | Fallback 已标 FallbackUsed=true，但 match_result 不感知 |
| GenerateBridge | 有 | 同上 |
| prompts/ | 空目录 | 提示词硬编码在 openai_compatible.go |

## 目标

1. **Vision 真实抽取**: OpenAICompatibleProvider 实现 ExtractPhotoContext，调用 OpenAI vision API（base64 图片 + system/user prompt）
2. **ReplayProvider**: 录制 Provider 调用到 JSON，支持从 JSON 回放（用于 eval / demo / CI）
3. **GoldenProvider**: 针对固定测试输入返回固定输出（用于 eval golden cases）
4. **Fallback 标记入 match_result**: embedding/bridge fallback 时在 match_result 中写 `provider_fallback=true`
5. **prompts/ 落地**: 从代码中提取 prompt 到 `prompts/{extract_photo_context, bridge, summary, privacy_check}.md`

## 范围外

- 不实现 summary prompt（SP4 才需要）
- 不支持非 OpenAI vision 协议（如 DashScope vision）
- ReplayProvider 不录制/回放 ExtractPhotoContext（vision 输入是图片文件，录 JSON 太大）

## 架构

```
internal/provider/
  openai_compatible.go    — 现有，加 ExtractPhotoContext (vision)
  vision.go               — 新增，base64 编码 + vision API 调用
  replay.go               — 新增，ReplayProvider
  golden.go               — 新增，GoldenProvider
  interface.go            — 现有 Provider 接口不变

prompts/
  extract_photo_context.md  — 新增，vision system prompt
  bridge.md                 — 新增，从 openai_compatible.go 提取
```

## 成功标准

1. `ctx ingest photo --provider llm` 调用真实 vision API，返回结构化 PhotoExtraction
2. `ctx demo run --provider replay` 从录制 JSON 回放，输出与录制时一致
3. `ctx eval run --suite bridge-llm` 使用 GoldenProvider，不调真实 API
4. 当 embedding/bridge fallback 时，`match_result` 含 `provider_fallback=true`
5. `prompts/` 目录含至少 2 个 prompt 文件
6. `go test ./...` 全部通过
