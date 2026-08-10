# SP4 — 删除 / TTL / 级联

- **状态**: Draft
- **创建**: 2026-05-17
- **关联**: RFC-001-v2 §10/§14; SP2

## 当前状态

| 能力 | 当前实现 | 问题 |
|------|----------|------|
| DeleteContext | 仅标记 StateDeleted + DeletedAt | 不级联 vector / match / summary / job |
| Asset delete | 无 CLI 命令 | 无法删除 asset 及关联 contexts |
| TTL 清理 | AddIntent 写 ExpiresAt | 无后台清理，过期数据保留 |
| Privacy gate | Match 入口一次校验 | 删除点无二次校验 |

## 目标

1. **DeleteContext 真级联**: 删除 context 时同步级联删除 context_vector、关联 match_result、user_context_summary、extraction_job（audit 保留）
2. **Asset delete + cascade contexts**: `ctx asset delete ASSET_ID --cascade-contexts` 删除 asset 并可级联删除其产生的 context items
3. **TTL 后台清理**: `ctx process --expire-ttl` CLI 一次性命令 + `cmd/ctx-web` 中 goroutine 定期清理
4. **Privacy gate 删除点二次校验**: 在删除前验证 caller 身份与 target 归属关系

## 范围外

- 不实现用户删除（user delete cascade）
- 不实现 match_result 独立删除 API
- TTL goroutine 不做分布式锁（单实例部署）
- Privacy gate 不做细粒度 ACL（仅验证 user == owner）

## 架构

```
internal/service/
  services.go        — DeleteContext 重写（级联）
  ttl.go             — 新增，TTL 清理逻辑

internal/repository/
  store.go           — Repository 接口扩展（Delete* 方法）
  entity_store.go    — file 后端 Delete* 实现
  entity_postgres.go — postgres 后端 Delete* 实现

internal/cli/
  cli.go             — 新增 asset delete、process --expire-ttl 子命令
```

## Repository 接口新增方法

```go
// Cascade delete helpers
DeleteContextVector(contextID string) error
DeleteMatchesByContextID(contextID string) error
DeleteSummariesByContextID(contextID string) error
DeleteJobsByContextID(contextID string) error
DeleteContextsByAssetID(assetID string) ([]domain.ContextItem, error)
DeleteAsset(id string) (*domain.SourceAsset, error)
FindExpiredContexts(now time.Time) ([]domain.ContextItem, error)
```

## 成功标准

1. `ctx context delete CTX_ID` 级联删除 vector + match + summary + job，audit 保留
2. `ctx asset delete ASSET_ID --cascade-contexts` 删除 asset + 关联 contexts（及级联）
3. `ctx process --expire-ttl` 清理所有过期 contexts（及级联）
4. 删除点验证 user ownership（非 owner 拒绝并记录 audit）
5. `go test ./...` 全部通过
6. `ctx demo run` 无回归
