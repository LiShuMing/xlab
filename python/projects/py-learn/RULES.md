
RULES:
1. 统一使用/home/lism/.venv/general-3.12的venv环境;
2. 大模型相关的交互统一使用~/.env中LLM_xxx相关的配置(基于openai sdk的qwen coding plan);
3. 使用Python强类型格式，符合现代python语言设计；
4. 架构层面，接口优先，注释充分，同时提供实现文档、使用文档说明；
5. 每次变更输出到CHNAGES_LOG.md日志中，记录修复问题、实现功能，以防止重复处理；
6. 针对大的任务，使用拆解任务的方式进行:先生成TASKS.md记录需要完成的tasks，然后基于task逐条/并行执行.
