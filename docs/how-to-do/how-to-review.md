# How to Do Code Review: A Senior Engineer's Guide

> **定位**：面向高级/资深开发者的现代化 Code Review 指南
> **适用场景**：OLAP 数据库引擎、分布式系统、高性能 C++ 服务
> **版本**：2026.03 - AI Era Edition

---

## Part 1: Core Principles

### 1.1 Code Review 的本质

Code Review 不是找茬，而是：

1. **质量关口** - 防止技术债务累积的第一道防线
2. **知识传递** - 让团队理解系统演进的方向和约束
3. **风险预判** - 在代码合并前识别潜在的线上故障
4. **能力建设** - 通过 Review 培养团队的技术品味

### 1.2 AI 时代的 Review 范式转变

| 传统 Review | AI-Era Review |
|-------------|---------------|
| 关注语法、格式、命名 | 这些由 Linter/Formatter/AI 预处理 |
| 逐行阅读代码 | 先读 PR 摘要和变更范围 |
| 人工发现所有问题 | 用 AI 辅助识别模式化问题 |
| 关注"代码是否正确" | 关注"代码是否适合系统" |

**Reviewer 的新职责**：

```text
┌─────────────────────────────────────────────────────────────┐
│  AI/Linter 处理的领域          │  Reviewer 聚焦的领域          │
├─────────────────────────────────────────────────────────────┤
│  - 格式规范                   │  - 业务逻辑正确性            │
│  - 基础命名                   │  - 系统边界约束              │
│  - 简单语法错误               │  - 并发安全性                │
│  - 单元测试覆盖率数字         │  - 性能回归风险              │
│  - 明显的安全漏洞             │  - 技术债的引入              │
│                               │  - 可维护性和可观测性        │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 资深工程师的 Review 视角

```text
Junior Reviewer:     "这个变量命名不符合规范"
Senior Reviewer:     "这个抽象是否泄露了实现细节？"

Junior Reviewer:     "这里缺少一个单元测试"
Senior Reviewer:     "这个测试是否覆盖了真实的故障场景？"

Junior Reviewer:     "代码功能看起来正确"
Senior Reviewer:     "代码在极端负载下是否依然稳健？"
```

---

## Part 2: The Review Checklist (分级)

### Level 1: P0 - 必须修复 (Blocking)

这些问题必须修复，否则不得合并。

#### 1.1 功能正确性

- [ ] 逻辑是否实现了预期的业务行为？
- [ ] 边界条件是否处理？（空输入、极大值、负数、超时、重试）
- [ ] 错误路径是否正确处理？是否有资源泄漏？
- [ ] 是否存在未定义行为 (UB)？

**AI 幻觉重点审查**：
```cpp
// AI 生成的代码：看似正确，但存在隐患
auto result = std::get_if<int>(&variant);
return *result;  // BUG: 未检查 result 是否为 nullptr

// 正确写法
auto result = std::get_if<int>(&variant);
if (!result) throw std::bad_variant_access();
return *result;
```

#### 1.2 并发安全

- [ ] 共享状态的访问是否有适当的同步？
- [ ] 是否存在死锁风险？（锁顺序、循环等待）
- [ ] 是否使用了正确的内存序？（memory_order）
- [ ] 是否存在数据竞争？（Data Race）

**OLAP 引擎场景**：
```cpp
// 反例：伪共享 (False Sharing)
struct Counter {
    int64_t count1;  // 线程 1 频繁写入
    int64_t count2;  // 线程 2 频繁写入 - 在同一 Cache Line
};

// 正例：Cache Line 对齐
struct alignas(64) CacheAlignedCounter {
    int64_t count;
    char padding[64 - sizeof(int64_t)];  // 填充到 Cache Line
};
```

#### 1.3 内存安全

- [ ] 是否使用智能指针替代裸指针？
- [ ] 是否存在悬垂引用/指针？
- [ ] 是否有内存泄漏风险？（异常路径、提前返回）
- [ ] 是否存在缓冲区溢出？

**StarRocks 向量化执行场景**：
```cpp
// 反例：频繁的内存分配导致碎片和放大
ColumnPtr create_column() {
    auto col = std::make_unique<Column>();
    for (int i = 0; i < 1000; ++i) {
        col->append(get_value(i));  // 每次 append 可能触发 realloc
    }
    return col;
}

// 正例：预分配容量
ColumnPtr create_column() {
    auto col = std::make_unique<Column>();
    col->reserve(1000);  // 预分配，避免多次 realloc
    for (int i = 0; i < 1000; ++i) {
        col->append(get_value(i));
    }
    return col;
}
```

#### 1.4 分布式一致性

- [ ] RPC 超时/失败是否有重试机制？
- [ ] 重试是否幂等？
- [ ] 是否存在部分成功导致的状态不一致？
- [ ] 是否有事务语义保证？

### Level 2: P1 - 强烈建议修复 (Should Fix)

这些问题应该修复，但可以由 Tech Lead 权衡后决定是否阻塞合并。

#### 2.1 性能风险

- [ ] 是否存在不必要的内存拷贝？
- [ ] 是否有更高效的算法选择？
- [ ] 是否充分利用了 SIMD 优化？
- [ ] 循环中是否有可提升的热点代码？

**SIMD 优化示例**：
```cpp
// 标量版本：慢
void add_arrays_scalar(float* a, float* b, float* c, size_t n) {
    for (size_t i = 0; i < n; ++i) {
        c[i] = a[i] + b[i];
    }
}

// SIMD 版本：快 4-8 倍
void add_arrays_simd(float* a, float* b, float* c, size_t n) {
    size_t i = 0;
    for (; i + 7 < n; i += 8) {
        __m256 va = _mm256_loadu_ps(a + i);
        __m256 vb = _mm256_loadu_ps(b + i);
        _mm256_storeu_ps(c + i, _mm256_add_ps(va, vb));
    }
    for (; i < n; ++i) {
        c[i] = a[i] + b[i];
    }
}
```

#### 2.2 可观测性

- [ ] 关键路径是否有日志？日志级别是否合理？
- [ ] 是否有 Metrics 暴露内部状态？
- [ ] 是否有 Tracing 支持调用链追踪？
- [ ] 错误信息是否足够诊断问题？

**日志最佳实践**：
```cpp
// 反例：信息不足
LOG(ERROR) << "Query failed";

// 正例：包含诊断信息
LOG(ERROR) << "Query failed: query_id=" << query_id
           << ", fragment_id=" << fragment_id
           << ", error_code=" << status.code()
           << ", message=" << status.message();
```

#### 2.3 异常安全

- [ ] 是否满足基本异常安全保证？（无资源泄漏）
- [ ] 关键操作是否满足强异常安全保证？（事务性）
- [ ] noexcept 是否正确标注？
- [ ] 异常路径是否可恢复？

#### 2.4 测试质量

- [ ] 单元测试是否覆盖核心边界用例？
- [ ] 是否有并发压力测试？
- [ ] 是否有内存泄漏检测？（ASAN/LSAN）
- [ ] 测试是否稳定、可重复？

**边界用例覆盖**：
```cpp
// 测试不应只覆盖"快乐路径"
TEST(TestFilter, NormalCase) {
    Filter filter({1, 2, 3});
    ASSERT_EQ(filter.apply(2), true);
}

// 应该覆盖边界和异常情况
TEST(TestFilter, EdgeCases) {
    // 空输入
    Filter empty_filter({});
    ASSERT_EQ(empty_filter.apply(0), false);

    // 极大值
    Filter large_filter({INT64_MAX});
    ASSERT_EQ(large_filter.apply(INT64_MAX), true);

    // 负数
    Filter negative_filter({-1});
    ASSERT_EQ(negative_filter.apply(-1), true);
}
```

### Level 3: P2 - 可选优化 (Nice to Have)

这些是技术品味的体现，可以在后续迭代中改进。

#### 3.1 代码可读性

- [ ] 命名是否自解释？
- [ ] 函数是否单一职责？
- [ ] 是否有合适的注释解释"Why"而非"What"？
- [ ] 复杂逻辑是否有设计文档链接？

#### 3.2 架构一致性

- [ ] 是否遵循现有架构模式？
- [ ] 是否引入了不必要的依赖？
- [ ] 抽象边界是否清晰？
- [ ] 是否符合依赖倒置原则？

#### 3.3 技术债管理

- [ ] 是否引入了 TODO 并关联 Issue？
- [ ] 是否有临时方案（hack）需要后续清理？
- [ ] 是否复制粘贴了代码应该抽取？

---

## Part 3: AI-Assisted Review Workflow

### 3.1 使用 AI 生成 PR 摘要

在开始 Review 前，先让 AI 帮助你快速理解变更范围：

```bash
Prompt 示例：
请分析以下 Git Diff，生成：
1. 变更的核心目的（一句话）
2. 涉及的关键模块
3. 潜在风险点
4. 需要特别关注的代码区域

git diff HEAD~1 --stat
```

### 3.2 使用 AI 辅助识别模式化问题

```json
Prompt 示例：
请检查以下代码是否存在：
1. 未处理的错误返回值
2. 潜在的内存泄漏
3. 并发访问共享数据但无同步
4. 使用了废弃 API

[粘贴代码片段]
```

### 3.3 防范 AI 生成代码的陷阱

AI 生成的代码常见问题清单：

| 问题类型 | 表现 | 如何发现 |
|----------|------|----------|
| 边界条件遗漏 | 未处理空输入、越界 | 检查所有 if 分支 |
| 废弃 API 调用 | 使用已标记 deprecated 的接口 | 对比代码库最新版本 |
| 内存泄漏 | 异常路径未释放资源 | 检查 RAII 使用 |
| 并发竞争 | 共享状态无锁保护 | 标记所有共享变量 |
| 过度简化 | 忽略错误处理、超时 | 检查所有外部调用 |
| 幻觉依赖 | 调用不存在的函数 | 编译验证 |

**AI 幻觉示例**：
```cpp
// AI 生成的代码：调用了不存在的内部 API

#include "starrocks/exec/fragment_executor.h"  // 该头文件不存在

auto executor = FragmentExecutor::create(ctx);  // API 不存在

// 正确做法：确认 API 存在并使用

#include "exec/fragment_instance.h"
auto executor = FragmentInstance::create(ctx);
```

### 3.4 AI 辅助的 Review 工具链

```bash
┌─────────────────────────────────────────────────────────────────┐
│  工具                      │  用途                              │
├─────────────────────────────────────────────────────────────────┤
│  GitHub Copilot           │  生成 PR 描述、解释复杂代码          │
│  Claude Code              │  分析变更影响、生成测试用例          │
│  clang-tidy               │  静态分析（AI 无法覆盖的底层问题）   │
│  clangd/CMake Tools       │  编译验证、符号跳转                  │
│  Address Sanitizer        │  运行时内存检测                      │
│  Thread Sanitizer         │  数据竞争检测                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Part 4: OLAP 引擎特定 Review 要点

### 4.1 查询执行引擎

Review 查询执行相关代码时的核心关注点：

#### 向量化执行

```cpp
// 关键检查点：
// 1. 是否使用了 Column 而非 Row 接口？
// 2. 是否充分利用了 SIMD 批处理？
// 3. 是否有不必要的标量回退？

// 反例：行式处理
for (const auto& row : table) {
    result.push_back(process_row(row));  // 无法利用 SIMD
}

// 正例：列式批处理
for (size_t i = 0; i < column->size(); i += BATCH_SIZE) {
    auto batch = column->get_batch(i, BATCH_SIZE);
    result.push_back(process_batch_simd(batch));  // SIMD 批处理
}
```

#### 内存管理

```cpp
// 关键检查点：
// 1. 是否使用 MemTracker 追踪内存？
// 2. 是否在 OOM 时优雅降级？
// 3. 是否有内存超限保护？

// 正例：内存追踪
auto col = Column::create(type);
RETURN_IF_ERROR(MemTracker::instance().consume(bytes));  // 追踪
col->reserve(rows);

// 异常时释放
try {
    // ... 处理
} catch (...) {
    MemTracker::instance().release(bytes);  // 释放
    throw;
}
```

#### 零拷贝优化

```cpp
// 关键检查点：
// 1. 是否避免了不必要的数据拷贝？
// 2. 是否使用了 StringView 而非 std::string？
// 3. 是否利用了 Slice 引用？

// 反例：不必要的拷贝
std::string get_key(const Row& row) {
    return row.get_column(0).get_string();  // 拷贝
}

// 正例：零拷贝
std::string_view get_key(const Row& row) {
    return row.get_column(0).get_string_view();  // 引用
}
```

### 4.2 存储引擎

#### 数据编码

```cpp
// 关键检查点：
// 1. 编码是否充分利用数据局部性？
// 2. 是否支持随机访问？
// 3. 编解码的性能开销？

// Dictionary Encoding 示例
class DictEncoder {
    std::unordered_map<std::string, uint32_t> dict_;
    std::vector<std::string> values_;

    uint32_t encode(std::string_view val) {
        auto it = dict_.find(val);
        if (it != dict_.end()) return it->second;

        uint32_t id = values_.size();
        dict_[std::string(val)] = id;  // 注意：这里需要拷贝
        values_.emplace_back(val);
        return id;
    }
};
```

#### 压缩算法

```cpp
// 关键检查点：
// 1. 压缩率 vs 解压速度的权衡？
// 2. 是否支持向量化解压？
// 3. 压缩是否稳定？（最坏情况）
```

#### 索引结构

```cpp
// 关键检查点：
// 1. 索引构建的内存开销？
// 2. 查询的 Cache 友好性？
// 3. 并发构建/访问的同步？

// ZoneMap 索引
struct ZoneMap {
    int64_t min;
    int64_t max;
    size_t null_count;

    bool can_prune(int64_t query_val) const {
        return query_val < min || query_val > max;  // 快速剪枝
    }
};
```

### 4.3 并发执行框架

#### 线程池与任务调度

```cpp
// 关键检查点：
// 1. 任务粒度是否合理？（太细 = 调度开销，太粗 = 负载不均）
// 2. 是否有优先级调度？
// 3. 是否支持取消/超时？

// 正例：带超时的任务执行
Status execute_with_timeout(std::function<Status()> task,
                            int64_t timeout_ms) {
    auto future = thread_pool_->submit([&]() {
        return task();
    });

    if (future.wait_for(timeout_ms) == std::future_status::timeout) {
        return Status::Timeout("Query execution timeout");
    }

    return future.get();
}
```

#### 无锁数据结构

```cpp
// 关键检查点：
// 1. 是否真的需要无锁？（大多数场景锁足够）
// 2. 内存序是否正确？
// 3. ABA 问题是否处理？

// 无锁计数器
class LockFreeCounter {
    std::atomic<int64_t> count_{0};

public:
    void increment() {
        count_.fetch_add(1, std::memory_order_relaxed);  // 宽松序
    }

    int64_t get() const {
        return count_.load(std::memory_order_acquire);  // 获取序
    }
};
```

### 4.4 分布式协调

#### RPC 通信

```cpp
// 关键检查点：
// 1. 超时设置是否合理？
// 2. 重试是否幂等？
// 3. 是否有熔断/降级机制？

// 正例：带重试的 RPC 调用
Status execute_with_retry(const TExecPlanFragmentParams& params,
                          int max_retries) {
    Status last_status;
    for (int i = 0; i < max_retries; ++i) {
        last_status = backend_client_->exec_plan_fragment(params);
        if (last_status.ok()) {
            return Status::OK();
        }
        if (!last_status.is_network_error()) {
            return last_status;  // 非网络错误不重试
        }
        // 指数退避
        backoff_sleep(i * 100);
    }
    return last_status;
}
```

#### 一致性协议

```cpp
// 关键检查点：
// 1. 是否满足所需的隔离级别？
// 2. 是否有分布式事务保证？
// 3. 故障恢复路径是否正确？
```

---

## Part 5: 资深工程师的技术审美

### 5.1 架构敏感度

**好代码的特征**：

```text
1. 抽象边界清晰 - 每个模块职责单一，依赖方向明确
2. 扩展点预留 - 新功能可以通过扩展而非修改现有代码实现
3. 测试友好 - 依赖可注入，逻辑可隔离测试
4. 可观测 - 关键路径有 Metrics/Logging/Tracing
5. 故障隔离 - 单点故障不会导致雪崩
```

**坏代码的嗅味**：

```text
1. 上帝类 - 一个类做了太多事情
2. 循环依赖 - 模块 A 依赖 B，B 又依赖 A
3. 隐藏依赖 - 构造函数外的隐式依赖
4. 魔法数字 - 没有解释的常量
5. 注释解释代码 - 说明代码本身不够清晰
```

### 5.2 技术债管理

```text
技术债分类：
┌─────────────────┬────────────────────────────────────────┐
│  类型            │  处理方式                               │
├─────────────────┼────────────────────────────────────────┤
│  有意的债        │  记录 TODO，关联 Issue，设定偿还计划    │
│  无意的债        │  立即重构，不要传播                      │
│  不可避免的债    │  隔离，封装，防止扩散                    │
│  策略性的债      │  明确记录，权衡利弊，定期审视            │
└─────────────────┴────────────────────────────────────────┘
```

### 5.3 Mentor 式的 Review 风格

**避免**：
```text
- "这写错了" → 太直接，没有解释
- "为什么不XXX？" → 听起来像质问
- "这段代码很乱" → 没有建设性
```

**推荐**：
```text
- "这里有个潜在问题：XXX。原因是..." → 解释 + 理由
- "考虑一下 XXX 场景，是否需要考虑处理？" → 引导思考
- "建议将这段逻辑抽取成函数，原因是..." → 建设性建议
```

**优秀 Review 评论示例**：

```text
> 关于 FragmentInstance 的内存追踪

这个实现基本正确，但我有几个建议：

1. 【P0】MemTracker::consume() 失败时的处理
   当前代码在 consume 失败时直接抛出异常，但这会导致已经
   分配的资源泄漏。建议：

   ```cpp
   SCOPED_RAW_TRACER(&tracker, bytes);  // RAII 风格，自动回滚
   // ... 分配逻辑
   ```text
2. 【P1】错误信息增强
   建议在 OOM 错误中包含查询 ID，便于线上排查：
   ```cpp
   return Status::MemoryLimitExceeded(
       "Query OOM: query_id={}, requested={}, available={}",
       query_id, bytes, tracker->limit());
   ```text
3. 【P2】考虑添加 Metrics
   建议在成功/失败时分别上报 Metrics，便于监控：
   ```cpp
   Metrics::instance()->increment("query_memory_allocated", bytes);
   ```text
你怎么看？
```

---

## Part 6: 最佳实践

### 6.1 Review 流程

```text
1. PR 创建者自检
  - 运行本地测试
  - 运行静态检查（clang-tidy）
  - 填写 PR 描述模板

2. CI 自动化检查
  - 编译通过
  - 单元测试通过
  - Lint 检查通过
  - Sanitizer 检查通过

3. Reviewer 审查
  - 第一次审查：关注功能正确性和架构
  - 第二次审查：关注性能和边界
  - 第三次审查：关注代码品味

4. 合并决策
  - 至少 1 个 Approve
  - 所有 P0 问题解决
  - CI 全绿
```

### 6.2 PR 大小原则

```text
理想 PR 特征：
- 变更行数：200-500 行（不含自动生成的代码）
- 关注点：单一功能/修复
- Review 时间：30-60 分钟内可完成

过大的 PR 如何处理：
1. 拆分为独立的逻辑步骤
2. 每个步骤可独立编译测试
3. 前一个 PR 合并后再提交下一个
```

### 6.3 Review 时间管理

```text
资深工程师的建议：
- 每天固定时间 Review（如上午 10 点，下午 3 点）
- 单次 Review 不超过 60 分钟（疲劳导致质量下降）
- 复杂 PR 分多次 Review，每次关注不同维度
```

### 6.4 紧急 Hotfix 的处理

```text
Hotfix 流程：
1. 仍然需要 Review（可简化但不能跳过）
2. 至少 1 人 Review + Tech Lead 批准
3. 先修复 + 合并，后补测试（但必须记录 TODO）
4. 事后必须复盘，添加回归测试
```

---

## Part 7: 常见 Review 陷阱

### 7.1 Reviewer 陷阱

| 陷阱 | 表现 | 避免方法 |
|------|------|----------|
| 走马观花 | 只看了大概就 Approve | 逐行阅读关键逻辑 |
| 过度关注细节 | 纠结命名而忽略架构 | 先读 PR 描述了解意图 |
| 确认偏误 | 信任资深成员的代码 | 一视同仁，代码说话 |
| 疲劳 Review | 连续 Review 多个 PR | 限制单次 Review 时长 |
| 权威效应 | 不敢质疑 Tech Lead | 营造平等讨论文化 |

### 7.2 代码作者陷阱

| 陷阱 | 表现 | 避免方法 |
|------|------|----------|
| 防御心理 | 把 Review 当批评 | 心态转变：代码是团队的 |
| 过度解释 | 评论里长篇大论 | 让代码自己说话 |
| 逐个修复 | 每次提交只改一点 | 一次性修复所有问题 |
| 测试不足 | 只覆盖正常路径 | 覆盖边界和异常场景 |

### 7.3 AI 生成代码陷阱

```text
识别 AI 生成代码的特征：
1. 过度使用设计模式（为了模式而模式）
2. 变量命名过于通用（data, result, handler）
3. 缺少边界条件处理
4. 调用了不存在的 API
5. 注释解释显而易见的代码

审查策略：
1. 要求作者解释关键逻辑
2. 运行编译验证 API 存在
3. 添加边界条件测试
4. 检查是否有内存泄漏
```

---

## Part 8: 工具链配置

### 8.1 推荐的 CI 配置

```yaml

# .github/workflows/ci.yml
name: Code Review CI

on: [pull_request]

jobs:
  review:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Build
        run: |
          cmake -B build -DCMAKE_BUILD_TYPE=Debug
          cmake --build build

      - name: Unit Tests
        run: |
          cd build
          ctest --output-on-failure

      - name: Clang-Tidy
        run: |
          clang-tidy-16 src/**/*.cpp \
            --config-file=.clang-tidy \
            -- -Ibuild/include

      - name: Address Sanitizer
        run: |
          cmake -B build-asan -DCMAKE_BUILD_TYPE=Debug \
                -DCMAKE_CXX_FLAGS="-fsanitize=address"
          cmake --build build-asan
          cd build-asan
          ctest --output-on-failure

      - name: Thread Sanitizer
        run: |
          cmake -B build-tsan -DCMAKE_BUILD_TYPE=Debug \
                -DCMAKE_CXX_FLAGS="-fsanitize=thread"
          cmake --build build-tsan
          cd build-tsan
          ctest --output-on-failure
```

### 8.2 Clang-Tidy 配置

```yaml

# .clang-tidy
---
Checks: >
  -*,
  bugprone-*,
  cert-*,
  clang-analyzer-*,
  cppcoreguidelines-*,
  misc-*,
  performance-*,
  portability-*,
  readability-*,
  -readability-magic-numbers,
  -readability-identifier-length

WarningsAsErrors: 'bugprone-*, cert-*, clang-analyzer-*'

CheckOptions:
  - key: readability-identifier-naming.ClassCase
    value: CamelCase
  - key: readability-identifier-naming.FunctionCase
    value: camelBack
  - key: readability-identifier-naming.VariableCase
    value: snake_case
...
```

### 8.3 Git Hooks

```bash

# .git/hooks/pre-commit

#!/bin/bash

# 运行格式化检查
if ! git diff --cached --name-only | grep -E '\.(cpp|hpp|h)$' | xargs -r clang-format -i; then
    echo "Code formatting check failed"
    exit 1
fi

# 运行编译检查
if ! cmake --build build --target all 2>/dev/null; then
    echo "Compilation check failed"
    exit 1
fi

exit 0
```

---

## Appendix A: 推荐书单

| 书籍 | 作者 | 推荐理由 |
|------|------|---------|
| Code Review Best Practices | Maxime Louzeur | 实战导向 |
| Effective C++ | Scott Meyers | C++ 必读 |
| More Effective C++ | Scott Meyers | 进阶必读 |
| C++ Concurrency in Action | Anthony Williams | 并发编程权威 |
| Systems Performance | Brendan Gregg | 性能分析圣经 |
| Database Internals | Alex Petrov | 数据库内部原理 |
| Designing Data-Intensive Applications | Martin Kleppmann | 数据系统架构 |

---

## Appendix B: 术语表

| 术语 | 定义 |
|------|------|
| OOM | Out of Memory，内存耗尽 |
| UB | Undefined Behavior，未定义行为 |
| RAII | Resource Acquisition Is Initialization |
| SIMD | Single Instruction Multiple Data |
| Cache Line | CPU 缓存基本单位，通常 64 字节 |
| False Sharing | 伪共享，多线程访问同一 Cache Line 导致性能下降 |
| Memory Order | C++11 内存序，定义原子操作的可见性 |
| ABI | Application Binary Interface |
| API | Application Programming Interface |

---

## 结语

> Code Review 的终极目标不是写出完美的代码，而是培养一支能写出好代码的团队。

**作为 Reviewer**：
- 保持谦逊 - 你的理解可能也是有限的
- 保持好奇 - 问"为什么这样设计"而非"为什么不那样写"
- 保持耐心 - 给新人成长的空间和时间

**作为代码作者**：
- 保持开放 - Review 意见是帮助你进步
- 保持专业 - 对事不对人
- 持续学习 - 每次 Review 都是学习机会

---

*文档版本：2026.03*
*最后更新：2026-03-04*
*维护者：StarRocks Committer Team*
