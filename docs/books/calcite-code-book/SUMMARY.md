# 《Apache Calcite 内核实现原理：从源码到本质》

## 目录

### 第一篇：奠基 — 理解 Calcite 的设计哲学
- [第1章：Calcite 的第一性原理](ch01-first-principles.md)
- [第2章：类型系统](ch02-type-system.md)

### 第二篇：SQL 解析 — 从文本到结构
- [第3章：SQL Parser](ch03-sql-parser.md)
- [第4章：SQL 验证](ch04-sql-validator.md)

### 第三篇：代数转换 — 从 SQL 到关系代数
- [第5章：SqlToRelConverter](ch05-sql-to-rel.md)
- [第6章：Rex 表达式体系](ch06-rex-expression.md)
- [第7章：RelNode 体系](ch07-relnode.md)

### 第四篇：查询优化 — 搜索最优计划
- [第8章：优化器框架](ch08-planner-framework.md)
- [第9章：Volcano Planner](ch09-volcano-planner.md)
- [第10章：Hep Planner](ch10-hep-planner.md)
- [第11章：优化规则深度解析](ch11-optimization-rules.md)
- [第12章：元数据系统](ch12-metadata-system.md)

### 第五篇：物理执行 — 从代数到代码
- [第13章：Convention 与代码生成](ch13-convention-codegen.md)
- [第14章：解释执行与运行时](ch14-interpreter-runtime.md)

### 第六篇：Schema 与适配器 — 连接外部世界
- [第15章：Schema 体系](ch15-schema.md)
- [第16章：适配器架构](ch16-adapter.md)
- [第17章：SQL 方言与双向转换](ch17-dialect.md)

### 第七篇：高级主题与前沿
- [第18章：物化视图与 Lattice](ch18-materialized-view.md)
- [第19章：关联子查询与解关联](ch19-correlation-decorrelation.md)
- [第20章：JDBC 集成与查询全流程](ch20-jdbc-lifecycle.md)
- [第21章：Hints 系统](ch21-hints.md)
- [第22章：流式查询与时态表](ch22-streaming.md)

### 第八篇：实战与演进
- [第23章：调试与诊断](ch23-debug-diagnosis.md)
- [第24章：性能基准与微基准测试](ch24-benchmark.md)
- [第25章：AI 时代的查询优化](ch25-ai-future.md)

### 附录
- [附录A：版本演进史](appendix-a-version-history.md)
- [附录B：源码阅读指南](appendix-b-source-index.md)
- [附录C：RelNode 完整继承体系图](appendix-c-relnode-hierarchy.md)
- [附录D：优化规则速查表](appendix-d-rules-reference.md)
- [附录E：SqlKind 枚举全量参考](appendix-e-sqlkind-reference.md)
- [附录F：自定义适配器 CheckList](appendix-f-adapter-checklist.md)
