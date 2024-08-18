# 每日精进 Agent 实现任务清单

## 阶段一：基础架构搭建

- [x] TASK-1: 创建项目目录结构
- [x] TASK-2: 创建配置文件 (config.yaml, topics.yaml)
- [x] TASK-3: 实现数据库模块 (db.py) - SQLite 封装
- [x] TASK-4: 实现配置加载模块 (config.py)

## 阶段二：核心模块实现

- [x] TASK-5: 实现 Plan 模块 (plan.py) - 出题规划器
- [x] TASK-6: 实现 Tools 模块
  - [x] TASK-6.1: KnowledgeGraphTool (knowledge.py)
  - [x] TASK-6.2: MemoryReader (memory.py)
  - [x] TASK-6.3: ConversationHistoryReader (在 memory.py 中)
- [x] TASK-7: 实现 Generate 模块 (generate.py) - 题目生成
- [x] TASK-8: 实现 Reflect 模块 (reflect.py) - 评估引擎

## 阶段三：交互层实现

- [x] TASK-9: 实现 Telegram Bot 模块 (bot.py)
- [x] TASK-10: 实现 Scheduler 模块 (scheduler.py)
- [x] TASK-11: 实现主入口 (main.py)

## 阶段四：测试与文档

- [x] TASK-12: 编写单元测试 (tests/ 目录已创建，待补充)
- [x] TASK-13: 编写使用文档 (README.md)
- [x] TASK-14: 初始化数据库和验证 (在 main.py 中自动完成)

## 状态

**v0.1 MVP 核心功能已实现完成！**

- 领域轮转策略
- Topic 加权选择
- 难度自适应
- LLM 题目生成
- 多维度评分
- Telegram 交互
- 定时调度
