# 变更日志

## 2026-04-06

### 新增功能

1. **项目基础架构**
   - 创建项目目录结构 (src/, tests/, data/, logs/)
   - 添加配置文件 (config.yaml, topics.yaml)
   - 添加依赖文件 (requirements.txt)

2. **数据库模块 (src/db.py)**
   - 实现 SQLite 数据库封装
   - 支持 domains, topics, questions, answers, topic_stats, hot_topics 表
   - 提供完整的 CRUD 操作和统计查询

3. **配置模块 (src/config.py)**
   - 支持从 YAML 文件加载配置
   - 支持环境变量替换 (${VAR} 和 ${VAR:default} 格式)
   - 自动从 ~/.env 读取 LLM 配置

4. **Plan 模块 (src/plan.py)**
   - 实现领域轮转策略 (周一至周日不同领域)
   - 实现 Topic 加权随机选择算法
   - 实现难度自适应调整逻辑
   - 实现题型选择器

5. **Tools 模块 (src/tools/)**
   - knowledge.py: 知识图谱工具，从 topics.yaml 加载知识
   - memory.py: 记忆读取工具，查询历史记录和统计
   - crawler.py: 热点爬虫工具 (预留接口)

6. **Generate 模块 (src/generate.py)**
   - 实现基于 LLM 的题目生成
   - 支持系统提示词和上下文构建
   - 实现题目质量验证和重试机制

7. **Reflect 模块 (src/reflect.py)**
   - 实现基于 LLM 的答案评估
   - 多维度评分 (概念/深度/边界)
   - 自动更新 topic 统计和难度

8. **Telegram Bot 模块 (src/bot.py)**
   - 实现消息推送和命令处理
   - 支持 /hint, /skip, /status, /history, /weak 等命令
   - 答案收集和回调机制

9. **Scheduler 模块 (src/scheduler.py)**
   - 基于 APScheduler 的定时任务
   - 支持每日推送、提醒、超时处理
   - 支持手动触发

10. **主入口 (src/main.py)**
    - 整合所有模块的 DailyLearningAgent 类
    - 支持调度器模式和单次运行模式
    - 完整的题目生成-推送-评估流程

### 设计特点

- 遵循 Python 强类型设计 (Type Hints)
- 接口优先，充分注释
- 模块化架构，职责清晰
- 支持自适应难度调整
- 完整的错误处理和日志记录
