# 第4章 Pass基础设施：优化的编排与执行框架

## 4.1 New Pass Manager架构

### 4.1.1 从Legacy到New：为什么要重建

LLVM经历了两代Pass Manager的演进：

| 特性 | Legacy PM | New PM |
|------|-----------|--------|
| IRUnit | 仅Function级别 | Module/CGSCC/Function/Loop四层 |
| 分析管理 | 无统一管理，Pass自行缓存 | AnalysisManager<IRUnit>统一管理 |
| 失效机制 | 粗粒度：修改Function失效所有 | 细粒度：基于IRUnit层次增量失效 |
| 参数化 | 构造函数传参 | PassBuilder + Pipeline解析 |
| 文本流水线 | 不支持 | `-passes=`文本语法 |
| 线程安全 | 差 | 好(分析结果按IRUnit隔离) |

New PM在LLVM 13成为默认，LLVM 16完全移除Legacy PM。

### 4.1.2 模板体系：PassManager<IRUnit> / AnalysisManager<IRUnit>

New PM的核心是两层模板：

```c++
// 源码: llvm/include/llvm/IR/PassManager.h (964行)

// Transform Pass: 执行变换
template <typename IRUnitT, typename AnalysisManagerT = AnalysisManager<IRUnitT>>
class PassManager {
  // PassManager<Module>    → 模块级Pass管理器
  // PassManager<Function>  → 函数级Pass管理器
  // PassManager<Loop>      → 循环级Pass管理器

  std::vector<std::unique_ptr<PassConcept<IRUnitT>>> Passes;

  PreservedAnalyses run(IRUnitT &IR, AnalysisManagerT &AM) {
    PreservedAnalyses PA = PreservedAnalyses::all();
    for (auto &P : Passes)
      PA.intersect(P->run(IR, AM));  // 执行Pass并累积保留信息
    return PA;
  }
};

// Analysis Pass: 提供分析结果
template <typename IRUnitT, typename ResultT>
class AnalysisInfoMixin {
  // ResultT run(IRUnitT &, AnalysisManagerT &);
  // 结果缓存在AnalysisManager中，按需计算
};

// AnalysisManager: 分析结果缓存与失效
template <typename IRUnitT>
class AnalysisManager {
  // 核心数据结构:
  DenseMap<AnalysisKey *, std::unique_ptr<AnalysisResultConcept>> AnalysisResults;
  DenseMap<AnalysisKey *, bool> AnalysesInProgress;  // 防止递归

  // 获取分析结果(缓存或计算)
  ResultT &getResult(IRUnitT &IR);

  // 失效分析结果
  void invalidate(IRUnitT &IR, const PreservedAnalyses &PA);
};
```

### 4.1.3 IRUnit层次：Module → CGSCC → Function → Loop

New PM定义了四个IRUnit层次，形成嵌套关系：

```
Module (编译单元)
  └── CGSCC (强连通分量 — 函数调用图中的SCC)
        └── Function (函数)
              └── Loop (自然循环)
```

每一层有自己的PassManager和AnalysisManager，通过Proxy跨层传播：

```c++
// 跨层次代理:
InnerAnalysisManagerProxy<AnalysisManager<Function>, Module>
  → 让Module级Pass可以查询Function级分析

OuterAnalysisManagerProxy<AnalysisManager<Module>, Function>
  → 让Function级Pass可以查询Module级分析(如TargetTransformInfo)
```

### 4.1.4 Analysis Invalidation机制

当一个Transform Pass修改了IR，它必须声明哪些分析结果仍然有效：

```c++
// PreservedAnalyses: 描述哪些分析被保留
PreservedAnalyses PA;

PA.preserve<DominatorTreeAnalysis>();     // 显式保留DominatorTree
PA.preserveSet<CFGAnalyses>();            // 保留所有CFG相关分析
PA.intersect(PreservedAnalyses::all());   // 保留一切(纯分析Pass)
PA.intersect(PreservedAnalyses::none());  // 什么都不保留(大幅修改IR的Pass)

// AnalysisManager根据PA决定哪些缓存需要失效:
void AnalysisManager::invalidate(IRUnitT &IR, const PreservedAnalyses &PA) {
  for (auto &[Key, Result] : AnalysisResults)
    if (!PA.preserved(Key))  // 未被声明保留的分析
      Result.reset();        // 释放缓存
}
```

**增量式分析维护**的关键：如果SimplifyCFG修改了基本块但保留了DominatorTree（因为DominatorTree支持增量更新），下一个需要DominatorTree的Pass无需重新计算——直接使用缓存的增量更新版本。

**数据库类比**：这与增量物化视图维护是同一问题——当基表数据变化时，需要确定哪些物化视图需要刷新。PreservedAnalyses相当于"变更数据捕获(CDC)"，告诉系统哪些视图(分析结果)不受此次变更影响。

---

## 4.2 PassBuilder与流水线构建

### 4.2.1 三文件解析

Pass的注册和流水线构建涉及三个核心文件：

| 文件 | 行数 | 职责 |
|------|------|------|
| `llvm/include/llvm/Passes/PassBuilder.h` | 1,005 | PassBuilder接口定义 |
| `llvm/lib/Passes/PassBuilder.cpp` | 2,847 | Pass注册与解析 |
| `llvm/lib/Passes/PassBuilderPipelines.cpp` | 2,507 | O0-Oz流水线定义 |

PassBuilder的核心方法：

```c++
class PassBuilder {
  // 解析-passes=文本语法
  Expected<PassBuilder::PipelineElement> parsePassPipeline(StringRef Pipeline);

  // 构建模块级Pass管理器
  ModulePassManager buildPerModuleDefaultPipeline(OptimizationLevel Level);

  // 构建函数级Pass管理器
  FunctionPassManager buildFunctionSimplificationPipeline(OptimizationLevel Level);

  // 构建循环级Pass管理器
  LoopPassManager buildLoopSimplificationPipeline(OptimizationLevel Level);

  // 注册回调钩子(扩展点)
  void registerPipelineParsingEPCallback(...);
  void registerOptimizerLastEPCallback(...);
};
```

### 4.2.2 O0/O1/O2/O3/Os/Oz的渐进式Pass列表

`PassBuilderPipelines.cpp`定义了每个优化级别的完整流水线。以下是O1→O2→O3的关键差异：

```
O1: 基本优化 — 编译时间敏感
  ├── SROA, SimplifyCFG, InstCombine
  ├── EarlyCSE (不做GVN)
  ├── 简单内联(只内联很小函数)
  ├── LICM (不做复杂版本)
  └── 基本循环优化(Rotation, IndVarSimplify)

O2: 标准优化 — 性能/编译时间平衡 ★ 最常用
  ├── O1全部 + 以下增强:
  ├── GVN(NewGVN)  ← O1没有
  ├── 循环展开     ← O1只做简单展开
  ├── LoopUnrollAndJam ← O1没有
  ├── 更激进的内联 ← 更大的inlineCost阈值
  ├── SLPOVectorizer ← O1没有
  ├── LoopVectorize  ← O1没有(最重要差异!)
  ├── Attributor    ← O1没有
  └── 更多次迭代的InstCombine

O3: 激进优化 — 运行时性能优先
  ├── O2全部 + 以下增强:
  ├── LoopVectorize更激进 ← 更大的最大展开因子
  ├── SLPVectorizer更激进
  ├── FunctionSpecialization ← O2没有
  ├── 更大的内联阈值
  └── 更多次Pass迭代

Os: 代码大小优化 — 类似O2但禁用增大代码的Pass
  ├── 禁用LoopUnroll
  ├── 禁用LoopVectorize
  └── 更小的内联阈值

Oz: 最小代码大小 — 极端大小优化
  ├── Os全部 + 以下增强:
  ├── 更小的内联阈值(几乎不内联)
  └── 更激进的代码外提(IROutliner)
```

**关键洞察**：O2和O1最大的区别是**向量化**——LoopVectorize和SLPVectorizer是性能提升最大的Pass，但它们也增加了代码大小和编译时间。

### 4.2.3 -passes=语法与自定义流水线

```bash
# 基本语法
-passes='sroa,instcombine,simplifycfg'

# 嵌套层次
-passes='module(sroa),function(instcombine,simplifycfg)'

# 循环层Pass
-passes='function(loop(licm,indvars))'

# CGSCC层Pass
-passes='cgscc(inline)'

# 重复
-passes='repeat<3>(instcombine,simplifycfg)'

# 使用默认流水线+自定义Pass
-passes='O2,function(my-pass)'
```

---

## 4.3 SCC遍历与CGSCC Pass Manager

### 4.3.1 LazyCallGraph构建与SCC分解

`LazyCallGraph`(定义在`llvm/lib/Analysis/LazyCallGraph.cpp`, 2072行)按需构建函数调用图，并分解为强连通分量(SCC)：

```
调用图示例:
  A → B → C → A    (SCC: {A, B, C} — 递归调用组)
  A → D             (D不在SCC中)
  D → E             (D和E各自独立)

SCC分解结果(拓扑序):
  SCC1: {E}        ← 叶节点，先处理
  SCC2: {D}
  SCC3: {A, B, C}  ← 根SCC，最后处理
```

**惰性构建**：LazyCallGraph不一次性构建整个调用图，而是在遍历SCC时按需探索。这避免了在大型程序上构建完整调用图的巨大开销。

### 4.3.2 DevirtSCCRepeatedPass：迭代去虚化

```c++
// 源码: llvm/include/llvm/Analysis/CGSCCPassManager.h
class DevirtSCCRepeatedPass {
  // 对SCC反复应用内联Pass直到收敛:
  // 第1轮: 内联后可能暴露新的去虚化机会
  // 第2轮: 利用新机会继续内联
  // ... 直到没有新变化或达到最大迭代次数

  unsigned MaxDevirtIterations;  // 默认4次
};
```

**为什么需要迭代？** 因为内联会暴露新的去虚化机会：

```
第1轮: f()调用g()——g是虚函数调用，无法内联
  ↓ 内联后，vtable已知
第2轮: g()被去虚化为具体函数G()——可以内联了
  ↓ 内联G()后，又暴露了h()的去虚化机会
第3轮: h()被去虚化...
```

**数据库类比**：这类似于级联物化视图刷新——刷新一个视图可能触发依赖它的视图也需要刷新，直到没有视图需要更新为止（不动点迭代）。

---

## 4.4 从数据库优化器视角看Pass Manager

### 4.4.1 Rule-based vs Cost-based

| 维度 | 数据库优化器 | LLVM Pass Manager |
|------|------------|-------------------|
| 变换决策 | Cost-based(代价模型) | Rule-based + 有限cost-based |
| 搜索空间 | 多种计划枚举+选优 | 固定顺序执行 |
| 回溯能力 | 有(保留多个候选) | 无(一旦变换不可撤销) |
| 收敛保证 | 有(代价递减) | 无(可能振荡) |
| 自适应 | 统计信息驱动 | PGO驱动(第19章) |

LLVM的Pass Pipeline本质上是**rule-based的确定性流水线**——Pass按固定顺序执行，每个Pass独立决定是否变换，不回溯全局最优。

### 4.4.2 优化顺序的搜索空间

Pass顺序对优化效果影响巨大。经典例子：

```
顺序1: SROA → InstCombine → LICM
  SROA消除alloca → InstCombine化简冗余 → LICM外提不变量
  ✅ 每步都为下一步创造了条件

顺序2: LICM → SROA → InstCombine
  LICM发现不了不变量(还在alloca中) → SROA后InstCombine来不及传播
  ❌ 结果差得多
```

这就是为什么`PassBuilderPipelines.cpp`有2507行——精心编排的Pass顺序是LLVM优化效果的关键。

### 4.4.3 Cascades Optimizer vs Pass Pipeline

Cascades/Columbia风格的查询优化器与LLVM Pass Pipeline的根本区别：

| 特性 | Cascades优化器 | Pass Pipeline |
|------|---------------|---------------|
| 搜索策略 | 自顶向下记忆化搜索 | 确定性顺序执行 |
| 计划空间 | 显式枚举多个等价计划 | 隐式(只保留当前最佳) |
| 代价评估 | 每个候选计划评估代价 | 仅在少数Pass中评估(如InlineCost) |
| 全局最优 | 近似全局最优 | 局部最优的序列组合 |

LLVM选择了Pass Pipeline而非Cascades，这是工程权衡：
- **确定性**：相同输入总是产生相同输出（调试友好）
- **编译时间**：不枚举计划空间，速度快
- **可组合性**：每个Pass独立，可以自由组合
- **代价**：可能错过全局最优（但实践中，精心编排的流水线已经足够好）

---

## 4.5 本章小结

本章建立了对LLVM优化器框架的核心理解：

1. **New Pass Manager的四层IRUnit体系**——Module/CGSCC/Function/Loop层次嵌套，AnalysisManager统一管理分析结果缓存，PreservedAnalyses实现增量式分析维护。

2. **PassBuilder三文件**——接口定义、Pass注册、流水线编排，O0-Oz的渐进式Pass列表是LLVM工程智慧的结晶。

3. **CGSCC Pass Manager**——LazyCallGraph的惰性构建、SCC拓扑排序、DevirtSCCRepeatedPass的迭代去虚化。

4. **与数据库优化器的类比**——Pass Pipeline是rule-based确定性流水线，而Cascades是cost-based搜索优化器。两种范式各有取舍，LLVM选择了确定性和编译时间，牺牲了全局最优的可能性。

下一章我们进入具体的标量优化Pass——从DCE到GVN，从LICM到SROA，逐一解析它们的算法和源码。
