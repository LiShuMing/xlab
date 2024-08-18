# 第18章 JIT编译与运行时代码生成

## 18.1 LLVM JIT架构演进

### 18.1.1 MCJIT → ORC JIT v1 → ORC JIT v2

```
JIT(Just-In-Time)编译: 在运行时将IR编译为机器码并执行

演进路径:

MCJIT (LLVM 3.0-):
  - 基于MC层的JIT
  - 每次编译整个模块
  - 不支持惰性编译(必须提前编译所有函数)
  - 不支持远程JIT

ORC JIT v1 (LLVM 3.7-):
  - 分层架构: IR层 → Object层
  - 支持惰性编译(按需编译函数)
  - 更好的资源管理
  - 但API复杂, 难以使用

ORC JIT v2 (LLVM 7-, 当前推荐):
  - 简化API: LLJIT / LLJITBuilder
  - 支持并发编译
  - 支持远程JIT
  - 支持运行时重优化(ReOptimize)
  - 支持自定义编译层
```

---

## 18.2 ORC JIT v2深度解析

### 18.2.1 核心组件

**源码**：`llvm/lib/ExecutionEngine/Orc/`

```
ORC JIT v2架构:

LLJIT (高级API)
├── IRTransformLayer       : IR变换层(在编译前应用Pass)
├── IRCompileLayer         : IR编译层(LLVM IR → 目标代码)
├── ObjectLinkingLayer     : 目标代码链接层
├── CompileOnDemandLayer   : 按需编译层(惰性编译!)
└── IndirectionUtils       : 跳板机制(实现惰性编译的关键)

工作流程:
  1. 添加IR模块: LLJIT::addIRModule(ThreadSafeModule)
  2. 查找符号: LLJIT::lookup("main")
  3. 如果符号未编译:
     → 通过跳板(stub)触发编译
     → 编译IR为机器码
     → 链接到进程
     → 替换跳板为实际代码地址
  4. 执行编译后的代码
```

### 18.2.2 CompileOnDemandLayer与惰性编译

```
惰性编译的核心: 跳板(Trampoline/Stub)

  函数调用流程:
  1. caller调用函数foo
  2. foo的跳板指向编译器的编译入口
  3. 编译器编译foo的IR
  4. 将跳板的目标地址更新为foo的实际代码
  5. 执行foo的代码
  6. 后续调用foo直接跳到实际代码(无需再编译)

  IndirectionUtils:
  - 创建跳板: JIT目标中的空函数
  - 编译后重写跳板: 修改跳板的目标地址
  - 支持远程跳板: 用于跨进程JIT

  收益:
  - 启动时间: 只编译入口函数, 其余按需编译
  - 内存: 从未调用的函数不编译, 节省内存
  - 适用于REPL/Lua/Julia等交互式环境
```

### 18.2.3 ReOptimizeLayer：运行时重新优化

```
ReOptimizeLayer: 根据运行时profile重新优化

  1. 初始编译: 使用O0快速编译(低延迟)
  2. 运行时profiling: 收集热函数和分支频率
  3. 重新优化: 对热函数使用O2/O3重新编译
  4. 替换代码: 原子切换到优化后的代码

  实现机制:
  - 函数入口插桩: 记录调用次数
  - 阈值触发: 调用次数超过阈值 → 加入重优化队列
  - 后台线程: 编译优化版本, 不阻塞执行
  - 代码替换: 修改跳板指向新代码

  类似技术:
  - Java JVM: C1(快速编译) → C2(优化编译)
  - JavaScript V8: Ignition(解释) → TurboFan(优化)
  - Python PyPy: 解释 → JIT追踪编译
```

---

## 18.3 JIT在数据库中的应用

### 18.3.1 查询编译：表达式JIT / 整行JIT / Vectorized vs Compiled

```
数据库JIT的两种范式:

1. Vectorized Execution (向量化执行):
   每个算子处理一批行(batch)
   例: HashJoin处理1000行/批
   优点: 缓存友好, 编译简单
   缺点: 中间结果物化, 函数调用开销

2. Compiled Execution (编译执行):
   将整个查询编译为一个函数
   例: SELECT sum(a+b) FROM t WHERE c>10
   → 编译为: for(row in t) if(row.c>10) sum += row.a + row.b
   优点: 零中间物化, 内联所有函数
   缺点: 编译延迟, 代码膨胀

   Vectorized + Compiled混合:
   热查询: Compiled (消除物化)
   冷查询: Vectorized (低编译延迟)
```

### 18.3.2 PostgreSQL JIT / Velox / Presto的LLVM JIT实践

```
PostgreSQL JIT:
  - 从PG 11开始支持LLVM JIT
  - JIT表达式求值: WHERE条件的LLVM编译
  - JIT聚合: 聚合函数的内联化
  - JIT元组解构: 消除DecodeTuple的开销
  - 使用ORC JIT v2
  - 阈值: 累计执行超过jit_above_cost时启用

Velox (Meta):
  - C++向量化的执行引擎
  - 表达式JIT: 将表达式树编译为LLVM IR
  - 算子JIT: 将Filter/Project编译为单函数
  - 用于Presto/Spark的本地执行

Presto C++ Worker:
  - 赛道的Prestissimo
  - 使用Velox + LLVM JIT
  - 将Presto的Java算子编译为C++/LLVM
  - 10-50倍性能提升
```

### 18.3.3 从编译器视角看：为什么数据库需要运行时代码生成

```
数据库需要JIT的根本原因:

1. 查询在编译期未知:
   SQL是声明式语言, 查询结构运行时才确定
   → 无法预先编译所有可能的查询

2. 数据特征在编译期未知:
   选择度、数据分布、值范围运行时才确定
   → 需要运行时代价评估和优化

3. 表达式求值的开销:
   通用表达式求值器: switch(opcode) + 间接调用
   JIT编译后: 直接的机器指令序列
   → 5-10倍加速

4. 算子融合:
   Filter → Project → Aggregate
   通用执行: 3次函数调用 + 2次中间结果物化
   JIT编译: 单循环, 无中间结果
   → 消除内存带宽瓶颈
```

---

## 18.4 JIT在LLM推理中的应用

### 18.4.1 动态shape的编译优化

```
LLM推理的动态shape挑战:

  输入: sequence_length是动态的(每次请求不同)
  KV Cache: 随推理步骤增长

  静态编译的问题:
  - 必须为每个可能的sequence_length编译 → 组合爆炸
  - 编译一个kernel需要秒级 → 不可接受

  JIT解法:
  1. 编译泛型kernel: 接受动态参数
  2. 对热shape特化: 常见sequence_length编译专用版本
  3. 运行时选择: 根据当前shape选择最优kernel

  torch.compile()的JIT策略:
  - 第一次推理: 使用通用kernel(JIT编译)
  - 后续相同shape: 缓存编译结果
  - 新shape: 重新JIT编译(或使用泛型版本)
```

### 18.4.2 Kernel fusion的运行时决策

```
算子融合的JIT决策:

  静态编译: 固定融合策略(保守或激进)
  JIT编译: 根据运行时信息动态决策

  决策因素:
  1. 输入shape: 大tensor → 更积极的融合(计算密集)
  2. GPU利用率: 低利用率 → 融合(减少kernel launch开销)
  3. 内存带宽: 带宽瓶颈 → 融合(减少中间结果)
  4. 缓存状态: 中间结果是否在缓存中 → 影响融合收益

  TVM / TensorRT / torch.compile的JIT策略:
  TVM: AutoTVM/Ansor搜索最优schedule → JIT编译
  TensorRT: 离线优化 + 运行时特化
  torch.compile: 动态图捕获 + JIT编译 + 缓存
```

---

## 18.5 本章小结

本章从JIT架构到应用场景全面解析：

1. **JIT演进**——MCJIT → ORC v1 → ORC v2，ORC v2的分层架构和惰性编译。
2. **ORC JIT v2**——CompileOnDemandLayer的跳板机制、ReOptimizeLayer的运行时重优化。
3. **数据库JIT**——Vectorized vs Compiled执行、PostgreSQL/Velox/Presto的LLVM JIT实践。
4. **LLM推理JIT**——动态shape的运行时编译、kernel fusion的JIT决策。

下一章进入Profile-Guided和ML驱动优化——从PGO到MLGO的演进。
