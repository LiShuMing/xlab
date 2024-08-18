# 附录F 数据库优化器与编译器优化概念映射表

## 核心概念映射

| 数据库概念 | 编译器概念 | 共同原理 |
|-----------|-----------|---------|
| 逻辑计划 → 物理计划 | IR → MachineInstr | 抽象→具体映射 |
| 代价模型 | TTI / InlineCost | 启发式代价估算 |
| 谓词下推 | LICM / DCE | 减少不必要计算 |
| 子查询物化/展开 | 函数内联 | 边界决策权衡 |
| 算子融合 | Loop Fusion / SLP | 减少中间结果 |
| 向量化执行 | SIMD Vectorization | 数据并行 |
| Join Reorder | Pass Ordering | 搜索空间排序 |
| 统计信息 | PGO Profile | 数据驱动决策 |
| 参数化查询 | 常量传播/特化 | 特化 vs 通用 |
| 增量物化视图 | Incremental Analysis | 增量维护 |
| 查询重写规则 | InstCombine规则 | 等价变换 |
| 执行计划缓存 | JIT代码缓存 | 避免重复编译 |
| 逻辑优化 | 中端IR优化 | 平台无关变换 |
| 物理优化 | 后端代码生成 | 平台相关选择 |
| 选择度估计 | 分支概率估计 | 频率/概率推断 |
| 列存储 vs 行存储 | AoS vs SoA布局 | 数据布局优化 |
| 分区裁剪 | 循环Tiling | 数据局部性 |
| MVCC | SSA def-use | 版本化管理 |
| WAL | 指令调度 | 有序性保证 |
| B+树索引 | GEP地址计算 | 高效查找 |
| Hash Join | Hash Table (CSE) | 基于哈希的匹配 |
| Sort-Merge Join | 归并排序算法 | 分治+合并 |
| Nested Loop Join | 标量循环 | 朴素遍历 |
| 2PC/3PC | 原子操作/内存屏障 | 一致性保证 |
| 死锁检测 | 循环依赖检测 | 图中环检测 |
| 连接池 | 寄存器池 | 资源复用 |
| 慢查询日志 | -print-after-all / -debug-only | 可观测性 |

## 优化流程映射

### 数据库查询优化流程
```
SQL → Parser → AST → 逻辑计划 → 逻辑优化 → 物理计划 → 代价评估 → 执行
```

### 编译器优化流程
```
C/C++ → Clang → AST → LLVM IR → 中端优化 → 代码生成 → 代价评估 → 执行
```

### 对应关系

| 阶段 | 数据库 | 编译器 |
|------|--------|--------|
| 输入语言 | SQL | C/C++/Rust |
| 词法/语法分析 | Parser | Clang Lexer/Parser |
| 中间表示 | 逻辑计划 | LLVM IR |
| 逻辑优化 | 谓词下推/列裁剪/表达式化简 | DCE/SROA/InstCombine |
| 物理优化 | Join算法选择/索引选择 | 指令选择/寄存器分配 |
| 代价评估 | IO代价+CPU代价 | TTI指令代价+内存代价 |
| 执行计划 | Volcano/Vectorized | MachineInstr序列 |
| 运行时 | 执行引擎 | CPU/GPU硬件 |
| 反馈 | EXPLAIN ANALYZE | -print-after-all / PGO |

## 关键算法映射

| 算法 | 数据库应用 | 编译器应用 |
|------|-----------|-----------|
| 动态规划 | Join重排序 | 寄存器分配(PBQP) |
| 贪心算法 | 索引选择 | 内联决策/寄存器分配(Greedy) |
| 遗传/进化算法 | 查询优化(多目标) | 算子调度(Ansor) |
| 强化学习 | 学习型优化器(LBO) | MLInlineAdvisor/MLGO |
| 模拟退火 | 参数调优 | AutoTVM schedule搜索 |
| 图着色 | 并发调度 | 寄存器分配(干涉图着色) |
| 哈希 | Hash Join/Aggregate | 值编号(GVN/CSE) |
| 格/偏序 | 数据依赖推理 | SCCP格/常量传播 |
| 不动点迭代 | 视图维护 | Attributor/SCCP收敛 |

## 从数据库工程师到编译器工程师的思维转换

### 1. 数据模型
- 数据库: 关系(表) → 元组(行) → 属性(列)
- 编译器: Module → Function → BasicBlock → Instruction

### 2. 优化目标
- 数据库: 最小化查询响应时间
- 编译器: 最小化程序执行时间

### 3. 信息来源
- 数据库: 统计信息(pg_stats) → 选择度/基数
- 编译器: PGO Profile → 分支概率/执行频率

### 4. 搜索空间
- 数据库: Join顺序 × 算法选择 × 索引选择
- 编译器: Pass顺序 × 内联决策 × 寄存器分配

### 5. 保守性
- 数据库: 必须保证查询结果正确(不多不少)
- 编译器: 必须保证程序语义不变(Verifier检查)

### 6. 可观测性
- 数据库: EXPLAIN / EXPLAIN ANALYZE
- 编译器: -print-after-all / -debug-only / -stats

### 7. 扩展性
- 数据库: 自定义算子/UDF/扩展
- 编译器: 自定义Pass/Dialect/回调

---

**总结**：编译器和数据库优化器是同一类问题的两个实例——**在庞大的搜索空间中，基于不完整的信息，找到近似最优的执行方案**。理解了这个同构性，数据库工程师可以快速掌握编译器的核心概念，编译器工程师也可以从数据库优化器中汲取灵感（如Cascades框架对Pass Pipeline的启发、学习型优化器对MLGO的启发）。
