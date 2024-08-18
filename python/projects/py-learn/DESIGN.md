## 每日精进 Agent — Python + Telegram Bot + SQLite

> 版本 v0.1 · 设计阶段 · 未涉及实现

---

## 一、系统目标

构建一个**全自动、可持久化、自适应**的每日学习 Agent，覆盖以下6个知识领域：

| 编号 | 领域 | 核心范围 |
|---|---|---|
| D1 | 语言精通 | C++ / Java 语言底层与工程实践 |
| D2 | 算法解题 | OI-wiki 全结构体覆盖 |
| D3 | Linux 精通 | OS / BPF / 高性能计算 |
| D4 | OLAP / 数据库 | 优化器、执行引擎、AI 计算框架 |
| D5 | 大规模架构 | 系统设计、技术管理 |
| D6 | 前沿追踪 | WASM / AI / BPF / VLDB / SIGMOD |

**核心质量要求**：每道题必须足以支撑架构师级别面试或技术评审场景的深度思考，不出知识点罗列题，只出需要推理和 tradeoff 的题。

---

## 二、整体架构

```
┌─────────────────────────────────────────────────────┐
│                   Scheduler（定时触发）               │
│               每天 08:00 cron / APScheduler           │
└────────────────────────┬────────────────────────────┘
                         │
              ┌──────────▼──────────┐
              │    Harness Agent    │
              │   Plan → Tool →     │
              │   Generate → Push   │
              │   → Collect →Reflect│
              └──────────┬──────────┘
          ┌──────────────┼──────────────┐
          │              │              │
   ┌──────▼──────┐ ┌─────▼──────┐ ┌───▼────────┐
   │  知识图谱    │ │  Memory DB │ │  热点爬虫  │
   │ topics.yaml │ │  SQLite    │ │ (每周一次) │
   └─────────────┘ └─────┬──────┘ └────────────┘
                         │
              ┌──────────▼──────────┐
              │   Telegram Bot      │
              │   推送题目 / 收答案  │
              │   /hint /skip 命令  │
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────┐
              │   Reflect Engine    │
              │   LLM 评分 + 写回   │
              │   Memory DB         │
              └─────────────────────┘
```

---

## 三、模块详细设计

### 3.1 Scheduler — 定时触发

**职责**：在每天固定时间启动 Agent 主流程。

**设计要点**：
- 使用 APScheduler（持久化 job store），进程重启不丢任务
- 支持时区配置（Asia/Tokyo）
- 主流程与 Telegram 收发分离，互不阻塞
- 超时机制：推送后 24h 未作答自动标记 `status=timeout`

**触发时间建议**：
- 08:00 — 推送当日题目
- 20:00 — 若未作答，发送一次提醒（可配置关闭）
- 23:30 — 超时收口，写入 timeout 记录

---

### 3.2 Plan — 出题规划器

**职责**：决定今天出什么领域、什么 topic、什么难度、什么题型。

#### 领域轮转策略

```
Mon → D1 语言精通
Tue → D2 算法解题
Wed → D3 Linux 精通
Thu → D4 OLAP / 数据库
Fri → D5 大规模架构
Sat → D6 前沿追踪
Sun → 综合复盘（薄弱点专项）
```

特例：若某领域近7天正确率 < 50%，下一个该领域的出题日自动注入额外薄弱点权重，加大相关 topic 的出现概率，而不打乱轮转节奏。

#### Topic 选择算法

```
score(topic) = base_weight(topic)
             + weak_bonus(topic)      # 历史正确率低 → 加分
             - recency_penalty(topic) # 最近出过 → 减分
             + frontier_bonus(topic)  # 本周有热点更新 → 加分

选择：weighted_random_choice(topics, score)
```

#### 难度自适应

| 条件 | 动作 |
|---|---|
| 该 topic 连续2次得分 ≥ 9 | 下次升一级（L2→L3→L4） |
| 该 topic 连续2次得分 ≤ 4 | 下次降一级 |
| 首次出题 | 默认 L3 |
| 周日复盘 | 固定取本周最低分 topic，难度不变 |

#### 题型选择

每个领域有默认题型偏好，同时加入随机性避免单调：

| 领域 | 主题型 | 备选题型 |
|---|---|---|
| D1 语言 | 深度概念题 | 找错/Debug题 |
| D2 算法 | 白板实现题 | Tradeoff分析题 |
| D3 Linux | 系统分析题 | Tradeoff分析题 |
| D4 OLAP | Tradeoff分析题 | 系统设计题 |
| D5 架构 | 系统设计题 | 管理决策题 |
| D6 前沿 | 论文评述题 | 深度概念题 |

---

### 3.3 Tool Use — 工具层

#### Tool 1：KnowledgeGraphTool

- 数据源：`topics.yaml`，静态结构，人工维护
- 结构：领域 → topic → subtopic → 关键考察点列表
- 输出：给 LLM 的 context，包含该 topic 的考察维度提示
- 更新频率：手动，每月或有新论文时补充

#### Tool 2：MemoryReader

- 数据源：SQLite `topic_memory` 表
- 输出：该 topic 历史得分列表、上次出题时间、薄弱点标记
- 用途：注入 Plan 的 score 函数 + 注入 Generate 的 prompt context

#### Tool 3：HotTopicCrawler（每周一次）

- 抓取源：
  - LWN.net（Linux 内核动态）
  - VLDB / SIGMOD proceedings（新论文标题+摘要）
  - ClickHouse / DuckDB / StarRocks blog
  - GitHub trending（Rust / C++ / Go 方向）
- 输出：热点摘要列表，写入 SQLite `hot_topics` 表
- 用途：D6 前沿追踪领域的出题素材，以及其他领域的"时效性延伸"

#### Tool 4：ConversationHistoryReader

- 读取最近10次对话摘要（SQLite `conversations` 表）
- 防止重复出相同题目
- 辅助 Reflect 做跨题知识关联

---

### 3.4 Generate — 题目生成

**输入**：Plan 的决策结果 + 三个 Tool 的 context

**Prompt 结构（System Prompt 固定部分）**：

```
你是一位资深架构师导师，专注大数据/OLAP/OS/高性能计算领域。
学员背景：10年工程师，C++/Java/Go/Python，目标成为架构师。
出题原则：
  - 不出知识点罗列题，只出需要推理和 tradeoff 的题
  - 每题必须包含：主问题 / 考察意图 / 追问预案 / 参考资料
  - 难度锚定：L4 = 能在 VLDB 论文中找到对应讨论的深度
```

**输出格式**（结构化，便于解析）：

```yaml
question:
  main: "..."          # 主问题正文
  intent:              # 考察意图（用于评分，不推送给用户）
    - "..."
  followups:           # 追问预案
    - trigger: "若答出X"
      prompt: "追问：..."
    - trigger: "若遗漏Y"
      prompt: "提示：..."
  extension: "..."     # 跨域延伸题
  references:          # 精准参考
    - "..."
```

**防退化机制**：
- 连续3次同领域题目必须换 topic
- 若生成结果中 `main` 字段字数 < 50，视为出题失败，重试（最多3次）
- 题目生成后存入 `pending_questions` 表，推送前可人工审阅（可选 flag）

---

### 3.5 Telegram Bot — 交互层

#### 消息类型设计

**推送消息（Bot → 用户）**：

```
━━━━━━━━━━━━━━━━━━━━
📚 今日精进 · Thu · OLAP/数据库 · L4

Cascades 优化器在处理 Join Reorder 时，
如何利用 Memo 结构避免等价变换的重复
计算？请从 Group / Expression / Winner
三个核心概念展开。

━━━━━━━━━━━━━━━━━━━━
可用命令：
/hint   — 获取一次提示（-1分）
/skip   — 跳过今日题目
/status — 查看本周进度
```

**用户回答**：直接发送文本，任意长度均可

**评分消息（Bot → 用户，回答后触发）**：

```
━━━━━━━━━━━━━━━━━━━━
📊 评分结果

概念准确性   ██████░░░░  6/10
系统深度     ████░░░░░░  4/10
边界思考     ███████░░░  7/10
─────────────────────
总分：7.2 / 10

✅ 答得好的部分：...
⚠️  遗漏的关键点：Enforcer 机制 / 
   Physical Properties 传播
📖 标准答案摘要：...
🔗 参考：Volcano/Cascades论文 §3.2
━━━━━━━━━━━━━━━━━━━━
```

#### 命令列表

| 命令 | 功能 |
|---|---|
| `/hint` | 触发一次追问提示，当日题目扣 1 分 |
| `/skip` | 跳过当日，记录为 skip，不影响 topic 权重 |
| `/status` | 展示本周7天的出题/得分/薄弱点摘要 |
| `/history [n]` | 查看最近 n 条题目和得分 |
| `/weak` | 列出当前所有薄弱点 topic |
| `/topic [名称]` | 强制指定下一次出题的 topic |
| `/level [L2/L3/L4]` | 临时覆盖下一次难度 |

---

### 3.6 Reflect — 评估引擎

**触发时机**：用户发送回答文本后，立即异步触发

**评分 Prompt 设计**：

```
【题目】{question.main}
【考察意图】{question.intent}（这是你的评分标准，不要透露给用户）
【用户回答】{user_answer}

请按以下维度评分，输出 JSON：
- concept_score (0-3)：概念准确性
- depth_score (0-4)：系统深度，是否触及实现原理
- boundary_score (0-3)：边界思考，是否讨论 tradeoff / 失效场景
- total: concept + depth + boundary
- strengths: [...] # 答得好的点
- gaps: [...]      # 遗漏的关键点
- summary: "..."   # 标准答案摘要（150字以内）
- followup: "..."  # 若用户想继续深入，推荐追问的方向
```

**写回 Memory DB**：

```sql
INSERT INTO topic_scores (topic_id, date, score, gaps)
UPDATE topic_stats SET
  avg_score = ...,
  attempt_count = attempt_count + 1,
  last_attempt = TODAY,
  is_weak = (avg_score < 6.0)
```

**触发专项复习规则**：
- 同一 topic 3次得分均 < 5 → `is_weak = TRUE`，加入高权重池
- 周日复盘日强制从 `is_weak = TRUE` 的 topic 中选题
- 当 `is_weak` topic 连续2次得分 ≥ 8 → 解除薄弱标记

---

## 四、数据库设计

### SQLite Schema

```sql
-- 领域和 topic 定义（从 topics.yaml 初始化导入）
CREATE TABLE domains (
  id TEXT PRIMARY KEY,        -- 'lang', 'algo', 'os', ...
  label TEXT,
  rotation_day INTEGER        -- 0=Sun,1=Mon,...
);

CREATE TABLE topics (
  id TEXT PRIMARY KEY,        -- 'cpp_memory_model'
  domain_id TEXT,
  name TEXT,
  level_default INTEGER,      -- 2/3/4
  tags TEXT                   -- JSON array: ["面试高频","L3"]
);

-- 每次出题记录
CREATE TABLE questions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  date TEXT,                  -- '2026-04-07'
  topic_id TEXT,
  level INTEGER,
  qtype TEXT,
  question_json TEXT,         -- 完整题目结构（JSON）
  status TEXT                 -- 'pending'/'answered'/'timeout'/'skip'
);

-- 每次作答和评分
CREATE TABLE answers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  question_id INTEGER,
  answer_text TEXT,
  concept_score REAL,
  depth_score REAL,
  boundary_score REAL,
  total_score REAL,
  gaps_json TEXT,             -- JSON array
  summary TEXT,
  created_at TEXT
);

-- topic 聚合统计（实时更新）
CREATE TABLE topic_stats (
  topic_id TEXT PRIMARY KEY,
  attempt_count INTEGER DEFAULT 0,
  avg_score REAL DEFAULT 0,
  last_attempt TEXT,
  current_level INTEGER DEFAULT 3,
  is_weak INTEGER DEFAULT 0,  -- bool
  last_score REAL
);

-- 热点素材（爬虫写入）
CREATE TABLE hot_topics (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  domain_id TEXT,
  title TEXT,
  summary TEXT,
  source_url TEXT,
  fetched_at TEXT,
  used INTEGER DEFAULT 0
);
```

---

## 五、配置文件设计

### `config.yaml`

```yaml
schedule:
  timezone: "Asia/Tokyo"
  push_time: "08:00"
  reminder_time: "20:00"
  timeout_hours: 24
  reminder_enabled: true

telegram:
  bot_token: "${TELEGRAM_BOT_TOKEN}"
  chat_id: "${TELEGRAM_CHAT_ID}"

llm:
  provider: "anthropic"
  model: "claude-opus-4-5"
  question_max_tokens: 1200
  reflect_max_tokens: 800
  retry_max: 3

crawler:
  enabled: true
  run_day: "Monday"
  run_time: "07:00"
  sources:
    - name: lwn
      url: "https://lwn.net/Articles/"
    - name: vldb
      url: "https://vldb.org/pvldb/"
    - name: clickhouse_blog
      url: "https://clickhouse.com/blog"

learning:
  default_level: 3
  level_up_threshold: 9.0      # 连续N次满足才升级
  level_up_consecutive: 2
  level_down_threshold: 4.0
  level_down_consecutive: 2
  weak_threshold: 6.0          # avg_score 低于此值标记薄弱
  weak_recovery_score: 8.0     # 连续N次高于此值解除薄弱
  weak_recovery_consecutive: 2
  hint_penalty: 1.0            # /hint 扣分
```

### `topics.yaml`（片段示意）

```yaml
domains:
  - id: db
    label: "OLAP / 数据库"
    rotation_day: 4  # Thursday
    topics:
      - id: cascades_optimizer
        name: "Cascades 优化器框架"
        level_default: 4
        tags: ["面试高频", "L4"]
        subtopics:
          - "Memo 结构与等价类"
          - "Physical Properties 传播"
          - "Enforcer 插入机制"
          - "Cost Model 接口设计"
        key_points:
          - "Group / Expression / Winner 三层结构"
          - "Top-down 搜索 vs bottom-up"
          - "与 Volcano/Starburst 的演进关系"
        references:
          - "Cascades paper: Graefe 1995"
          - "CMU 15-721 Lecture 13"
```

---

## 六、关键流程时序

### 每日出题流程

```
08:00
  Scheduler.trigger()
    │
    ├─ Plan.decide()
    │    ├─ 读 topic_stats（Memory DB）
    │    ├─ 读 hot_topics（若 Sat）
    │    └─ 返回 {domain, topic, level, qtype}
    │
    ├─ Tools.gather_context()
    │    ├─ KnowledgeGraphTool → topic 考察维度
    │    ├─ MemoryReader → 历史得分 + 薄弱标记
    │    └─ ConversationHistoryReader → 近期题目防重
    │
    ├─ Generate.create_question()
    │    ├─ 调用 Claude API（System + Context + Plan）
    │    ├─ 解析 YAML 输出，验证字段完整性
    │    └─ 写入 questions 表（status=pending）
    │
    └─ TelegramBot.push()
         └─ 发送题目文本（不含 intent 字段）

用户作答（任意时间）
  TelegramBot.on_message()
    │
    ├─ 更新 questions.status = 'answered'
    ├─ 写入 answers.answer_text
    │
    └─ Reflect.evaluate() [async]
         ├─ 调用 Claude API（评分 Prompt）
         ├─ 解析评分 JSON
         ├─ 写入 answers（scores + gaps + summary）
         ├─ 更新 topic_stats（avg_score / is_weak / level）
         └─ TelegramBot.push_feedback()
```

---

## 七、非功能性设计

### 可靠性

- **LLM 调用失败**：指数退避重试，最多3次；全部失败则推送"今日题目生成失败，已记录，明日补发"
- **Telegram 推送失败**：本地队列缓存，每5分钟重试
- **SQLite 写入**：所有写操作包在事务中，进程崩溃不丢数据
- **进程重启**：APScheduler 使用 SQLite job store，重启后恢复未执行 job

### 可观测性

- 结构化日志（JSON 格式）：每次 Plan / Generate / Reflect 的关键参数和耗时
- 每周自动生成学习报告（周日发送）：
  - 7日出题数 / 完成率 / 平均分
  - 各领域得分热图
  - 本周新增 / 解除薄弱 topic 列表
  - 难度分布变化

### 隐私

- `question.intent` 字段仅存 DB，不发送给用户
- Telegram 交互仅限配置的 `chat_id`，拒绝其他来源消息
- LLM API Key 通过环境变量注入，不入代码库

---

## 八、部署方案

### 最小化部署（推荐起步）

```
本地 Mac / Linux 机器 或 云端小型 VPS（1C1G 足够）

├── Python 3.11+
├── 依赖：anthropic / python-telegram-bot / apscheduler / pyyaml
├── SQLite（无需安装，Python 内置）
├── systemd service 或 screen 保持运行
└── 环境变量：TELEGRAM_BOT_TOKEN / ANTHROPIC_API_KEY
```

### 目录结构

```
daily-agent/
├── config.yaml
├── topics.yaml
├── data/
│   └── memory.db          # SQLite
├── logs/
│   └── agent.jsonl
├── src/
│   ├── main.py            # 入口 + Scheduler
│   ├── plan.py            # Plan 模块
│   ├── tools/
│   │   ├── knowledge.py
│   │   ├── memory.py
│   │   └── crawler.py
│   ├── generate.py        # Generate 模块
│   ├── reflect.py         # Reflect 模块
│   ├── bot.py             # Telegram Bot
│   └── db.py              # SQLite 封装
└── tests/
    ├── test_plan.py
    └── test_reflect.py
```

---

## 九、迭代路线图

| 阶段 | 周期 | 目标 |
|---|---|---|
| v0.1 MVP | Week 1 | 手动触发出题 + Telegram 推送 + 评分回显 |
| v0.2 记忆 | Week 2 | SQLite 写回 + 薄弱点权重 + /status 命令 |
| v0.3 自适应 | Week 3 | 难度自动升降级 + 周日复盘日逻辑 |
| v0.4 热点 | Week 4 | HotTopicCrawler + 前沿题素材注入 |
| v0.5 报告 | Month 2 | 每周学习报告 + 得分趋势图 |
| v1.0 稳定 | Month 3 | 完整测试覆盖 + 配置热重载 + 错误告警 |

---

## 十、核心风险与应对

| 风险 | 影响 | 应对 |
|---|---|---|
| LLM 出题质量退化 | 题目太简单或重复 | 质量检测：字数/结构/与历史相似度三重过滤 |
| topics.yaml 覆盖不足 | 某领域题目枯竭 | 每月人工补充 + LLM 辅助扩展 topic 列表 |
| 坚持率下降 | 系统失去价值 | /skip 不惩罚 + 连续打卡提示 + 周报正向激励 |
| API 费用超预期 | — | 每次调用 max_tokens 严格限制，预估月费 < $5 |

