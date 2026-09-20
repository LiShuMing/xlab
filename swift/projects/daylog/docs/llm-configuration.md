# LLM 配置与接口接入设计

2026-09-18：用户明确允许使用 `~/.env` 中的相关配置。本文补充 [技术设计](technical-design.md) 的 Provider、配置加载与凭据边界。

状态：已实现白名单解析、完整配置优先级、Keychain 导入、Chat Completions 客户端和日/近 7 天回顾。已用固定无业务提示验证真实接口成功。实际代码入口为 DayLog/Core/LLM.swift、Services/ConfigStore.swift、App/AppStore.swift；下文的多 Provider 等抽象仍属扩展设计。本文不记录真实密钥、地址或模型值。

## 1. 当前配置事实

本机 `~/.env` 存在，以下四项均已填写、没有重复定义，值中未发现变量展开语法：

| 变量 | 映射字段 | 设计约定 |
| --- | --- | --- |
| LLM_BASE_URL | baseURL | API 根地址，保留原有路径前缀 |
| LLM_API_KEY | credential | 认证凭据，运行时使用或导入 Keychain |
| LLM_MODEL | modelID | 请求指定的模型，不硬编码在源码中 |
| LLM_TIMEOUT | requestTimeout | 设计约定单位为秒，用作单次操作总时限 |

只记录结构观察：当前地址是 HTTPS、具有 `/v1` 结尾的 API 根路径，没有 URL 内嵌认证或 query；timeout 为 1–600 范围内数值。结构检查本身不能证明协议兼容性；本轮已另行通过真实 Chat Completions 请求验证当前配置。 秒单位是本项目约定，不是对其他程序消费同名变量方式的判断。

文件中也有其他通用 API 凭据变量；本项目只读取上述 `LLM_*` 白名单，不自动把 `OPENAI_API_KEY` 或 `API_KEY` 与此 endpoint 混用。

## 2. 配置来源与优先级

配置作为完整 profile 解析，包含 endpoint、model、credential、timeout 与 protocol。禁止从不同来源逐字段拼接，以免给一个服务发送另一个服务的凭据。

1. 用户在应用中明确选择并保存的 profile。
2. 若没有显式 profile，开发/测试进程中完整的 `LLM_*` 配置组。
3. 本机非沙盒开发模式默认读取 `~/.env` 中的完整配置组。
4. 沙盒版本尚未导入时显示“从配置文件导入”，不把无法访问当成配置为空。

高优先级来源只提供部分字段时，返回 missingFields，不从低优先级静默补齐。测试用 MockProvider 显式选择，不冒充真实模型已连接。

启动时加载一次配置快照；提供“重新载入/重新导入”。首版不监听文件变化。已开始的请求固定使用开始时的 profileRevision，新配置只影响新请求。

macOS 从 Finder/Dock 启动应用时，不应假设它继承终端的 shell 环境，因此不能只依赖 ProcessInfo.environment，更不能通过 `source ~/.env` 启动 shell 来加载配置。

## 3. 开发模式与正式 App

### 本机开发

由 DotEnvConfigLoader 只读解析真实用户 home 下的 `.env`。不将文件复制进项目，不修改该文件，不把凭据写入 Xcode scheme、Info.plist、启动参数或日志。开发时可直接在内存中使用凭据，无需本轮提前写入 Keychain。

### Sandbox App

沙盒不能假设能直接访问真实用户 home 的隐藏文件；容器中的 home 也不等于原来的 `~`。

设置页使用系统文件选择面板导入，允许显示隐藏文件。获得文件访问权后，解析完整白名单配置：当前实现把完整白名单 profile 一起写入 Keychain，保证地址、模型与密钥原子切换。导入成功后使用保存的快照，不要求持续访问原文件；首版无需为持续读取保存 security-scoped bookmark。

导入失败不覆盖现有 profile。切换 endpoint 时凭据引用要重新绑定该服务，不把旧 endpoint 的密钥隐式带过去。成功导入仍不等于连接验证成功。

## 4. Dotenv 解析约束

DotEnvConfigLoader 是纯文本解析器，不执行 shell、不执行命令替换，也不展开文件中的变量。

- 支持 UTF-8/BOM、LF/CRLF、空行、整行注释和可选 `export` 前缀。
- 按第一个 `=` 分割变量名和值；仅处理四个白名单名称，其他行忽略。
- 支持单引号、双引号；引号内 `#` 为内容。未加引号的行内注释要求 `#` 前有空白。
- 双引号转义使用明确的有限集合；不接受不完整引号或真实跨行值。
- 对白名单项检测重复定义、缺值、变量展开/命令替换语法，返回字段名与行号，不回显原文。
- URL 必须可解析且有 host；不接受 URL 内嵌用户名/密码。正式远程连接要求 HTTPS；本地 HTTP Provider 是独立配置，不通过禁用全局传输校验实现。
- API key 不允许包含 CR/LF，避免进入非法认证 header。modelID 去除外侧空白后必须非空。
- timeout 按正数秒解析，建议允许 1–600；超范围报错，不静默改写用户值。

Swift 解析器已落地，正反向案例由 DayLogChecks 验证。

## 5. Profile 与 Provider 的职责

| 类型（计划） | 职责 |
| --- | --- |
| LLMConfigResolver | 选择来源，获得完整且有效的 profile |
| DotEnvConfigLoader | 读取与解析白名单值，不涉及网络 |
| LLMProfile | profileID、profileRevision、baseURL、modelID、timeout、protocol、credentialRef、source |
| CredentialStore | 内存凭据 / Keychain 读写；禁止默认打印内容 |
| LLMProviderFactory | 按显式协议创建 Provider，避免靠模型名称猜协议 |
| OpenAICompatibleProvider | 当前 LLMClient 已实测 chat-completions；独立 Provider 类型尚未拆出 |
| ReviewService | 输入快照、请求生命周期、来源校验与草稿保存 |

`~/.env` 当前没有协议字段。当前已实测通过 OpenAI-compatible Chat Completions，首版固定使用该协议，但 `/v1` 不构成兼容性证据。必要时由设置明确选择其他协议，不盲目尝试多个 endpoint 或向另一家服务转发。

具体服务若不兼容，保留域接口和现有环境变量，新增对应 Provider；无需修改任务/日记 UI。

## 6. 接口契约

当前调用 `LLMClient.generate(config:system:prompt:test:)`，返回非空文本。下面是后续拆分 Provider 的目标契约；usage、finishReason、结构化引用暂未暴露。

| 对象 | 主要内容 |
| --- | --- |
| ReviewInput | 日期范围、任务事实、选定工作记录、sourceManifest、输出语言 |
| RequestContext | requestID、profileID/revision、deadline、取消状态 |
| GenerationResult | 草稿内容、可选来源引用、可选 usage、finishReason |
| ProviderError | configuration / authentication / modelUnavailable / timeout / cancelled / rateLimited / transport / invalidResponse |

首版采用非流式生成，减少兼容性假设。未来流式接口可返回 textDelta/completed 等事件，不迫使业务层处理各服务的 SSE 格式。

候选 Chat Completions 适配器的请求路径按根地址**追加相对资源路径**，保留网关前缀与 `/v1`。例如配置路径为 `/gateway/v1` 时，目标路径是 `/gateway/v1/chat/completions`；不能使用以 `/` 开始的相对路径意外丢弃前缀，也不重复添加 `/v1`。

配置为完整资源 URL 时返回说明或要求显式选择 URL 模式，不能再盲目追加。认证方式、请求体与响应结构必须在该 Provider 对接时验证，不假设所有模型都支持相同采样参数、结构化输出或 usage 字段。

URLSession 请求禁止自动把认证请求跟随到另一个 origin；配置选定的 endpoint 是凭据使用边界。错误映射只保留 HTTP 状态、错误类别和脱敏 requestID，默认不展示或记录服务端原始响应正文。

## 7. 超时、取消与重试

LLM_TIMEOUT 约定为整个逻辑生成操作的时限，包含网络与响应等待；当前不自动重试；不把 URLSession 的网络空闲时限误当成总时限。请求超时控制与明确的 deadline 配合，取消必须传播到实际 URLSessionTask。

配置错误、401/403、未知模型等错误不自动重试。429/临时 5xx 当前也不自动重试，用户可手动再次生成；遵守 Retry-After 的有限重试作为后续扩展。连接验证仅做一次请求。

ReviewService 使用 requestID 和 profileRevision 忽略取消后迟到的响应。连接失败只影响回顾区，任务和工作记录保持可用。

## 8. 设置页与连接验证

当前设置页只显示配置来源和连接状态；模型、地址和密钥均不回显。协议固定为 Chat Completions。

“测试连接”发送固定的无业务内容提示，并限制返回规模；不上传真实 TODO、历史记录或个人日记。成功后标记最近测试时间与 profileRevision，不把旧 profile 的测试结果沿用到新配置。

已执行固定提示的真实连接验证，成功收到有效响应；另在原生 UI 中用虚构演示任务验证生成、编辑、采纳全流程。

## 9. 验收与测试

解析测试用完全虚构值，覆盖引号、`=`、`#`、CRLF、重复项、缺项、展开语法和字段值不泄露。不得将真实 `.env` 做测试 fixture。

配置解析与优先级测试验证整组切换、不串用通用凭据变量、损坏高优先级配置不隐式回退。路径拼接已经覆盖；URLProtocol stub 的取消/超时、错误脱敏与重定向验证尚待补齐。

集成验收再检查：沙盒导入、Keychain 保存/读取、应用重启后 profile 可用、重新导入后旧请求不覆盖新结果，以及一次无业务内容的真实连接测试。
