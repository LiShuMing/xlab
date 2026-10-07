# Tech Radar 内容工作台：产品设计文档

状态：Draft for review
版本：0.2
日期：2026-10-07
目标读者：产品设计、内容运营、技术实现

## 1. 产品定义

Tech Radar 是一个面向技术创作者的本地优先内容工作台。它持续收集用户关注的
X、Reddit、GitHub、RSS 和其他技术来源，将重复信息合并为事件，沉淀到 Topic
素材池，并帮助用户把新增证据转化为 Blog、小红书、公众号和知乎内容。

它不是资讯阅读器，也不是一次性 LLM 写作工具。产品的核心对象是：

```text
Source -> Material -> Event -> Topic -> Article -> Publication
```

所有自动化最终都要回答三个问题：

1. 今天真正新增了什么？
2. 它和历史素材相比有什么新信息？
3. 哪篇文章应该因此新建或更新？

## 2. 用户与使用场景

### 2.1 初始用户

第一阶段服务单个高级技术创作者：

- 长期跟踪数据库、C++、Rust、Linux、存储、硬件和 AI Infra。
- 每天面对数百条候选，但只希望处理真正新增且可写的内容。
- 需要保留原文、上下文和证据，不接受无来源的 LLM 总结。
- 同一素材要能够派生 Blog、公众号、知乎和小红书版本。
- 希望自动化准备草稿，但保留最终编辑和发布决定。

### 2.2 后续用户

- 小型技术内容团队。
- 开源项目 DevRel 或产品团队。
- 数据库、Infra、AI 方向的研究和竞争情报团队。

第二阶段才考虑成员、权限、任务所有者和共享审核。

## 3. 用户问题

| 问题 | 当前代价 | 产品响应 |
|---|---|---|
| 来源分散 | 多个平台重复浏览 | 统一 Sources 和 Inbox |
| 转帖和复述多 | 同一事件反复阅读 | Event Cluster 合并 |
| 不知道什么是新增 | 日报每天重新开始 | Topic Delta 和历史对比 |
| 写作缺乏证据链 | LLM 容易泛化或幻觉 | Claim 到 Material 的引用 |
| 多平台重复改写 | 每个平台重新整理 | 一篇母稿，多平台 Adapter |
| 发布状态分散 | 容易漏发或重复发 | Distribution Center 和 Ledger |
| 自动化过程不可见 | 失败后难以恢复 | Activity、Runs 和阶段状态 |

## 4. 产品原则

### 4.1 Signal over noise

默认界面突出“新增、重要、需要处理”，而不是展示所有数据。历史内容可以搜索，
但不占据每日工作面。

### 4.2 Context stays attached

任何摘要、Topic、文章段落和发布版本都能回到原始 Material 和上下文。搜索结果
打开时回到具体事件，而不是只显示孤立文本。

### 4.3 Automation is reviewable

自动动作必须留下状态、输入、输出和原因。系统可以持续工作，但人工拥有最终方向
和发布决定。

### 4.4 One object, one owner, one state

第一阶段虽然只有单用户，仍然明确每个 Material、Article 和 Publication 的状态。
后续增加团队时可以自然扩展 owner 和 reviewer，而不用重写工作流。

### 4.5 Extensibility is visible

素材源和发布平台不是隐藏在配置文件中的实现细节。产品界面要展示插件能力、连接
状态、增量游标、最近运行和可用动作。

## 5. 对 Raft 的参考与边界

参考 [Raft](https://raft.build/) 的不是品牌样式，而是工作组织方式：

- 一个共享 Workspace 承载不同类型的工作对象。
- 左侧稳定导航，减少在不同工具间切换。
- Activity 集中展示“离开期间发生了什么”。
- Task 状态和 owner 避免同一工作被重复执行。
- Search 可以跳回原始上下文，而不是只返回摘要。
- 通知保持安静，只在确实需要人工处理时打断。

Tech Radar 不复制聊天频道模型。内容平台的中心对象是 Material 和 Article，因此主
界面采用“导航 + 素材流 + 证据详情”三栏结构，Conversation 只作为将来的协作能力。

## 6. 信息架构

```text
Workspace
├── Activity             今日新增、失败、待审核
├── Materials
│   ├── Inbox            未处理素材
│   ├── Accepted         已接受素材
│   ├── Duplicates       重复与聚类结果
│   └── Rejected         被过滤内容
├── Topics
│   ├── Database
│   ├── Storage
│   ├── Linux
│   ├── C++
│   └── Rust
├── Articles
│   ├── Candidates       待生成
│   ├── Drafts           草稿
│   ├── Review           待审核
│   └── Published        已发布母稿
├── Distribution
│   ├── Blog
│   ├── Xiaohongshu
│   ├── WeChat
│   └── Zhihu
├── Sources              素材源与连接
├── Extensions           Collector/Publisher 插件
├── Runs                 采集和生成运行记录
└── Settings             Topic、质量、调度、模型
```

## 7. 核心页面

### 7.1 Activity

回答“我离开期间发生了什么”。默认只显示：

- 每个 Topic 的新增 Event 数量。
- 新出现的高优先级个人红心或点赞。
- 已生成、等待审核的文章版本。
- Source 或 Publication 的失败。
- 需要人工确认的小红书 Preview。

支持 All、Unread、Needs review 三个过滤器。常规采集成功不产生通知，只进入
Activity；只有失败、审核和人工发布确认触发提醒。

### 7.2 Material Inbox

这是产品的主工作面，采用三栏布局。

左栏：Workspace 导航和 Topic 快捷入口。
中栏：素材流、过滤器和批量操作。
右栏：当前素材详情和证据上下文。

Material Card 最小展示：

- 标题或首段。
- 来源平台、作者、发布时间。
- 新增、更新、重复或个人精选状态。
- Topic、质量分、novelty、互动指标。
- Event 内的来源数量。
- 是否已被文章消费。

右侧详情展示：

- 原始链接和完整正文。
- 命中的 Target、关键词和可信作者权重。
- 去重指纹和合并理由。
- Event 内其他来源。
- Topic 路由及置信度。
- 已引用该 Event 的文章版本。
- 接受、拒绝、合并、移动 Topic、加入选题动作。

### 7.3 Topic Room

每个 Topic 是长期工作空间，不是临时标签页。

```text
Topic Header
├── 今日新增 / 未消费 / 本周趋势
├── Writing Policy
├── Trusted Sources
└── Generate Draft

Topic Body
├── Delta Feed
├── Event Clusters
├── Article Candidates
└── Living Articles
```

用户可以看到一条 Event 为什么进入 Topic，以及它相对于已有文章的新增信息。

### 7.4 Article Studio

采用“结构/正文/证据”三部分：

- Outline：章节、claim、未解决问题。
- Editor：母稿 Markdown 和版本差异。
- Evidence：当前段落引用的 Event 和原始 Material。

关键动作：

- 使用选中增量生成新文章。
- 为 Living Article 创建增量版本。
- 接受或拒绝 LLM 建议。
- 查看两个版本的 material set 差异。
- 检查无证据 claim。
- 批准母稿进入 Distribution。

### 7.5 Distribution Center

每一行对应 `ArticleVersion x Platform`：

| 平台 | Artifact | 状态 | 最后动作 | 下一动作 |
|---|---|---|---|---|
| Blog | Markdown/HTML | ready | 构建通过 | Publish |
| 小红书 | copy + images | previewed | 已打开预览 | 人工发布 |
| 公众号 | draft | prepared | 已写入草稿箱 | 人工审核 |
| 知乎 | draft | failed | 登录失效 | Retry |

平台 Adapter 必须公开它支持 prepare、preview、draft、publish 中的哪些能力。界面
不能显示插件并不支持的动作。

### 7.6 Sources

Sources 不是简单账号列表，而是可观测的增量输入：

- 插件、Target 类型和连接状态。
- 最近成功时间、当前 cursor、重叠窗口。
- 最近新增、更新、重复、过滤数量。
- 预计每日调用量和最近错误。
- Test connection、Run now、Pause、Edit。

新增 Source 时由插件提供配置 schema，Web 自动生成表单，不在前端硬编码 X、Reddit
或 GitHub 字段。

### 7.7 Extensions

展示两类扩展：

- Source Connector：采集、增量游标、认证和能力。
- Delivery Adapter：渲染、验证、预览和发布能力。

每个 Extension 展示版本、来源、权限、配置项、最近运行、健康状态和升级兼容性。
第一阶段只加载本地受信任 Python 包，不提供远程插件市场。

## 8. Material 工作流

```text
New -> Accepted -> Clustered -> Routed -> Consumed
   \-> Duplicate
   \-> Rejected
   \-> Needs review
```

默认自动处理：

- 精确重复直接进入 Duplicate。
- 高置信度 Event 合并自动完成。
- 高质量且 Topic 置信度高的素材自动 Accepted/Routed。

需要人工处理：

- 两个 Event 的合并置信度接近阈值。
- 高优先级个人精选被质量规则拒绝。
- 同时命中多个竞争 Topic。
- 来源可信度不足但传播热度很高。

## 9. Article 工作流

```text
Candidate -> Drafting -> Review -> Approved -> Distributed
                  \-> Failed
```

Candidate Policy 根据新增 Event 数、novelty、个人精选和重要 Release 触发。用户可以
调整阈值，但产品不会为了“每日有文章”而强制生成低质量内容。

三类内容：

- Daily Digest：Topic 当日新增摘要。
- Deep Dive：围绕一个高价值 Event 的独立文章。
- Living Article：长期主题的增量版本。

## 10. 搜索与命令入口

全局 `Ctrl+K` 搜索 Material、Event、Topic、Article、Source 和 Run。搜索结果打开
时进入对象的上下文位置，保留过滤器和选中状态。

命令入口支持：

- Run source now
- Move to topic
- Create article candidate
- Compare article versions
- Prepare for platform
- Retry failed job

第一阶段不提供自然语言执行不可逆发布动作。

## 11. 批量操作

Material Inbox 支持多选：

- Accept / Reject。
- Move to Topic。
- Merge into Event。
- Add to Article Candidate。
- Mark reviewed。

批量操作先显示影响范围。Merge、Reject 和 Publication 状态修改写入 audit log，并
支持通过反向操作恢复，不直接删除原始 Material。

## 12. Web 视觉与交互方向

### 12.1 视觉语言

- 桌面优先，适配 1280px 到 1920px；窄屏退化为列表加抽屉。
- 高信息密度，但只使用一个主要强调色。
- 状态使用文字、图标和颜色共同表达。
- 内容本身优先于统计卡片，不构造无行动价值的 Dashboard。
- 列表滚动时保留导航、筛选和详情上下文。

### 12.2 Raft-inspired 但内容优先

- 使用 Raft 式 Workspace 导航和 Activity 汇总。
- 将 Channel 替换为 Topic Room。
- 将 Task Board 替换为 Article Pipeline。
- 将 Thread Context 替换为 Event Evidence。
- 将 Agent 状态替换为 Source/Run/Composer 状态。

### 12.3 响应式行为

- >= 1200px：三栏 Material Workspace。
- 768–1199px：导航折叠，中栏 + 右侧详情。
- < 768px：单列，详情以全屏 Sheet 打开，只提供审核和阅读能力。

移动端不承担复杂文章编辑和 Extension 配置。

## 13. 产品限制

- 第一阶段是本地单用户产品，没有成员和权限体系。
- OpenCLI 来源需要本机浏览器登录态，无法保证无人值守长期运行。
- X/Reddit 内容可能被删除、限流或变为私有。
- LLM 分类和写作是建议，不能替代来源验证。
- 小红书只能自动准备和预览，最终发布保留人工操作。
- 插件运行在主进程内，第一阶段只允许安装受信任扩展。
- 离线时只能访问已缓存的素材和 artifact。

## 14. MVP 范围

### Must have

- Activity、Material Inbox、Topic Room、Article Studio、Distribution、Sources、Runs。
- X/Reddit 现有 Collector 可见化。
- 精确、URL、内容和 Event 去重结果可解释。
- Topic 增量和素材消费状态。
- Blog artifact 与小红书 preview artifact。
- 全局搜索、批量审核和失败重试。

### Should have

- GitHub Release、RSS Connector。
- Living Article 版本差异。
- Source/Publisher 配置 schema 自动表单。
- SSE 运行进度。

### Later

- 团队、owner、reviewer、评论和通知。
- 远程部署、多 Worker 和 PostgreSQL。
- Extension Marketplace 和进程隔离。
- 移动端完整编辑。

## 15. 成功指标

- 每日新增素材中重复内容占比下降。
- 从打开 Inbox 到完成当日审核的时间。
- 进入文章的 Material 中具备有效来源的比例。
- 每篇文章的新增 Event 比例。
- 草稿被人工接受、修改、拒绝的比例。
- 重复发布次数必须为零。
- Source 失败恢复时间和 daily run 成功率。

不以“每天生成多少篇文章”作为核心指标，避免激励低质量输出。

## 16. 产品实施顺序

1. 先实现 Application Service、增量模型和审计状态。
2. 建立只读 Web Shell、Activity、Materials、Topics、Runs。
3. 加入 Material 审核、批量操作和 Article Candidate。
4. 加入 Article Studio 和证据链。
5. 加入 Distribution、Blog 和小红书 Preview。
6. 最后加入 Extension 配置 UI 和每日调度管理。

Web 界面不是数据库 CRUD 外壳；只有底层状态语义稳定后才开放写操作。

## 17. 产品验收

- 用户在一个界面内完成“发现新增 -> 判断价值 -> 加入 Topic -> 生成文章 -> 准备发布”。
- 任意摘要或文章 claim 都能回到原始 Material。
- 同一 Event 不会在 Inbox 中以多个独立候选出现。
- 用户可以解释一条 Material 为什么进入某个 Topic、为什么被过滤或合并。
- Source 和 Publication 失败可以局部重试，不重跑整个系统。
- 新增 Connector 或 Delivery Adapter 不需要修改 Material、Topic 或 Article 页面。

## 18. 参考资料

- [Raft 产品主页](https://raft.build/)
- [Raft：Divide the work](https://docs.raft.build/divide-the-work/)
- [Raft：Catch up in one place](https://docs.raft.build/catch-up-in-one-place/)
- [Raft：Search your raft](https://docs.raft.build/search-your-raft/)
- [Raft：Get pinged when it matters](https://docs.raft.build/get-pinged-when-it-matters/)
