# Tech Radar

Tech Radar 是一个可扩展的个人技术情报 MVP。它把“关注什么”“从哪里采集”
和“发布到哪里”分离，当前用 OpenCLI 读取 X/Reddit 登录态内容，写入 SQLite，
经过确定性评分后生成 Markdown 与 JSONL 日报。

从日报工具演进为增量内容生产平台的方案已经拆分为
[产品设计](docs/product-design.md)和[技术设计](docs/technical-design.md)，入口见
[平台设计索引](docs/platform-design.md)。

## 架构

~~~text
账号 / List / Subreddit / Query / Repo
                │ Target 配置
                ▼
 Collector 插件 ──► Signal 统一模型 ──► Processor 插件
 OpenCLI              SQLite 去重          规则评分 / LLM
 RSS / GitHub API                          聚类 / 摘要 / 翻译
                │
                ▼
 Publisher 插件 ──► Markdown / JSONL / 公众号 / 知乎 / 小红书
~~~

关键设计：

- Target 可表示账号、X List、时间线、搜索、subreddit 或任意第三方对象，数量不设上限。
- Collector、Processor、Publisher 通过显式注册表扩展，核心流水线不依赖平台名称。
- OpenCLI 能力从实时 registry 读取；采集器默认拒绝 access 不是 read 的命令。
- SQLite 以 platform + external_id 全局去重，来源关联表保留命中的全部 Target。
- Target 的 priority 会进入评分；个人红心/upvoted 默认 100，普通时间线默认 20。
- 一个 Target 可用 subjects + {subject} 扇出为多个人物、主题或社区查询。
- 质量过滤器去除过短、营销关键词和正文重复项，个人主动点赞内容不被误删。
- Top Picks 使用作者与主题配额，避免单一大号或热点垄断整份报告。
- 单个平台失败不会阻塞其他平台；fail_fast 可切换为严格模式。
- JSONL 是后续 LLM 编排、内容后台和第三方发布服务的稳定交换格式。

## 本机初始化

OpenCLI 需要 Node.js 20.18.1 或更高版本。Windows 侧安装：

~~~powershell
npm install -g @jackwener/opencli
opencli doctor
~~~

COOKIE / INTERCEPT / UI 类型的命令还需要安装 OpenCLI Chrome 扩展，并保持 X、
Reddit 登录。扩展地址：
https://chromewebstore.google.com/detail/opencli/ildkmabpimmkaediidaifkhjpohdnifk

在 WSL 中安装本项目：

~~~bash
cd /home/lism/work/xlab/python/projects/tech-radar
python3 -m venv .venv
.venv/bin/pip install -e .
cp config.example.toml config.toml
~~~

运行：

~~~bash
.venv/bin/tech-radar --config config.toml check
.venv/bin/tech-radar --config config.toml doctor
.venv/bin/tech-radar --config config.toml collect
.venv/bin/tech-radar --config config.toml publish
# 等价于 collect + publish；任一源失败仍会发布成功采集的内容
.venv/bin/tech-radar --config config.toml run
~~~

启动本地素材工作台：

~~~bash
cd /home/lism/work/xlab/python/projects/tech-radar
.venv/bin/pip install -e '.[web]'
cd web && npm install && npm run build && cd ..
.venv/bin/tech-radar --config config.toml workspace-sync
.venv/bin/tech-radar --config config.toml serve
~~~

然后在 Windows 或 WSL 浏览器访问 `http://127.0.0.1:8765`。Web 启动时会幂等地
把旧 `signals` 同步为 Material、内容指纹、Event 和 Topic；旧表不会删除。当前界面
支持 Inbox 筛选、全文搜索、素材详情、来源证据、手动加入 Topic，以及基于 Topic
生成带 Evidence ID 的规则版 Markdown 草稿。草稿默认写入
`var/artifacts/articles/<article-id>/<version-id>/article.md`，相同素材集合不会重复生成。

### 内容生产闭环

Web 工作台现在覆盖第一条可验证的本地闭环：

1. 在 Material Inbox 筛选素材、查看原始链接和来源证据，并加入 Topic。
2. 从 Topic 生成文章后，进入 `/?section=articles` 编辑；每次保存都创建不可变的新版本。
3. 审核当前版本，通过后为 Blog 与小红书创建幂等的分发任务。
4. 在 `/?section=distribution` 生成发布包并预览。Blog 产出 Markdown；小红书产出
   限长文案、3 张 PNG 卡片、manifest、内容指纹和本地去重账本。
5. 用户在真实平台完成最后发布，再填写公开 URL 和确认说明。系统只在此时把任务和
   小红书去重账本标记为 `published`，防止同一发布包重复投递。

状态流转为 `pending → prepared → previewed → published`。系统不会自动点击真实平台的
“发布”按钮，也不会把本地预览冒充为发布成功。发布产物位于
`var/artifacts/publications/<job-id>/`，小红书账本位于
`var/.publish/xhs-ledger.json`。Delivery Adapter 使用显式协议与注册表，后续可用同样的
边界接入公众号、知乎或其他发布渠道。

输出默认位于 output/daily/YYYY-MM-DD.md 与 output/jsonl/YYYY-MM-DD.jsonl，
数据库位于 var/tech-radar.sqlite3。这些运行产物不会提交到 Git。

## 添加关注对象

先从 OpenCLI 实时查询命令参数，不在代码中假设固定命令列表：

~~~powershell
opencli twitter --help
opencli twitter tweets --help
opencli reddit user-posts --help
opencli list -f json
~~~

然后在 config.toml 增加 Target。例如 X 账号：

~~~toml
[[targets]]
id = "x-datafusion"
collector = "opencli"
platform = "twitter"
command = "tweets"
arguments = ["ApacheDataFusion", "--limit", "30"]
tags = ["rust", "database", "query-engine"]
priority = 40
enabled = true
~~~

Reddit 用户：

~~~toml
[[targets]]
id = "reddit-some-engineer"
collector = "opencli"
platform = "reddit"
command = "user-posts"
arguments = ["some_engineer", "--limit", "30"]
tags = ["reddit", "database"]
priority = 40
enabled = true
~~~

你的主动选择应作为首要信号。默认配置已经加入：

~~~toml
[[targets]]
id = "x-liked"
collector = "opencli"
platform = "twitter"
command = "likes"
arguments = ["--all", "--max-pages", "10"]
tags = ["x", "personal-curation", "liked"]
priority = 100

[[targets]]
id = "reddit-upvoted"
collector = "opencli"
platform = "reddit"
command = "upvoted"
arguments = ["--limit", "100"]
tags = ["reddit", "personal-curation", "upvoted"]
priority = 100
~~~

生成的 Markdown 会把 priority >= 100 的内容放进“个人精选”，其余内容放进
“补充观察”。同一内容命中多个 Target 时只展示一次，并保留全部来源和标签。

X 关注账号较多时，优先在 X 建 List，然后用 twitter list-tweets 采集，能显著减少
命令次数与限流风险。

也可以在一个 Target 中批量跟踪人物：

~~~toml
[[targets]]
id = "x-people-watchlist"
collector = "opencli"
platform = "twitter"
command = "tweets"
arguments = ["{subject}", "--limit", "15"]
subjects = ["ClickHouseDB", "duckdb", "rustlang", "andy_pavlo"]
tags = ["people", "trusted-author"]
priority = 65
~~~

相同机制也用于 X 主题搜索、Reddit subreddit 周榜和 Reddit 主题搜索。某个 subject
失败不会丢弃已经成功采集的其他 subject；只有全部失败时该 Target 才报告失败。

## 扩展第三方平台

新增采集平台只需实现 domain.Collector 协议。仓库内插件可在 builtins.create_registry
注册；独立 Python 包可声明 tech_radar.collectors、tech_radar.processors 或
tech_radar.publishers entry point，无需修改核心项目。采集结果统一转成 Signal，
不需要修改存储、评分或发布代码。适合下一步添加：

- GitHub GraphQL / REST：release、trending、star 增量、指定组织与仓库。
- RSS/Atom：官方博客、数据库 release notes、Linux kernel mailing list。
- Hacker News、Lobsters、YouTube、arXiv 等公开数据源。
- OpenCLI 新增的网站适配器，或私有 ~/.opencli/clis 适配器。

## 扩展处理与发布

Processor 是可串联的。默认处理链包含：

- keyword-score：个人优先级、技术关键词与互动指标评分。
- topic-rule：离线主题分类、价值判断和写作角度，完全不调用外部模型。
- openai-enrich：可选的中文摘要、主题、价值判断、相关度和写作选题富化。

报告会生成“今日概览”“今日 Top Picks”“主题候选池”“值得持续关注的人”
“可写作选题”“个人精选”六个层次。
默认分页拉取 X 红心历史、采集 100 条 Reddit upvoted，并额外覆盖人物 watchlist、
六组 X 技术主题、七个 Reddit 社区周榜和六组 Reddit 技术搜索。日报最多展示
300 条，其中 Top Picks 30 条、每个主题最多 15 条、人物榜 25 人、写作候选 50 条。
可分别通过 Target 的
--all/--max-pages/--limit 以及 Publisher 的
limit、priority_read_limit、topic_candidate_limit、people_limit、
writing_candidate_limit 调整。

每个 Publisher 都有独立的 SQLite 发布账本。已经进入某次报告的内容不会再次出现；
当候选池没有新增内容时不会生成空报告。同一天出现新内容时会生成带 -02、-03
后缀的新版本，避免覆盖前一批结果。
OpenAI 富化默认关闭。启用时安装可选依赖：

~~~bash
.venv/bin/pip install -e '.[llm]'
export OPENAI_API_KEY='...'
~~~

然后在 config.toml 设置 processing.openai.enabled = true，并填写当前账号可用的
model。API key 只从环境变量读取，不写入配置或数据库。处理器通过 Responses API
Structured Outputs 严格返回固定字段；每条内容最多发送 2000 字符，不发送 Cookie、
浏览器状态或 OpenCLI 凭据。fail_open = true 时 API 暂时失败仍会生成规则版报告。
官方接口说明：https://developers.openai.com/api/docs/guides/structured-outputs

日报 Publisher 当前实现 Markdown 和 JSONL；内容工作台另有 Blog Markdown 与小红书
发布包 Delivery Adapter。小红书 Adapter 只生成经过校验、可预览的本地包，并保存
publication ledger（内容 hash、manifest、状态），由人工完成平台发布并回填 URL。
公众号和知乎仍是后续 Adapter。这样采集调度与平台登录、风控、排版变化彼此隔离。

## 测试

~~~bash
cd /home/lism/work/xlab/python/projects/tech-radar
PYTHONPATH=src python3 -m unittest discover -s tests -v
~~~

测试覆盖 OpenCLI 只读保护、字段归一化、跨 Target 去重，以及离线样本到 Markdown
的完整流水线，因此浏览器桥接未连接时也可以验证构建。

也可以直接生成一份离线演示日报：

~~~bash
.venv/bin/tech-radar --config config.demo.toml run
~~~
