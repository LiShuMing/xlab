# 第30章：测试与 Benchmark

> 没有测试的代码是不可信的。DuckDB 的测试体系覆盖了从 SQL 语义到并发正确性的各个层面，且以 SQL 驱动的方式让测试可读、可维护、可扩展。

## 30.1 .test / .test_slow 体系：SQL 驱动的回归测试

### 测试文件格式

DuckDB 使用自定义的 `.test` 文件格式，以 SQL 语句和预期结果驱动：

```
# test/sql/copy/parquet/read_parquet.test

statement ok
CREATE TABLE test AS SELECT * FROM read_parquet('test.parquet');

query I
SELECT COUNT(*) FROM test
----
1000

query RRI
SELECT avg(col1), sum(col2), count(*) FROM test WHERE col1 > 50
----
52.3, 45678.9, 500

statement error
SELECT * FROM nonexistent_table
----
Catalog Error: Table with name nonexistent_table does not exist
```

关键语法：
- `statement ok` — 期望执行成功
- `statement error` — 期望执行失败，后跟错误消息匹配
- `query <types>` — 执行查询，`<types>` 指定每列的类型（I=整数, R=实数, T=文本, B=布尔）
- `----` 分隔查询和预期结果
- `hash-threshold` — 控制结果哈希比较，避免大规模结果的精确匹配

### .test_slow

`.test_slow` 文件只在慢速测试模式下运行，通常包含耗时的大数据量测试。CI 中默认不运行，仅在完整测试时执行。

### 测试目录组织

```
test/sql/
├── aggregate/        # 聚合函数测试
├── catalog/          # 目录操作测试
├── copy/             # COPY 和文件格式测试
├── create/           # DDL 测试
├── filter/           # 过滤条件测试
├── function/         # 内置函数测试
├── index/            # 索引测试
├── join/             # Join 测试
├── noise_page/       # 页面噪声测试
├── prepared/         # 预处理语句测试
├── raft/             # Raft 一致性测试
├── rename/           # 重命名测试
├── rollup/           # Rollup 测试
├── subquery/         # 子查询测试
├── timestamp/        # 时间戳测试
├── transaction/      # 事务测试
├── window/           # 窗口函数测试
└── ...
```

每个子目录按功能领域组织，新特性有专门的子目录。

## 30.2 BenchmarkRunner：micro/macro benchmark 的设计

### Benchmark 框架

DuckDB 的 benchmark 系统位于 `test/extension/tpch/dbgen/` 和 `benchmark/` 目录：

```cpp
// benchmark 目录结构
benchmark/
├── micro/          # 微基准测试（单个算子）
│   ├── filter/
│   ├── join/
│   ├── aggregate/
│   └── scan/
├── tpch/           # TPC-H 基准测试
├── tpcc/           # TPC-C 基准测试
└── clickbench/     # ClickBench 基准测试
```

### Benchmark 运行方式

```bash
# 运行单个 benchmark
./build/release/benchmark/benchmark_runner benchmark/micro/filter/int_filter.bench

# 运行 TPC-H
./build/release/benchmark/benchmark_runner benchmark/tpch/tpch_sf1.bench

# 运行所有 micro benchmark
./build/release/benchmark/benchmark_runner benchmark/micro/
```

每个 benchmark 文件指定查询、数据规模、运行次数等参数。`BenchmarkRunner` 负责加载数据、执行查询、收集计时信息。

## 30.3 ClickBench / TPC-H / TPC-DS 的测试覆盖

### TPC-H

DuckDB 提供完整的 TPC-H 支持作为扩展：

```sql
-- 安装并加载 TPC-H 扩展
INSTALL tpch;
LOAD tpch;

-- 生成数据（SF 1 = ~1GB）
CALL dbgen(sf=1);

-- 运行全部 22 条查询
PRAGMA tpch_queries;
```

TPC-H 的 22 条查询覆盖了：
- 单表扫描 + 过滤 + 聚合（Q1, Q6）
- 多表 Join + 子查询（Q2, Q4, Q13, Q17）
- 排序 + LIMIT（Q3, Q5, Q10）
- 复杂嵌套子查询（Q7, Q8, Q9）
- 窗口函数（Q18, Q22）

### ClickBench

ClickBench 是专门为分析型数据库设计的基准，基于真实广告流量数据：

- 单表，1 亿行，105 列
- 混合数据类型（整数、字符串、日期）
- 43 条查询覆盖点查、范围查询、聚合、Top-N

DuckDB 在 ClickBench 上表现优异，特别是在单机场景下——这得益于向量化执行 + 列式存储 + Zone Map 裁剪的协同。

### TPC-DS

TPC-DS 是比 TPC-H 更复杂的决策支持基准：

- 99 条查询
- 多表 Join、复杂嵌套、窗口函数、递归
- 数据倾斜和异常值

DuckDB 支持 TPC-DS 的绝大多数查询，少数不支持的特性（如递归 CTE 的某些模式）正在开发中。

## 30.4 Sanitizers：ThreadSanitizer、LeakSanitizer 在 DuckDB 中的实践

### 编译与运行

```bash
# ThreadSanitizer 构建
cmake -DCMAKE_BUILD_TYPE=Debug -DENABLE_THREAD_SANITIZER=1 ..
make -j

# AddressSanitizer 构建
cmake -DCMAKE_BUILD_TYPE=Debug -DENABLE_ADDRESS_SANITIZER=1 ..
make -j

# UndefinedBehaviorSanitizer 构建
cmake -DCMAKE_BUILD_TYPE=Debug -DENABLE_UNDEFINED_SANITIZER=1 ..
make -j
```

### ThreadSanitizer (TSan)

DuckDB 的并发模型依赖原子操作和精细的锁层次。TSan 检测：
- 数据竞争（两个线程同时访问同一内存，至少一个写入）
- 死锁（锁的获取顺序不一致）
- TSan 误报（DuckDB 中的某些无锁数据结构会触发 TSan 误报，通过注解抑制）

### AddressSanitizer (ASan)

ASan 检测：
- 堆缓冲区溢出
- 栈缓冲区溢出
- 使用后释放（Use-After-Free）
- 双重释放（Double-Free）
- 内存泄漏（配合 LeakSanitizer）

### 在 CI 中的使用

DuckDB 的 CI 矩阵包括 Sanitizer 构建：
- 每次提交都运行 ASan + TSan 测试
- 只运行 `.test` 文件（不运行 `.test_slow`），控制运行时间
- 发现问题时阻止合并

## 30.5 CMake 测试配置

```cmake
# 核心测试命令
ctest --output-on-failure         # 运行所有测试
ctest -R sql -j8                  # 并行运行 SQL 测试
ctest -R unittest                  # 运行 C++ 单元测试
```

DuckDB 使用 CTest 组织测试。SQL 测试通过 `test_sqlite_test.sh` 或直接调用测试运行器执行。单元测试使用 Catch2 框架。

## 本章小结

DuckDB 的测试体系体现了一个务实的选择：**SQL 即测试**。

- `.test` 文件让测试可读、可写、可维护——数据库工程师用 SQL 写测试，不需要学框架
- TPC-H/ClickBench 提供行业标准基准，确保性能不退化
- Sanitizer 在 CI 中捕获并发和内存错误——这在 C++ 代码库中至关重要

与 PostgreSQL 的对比：PostgreSQL 使用 TAP（Test Anything Protocol）+ 自定义的 `pg_regress` 框架。DuckDB 的 `.test` 格式更简洁，但不如 TAP 成熟。与 Spark 的对比：Spark 使用 ScalaTest + 黄金文件，测试粒度更粗。DuckDB 的 SQL 驱动测试让每个优化规则都有细粒度的回归覆盖。
