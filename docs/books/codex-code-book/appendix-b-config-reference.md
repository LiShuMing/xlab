# 附录B：关键配置文件参考

## CLAUDE.md / AGENTS.md 的加载位置

```
优先级从低到高：
1. ~/.claude/CLAUDE.md               # 全局用户指令
2. ~/.claude/rules/*.md              # 全局规则文件
3. <project>/AGENTS.md               # 项目指令
   或 <project>/.claude/AGENTS.md
4. <project>/.claude/rules/*.md       # 项目本地规则
```

## ExecPolicy 规则文件

```
格式：Starlark（Bazel 的配置语言）
位置：<config_folder>/rules/*.rules
      ~/.codex/rules/default.rules   # 全局默认
      <project>/.claude/rules/*.rules # 项目级

示例规则：
  allow for prefix ["git", "status"]
  prompt for prefix ["npm", "publish"]
  forbid for prefix ["rm", "-rf", "/"]
  allow network "api.github.com:443" https_connect
  prompt for network "*:*" socks5_tcp
```

## 沙箱配置

```toml
# 在 codex.toml 或 config 中
[permissions]
default = "workspace"  # 或 "read-only", "danger-full-access"

[permissions.custom]
name = "my-profile"
file_system = [
    { path = ":root", access = "read" },
    { path = ":project_roots", access = "write" },
]
network = "enabled"  # 或 "restricted"
```

## 关键环境变量

| 变量 | 用途 |
|------|------|
| `CODEX_HOME` | Codex 数据和配置目录（默认 `~/.codex`） |
| `CODEX_API_KEY` | API Key 认证 |
| `CODEX_CONNECTORS_TOKEN` | MCP Connectors 认证 |
| `TMPDIR` | macOS 临时目录（沙箱可写策略会检查） |
| `EXEC_WRAPPER` | Shell Escalation 的 exec 截获 wrapper |
| `CODEX_ESCALATE_SOCKET` | Shell Escalation 的 Unix socket FD |
| `RUST_LOG` | Tracing 日志级别控制 |
| `NO_COLOR` | 禁用终端颜色输出 |

## 终端能力

```
kitty keyboard protocol → 增强按键支持（修饰键组合）
bracketed paste          → 安全粘贴（区分输入和粘贴）
true color (24-bit)      → 精确颜色渲染
OSC 9                    → 桌面通知
Synchronized Output      → 防止撕裂渲染
```
