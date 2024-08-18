# 附录 C：参考资源与社区贡献指南

## 官方资源

| 资源 | 链接 | 说明 |
|------|------|------|
| DuckDB 官网 | https://duckdb.org/ | 文档、博客、API 参考 |
| DuckDB GitHub | https://github.com/duckdb/duckdb | 源码、Issue、PR |
| DuckDB Labs | https://duckdblabs.com/ | 商业支持、咨询 |
| DuckDB Foundation | https://duckdb.org/foundation/ | 开源治理、捐赠 |
| MotherDuck | https://motherduck.com/ | 云端 DuckDB |
| DuckLake | https://ducklake.select/ | Lakehouse 格式规范 |

## 关键论文

1. **"Data Management for Data Science — Towards Embedded Analytics"** (CIDR 2020)
   — DuckDB 的学术宣言，定义了"嵌入式分析"范式

2. **"MonetDB/X100: Hyper-Pipelining Query Execution"** (CIDR 2005)
   — 向量化执行的理论基础

3. **"Saving Private Hash Join"** (VLDB 2025)
   — DuckDB Hash Join 溢出处理的优化

4. **"Run-time Efficient On-the-Fly Data Loading"** (CIDR 2025)
   — 运行时可扩展解析器

5. **"Data Blocks: Join-Aware Query Processing for Block-Based Storage"** (ICDE 2022)
   — Block 级别的存储与查询优化

6. **Peter Boncz 博士论文** "Database Architecture Solutions for Performance and Functionality" (2002)
   — BAT 代数的理论基础

## 源码阅读建议

### 推荐阅读顺序

```
第一遍（建立全景）:
  1. src/include/duckdb/main/database.hpp    — 全局入口
  2. src/include/duckdb/main/connection.hpp  — 查询入口
  3. src/include/duckdb/common/types.hpp     — 类型系统
  4. src/include/duckdb/common/types/vector.hpp — 向量
  5. src/include/duckdb/storage/storage_info.hpp — 存储常量

第二遍（理解数据流）:
  1. Parser → Binder → Planner → Optimizer → Executor
  2. 跟踪一条简单 SQL 的完整执行路径

第三遍（深入模块）:
  按本书章节顺序，每个模块读关键头文件 + 一个实现文件
```

### 调试技巧

```bash
# 编译 Debug 版本
cmake -DCMAKE_BUILD_TYPE=Debug ..
make -j

# 启用 PRAGMA debug
./build/debug/duckdb
PRAGMA enable_progress_bar;
PRAGMA enable_object_cache;

# 查看逻辑计划
EXPLAIN SELECT * FROM t WHERE a > 10;

# 查看物理计划
EXPLAIN ANALYZE SELECT * FROM t WHERE a > 10;

# 禁用优化器（调试逻辑计划）
SET enable_optimizer=false;

# 查看查询 Profile
PRAGMA enable_profiling;
SELECT * FROM t WHERE a > 10;
```

## 社区贡献指南

### 贡献方式

1. **Bug 报告**：在 GitHub Issues 提交，附上复现步骤和 DuckDB 版本
2. **代码贡献**：Fork → 分支 → PR，需通过 CI 和代码审查
3. **测试贡献**：添加 `.test` 文件覆盖边界情况
4. **文档贡献**：改进官方文档或博客文章
5. **扩展开发**：开发新的 DuckDB Extension

### 代码风格

- C++17 标准
- 4 空格缩进
- 成员变量使用 `snake_case`
- 类名使用 `PascalCase`
- 析构函数不在头文件中内联（确保前向声明兼容）
- 所有公共 API 通过 `src/include/duckdb/` 导出

### 测试要求

- 每个 Bug Fix 必须附带回归测试
- 新功能必须有 `.test` 文件覆盖
- 运行 `ctest -R sql` 确保所有 SQL 测试通过
- 修改并发代码时运行 ThreadSanitizer 测试

### PR 审查流程

1. 自动 CI 检查（编译、测试、Sanitizer）
2. 核心团队成员代码审查
3. 至少一位审查者批准后合并
4. 大型 PR 建议先开 Issue 讨论方案

## 推荐扩展阅读

### 列式数据库

- *The Design and Implementation of Modern Column-Oriented Database Systems* (Abadi et al., 2013) — 列式数据库的权威综述
- *C-Store: A Column-oriented DBMS* (Stonebraker et al., 2005) — 最早的商业列式数据库之一

### 向量化执行

- *Vectorization vs. Compilation in Query Execution* (Kersten et al., 2018) — 向量化 vs 编译执行的对比
- *Everything You Always Wanted to Know About Compiled and Vectorized Queries But Were Afraid to Ask* (Kersten et al., 2019) — 更深入的对比

### 事务与并发

- *MVCC: A Practical Multi-Version Concurrency Control* (Bernstein et al., 1987) — MVCC 的经典论文
- *A Critique of ANSI SQL Isolation Levels* (Berenson et al., 1995) — 事务隔离级别的批判性分析

### 嵌入式数据库

- *Architecture of a Database System* (Hellerstein et al., 2007) — 数据库系统架构的综述
- *SQLite: Past, Present, and Future* (Gaffney et al., 2022) — 嵌入式数据库的前辈

### Lakehouse

- *Lakehouse: A New Generation of Open Platforms that Unify Data Warehousing and Advanced Analytics* (Armbrust et al., 2021) — Lakehouse 概念的提出
- *Apache Iceberg: An Open Table Format for Huge Analytic Datasets* — Iceberg 规范
