# py-ego Change Logs

## 2026-03-23 - Feature: English Comments & Command History

### Summary
Two enhancements:
1. Added bilingual (Chinese + English) comments to all role model fields
2. Implemented command history with up/down arrow key navigation

### Files Modified

| File | Changes |
|------|---------|
| `roles/role.py` | Added English comments to `RoleStyle`, `RoleKnowledge`, `RolePersonality`, `RoleExample`, `Role` classes and all their fields. Format: "English comment / 中文说明" |
| `main.py` | Added `setup_readline()` function for command history. Added `get_input_with_history()` wrapper. History persisted to `data/.input_history`. Max 1000 entries. |

### New Features

**Command History (上下键历史)**
- Up arrow (↑): Navigate to previous command
- Down arrow (↓): Navigate to next command
- History persists across sessions in `data/.input_history`
- Works on macOS/Linux (uses built-in `readline` module)

**Bilingual Field Comments**
```python
class RolePersonality(BaseModel):
    background: str  # Professional background... / 背景故事
    traits: list[str]  # Personality traits... / 性格特点
    speaking_style: str  # How the role communicates... / 说话风格
    catchphrases: list[str]  # Signature phrases... / 口头禅
```

### Test Results
- 17/17 tests passing
- Application runs correctly with history support

---

## 2026-03-23 - Docs: Added File Modification Policy

### Summary
Added a new rule to `CLAUDE.md` for file modification safety.

### File Modified
- `CLAUDE.md`: Added "File Modification Policy" section

### New Rule
```
# File Modification Policy
- **配置文件保护:** 不要擅自修改配置文件（如 `.env`、`settings.json`、`pyproject.toml` 等）。
- **目录边界:** 尽量不要修改本目录以外的文件。如果需要修改外部文件，务必同使用者再三确认。
- **确认流程:** 任何跨目录或配置相关的修改，必须：
  1. 明确告知用户要修改的文件路径
  2. 说明修改原因和内容
  3. 等待用户明确同意后再执行
```

---

## 2026-03-23 - Feature: Rich Role System with Character Depth

### Summary
Enhanced role system with four dimensions for richer, more immersive character interactions:
1. **背景故事 (Personality)** - Professional background, character traits, speaking style, catchphrases
2. **知识库 (Knowledge)** - Domain expertise, key concepts, classic quotes, references
3. **示例对话 (Examples)** - Few-shot dialogues showing the role's speaking style
4. **关系记忆 (Relationship)** - Long-term memory of interactions with each user

### New Models

```python
class RolePersonality(BaseModel):
    background: str              # "你在北京大学心理学系深造..."
    traits: list[str]            # ["温和", "耐心", "共情", "专业"]
    speaking_style: str          # "温暖、理解、引导式提问..."
    catchphrases: list[str]      # ["我听到了你的感受", "我们一起来看看"]

class RoleKnowledge(BaseModel):
    domain_expertise: list[str]  # ["认知行为疗法", "正念减压"]
    key_concepts: list[str]      # ["认知扭曲", "情绪颗粒度"]
    classic_quotes: list[str]    # ["「情绪就像天气...」"]
    references: list[str]        # ["《认知疗法》- Judith Beck"]

class RoleExample(BaseModel):
    context: str | None          # "用户表达了焦虑情绪"
    user_input: str              # "最近总是睡不着..."
    assistant_response: str      # "听起来工作压力让你很困扰..."
```

### Files Modified

| File | Changes |
|------|---------|
| `roles/role.py` | Added `RolePersonality`, `RoleKnowledge`, `RoleExample` models. Added `build_full_system_prompt()` and `build_examples_context()` methods. Enriched all 4 predefined roles with detailed personality, knowledge, and examples. |
| `roles/role_manager.py` | Added `RelationshipManager` class for relationship memory. Added `get_system_prompt()` that combines all dimensions. Added `get_examples_context()` for few-shot learning. |
| `chat_service.py` | Updated `ChatContext` to include examples. Uses `get_system_prompt()` for full prompt with personality/knowledge/relationship. |

### Predefined Role Details

**心理陪护师 (Therapist)**
- 背景：北大心理学博士，5000+小时咨询经验
- 特点：温和、耐心、共情、不评判
- 领域：CBT、正念减压、情绪聚焦疗法
- 口头禅："我听到了你的感受"、"你愿意多说说吗？"

**研究员 (Researcher)**
- 背景：清华社科博士，顶级智库工作经历
- 特点：严谨、客观、逻辑性强
- 领域：社会科学研究方法、政策分析
- 口头禅："从研究的角度来看"、"数据显示"

**学习者 (Learner)**
- 背景：学习科学研究者，终身学习践行者
- 特点：耐心、鼓励型、善于比喻
- 领域：认知科学、间隔重复、费曼学习法
- 口头禅："让我们一步步来"、"试试这个练习"

**哲学家 (Philosopher)**
- 背景：哈佛哲学系深造，专攻存在主义和东方哲学
- 特点：深邃、温和、善问、开放
- 领域：存在主义、东方哲学、伦理学
- 口头禅："这让我想起"、"你有没有想过"

### System Prompt Construction

The full system prompt is now built dynamically:

```
[Base system prompt]

## 你的背景
[personality.background]

## 你的性格特点
[personality.traits joined]

## 你的说话风格
[personality.speaking_style]

## 你常用的表达方式
[personality.catchphrases]

## 你的专业领域
[knowledge.domain_expertise joined]

## 你熟悉的核心概念
[knowledge.key_concepts bulleted]

## 你可以引用的经典语录
[knowledge.classic_quotes bulleted]

## 你与用户的关系记忆
[relationship memory]
```

### Data Structure

```
data/
├── profile.md                    # 全局画像
├── profile_therapist.md          # 心理陪护师专属画像
├── relationship_therapist.md     # 与心理陪护师的关系记忆
├── therapist/
│   ├── memory.json
│   ├── faiss.index
│   └── dim.txt
├── researcher/
│   └── ...
└── ...
```

### Test Results
- 17/17 tests passing
- Role switching works correctly
- Rich system prompt builds correctly

---

## 2026-03-23 - Feature: Multi-Agent Role System

### Summary
Implemented a multi-role system that abstracts the therapist persona into a configurable agent system.

### Files Created

| File | Lines | Purpose |
|------|-------|---------|
| `roles/__init__.py` | 6 | Role package initialization |
| `roles/role.py` | 185 | `Role` Pydantic model with predefined roles |
| `roles/role_manager.py` | 145 | `RoleManager` for loading, switching roles |

### Files Modified

| File | Changes |
|------|---------|
| `profile.py` | Added layered profile support: global + role-specific |
| `chat_service.py` | Now accepts `RoleManager`, delegates memory/profile to role manager |
| `cli/ui.py` | All print methods accept optional `Role` parameter |
| `cli/commands.py` | Added `/role`, `/roles`, `/roleinfo` commands |
| `main.py` | Initializes `RoleManager`, prompt shows role icon |

### Design Decisions
1. **独立记忆**: Each role has its own `data/{role_id}/` directory
2. **分层画像**: Global `profile.md` + role-specific `profile_{role_id}.md`

---

## 2026-03-23 - Major Refactoring: Modern Python & AI Agent Architecture

### Summary
Refactored the entire codebase to align with CLAUDE.md standards.

### Files Created

| File | Lines | Purpose |
|------|-------|---------|
| `exceptions.py` | 55 | Custom exception hierarchy |
| `models.py` | 70 | Pydantic models |
| `llm_client.py` | 96 | LLM client wrapper |
| `chat_service.py` | 138 | Core chat business logic |
| `profile.py` | 111 | User profile management |
| `cli/__init__.py` | 6 | CLI package |
| `cli/ui.py` | 271 | Terminal UI utilities |
| `cli/commands.py` | 119 | Slash command handlers |

### Files Modified

| File | Changes |
|------|---------|
| `config.py` | Migrated to Pydantic Settings |
| `embeddings.py` | Added type hints, silent fallback |
| `memory_store.py` | Added type hints, configurable data_dir |
| `main.py` | Simplified to thin entry point |
| `requirements.txt` | Added pydantic, structlog |

### Test Results
- 17/17 tests passing
- Application starts correctly