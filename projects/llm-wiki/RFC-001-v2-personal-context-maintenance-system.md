# RFC-001-v2：Personal Context Maintenance System

**面向社交连接的个人 Context 维护系统 POC 设计**

状态：Draft v2  
目标阶段：Engineering POC  
产品入口：CLI-first  
主语言：Go  
辅助语言：Python  
核心目标：从照片、文本、profile、社交意图等输入中生成、维护、检索个人 context，并安全地用于社交匹配和连接理由生成。

---

## 1. 背景

传统社交产品依赖用户主动表达：填写资料、发动态、主动聊天、手动维护兴趣标签。

AI 社交产品可以换一种路径：

```text
用户上传生活材料
    ↓
系统抽取个人 context
    ↓
用户确认、编辑、授权
    ↓
系统基于 context 发现人与人之间的连接理由
    ↓
生成自然、低冒犯、可解释的破冰方式
```

本系统不是普通相册，也不是普通 RAG 系统，而是一个面向社交场景的 **Personal Context Maintenance System**。

它的核心能力是：

```text
将用户生活证据转化为可授权、可追溯、可查询、可删除、可用于社交连接的 context。
```

---

## 2. 设计目标

### 2.1 POC 需要验证的问题

POC 阶段重点验证 6 件事：

| 问题 | 说明 |
|---|---|
| Context 是否可生成 | 照片、文本、profile、意图能否稳定生成 context |
| Context 是否可信 | 是否有来源、置信度、证据、模型版本 |
| Context 是否可维护 | 用户能否 review、approve、edit、reject、delete |
| Context 是否可检索 | 能否按语义、标签、时间、权限查到 relevant context |
| Context 是否可连接 | 能否基于双方 context 生成连接理由 |
| Context 是否安全 | 不泄露精确位置、人脸身份、私密关系、儿童信息 |

### 2.2 POC 非目标

POC 阶段暂不做：

| 非目标 | 原因 |
|---|---|
| 移动端 App | CLI-first 更快验证系统链路 |
| 实时聊天 | 不是 context 系统核心 |
| 微服务 | POC 阶段复杂度过高 |
| Kafka / Flink | Postgres job table 足够 |
| Milvus / Qdrant | pgvector 足够支撑早期验证 |
| Neo4j | 先用关系表模拟 entity edge |
| 自建 VLM | 1000 张图片级别 API 更快 |
| 人脸身份识别 | 隐私风险高，POC 不碰 |
| 自动公开推荐 | 所有 context 默认需要权限控制 |

---

## 3. 核心原则

### 3.1 Context 不是 Persona Prompt

不要给每个用户维护一个巨大的 persona prompt：

```text
Kevin 是数据库工程师，喜欢 AI infra、咖啡、旅行、夜市……
```

这种方式有几个问题：

| 问题 | 说明 |
|---|---|
| 不可追溯 | 不知道这条信息从哪里来 |
| 不可删除 | 删除某张照片后，不知道 summary 里哪些内容要删 |
| 不可授权 | 无法控制哪些内容能用于匹配 |
| 不可审计 | 不知道推荐使用了哪些证据 |
| 不可纠错 | 用户很难修正单条错误 |

正确方式是维护很多条小的 context item：

```json
{
  "id": "ctx_101",
  "user_id": "u_kevin",
  "type": "photo_event",
  "text": "用户在 2025 年夏天拍摄过上海夜市相关照片，适合围绕美食、城市漫游、周末探索建立社交话题。",
  "source_type": "photo",
  "source_asset_id": "asset_882",
  "confidence": 0.84,
  "visibility": "match_only",
  "purpose": ["self_memory", "matching", "generation"],
  "sensitivity": 1,
  "state": "active"
}
```

### 3.2 系统知道，不等于用户可见

系统内部可以知道：

```text
用户 A 和用户 B 都在上海某个夜市附近拍过照片。
```

但对外连接理由只能说：

```text
你们都喜欢上海的夜市、美食和城市漫游。
```

禁止说：

```text
你们都在 2025 年 8 月 17 日晚上去过同一个夜市。
```

这个原则贯穿整个架构：

```text
Context Retrieval
    ↓
Privacy Gate
    ↓
Safe Context Pack
    ↓
Bridge Generation
    ↓
Redaction Check
    ↓
User-visible Output
```

### 3.3 LLM 负责候选理解，系统负责确定性约束

系统不能把核心判断完全交给 LLM。

```text
LLM / VLM:
  - 图片理解
  - context 候选生成
  - summary 文案生成
  - bridge 文案生成

Go System:
  - schema 校验
  - 权限判断
  - 状态机
  - 审计
  - 删除链路
  - ranking
  - privacy gate
  - 是否允许使用某条 context
```

一句话：

```text
模型可以提出候选，系统决定能不能用。
```

---

## 4. 技术决策

### 4.1 语言分工

| 层 | 语言 | 责任 |
|---|---|---|
| CLI | Go | 用户入口、命令编排 |
| Core Service | Go | context 生命周期、权限、审计、匹配 |
| Repository | Go | Postgres / pgvector 访问 |
| Provider Adapter | Go | 调用模型 API、embedding API |
| Job Worker | Go | 图片处理、模型调用、embedding、summary |
| Eval / Prompt Lab | Python | prompt 实验、模型对比、评测集、报告 |
| Data Analysis | Python | context 质量分析、成本分析、错误分析 |
| Replay / Golden | Python + JSON | 生成和维护可复现模型输出 |
| Future Web UI | TypeScript，可选 | context review / admin console |
| Future Local Privacy Tool | Rust，可选 | 本地图片处理、EXIF 清理、隐私扫描 |

### 4.2 为什么 Go 做主系统

Go 负责主系统的原因：

| 原因 | 价值 |
|---|---|
| 单 binary | CLI / server / worker 部署简单 |
| 并发模型简单 | 批量处理照片、模型调用、DB 查询方便 |
| 性能稳定 | 后续扩展到 API server 更自然 |
| 类型约束足够强 | 权限、状态机、context schema 更稳 |
| Postgres 生态成熟 | pgx、sqlc、goose / atlas 成熟 |
| 运维简单 | 比 Python 更适合作为长期服务端主干 |

### 4.3 为什么 Python 仍然保留

Python 不作为主 server，但用于：

| 用途 | 说明 |
|---|---|
| Prompt 实验 | 快速比较不同 prompt |
| 模型对比 | Qwen / Doubao / local model 对比 |
| Eval harness | 批量跑 extraction / privacy / matching 测试 |
| 数据分析 | approve rate、reject rate、成本、失败模式 |
| Golden 生成 | 保存模型输出，给 Go ReplayProvider 使用 |
| Notebook | 人工分析 context 质量 |

这种分工是：

```text
Go 负责可运行系统。
Python 负责研究、实验和评测。
```

---

## 5. POC 技术栈

### 5.1 Go 主系统

| 模块 | 选择 |
|---|---|
| CLI | Cobra |
| DB Driver | pgx |
| SQL 生成 | sqlc |
| Migration | goose 或 atlas |
| Config | YAML + env |
| Logging | slog / zap |
| Main DB | PostgreSQL |
| Vector | pgvector |
| Asset Store | Local filesystem |
| Job Queue | Postgres job table |
| Test | go test |
| API Server，可选 | chi / Gin / Echo |
| Model Provider | Go HTTP client |

### 5.2 Python 辅助系统

| 模块 | 选择 |
|---|---|
| Eval scripts | Python 3.11+ |
| Schema validation | Pydantic |
| Notebook | Jupyter |
| Data analysis | pandas |
| Image experiment | Pillow / pillow-heif |
| Prompt runner | 自研简单 runner |
| Reports | Markdown / JSON / CSV |
| Golden files | JSON |

### 5.3 存储

| 数据 | 存储 |
|---|---|
| 用户 | PostgreSQL |
| 照片 / 视频资产 metadata | PostgreSQL |
| 原始图片 | Local filesystem，后续 OSS / COS / S3 |
| context item | PostgreSQL |
| embedding | pgvector |
| summary | PostgreSQL |
| entity edge | PostgreSQL |
| audit log | PostgreSQL |
| model call log | PostgreSQL |
| replay / golden | JSON 文件 |

---

## 6. 总体架构

```text
                    ┌────────────────────┐
                    │      Go CLI         │
                    │  ctx user/create    │
                    │  ctx ingest/photo   │
                    │  ctx match/run      │
                    └─────────┬──────────┘
                              │
                              v
                    ┌────────────────────┐
                    │  Go Core Services   │
                    │                    │
                    │ UserService         │
                    │ AssetService        │
                    │ ContextService      │
                    │ ReviewService       │
                    │ PrivacyGate         │
                    │ MatchingService     │
                    │ BridgeService       │
                    │ CostService         │
                    │ EvalCommand Bridge  │
                    └─────────┬──────────┘
                              │
          ┌───────────────────┼───────────────────┐
          v                   v                   v
┌────────────────┐   ┌────────────────┐   ┌────────────────┐
│ PostgreSQL      │   │ Local Assets    │   │ Model Providers│
│ + pgvector      │   │ ./data/assets   │   │ Qwen/Doubao    │
│ context tables  │   │ ./data/thumbs   │   │ Replay/Mock    │
└────────────────┘   └────────────────┘   └────────────────┘
                                                    │
                                                    v
                                       ┌────────────────────┐
                                       │ Python Eval Layer   │
                                       │ prompt experiments  │
                                       │ golden generation   │
                                       │ quality reports     │
                                       └────────────────────┘
```

---

## 7. 系统模块

### 7.1 Go CLI

CLI 是 POC 产品入口。

核心命令：

```bash
ctx init
ctx user create
ctx user list
ctx ingest photo
ctx ingest note
ctx intent set
ctx process run
ctx review list
ctx review approve
ctx review reject
ctx context list
ctx context edit
ctx context delete
ctx query self
ctx summary build
ctx match run
ctx bridge
ctx privacy audit
ctx cost show
ctx eval run
ctx export
```

CLI 不直接写业务逻辑，只负责调用 service。

### 7.2 UserService

负责：

```text
创建用户
查看用户
更新 profile
设置城市
设置默认用户
```

示例：

```bash
ctx user create kevin \
  --name "Kevin Li" \
  --city "上海" \
  --bio "数据库工程师，关注 AI infra、城市漫游、咖啡和旅行"
```

### 7.3 AssetService

负责：

```text
照片导入
文本 note 导入
文件 hash 去重
EXIF 读取
asset metadata 写入
本地文件存储
asset 删除
```

照片导入示例：

```bash
ctx ingest photo ./photos/kevin/*.HEIC \
  --user kevin \
  --album "上海夜市" \
  --visibility private \
  --purpose self_memory,matching
```

文本导入示例：

```bash
ctx ingest note \
  --user kevin \
  --type preference \
  --text "最近想认识同城、对 AI infra 和数据库系统感兴趣、周末可以一起喝咖啡或 citywalk 的人" \
  --visibility match_only \
  --purpose self_memory,matching,generation
```

### 7.4 ExtractionService

负责把 source asset 转成结构化候选 context。

照片处理链路：

```text
source_asset
  ↓
EXIF parse
  ↓
image normalize / thumbnail
  ↓
VisionProvider.ExtractPhotoContext
  ↓
schema validate
  ↓
privacy classify
  ↓
context candidate
  ↓
pending_review
```

注意：

```text
模型输出不能直接变成 active context。
```

照片模型输出需要先进入：

```text
state = pending_review
visibility = private
```

### 7.5 ContextService

负责 context 生命周期。

状态机：

```text
draft
  ↓
pending_review
  ↓
active
  ↓
expired
  ↓
deleted
```

以及：

```text
reject
edit
merge
expire
delete cascade
```

### 7.6 ReviewService

负责用户确认模型生成的 context。

```bash
ctx review list --user kevin
ctx review approve ctx_101 --visibility match_only
ctx review reject ctx_102 --reason "模型误判"
ctx context edit ctx_103 --text "这不是夜市，是音乐节"
```

Review 是 POC 的核心产品行为之一。

它验证：

```text
用户是否信任这些 context？
用户是否愿意维护这些 context？
模型生成的 context 是否有用？
```

### 7.7 PrivacyGate

负责判断某条 context 能不能用于某个目的。

核心输入：

```text
context
actor_user
purpose
target_user
operation
```

核心输出：

```text
allow / deny
reason
redaction hints
```

伪代码：

```go
func CanUseContext(ctx ContextItem, actor UserID, purpose Purpose, target *UserID) PolicyDecision {
    if ctx.State != StateActive {
        return Deny("context_not_active")
    }

    if ctx.DeletedAt != nil {
        return Deny("context_deleted")
    }

    if ctx.ExpiresAt != nil && ctx.ExpiresAt.Before(time.Now()) {
        return Deny("context_expired")
    }

    if !ctx.Purpose.Contains(purpose) {
        return Deny("purpose_not_allowed")
    }

    if actor == ctx.UserID && purpose == PurposeSelfMemory {
        return Allow("owner_self_memory")
    }

    if purpose == PurposeMatching {
        if ctx.Visibility.In("match_only", "public") && ctx.Sensitivity <= SensitivityNormal {
            return Allow("allowed_for_matching")
        }
        return Deny("not_allowed_for_matching")
    }

    if purpose == PurposeGeneration {
        if ctx.Visibility.In("match_only", "public") && ctx.Sensitivity <= SensitivityNormal {
            return Allow("allowed_for_generation")
        }
        return Deny("not_allowed_for_generation")
    }

    return Deny("default_deny")
}
```

### 7.8 EmbeddingService

负责：

```text
context text embedding
user summary embedding
intent embedding
可选 image embedding
```

POC 阶段建议先做文本 embedding：

```text
context_item.text -> embedding -> context_vector
```

图片 embedding 可以第二阶段开启。

### 7.9 QueryService

负责个人 context 查询。

示例：

```bash
ctx query self \
  --user kevin \
  --text "我有哪些适合和别人聊的周末生活话题？"
```

Self query 可以使用：

```text
private
match_only
friend_only
public
```

但输出需要标注：

```text
context id
source
confidence
visibility
sensitivity
```

### 7.10 MatchingService

负责寻找候选连接对象。

召回分三路：

```text
结构化 entity 召回
向量召回
当前 intent 召回
```

排序公式：

```text
match_score =
  0.25 * semantic_similarity
+ 0.20 * shared_interest_score
+ 0.15 * current_intent_match
+ 0.10 * geo_compatibility
+ 0.10 * recency_score
+ 0.10 * source_trust_score
+ 0.05 * novelty_score
+ 0.05 * safety_score
- 0.20 * privacy_risk
- 0.30 * negative_feedback
```

POC 阶段用规则打分即可。

### 7.11 BridgeService

负责生成连接理由。

输入必须是 PrivacyGate 过滤后的 safe context pack。

```json
{
  "user_a": {
    "safe_contexts": [
      "喜欢 AI infra、数据库系统、技术创业",
      "喜欢上海夜市、咖啡馆和城市漫游",
      "当前想认识同城、轻松聊天的人"
    ]
  },
  "user_b": {
    "safe_contexts": [
      "喜欢探店、展览、夜市和轻户外",
      "近期想认识同城朋友",
      "对科技展和创业活动有兴趣"
    ]
  },
  "constraints": [
    "不要暴露精确 GPS",
    "不要提具体拍摄时间",
    "不要提照片中其他人物身份",
    "不要使用 private context"
  ]
}
```

输出：

```json
{
  "connection_reason": "你们都喜欢上海的城市生活、美食探店和轻松的周末活动，同时也有技术和科技展相关的话题交集。",
  "icebreakers": [
    "上海最近有什么适合周末走走的地方吗？",
    "你更喜欢咖啡馆聊天，还是边走边聊的 citywalk？",
    "最近有没有看过什么有意思的科技展？"
  ],
  "contexts_used": {
    "user_a": ["ctx_101", "ctx_007"],
    "user_b": ["ctx_211", "ctx_245"]
  },
  "privacy_check": {
    "private_context_used": false,
    "exact_location_exposed": false,
    "face_identity_used": false
  }
}
```

---

## 8. Model Provider 设计

### 8.1 Go Interface

Go 主系统通过接口访问模型。

```go
type VisionExtractor interface {
    ExtractPhotoContext(
        ctx context.Context,
        input PhotoExtractionInput,
    ) (*PhotoExtractionResult, error)
}

type TextEmbedder interface {
    EmbedTexts(
        ctx context.Context,
        texts []string,
    ) ([]Embedding, error)
}

type TextGenerator interface {
    GenerateBridge(
        ctx context.Context,
        input BridgeGenerationInput,
    ) (*BridgeGenerationResult, error)

    GenerateSummary(
        ctx context.Context,
        input SummaryInput,
    ) (*SummaryResult, error)
}
```

### 8.2 Provider 类型

| Provider | 用途 |
|---|---|
| `MockProvider` | 单测，返回固定结果 |
| `ReplayProvider` | 从 golden JSON 读取历史模型输出 |
| `QwenProvider` | 调用 Qwen / 阿里百炼 |
| `DoubaoProvider` | 调用豆包 / 火山模型 |
| `PythonProvider` | 可选，通过 subprocess 或 HTTP 调 Python 实验服务 |
| `LocalProvider` | 后续本地模型 |

POC 优先实现：

```text
MockProvider
ReplayProvider
QwenProvider 或 DoubaoProvider
```

### 8.3 ReplayProvider

ReplayProvider 对 POC 很重要。

原因：

```text
真实模型输出不稳定
模型调用有成本
测试需要可复现
隐私边界测试不能依赖随机输出
```

Golden 文件示例：

```text
evals/golden/photo_extract/qwen_vl/asset_001.json
evals/golden/bridge/qwen_plus/kevin_amy.json
```

Go 测试时可以使用：

```bash
ctx process run --provider replay
ctx bridge --provider replay --user kevin --target amy
```

---

## 9. Python Eval Layer

Python 层不参与主业务运行，主要负责实验和评测。

### 9.1 Python 目录

```text
python/
  eval/
    run_extraction_eval.py
    run_privacy_eval.py
    run_matching_eval.py
    run_bridge_eval.py
    report.py

  experiments/
    compare_vision_models.py
    compare_embedding_models.py
    prompt_ab_test.py
    analyze_context_quality.py

  providers/
    qwen.py
    doubao.py
    local_model.py

  schemas/
    photo_extract.py
    bridge_result.py

  notebooks/
    context_quality_analysis.ipynb

  golden/
    photo_extract/
    bridge/
    summary/
```

### 9.2 Python Eval 输出

Python eval 统一输出 JSON report：

```json
{
  "suite": "privacy",
  "total_cases": 50,
  "passed": 48,
  "failed": 2,
  "failures": [
    {
      "case_id": "bridge_exact_location_leak",
      "expected": "no exact location",
      "actual": "output contained street name"
    }
  ],
  "metrics": {
    "private_context_leak_count": 0,
    "gps_leak_count": 1,
    "face_identity_leak_count": 0
  }
}
```

Go CLI 可以读取这个结果：

```bash
ctx eval report --input python/eval/reports/privacy.json
```

---

## 10. 数据模型

### 10.1 app_user

```sql
CREATE TABLE app_user (
  id UUID PRIMARY KEY,
  handle TEXT UNIQUE NOT NULL,
  display_name TEXT,
  city TEXT,
  profile_text TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);
```

### 10.2 source_asset

存储照片、note、profile、intent 等原始输入。

```sql
CREATE TABLE source_asset (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES app_user(id),

  asset_type TEXT NOT NULL, -- photo, video, note, profile, intent
  uri TEXT,
  sha256 TEXT,
  original_filename TEXT,

  metadata JSONB NOT NULL DEFAULT '{}',

  visibility TEXT NOT NULL DEFAULT 'private',
  sensitivity SMALLINT NOT NULL DEFAULT 0,
  state TEXT NOT NULL DEFAULT 'active',

  observed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now()
);
```

照片 metadata 示例：

```json
{
  "width": 3024,
  "height": 4032,
  "device": "iPhone",
  "exif_time": "2025-08-17T19:22:00+08:00",
  "gps": {
    "lat_encrypted": "...",
    "lng_encrypted": "...",
    "city": "上海",
    "district": "黄浦区",
    "share_level": "city"
  },
  "album": "上海夜市"
}
```

### 10.3 extraction_job

POC 阶段使用 Postgres job table，不引入 Kafka。

```sql
CREATE TABLE extraction_job (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES app_user(id),
  source_asset_id UUID REFERENCES source_asset(id),

  job_type TEXT NOT NULL, -- exif, vision, embedding, summary
  status TEXT NOT NULL,  -- pending, running, succeeded, failed

  input JSONB NOT NULL DEFAULT '{}',
  output JSONB NOT NULL DEFAULT '{}',
  error TEXT,

  model_provider TEXT,
  model_name TEXT,
  prompt_version TEXT,

  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now()
);
```

### 10.4 context_item

核心表。

```sql
CREATE TABLE context_item (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES app_user(id),

  type TEXT NOT NULL, -- photo_event, interest, place, activity, intent, preference, summary_fact
  text TEXT NOT NULL,
  attrs JSONB NOT NULL DEFAULT '{}',

  source_type TEXT NOT NULL, -- photo, note, profile, model, behavior
  source_asset_id UUID REFERENCES source_asset(id),
  source_context_ids UUID[] DEFAULT '{}',

  confidence NUMERIC(4,3),
  source_trust NUMERIC(4,3),

  sensitivity SMALLINT NOT NULL, -- 0 low, 1 normal, 2 sensitive, 3 highly_sensitive
  visibility TEXT NOT NULL,     -- private, match_only, friend_only, public, blocked
  purpose TEXT[] NOT NULL,      -- self_memory, matching, recommendation, generation, training

  state TEXT NOT NULL,          -- draft, pending_review, active, rejected, expired, deleted
  review_status TEXT DEFAULT 'unreviewed',

  observed_at TIMESTAMPTZ,
  expires_at TIMESTAMPTZ,
  deleted_at TIMESTAMPTZ,

  model_provider TEXT,
  model_version TEXT,
  prompt_version TEXT,

  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);
```

建议索引：

```sql
CREATE INDEX idx_context_user_state
ON context_item(user_id, state);

CREATE INDEX idx_context_visibility_purpose
ON context_item(visibility, sensitivity);

CREATE INDEX idx_context_attrs_gin
ON context_item USING GIN(attrs);

CREATE INDEX idx_context_observed_at
ON context_item(observed_at);
```

### 10.5 context_vector

```sql
CREATE TABLE context_vector (
  id UUID PRIMARY KEY,
  context_id UUID REFERENCES context_item(id),
  user_id UUID NOT NULL REFERENCES app_user(id),

  vector_type TEXT NOT NULL, -- text, image, user_summary, intent
  embedding VECTOR(1024),
  embedding_model TEXT NOT NULL,

  visibility TEXT NOT NULL,
  sensitivity SMALLINT NOT NULL,

  created_at TIMESTAMPTZ DEFAULT now()
);
```

POC 阶段：

```text
先只做 text embedding。
```

第二阶段再增加：

```text
image embedding
video segment embedding
face clustering embedding，需谨慎
```

### 10.6 entity

```sql
CREATE TABLE entity (
  id UUID PRIMARY KEY,
  entity_type TEXT NOT NULL, -- interest, place, activity, topic, object
  name TEXT NOT NULL,
  canonical_name TEXT,
  attrs JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT now()
);
```

### 10.7 user_entity_edge

```sql
CREATE TABLE user_entity_edge (
  user_id UUID NOT NULL REFERENCES app_user(id),
  entity_id UUID NOT NULL REFERENCES entity(id),

  weight NUMERIC(5,3) NOT NULL,
  confidence NUMERIC(4,3),
  source_context_id UUID REFERENCES context_item(id),

  visibility TEXT NOT NULL,
  sensitivity SMALLINT NOT NULL,

  updated_at TIMESTAMPTZ DEFAULT now(),

  PRIMARY KEY (user_id, entity_id)
);
```

### 10.8 user_context_summary

```sql
CREATE TABLE user_context_summary (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES app_user(id),

  summary_type TEXT NOT NULL, -- stable, recent, social_card, intent, travel, food, work
  text TEXT NOT NULL,
  attrs JSONB DEFAULT '{}',

  source_context_ids UUID[] DEFAULT '{}',

  confidence NUMERIC(4,3),
  sensitivity SMALLINT NOT NULL,
  visibility TEXT NOT NULL,
  purpose TEXT[] NOT NULL,

  version INT NOT NULL DEFAULT 1,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);
```

### 10.9 model_call_log

```sql
CREATE TABLE model_call_log (
  id UUID PRIMARY KEY,
  user_id UUID,

  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  task_type TEXT NOT NULL, -- vision_extract, text_embed, bridge, summary

  input_tokens INT,
  output_tokens INT,
  image_count INT DEFAULT 0,
  cost_estimated NUMERIC(12,6),
  latency_ms INT,

  status TEXT,
  error TEXT,

  created_at TIMESTAMPTZ DEFAULT now()
);
```

### 10.10 context_usage_audit

每次使用 context 都要记录。

```sql
CREATE TABLE context_usage_audit (
  id UUID PRIMARY KEY,
  context_id UUID REFERENCES context_item(id),
  user_id UUID NOT NULL,

  used_by TEXT NOT NULL, -- query, match, bridge, summary
  purpose TEXT NOT NULL,

  target_user_id UUID,
  allowed BOOLEAN NOT NULL,
  reason TEXT,

  created_at TIMESTAMPTZ DEFAULT now()
);
```

### 10.11 match_result

```sql
CREATE TABLE match_result (
  id UUID PRIMARY KEY,

  user_id UUID NOT NULL REFERENCES app_user(id),
  target_user_id UUID NOT NULL REFERENCES app_user(id),

  score NUMERIC(6,4) NOT NULL,
  score_breakdown JSONB NOT NULL DEFAULT '{}',

  context_ids UUID[] DEFAULT '{}',
  safe_context_pack JSONB NOT NULL DEFAULT '{}',

  bridge_result JSONB DEFAULT '{}',
  privacy_check JSONB DEFAULT '{}',

  created_at TIMESTAMPTZ DEFAULT now()
);
```

---

## 11. 核心数据结构：Go Domain Model

### 11.1 ContextItem

```go
type ContextItem struct {
    ID        uuid.UUID
    UserID    uuid.UUID

    Type string
    Text string
    Attrs map[string]any

    SourceType       string
    SourceAssetID    *uuid.UUID
    SourceContextIDs []uuid.UUID

    Confidence  float64
    SourceTrust float64

    Sensitivity Sensitivity
    Visibility  Visibility
    Purpose     []Purpose

    State        ContextState
    ReviewStatus ReviewStatus

    ObservedAt *time.Time
    ExpiresAt  *time.Time
    DeletedAt  *time.Time

    ModelProvider string
    ModelVersion  string
    PromptVersion string

    CreatedAt time.Time
    UpdatedAt time.Time
}
```

### 11.2 Visibility

```go
type Visibility string

const (
    VisibilityPrivate    Visibility = "private"
    VisibilityMatchOnly  Visibility = "match_only"
    VisibilityFriendOnly Visibility = "friend_only"
    VisibilityPublic     Visibility = "public"
    VisibilityBlocked    Visibility = "blocked"
)
```

### 11.3 Purpose

```go
type Purpose string

const (
    PurposeSelfMemory     Purpose = "self_memory"
    PurposeMatching       Purpose = "matching"
    PurposeRecommendation Purpose = "recommendation"
    PurposeGeneration     Purpose = "generation"
    PurposeTraining       Purpose = "training"
)
```

### 11.4 Sensitivity

```go
type Sensitivity int

const (
    SensitivityLow Sensitivity = iota
    SensitivityNormal
    SensitivitySensitive
    SensitivityHighlySensitive
)
```

---

## 12. 照片处理流程

### 12.1 输入

```bash
ctx ingest photo ./photos/kevin/*.HEIC --user kevin --album "上海夜市"
```

### 12.2 处理链路

```text
1. 读取文件
2. 计算 sha256
3. 去重
4. 拷贝到 ./data/assets/{user_id}/{asset_id}
5. 读取 EXIF
6. GPS 降级
7. 创建 source_asset
8. 创建 extraction_job
9. process run 执行 job
10. 调用 VisionProvider
11. 校验模型输出
12. 生成 pending_review context
13. 生成 embedding
14. 写入 audit 和 model_call_log
```

### 12.3 GPS 降级规则

原始 GPS 不进入 match / bridge。

```text
exact gps:
  存储：加密或 POC 中不存明文
  visibility: private
  purpose: self_memory only

city / district:
  visibility: match_only
  purpose: matching, generation
```

推荐结构：

```json
{
  "gps": {
    "exact_available": true,
    "city": "上海",
    "district": "黄浦区",
    "share_level": "city",
    "exact_location_exposed": false
  }
}
```

---

## 13. Vision Extraction Contract

模型输出必须符合统一 contract。

```json
{
  "scene": {
    "place_type": ["夜市", "城市街道", "户外"],
    "background": "户外城市夜市，人群较多，有霓虹灯和小吃摊",
    "objects": ["小吃摊", "招牌", "霓虹灯", "人群"],
    "ocr_text": ["烧烤", "冰粉"]
  },
  "people": {
    "count": 2,
    "visible_expressions": ["开心", "放松"],
    "activity": "两个人在夜市合照或同行",
    "identity": "unknown"
  },
  "location_hint": {
    "should_use_exif_first": true,
    "visual_guess": null,
    "confidence": 0.0
  },
  "time_hint": {
    "should_use_exif_first": true,
    "visual_guess_year": null,
    "confidence": 0.0
  },
  "social_topics": ["美食", "城市漫游", "周末探索", "夜生活"],
  "privacy_flags": {
    "has_face": true,
    "has_child_risk": false,
    "has_plate": false,
    "has_work_badge": false,
    "has_exact_location": true
  },
  "confidence": {
    "scene": 0.91,
    "people_count": 0.85,
    "expression": 0.72,
    "ocr": 0.81,
    "social_topics": 0.78
  }
}
```

---

## 14. Context 生成规则

从 Vision Extraction 生成 context item。

示例：

```text
用户在 2025 年夏天拍摄过上海夜市相关照片，画面包含小吃摊、霓虹灯和人群，氛围轻松热闹，适合围绕美食、城市漫游、周末探索建立社交话题。
```

规则：

| 字段 | 规则 |
|---|---|
| 年份 | EXIF 优先，模型不得强猜 |
| 地点 | GPS / 用户资料优先，只使用城市级 |
| 人物 | 只描述人数、姿态、可见表情，不识别身份 |
| 表情 | 只能说“看起来开心 / 放松”，不判断心理 |
| 关系 | 不得写“情侣 / 家人”，除非用户显式标注 |
| 儿童 | 默认 sensitivity = 3，不进入 matching |
| 车牌 / 工牌 | 默认 blocked 或 private |
| 故事 | 标记为生成式文案，不作为事实 |

---

## 15. CLI 产品流程

### 15.1 初始化

```bash
ctx init \
  --db postgres://ctx:ctx@localhost:5432/context_poc \
  --asset-store ./data/assets \
  --config ./ctx.yaml
```

### 15.2 创建用户

```bash
ctx user create kevin \
  --name "Kevin Li" \
  --city "上海" \
  --bio "数据库工程师，关注 AI infra、城市漫游、咖啡和旅行"

ctx user create amy \
  --name "Amy" \
  --city "上海" \
  --bio "喜欢探店、展览、夜市和轻户外"
```

### 15.3 导入照片

```bash
ctx ingest photo ./demo/kevin/*.jpg \
  --user kevin \
  --album "kevin_demo" \
  --visibility private
```

### 15.4 导入 note

```bash
ctx ingest note \
  --user kevin \
  --type profile \
  --text "我关注 AI infra、数据库系统、技术创业，也喜欢咖啡、citywalk 和夜市。" \
  --visibility match_only \
  --purpose self_memory,matching,generation
```

### 15.5 设置社交意图

```bash
ctx intent set \
  --user kevin \
  --text "想认识同城、喜欢技术创业、咖啡、城市漫游的人，先轻松聊天" \
  --ttl 14d
```

### 15.6 处理数据

```bash
ctx process run \
  --user kevin \
  --jobs exif,vision,context,embedding,summary \
  --limit 100
```

### 15.7 Review

```bash
ctx review list --user kevin
```

输出示例：

```text
Pending Contexts for kevin

[ctx_101]
confidence: 0.86
sensitivity: normal
source: photo asset_882
suggested_visibility: match_only

text:
用户在 2025 年夏天拍摄过上海夜市照片，画面包含小吃摊、霓虹灯、人群，适合围绕美食和城市漫游建立社交话题。

actions:
  approve / reject / edit
```

批准：

```bash
ctx review approve ctx_101 \
  --visibility match_only \
  --purpose self_memory,matching,generation
```

编辑：

```bash
ctx context edit ctx_101 \
  --text "我喜欢上海夜市、城市漫游和有烟火气的周末活动"
```

拒绝：

```bash
ctx review reject ctx_102 --reason "模型误判"
```

### 15.8 查询个人 context

```bash
ctx query self \
  --user kevin \
  --text "我有哪些适合和别人聊的周末生活话题？"
```

输出：

```text
Query: 我有哪些适合和别人聊的周末生活话题？

1. 上海夜市和城市漫游
   reason: 多条照片 context 显示用户喜欢城市街区、夜市、美食场景
   context_ids: ctx_101, ctx_133
   confidence: 0.84
   visibility: match_only

2. 咖啡馆和轻松聊天
   reason: 用户手填 note 和照片 context 都支持
   context_ids: ctx_144
   confidence: 0.91
   visibility: match_only

3. AI infra 和数据库系统
   reason: 用户 profile 显式提到
   context_ids: ctx_006
   confidence: 0.96
   visibility: match_only
```

### 15.9 生成社交名片

```bash
ctx summary build --user kevin --type social_card
```

输出：

```text
Kevin 的社交名片

长期兴趣：
- AI infra、数据库系统、技术创业
- 城市漫游、咖啡馆、夜市、美食
- 轻松但有信息密度的聊天

近期状态：
- 更适合同城、低压力、周末型社交
- 可以从咖啡、citywalk、技术趋势、上海夜市聊起

适合的破冰话题：
1. 上海最近有什么适合周末走走的地方？
2. 你更喜欢咖啡馆聊天还是夜市散步？
3. 最近 AI infra 里面你觉得哪个方向最有意思？
```

### 15.10 匹配

```bash
ctx match run --user kevin --pool all --top 5
```

输出：

```text
Top matches for kevin

#1 Amy
score: 0.86

connection_reason:
你们都在上海，且都喜欢城市漫游、夜市、美食和轻松的周末活动。
Kevin 还关注 AI infra，Amy 近期也对科技展和创业活动有兴趣。

safe_icebreakers:
1. 上海最近有什么你觉得值得去的夜市或街区吗？
2. 你更喜欢咖啡馆聊天，还是边走边聊的 citywalk？
3. 最近有没有看过什么有意思的科技展？

contexts_used:
kevin: ctx_101, ctx_007, ctx_144
amy: ctx_211, ctx_245, ctx_260

privacy_check:
exact GPS: not exposed
face identity: not used
private contexts: not used
```

### 15.11 Bridge

```bash
ctx bridge --user kevin --target amy
```

输出：

```text
Bridge: kevin -> amy

Connection type:
同城兴趣连接 + 周末生活方式连接 + 轻技术话题连接

Why:
你们都喜欢上海的城市生活、美食探店和轻松的周末活动。
Kevin 的技术兴趣和 Amy 的科技展兴趣也有潜在交集。

Recommended first message:
“你最近有发现上海什么适合周末走走的地方吗？我最近有点想找夜市、咖啡馆或者科技展这类轻松一点的活动。”

Do not mention:
- 精确拍摄地点
- 照片中的其他人物
- 具体拍摄时间
- 未确认的情绪判断
```

### 15.12 隐私审计

```bash
ctx privacy audit --user kevin
```

输出：

```text
Privacy Audit for kevin

Assets:
  photos: 1032
  photos_with_exact_gps: 412
  photos_with_faces: 286
  photos_with_possible_children: 12

Contexts:
  total: 1840
  private: 1290
  match_only: 488
  public: 0
  friend_only: 62

High sensitivity:
  exact GPS contexts exposed: 0
  face identity contexts exposed: 0
  child-related contexts exposed: 0

Warnings:
  - 12 assets may contain children. Excluded from matching by default.
  - 412 photos contain exact GPS. GPS has been downgraded to city-level for matching.
```

---

## 16. 查询与匹配设计

### 16.1 Self Query

用户查自己，可以使用：

```text
private
match_only
friend_only
public
```

但输出时要展示来源和可见性。

### 16.2 Match Query

用于候选匹配，只能使用：

```text
visibility in match_only, public
purpose contains matching
sensitivity <= normal
state = active
```

### 16.3 Bridge Query

用于生成连接理由，只能使用：

```text
visibility in match_only, public
purpose contains generation
sensitivity <= normal
state = active
```

并且要经过：

```text
PrivacyGate
    ↓
SafeContextPack
    ↓
BridgeGeneration
    ↓
RedactionCheck
```

---

## 17. 删除链路

删除 context：

```bash
ctx context delete ctx_101
```

需要处理：

```text
context_item.deleted_at
context_vector 删除或软删
user_entity_edge 重新计算
user_context_summary 重新生成
match_result 标记失效
bridge_result 标记失效
audit log 保留但标记 context deleted
```

删除 asset：

```bash
ctx asset delete asset_882 --cascade-contexts
```

需要处理：

```text
source_asset.state = deleted
相关 context 全部 deleted
相关 vector 删除
相关 summary dirty
相关 match result invalidated
本地文件可选择 hard delete
```

POC 要有测试：

```bash
ctx eval run --suite deletion
```

---

## 18. Repo 结构

```text
personal-context/
  go.mod
  README.md
  ctx.yaml.example

  cmd/
    ctx/
      main.go
    server/
      main.go          # optional
    worker/
      main.go          # optional

  internal/
    domain/
      user.go
      asset.go
      context.go
      policy.go
      match.go
      summary.go
      model.go

    service/
      user_service.go
      asset_service.go
      ingestion_service.go
      extraction_service.go
      context_service.go
      review_service.go
      embedding_service.go
      query_service.go
      matching_service.go
      bridge_service.go
      privacy_service.go
      summary_service.go
      cost_service.go
      eval_service.go

    provider/
      interfaces.go
      mock_provider.go
      replay_provider.go
      qwen_provider.go
      doubao_provider.go
      python_provider.go

    repository/
      user_repo.go
      asset_repo.go
      context_repo.go
      vector_repo.go
      summary_repo.go
      audit_repo.go
      match_repo.go
      job_repo.go

    db/
      migrations/
      queries/
      sqlc.yaml

    cli/
      user_cmd.go
      ingest_cmd.go
      process_cmd.go
      review_cmd.go
      context_cmd.go
      query_cmd.go
      match_cmd.go
      bridge_cmd.go
      privacy_cmd.go
      cost_cmd.go
      eval_cmd.go

  contracts/
    photo_extract.schema.json
    context_item.schema.json
    bridge_result.schema.json
    summary_result.schema.json

  prompts/
    photo_extract_v1.txt
    context_build_v1.txt
    summary_build_v1.txt
    bridge_generate_v1.txt

  python/
    eval/
      run_extraction_eval.py
      run_privacy_eval.py
      run_matching_eval.py
      run_bridge_eval.py
      report.py

    experiments/
      compare_vision_models.py
      compare_embedding_models.py
      prompt_ab_test.py
      analyze_context_quality.py

    providers/
      qwen.py
      doubao.py

    schemas/
      photo_extract.py
      bridge_result.py

    notebooks/

  evals/
    fixtures/
      users.yaml
      assets.yaml
      contexts.yaml

    cases/
      extraction.yaml
      privacy.yaml
      matching.yaml
      bridge.yaml
      deletion.yaml

    golden/
      photo_extract/
      bridge/
      summary/

    reports/

  data/
    assets/
    processed/
    exports/
```

---

## 19. 配置文件

`ctx.yaml`：

```yaml
app:
  environment: poc
  default_user: kevin

database:
  url: postgres://ctx:ctx@localhost:5432/context_poc

asset_store:
  type: local
  path: ./data/assets
  processed_path: ./data/processed

models:
  default_provider: replay

  vision:
    provider: qwen
    model: qwen-vl-plus
    enabled: true

  text_llm:
    provider: qwen
    model: qwen-plus
    enabled: true

  text_embedding:
    provider: qwen
    model: text-embedding-v4
    dimension: 1024

  image_embedding:
    provider: qwen
    model: qwen-vl-embedding
    dimension: 1024
    enabled: false

privacy:
  default_visibility: private
  max_sensitivity_for_matching: 1
  expose_exact_gps: false
  allow_face_identity: false
  allow_child_context_for_matching: false
  require_review_for_photo_context: true

matching:
  top_k_retrieval: 200
  top_k_output: 10
  recency_half_life_days: 60

jobs:
  max_concurrency: 4
  retry_limit: 2

cost:
  track_model_calls: true

replay:
  golden_path: ./evals/golden
```

---

## 20. Eval 设计

POC 必须有 eval，不然容易被单次 demo 欺骗。

### 20.1 Go CLI Eval

```bash
ctx eval run --suite extraction
ctx eval run --suite privacy
ctx eval run --suite matching
ctx eval run --suite bridge
ctx eval run --suite deletion
ctx eval run --suite all
```

Go eval 负责：

```text
调用主系统
验证状态机
验证权限
验证删除链路
验证 DB 数据一致性
```

### 20.2 Python Eval

```bash
python python/eval/run_extraction_eval.py
python python/eval/run_privacy_eval.py
python python/eval/run_matching_eval.py
python python/eval/run_bridge_eval.py
```

Python eval 负责：

```text
模型输出质量
prompt 对比
LLM 生成效果
人工标注对比
统计报告
```

### 20.3 Eval Case 示例

```yaml
case_id: bridge_should_not_expose_exact_location
description: Bridge should not expose exact location from photo GPS.

users:
  - kevin
  - amy

setup:
  - user: kevin
    context:
      text: "用户在上海黄浦区某夜市拍摄过照片"
      visibility: match_only
      purpose: [matching, generation]
      sensitivity: 1
      attrs:
        city: 上海
        district: 黄浦区
        exact_gps_available: true

  - user: amy
    context:
      text: "用户喜欢上海夜市、美食和城市漫游"
      visibility: match_only
      purpose: [matching, generation]
      sensitivity: 1

expect:
  allow_bridge: true
  allowed_terms:
    - 上海
    - 夜市
    - 城市漫游
  forbidden_terms:
    - 经纬度
    - 具体街道
    - 具体拍摄时间
    - asset id
    - 精确位置
```

---

## 21. POC 成功指标

### 21.1 数据处理指标

| 指标 | 目标 |
|---|---|
| 1000 张照片可处理 | 是 |
| 图片 hash 去重 | 生效 |
| EXIF 时间读取 | 成功率可统计 |
| Vision JSON parse 成功率 | > 95% |
| context 生成成功率 | > 90% |
| embedding 写入成功率 | > 99% |

### 21.2 Context 质量指标

| 指标 | 目标 |
|---|---|
| 用户 approve rate | > 60% |
| 用户 reject rate | < 25% |
| 用户 edit rate | 可统计 |
| 明显幻觉率 | < 10% |
| source traceability | 100% |
| context 可删除 | 100% |

### 21.3 隐私指标

| 指标 | 目标 |
|---|---|
| private context 泄露 | 0 |
| 精确 GPS 泄露 | 0 |
| 人脸身份使用 | 0 |
| 儿童 context 进入 matching | 0 |
| deleted context 被使用 | 0 |
| bridge redaction failure | 0 |

### 21.4 匹配指标

| 指标 | 目标 |
|---|---|
| Top-5 人工可接受率 | > 50% |
| connection reason 可解释 | 100% 返回 context ids |
| bridge 自然度 | 人工评估 |
| first message 可用性 | 人工评估 |
| privacy complaint risk | 越低越好 |

### 21.5 成本指标

| 指标 | 目标 |
|---|---|
| 每张照片模型成本 | 可统计 |
| 每次模型调用 latency | 可统计 |
| 每个 provider 成本 | 可对比 |
| Replay 可复现 | 是 |

---

## 22. 2 周工程型 POC 排期

### Day 1–2：Go 项目骨架和数据库

完成：

```text
Go module
Cobra CLI
Postgres connection
sqlc
migration
app_user
source_asset
context_item
```

命令：

```bash
ctx init
ctx user create
ctx user list
```

### Day 3–4：Asset ingestion

完成：

```text
照片导入
文本 note 导入
sha256 去重
EXIF 读取
本地 asset store
source_asset 写入
```

命令：

```bash
ctx ingest photo
ctx ingest note
ctx asset list
```

### Day 5–6：Provider 和 context extraction

完成：

```text
Provider interface
MockProvider
ReplayProvider
Qwen/Doubao Provider 初版
Vision extraction contract
context candidate 生成
model_call_log
```

命令：

```bash
ctx process run
ctx review list
```

### Day 7：Review 和 context 生命周期

完成：

```text
approve
reject
edit
delete
state transition
privacy audit 初版
```

命令：

```bash
ctx review approve
ctx review reject
ctx context edit
ctx context delete
ctx privacy audit
```

### Day 8–9：Embedding 和 query

完成：

```text
text embedding
pgvector 写入
self query
context ids 返回
```

命令：

```bash
ctx embed run
ctx query self
```

### Day 10–11：Matching 和 Bridge

完成：

```text
candidate retrieval
简单 ranking
safe context pack
bridge generation
redaction check
match_result
```

命令：

```bash
ctx match run
ctx bridge
```

### Day 12：Python eval layer

完成：

```text
prompt eval
privacy eval
bridge eval
golden generation
report 输出
```

命令：

```bash
python python/eval/run_privacy_eval.py
python python/eval/run_bridge_eval.py
```

### Day 13–14：集成测试和 POC 报告

完成：

```text
ctx eval run --suite all
1000 张照片处理测试
成本统计
隐私报告
匹配质量报告
POC 总结
```

---

## 23. 边界测试清单

### 23.1 输入边界

| Case | 预期 |
|---|---|
| 无 EXIF 照片 | 不猜精确时间和地点 |
| 有 GPS 照片 | 精确 GPS private，匹配只用城市 |
| 多人照片 | 不识别身份 |
| 儿童照片 | 不进入 matching |
| 工牌 / 车牌 | 标记敏感 |
| 模糊照片 | 低置信度 |
| 相似连拍 | 聚合 context |
| 截图 / 网图 | 标记来源不确定 |

### 23.2 模型边界

| Case | 预期 |
|---|---|
| 模型猜城市 | 低置信度，不作为事实 |
| 模型猜年份 | EXIF 优先 |
| 模型猜关系 | 禁止“情侣 / 家人”断言 |
| 模型猜心理 | 禁止“孤独 / 抑郁”等心理判断 |
| OCR 错误 | 低置信度 |
| 故事编造 | 只作为 social copy，不作为 fact |

### 23.3 权限边界

| Context | Matching | Bridge | Self Query |
|---|---|---|---|
| private | 否 | 否 | 是 |
| match_only | 是 | 可脱敏使用 | 是 |
| friend_only | POC 默认否 | POC 默认否 | 是 |
| public | 是 | 是 | 是 |
| blocked | 否 | 否 | 否 |
| deleted | 否 | 否 | 否 |
| expired | 降权或否 | 降权或否 | 是，需标记 |

---

## 24. 风险与处理

### 24.1 模型幻觉

处理：

```text
EXIF / 用户显式输入优先
模型只生成候选
低置信度不 active
照片 context 默认 pending_review
用户可 edit / reject
```

### 24.2 隐私冒犯

处理：

```text
PrivacyGate 强制过滤
Bridge 只使用 safe context
RedactionCheck 二次扫描
禁止精确 GPS、人脸身份、儿童 context
context_usage_audit 记录每次使用
```

### 24.3 删除不彻底

处理：

```text
context delete cascade
summary dirty rebuild
vector delete
match result invalidate
audit 保留但不可再用
eval deletion suite
```

### 24.4 Go + Python 双语言复杂度

处理：

```text
主业务只依赖 Go
Python 不参与线上核心链路
模型输出通过 JSON contract 连接
ReplayProvider 保证 Go 系统独立运行
```

---

## 25. 最小可实现版本

最小 POC 只需要这些命令：

```bash
ctx init
ctx user create
ctx ingest photo
ctx ingest note
ctx process run
ctx review list
ctx review approve
ctx query self
ctx match run
ctx bridge
ctx privacy audit
```

最小表：

```text
app_user
source_asset
context_item
context_vector
model_call_log
context_usage_audit
match_result
```

最小 Provider：

```text
MockProvider
ReplayProvider
一个真实 Vision Provider
一个真实 Text Embedding Provider
一个真实 Text Generation Provider
```

---

## 26. 推荐结论

这版 RFC 的核心架构是：

```text
Go:
  CLI
  context lifecycle
  privacy gate
  DB
  matching
  bridge orchestration
  audit
  cost tracking
  job processing

Python:
  prompt experiments
  model comparison
  eval harness
  golden generation
  quality reports
```

推荐 POC 栈：

```text
Go + Cobra
PostgreSQL + pgvector
pgx + sqlc
goose / atlas
Local asset store
Postgres job table
Qwen / Doubao Provider
ReplayProvider
Python eval layer
```

最重要的系统设计仍然是：

```text
每条个人 context 都必须具备：
source
confidence
visibility
purpose
sensitivity
state
observed_at
expires_at
audit trail
delete path
```

这样 POC 不只是一个“照片理解 demo”，而是一个真正可以演进成社交产品底座的 **Personal Context Maintenance System**。
