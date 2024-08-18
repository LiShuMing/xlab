# SP5 — Web 收尾

- **状态**: Draft
- **创建**: 2026-05-17
- **关联**: RFC-001-v2 §19; SP1~SP4

## 当前状态

| 能力 | 当前实现 | 问题 |
|------|----------|------|
| HTML | 768 行 server.go 内 indexHTML 常量 | 不可维护，需拆到 templates/ |
| 静态资源 | 内联 CSS | 无 static/ 目录 |
| Token 鉴权 | 无 | 所有 /api/* 无保护 |
| CSRF | 无 | 无防护 |
| API 端点 | 9 个（state/demo/process/embed/match/bridge/note/photo/edit/approve） | 缺 reject/delete/asset delete/intent/cost/audit/eval/ttl |
| Photo 上传错误 | 有 defer os.RemoveAll(tmpDir) | 正常路径 OK，但 MaxBytesReader 超限时无清理 |
| 测试 | 195 行 server_test.go | 无 auth 失败路径，覆盖不足 |

## 目标

1. **HTML 拆分 + embed.FS**: 内联 HTML 拆到 `internal/web/templates/index.html`，用 `//go:embed` 打包
2. **Token 鉴权**: 启动时生成或从 `ctx.yaml` 的 `server.auth_token` 读取，保护所有 `/api/*`，通过 `Authorization: Bearer <token>` 或 cookie `ctx_token` 传递
3. **CSRF**: double-submit cookie 模式 — 设置 `ctx_csrf` cookie（SameSite=Strict），前端在 `X-CSRF-Token` header 回传
4. **API 对齐 CLI**: 新增端点
5. **Photo 上传错误清理**: MaxBytesReader 超限、写入失败等路径确保 tmpDir 清理
6. **测试覆盖**: 每个 API 至少 1 happy path + 1 auth 失败

## 新增 API 端点

| 端点 | 方法 | 对应 CLI |
|------|------|----------|
| `/api/context/reject` | POST | `ctx review reject` |
| `/api/context/delete` | POST | `ctx context delete --user` |
| `/api/asset/delete` | POST | `ctx asset delete --cascade-contexts` |
| `/api/intent` | POST | `ctx intent set` |
| `/api/cost` | GET | `ctx cost show` |
| `/api/audit` | GET | audit log query |
| `/api/eval/run` | POST | `ctx eval run` |
| `/api/process/expire-ttl` | POST | `ctx process --expire-ttl` |

## 范围外

- 不实现多用户 session（单 token 鉴权）
- 不实现 OAuth / OIDC
- 不做 UI 重设计 / 框架迁移
- 不做 WebSocket / SSE

## 架构

```
internal/web/
  server.go           — Route 注册 + 处理器（精简）
  auth.go             — Token 鉴权 middleware
  csrf.go             — CSRF 生成 + 校验
  templates/
    index.html        — 主页面（从 server.go 移出）
  static/             — 空（未来 CSS/JS 文件）
  server_test.go      — 扩展测试

cmd/ctx-web/
  main.go             — 启动逻辑（已有，局部调整）
```

## 成功标准

1. `go build ./... && go test ./...` 通过
2. 无 token 请求 `/api/*` 返回 401
3. 有效 token 请求 `/api/*` 正常响应
4. CSRF cookie 设置 + header 校验通过
5. Photo 上传错误路径无临时文件泄漏
6. 新增 8 个 API 端点可用
7. `server_test.go` 覆盖所有端点（happy + auth fail）
8. `ctx demo run` + `ctx-web` 前端加载无回归
