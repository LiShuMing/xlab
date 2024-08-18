# 第9章：沙箱与安全隔离——三层防线

> 源码版本：2026-05-04
> 关键文件：`sandboxing/src/`, `linux-sandbox/src/`, `shell-escalation/src/`, `core/src/exec_policy.rs`, `core/src/network_policy_decision.rs`, `protocol/src/permissions.rs`, `protocol/src/models.rs`

---

## 9.1 安全模型的整体设计

Codex 的安全模型是一个"纵深防御"体系——不是靠单层防线，而是三层独立且互补的防护：

```
┌──────────────────────────────────────────┐
│              第三层：ExecPolicy          │
│   命令级规则引擎（.rules 文件）           │
│   Allow / Prompt / Forbidden 三级决策    │
├──────────────────────────────────────────┤
│              第二层：平台沙箱            │
│   Linux: bubblewrap + seccomp           │
│   macOS: Seatbelt (sandbox-exec)        │
│   Windows: Restricted Token + WFP       │
├──────────────────────────────────────────┤
│              第一层：权限配置            │
│   PermissionProfile → FileSystemPolicy  │
│                     + NetworkPolicy      │
│   定义"什么可以读/写/联网"               │
└──────────────────────────────────────────┘
```

三层各司其职：
- **第一层（PermissionProfile）** 定义"理论上可以做什么"——文件系统读写范围、网络是否开启
- **第二层（平台沙箱）** 在 OS 层面强制执行第一层的限制——即使 AI 生成恶意命令，OS 内核也会拦截
- **第三层（ExecPolicy）** 在命令执行前做"语义级"判断——这个命令是否危险？是否需要用户批准？

---

## 9.2 第一层：PermissionProfile——权限的"编译目标"

### 从旧到新：SandboxPolicy → PermissionProfile

Codex 的权限模型经历了一次重构。旧版 `SandboxPolicy` 是一个扁平枚举：

```rust
// protocol/src/protocol.rs:1030
pub enum SandboxPolicy {
    DangerFullAccess,                        // 无限制
    ReadOnly { network_access: bool },       // 全盘只读
    ExternalSandbox { network_access: ... }, // 外部沙箱
    WorkspaceWrite {                         // 工作目录可写
        writable_roots: Vec<AbsolutePathBuf>,
        network_access: bool,
        exclude_tmpdir_env_var: bool,
        exclude_slash_tmp: bool,
    },
}
```

新版 `PermissionProfile` 更结构化，明确区分了文件系统和网络两个维度：

```rust
// protocol/src/models.rs:304
pub enum PermissionProfile {
    Managed {
        file_system: ManagedFileSystemPermissions,
        network: NetworkSandboxPolicy,
    },
    Disabled,                                  // 不使用沙箱
    External { network: NetworkSandboxPolicy }, // 外部沙箱
}
```

核心转换方法是 `to_runtime_permissions()`：

```rust
// protocol/src/models.rs:536
pub fn to_runtime_permissions(&self) -> (FileSystemSandboxPolicy, NetworkSandboxPolicy)
```

这个方法将配置层的 `PermissionProfile` 编译为运行时可直接执行的 `FileSystemSandboxPolicy` + `NetworkSandboxPolicy`。

### FileSystemSandboxPolicy：文件系统的访问控制矩阵

```rust
// protocol/src/permissions.rs:194-202
pub struct FileSystemSandboxPolicy {
    pub kind: FileSystemSandboxKind,  // Restricted/Unrestricted/ExternalSandbox
    pub glob_scan_max_depth: Option<usize>,
    pub entries: Vec<FileSystemSandboxEntry>,
}
```

其中 `FileSystemSandboxKind` 决定整体策略级别：
- **Restricted**：按 entries 列表逐条匹配（默认）
- **Unrestricted**：全盘读写
- **ExternalSandbox**：沙箱由外部进程管理，内核层不做限制

每个 `FileSystemSandboxEntry` 描述一条路径的访问权限：
```rust
pub struct FileSystemSandboxEntry {
    pub path: FileSystemPath,           // 可以是 Path/Special/GlobPattern
    pub access: FileSystemAccessMode,   // Read/Write/None
}
```

`FileSystemPath` 支持三种形式：
- `Path { path }`：具体路径
- `Special { value }`：语义化路径（`Root`、`ProjectRoots`、`Tmpdir`、`SlashTmp`）
- `GlobPattern { pattern }`：git-style glob（仅支持 `None` 访问模式，即 deny-read）

当 `access = None` 时，表示"禁止读取此路径"——这是一种 deny-read 机制，即使在可写目录中也能保护 `.git`、`.codex`、`.agents` 等敏感元数据目录。

### WritableRoot：可写 ≠ 任意写

```rust
// protocol/src/protocol.rs:1086-1096
pub struct WritableRoot {
    pub root: AbsolutePathBuf,
    pub read_only_subpaths: Vec<AbsolutePathBuf>,  // 可写根下的只读子路径
    pub protected_metadata_names: Vec<String>,     // 受保护的元数据名
}
```

即使一个目录被标记为 writable，其中的 `.git`、`.codex`、`.agents` 目录仍然受到保护——Agent 不能修改 Git hooks 或 Codex 配置文件来提权。

### 权限的合并与相交

`policy_transforms.rs` 实现了权限的代数运算：

```rust
// sandboxing/src/policy_transforms.rs
pub fn effective_permission_profile(
    permission_profile: &PermissionProfile,
    additional_permissions: Option<&AdditionalPermissionProfile>,
) -> PermissionProfile
```

- **merge_permission_profiles**：合并两个权限集（取并集）
- **intersect_permission_profiles**：相交两个权限集（取交集，用于子 Agent 权限收缩）
- **effective_permission_profile**：将基础权限和附加权限组合为最终生效的权限

这是一个精妙的设计：父 Agent 派生子 Agent 时，子 Agent 的权限是"父权限 ∩ 请求权限"——子 Agent 永远无法获得比父 Agent 更多的权限。

### 平台沙箱的选择逻辑

```rust
// sandboxing/src/policy_transforms.rs:509-529
pub fn should_require_platform_sandbox(
    file_system_policy: &FileSystemSandboxPolicy,
    network_policy: NetworkSandboxPolicy,
    has_managed_network_requirements: bool,
) -> bool
```

判定规则：
1. 有 managed network requirements → **必须启用**
2. 网络受限 + 非 ExternalSandbox → **必须启用**
3. Restricted 文件系统 + 非全盘写 → **必须启用**
4. Unrestricted / ExternalSandbox → **不需要**

---

## 9.3 第二层：平台沙箱——OS 级强制隔离

### SandboxManager：统一的沙箱调度器

```rust
// sandboxing/src/manager.rs:132-261
pub struct SandboxManager;

impl SandboxManager {
    // 根据策略和偏好选择沙箱类型
    pub fn select_initial(&self, ...) -> SandboxType;

    // 将普通命令转换为沙箱包装后的命令
    pub fn transform(&self, request: SandboxTransformRequest) 
        -> Result<SandboxExecRequest, SandboxTransformError>;
}
```

`SandboxType` 枚举定义了平台沙箱类型：
```rust
pub enum SandboxType {
    None,
    MacosSeatbelt,
    LinuxSeccomp,
    WindowsRestrictedToken,
}
```

`transform()` 方法的核心逻辑是：将原始命令 `["git", "status"]` 转换为沙箱包装命令，如：
```
/usr/bin/sandbox-exec -p "(version 1)..." -DREADABLE_ROOT_0=/Users/... -- git status
```

### Linux：bubblewrap + seccomp 双层隔离

Linux 沙箱采用两层机制：

**文件系统层：bubblewrap（bwrap）**

bwrap 创建一个临时的文件系统命名空间，通过 bind mount 精确控制哪些目录可见、哪些可写。`linux-sandbox/src/bwrap.rs` 和 `vendored_bwrap.rs` 负责 bwrap 的启动和管理。

关键：当 WSL1 检测到需要 bwrap 但 bwrap 不可用时，会明确报错拒绝运行，而不是静默降级。

**系统调用层：seccomp BPF**

```rust
// linux-sandbox/src/landlock.rs:169-267
fn install_network_seccomp_filter_on_current_thread(
    mode: NetworkSeccompMode,
) -> Result<(), SandboxErr>
```

seccomp 过滤器是用 BPF（Berkeley Packet Filter）程序编写的，在内核层面过滤系统调用。两种模式：

| Syscall | Restricted 模式 | ProxyRouted 模式 |
|---------|----------------|------------------|
| connect/accept/bind/listen | **拒绝** | 允许（仅AF_INET） |
| sendto/sendmmsg | **拒绝** | 允许 |
| socket | 仅AF_UNIX | 仅AF_INET/AF_INET6 |
| socketpair | 仅AF_UNIX | 拒绝AF_UNIX |
| ptrace/process_vm_* | **拒绝** | **拒绝** |
| io_uring_* | **拒绝** | **拒绝** |

注意：`recvfrom` 被**故意保留**——因为 `cargo clippy` 等工具需要通过 socketpair 与子进程通信。这体现了"最小可用"而非"最小权限"的设计哲学。

**Landlock 传统路径**：`install_filesystem_landlock_rules_on_current_thread()` 使用 Linux Landlock ABI V5，全盘只读 + 指定目录读写的方式。但当前主路径是 bwrap，Landlock 仅作为遗留/备用方案。

### macOS：Seatbelt (sandbox-exec)

```rust
// sandboxing/src/seatbelt.rs
pub const MACOS_PATH_TO_SEATBELT_EXECUTABLE: &str = "/usr/bin/sandbox-exec";
```

路径被硬编码为 `/usr/bin/sandbox-exec`——这是有意为之的安全措施：阻止攻击者通过修改 PATH 环境变量注入恶意 sandbox-exec。

Seatbelt 使用 SBPL（Schema-Based Profile Language）编写策略。策略由多个片段组合而成：

```
完整的 Seatbelt 策略 = 
    base_policy           (seatbelt_base_policy.sbpl, 编译时嵌入)
  + file_read_policy     (动态生成的可读路径规则)
  + file_write_policy    (动态生成的可写路径规则)
  + deny_read_policy     (glob 转换的 deny 规则)
  + network_policy       (动态生成的网络规则)
  + platform_defaults    (restricted_read_only_platform_defaults.sbpl)
```

**文件访问策略**通过参数化的方式实现：
```rust
fn build_seatbelt_access_policy(
    action: &str,        // "file-read*" 或 "file-write*"
    param_prefix: &str,  // "READABLE_ROOT" 或 "WRITABLE_ROOT"
    roots: Vec<SeatbeltAccessRoot>,
) -> (String, Vec<(String, PathBuf)>)
```

每个根路径都被转化为 `-DREADABLE_ROOT_0=/path` 形式的参数，策略中通过 `(param "READABLE_ROOT_0")` 引用。这避免了将路径硬编码到策略文本中，也防止了路径注入。

**网络策略**根据代理配置动态生成：
- 有代理配置时：仅允许连接到代理的 loopback 端口 + DNS（53端口，用于解析代理地址）
- 无代理 + 网络开启：`(allow network-outbound) (allow network-inbound)`
- 无代理 + 网络关闭：拒绝所有网络访问

**Unix Domain Socket 控制**支持白名单模式，可以精确指定允许的 Unix socket 路径。

**Deny-Read Glob 转换**：`seatbelt_regex_for_unreadable_glob()` 将 git-style glob 模式（`**/.env`）转换为 Seatbelt 的正则表达式。因为 Seatbelt 不支持 glob，所以必须在策略生成时做翻译。

### Windows：Restricted Token + WFP

Windows 沙箱使用 Restricted Token 限制进程权限 + Windows Filtering Platform（WFP）控制网络访问。关键配置：

```rust
// protocol/src/config_types.rs
pub enum WindowsSandboxLevel {
    Disabled,
    // ...
}
```

`windows-sandbox-rs/src/` 中包含 WFP 规则安装、ConPTY 支持、进程权限控制等完整实现。

---

## 9.4 第三层：ExecPolicy——命令级语义防火墙

ExecPolicy 是三层防线中最"智能"的一层。它不是简单的 yes/no，而是一个完整的规则引擎。

### 规则系统：`.rules` 文件的加载与合并

```rust
// core/src/exec_policy.rs:572-629
pub async fn load_exec_policy(config_stack: &ConfigLayerStack) -> Result<Policy, ExecPolicyError>
```

规则文件（`.rules` 扩展名）从多个 ConfigLayer 加载，按优先级从低到高：
1. 全局层（用户级 `~/.codex/rules/`）
2. 项目层（`<project>/.claude/rules/`）
3. 需求层（`requirements().exec_policy`）

高优先级层的规则可以覆盖低优先级层。最终通过 `parser.build()` 编译为 `Policy` 对象。

### 决策引擎：Allow / Prompt / Forbidden

```rust
// core/src/exec_policy.rs:272-379
pub(crate) async fn create_exec_approval_requirement_for_command(
    &self, req: ExecApprovalRequest<'_>,
) -> ExecApprovalRequirement
```

对每个命令的处理流程：

```
1. 命令解析：shell_c 解析 → 提取多个逻辑命令
   "bash -c 'cd /x && git push'" → ["cd /x", "git push"]

2. 规则匹配：
   ├─→ PrefixRule 匹配（精确前缀/glob）
   ├─→ NetworkRule 匹配（域名+协议）
   └─→ 未匹配 → heuristics fallback

3. 决策：
   ├─→ Forbidden: 禁止执行，返回原因
   ├─→ Prompt: 需要用户批准
   └─→ Allow: 
       ├─→ bypass_sandbox = true  → 不套沙箱
       └─→ bypass_sandbox = false → 在沙箱内执行
```

### 未匹配命令的启发式判断

```rust
// core/src/exec_policy.rs:632-745
pub(crate) fn render_decision_for_unmatched_command(
    command: &[String],
    context: UnmatchedCommandContext<'_>,
) -> Decision
```

当一个命令没有被任何 `.rules` 规则匹配到时，ExecPolicy 使用启发式判断：

1. **已知安全命令白名单**：`is_known_safe_command(command)` — 如 `ls`, `cat`, `echo`, `pwd` 等 → **Allow**
2. **危险命令检测**：`command_might_be_dangerous(command)` — 如 `rm -rf /`, `curl | sh` 等 → **Prompt**
3. **沙箱存在**：如果沙箱足够强（Restricted + 全盘读），非危险命令 → **Allow**
4. **无沙箱保护** + 非危险命令 → 取决于 `AskForApproval`：
   - `OnRequest` + Unrestricted → **Allow**（用户说"直接执行"）
   - `UnlessTrusted` → **Prompt**
   - `Never` → **Allow**（信任沙箱保护）

关键注释：
```rust
// exec_policy.rs:654-663
// On Windows, ReadOnly sandbox is not a real sandbox, so special-case it here.
let environment_lacks_sandbox_protections = cfg!(windows)
    && profile_is_managed_read_only(...);
```

Windows 上的 ReadOnly 沙箱不是"真正的沙箱"，所以需要特殊处理——没有沙箱保护时，危险命令必须经过 Prompt。

### 自动修正建议：用户"记住"的智能实现

当用户批准一个需要 Prompt 的命令后，ExecPolicy 可以自动生成修正建议：

```rust
// core/src/exec_policy.rs:817-857
fn try_derive_execpolicy_amendment_for_prompt_rules(
    matched_rules: &[RuleMatch],
) -> Option<ExecPolicyAmendment>
```

如果 Prompt 是由启发式触发的（而非用户明确规则），系统会建议将这条命令的前缀（如 `["python3"]`）添加到 allow 列表中。但如果任何 Prompt 来自显式规则，则不会建议修正——因为那是用户有意设置的策略。

`BANNED_PREFIX_SUGGESTIONS` 列表包含了 99 个永远不应该被自动建议的命令前缀，如 `python3 -c`、`bash -lc`、`sudo`、`osascript` 等——这些是可以绕过沙箱或执行任意代码的命令入口，自动将它们加入 allowlist 会严重降低安全性。

### 网络规则

ExecPolicy 还支持按域名和协议的网络规则：

```rust
// core/src/exec_policy.rs:431-475
pub(crate) async fn append_network_rule_and_update(
    &self, codex_home: &Path, host: &str,
    protocol: NetworkRuleProtocol, decision: Decision, ...
)
```

当 Agent 尝试访问一个被网络策略拦截的域名时，用户可以"记住"这个决定——允许或拒绝后续访问。

---

## 9.5 Shell Escalation：当沙箱"不够用"时

有些命令确实需要突破沙箱限制才能正常工作——例如需要访问 `/var/run/docker.sock` 的 docker 命令。这时 shell escalation 机制介入。

### 架构：Server-Client 模式

```rust
// shell-escalation/src/unix/escalate_protocol.rs
pub const ESCALATE_SOCKET_ENV_VAR: &str = "CODEX_ESCALATE_SOCKET";
pub const EXEC_WRAPPER_ENV_VAR: &str = "EXEC_WRAPPER";
```

工作原理：
1. **Escalation Server** 在沙箱外启动，监听 Unix datagram socket
2. **Shell Wrapper** 通过 `EXEC_WRAPPER` 环境变量注入到沙箱内的 shell 中
3. 当 shell 尝试 `exec()` 一个被沙箱拦截的二进制时，wrapper 截获调用，通过 socket 发送 `EscalateRequest` 给 server
4. Server 根据 `EscalationPolicy` 返回决策：`Run`（允许）/ `Escalate`（提权执行）/ `Deny`（拒绝）

### 决策类型

```rust
pub enum EscalationDecision {
    Run,                          // 在沙箱内执行
    Escalate(EscalationExecution), // 在沙箱外执行
    Deny { reason: Option<String> },
}

pub enum EscalationExecution {
    Unsandboxed,                  // 完全无沙箱
    TurnDefault,                  // 使用当前 Turn 的默认沙箱配置
    Permissions(EscalationPermissions), // 使用指定的权限配置
}
```

---

## 9.6 网络沙箱：代理驱动的访问控制

```rust
// core/src/network_policy_decision.rs
pub(crate) fn network_approval_context_from_payload(
    payload: &NetworkPolicyDecisionPayload,
) -> Option<NetworkApprovalContext>
```

网络沙箱通过代理实现：
- **HTTP 代理**（`network-proxy/src/http_proxy.rs`）：MITM 代理，可以检查/拦截 HTTP 请求
- **SOCKS5 代理**（`network-proxy/src/socks5.rs`）：TCP 和 UDP 级别的代理

当网络请求被拦截时，`denied_network_policy_message()` 生成用户友好的错误消息：
```rust
match blocked.reason.as_str() {
    "denied" => "domain is explicitly denied by policy...",
    "not_allowed" => "domain is not on the allowlist...",
    "not_allowed_local" => "local/private network addresses are blocked...",
    "method_not_allowed" => "request method is blocked...",
    "proxy_disabled" => "network proxy is disabled",
    ...
}
```

---

## 9.7 安全数据流：一次 Shell 命令执行的完整安全路径

结合三层防线，一次 `shell git push` 的完整安全检查流程：

```
1. PermissionProfile.to_runtime_permissions()
   → FileSystemSandboxPolicy { kind: Restricted, entries: [cwd=Write, /=Read] }
   → NetworkSandboxPolicy::Restricted

2. SandboxManager.transform()
   → SandboxType::MacosSeatbelt (或 LinuxSeccomp)
   → 命令从 ["git", "push"] 变成 ["/usr/bin/sandbox-exec", "-p", "...", "--", "git", "push"]

3. ExecPolicyManager.create_exec_approval_requirement_for_command()
   → "git" 是已知安全命令 → Decision::Allow
   → bypass_sandbox = false (在沙箱内执行)

4. 执行:
   → seatbelt 限制文件写入只能在 cwd
   → 网络策略允许 git 通过代理访问远程
   → 如果 git 尝试写 ~/.ssh/ → seatbelt 拦截
```

---

## 9.8 类比 OS 视角

| OS 安全机制 | Codex 安全体系 |
|------------|---------------|
| 文件系统权限 (rwx) | FileSystemSandboxPolicy (Read/Write/None per entry) |
| seccomp / pledge | Linux seccomp BPF / macOS Seatbelt SBPL |
| chroot / namespace | Linux bubblewrap |
| sudo + timestamp | ExecPolicy + ApprovedCommandPrefixSaved |
| firewall (iptables) | NetworkProxy + NetworkPolicy |
| capabilities | EscalationPolicy (细粒度提权) |
| MAC (SELinux/AppArmor) | WritableRoot.protected_metadata_names |
| setuid | shell-escalation EXEC_WRAPPER |

---

## 9.9 本章要点

1. **三层纵深防御**：PermissionProfile（权限定义）→ 平台沙箱（OS 级隔离）→ ExecPolicy（语义级规则引擎）。
2. **PermissionProfile 是核心抽象**：新版 `Managed/Disabled/External` 三个变体，通过 `to_runtime_permissions()` 编译为可执行的沙箱策略。
3. **子 Agent 权限只减不增**：通过 `intersect_permission_profiles` 实现权限收缩。
4. **Linux 双隔离**：bubblewrap（文件系统）+ seccomp BPF（系统调用），seccomp 有 Restricted 和 ProxyRouted 两种模式。
5. **macOS Seatbelt 策略组合**：base + file-read + file-write + deny-read + network + platform_defaults 六层片段。
6. **ExecPolicy 三级决策**：Allow/Prompt/Forbidden，未匹配命令有完整的启发式后备逻辑。
7. **Shell Escalation 是受控的"沙箱逃逸"**：通过 EXEC_WRAPPER 截获 exec() 调用，server-client 模式做提权决策。
8. **安全是纵深防御，不是单点**：每层都有 fallback，每层都可能失败——但三层组合起来提供了实际有效的保护。
