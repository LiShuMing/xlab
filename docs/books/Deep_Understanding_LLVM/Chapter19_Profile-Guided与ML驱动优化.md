# 第19章 Profile-Guided与ML驱动优化

## 19.1 PGO(Profile-Guided Optimization)

### 19.1.1 插桩PGO：InstrProfiling / PGOInstrumentation

```
插桩PGO流程:

步骤1: 插桩编译
  clang -fprofile-generate=./profile_dir -O2 source.c -o source_instr
  → 编译器在每个基本块入口插入计数器递增指令

步骤2: 运行程序收集profile
  ./source_instr <典型输入>
  → 生成 default_*.profraw 文件

步骤3: 合并profile数据
  llvm-profdata merge ./profile_dir/*.profraw -o default.profdata

步骤4: 使用profile重新编译
  clang -fprofile-use=./default.profdata -O2 source.c -o source_opt

插桩PGO的测量内容:
  - 基本块执行次数
  - 边执行次数(基本块之间的转移)
  - 函数入口计数
  - 间接调用目标分布

源码入口:
  llvm/lib/Transforms/Instrumentation/PGOInstrumentation.cpp
  llvm/lib/ProfileData/InstrProf.cpp
  llvm/lib/ProfileData/InstrProfReader.cpp
  llvm/lib/ProfileData/InstrProfWriter.cpp
```

### 19.1.2 采样PGO：SampleProfile / AutoFDO

```
采样PGO流程(无需重新编译!):

步骤1: 使用perf采集性能数据
  perf record -b ./source <典型输入>  # -b: 分支采样

步骤2: 转换为LLVM profile格式
  create_llvm_prof --binary=./source --profile=perf.data --out=source.prof

步骤3: 使用采样profile编译
  clang -fprofile-sample-use=./source.prof -O2 source.c -o source_opt

采样PGO vs 插桩PGO:

| 维度 | 插桩PGO | 采样PGO |
|------|---------|---------|
| 精度 | 高(每条边精确计数) | 中(统计采样, 有噪声) |
| 开销 | 高(5-100%运行时开销) | 低(<5%运行时开销) |
| 部署 | 需要两次编译 | 可以用生产流量 |
| 数据量 | 大(完整计数) | 小(采样点) |
| 适用 | 开发/测试 | 生产环境 |

源码入口:
  llvm/lib/ProfileData/SampleProf.cpp
  llvm/lib/ProfileData/SampleProfReader.cpp
  llvm/lib/Transforms/IPO/SampleProfile.cpp
```

### 19.1.3 PGO驱动的优化

```
PGO启用的关键优化:

1. 函数布局(BasicBlockPlacement):
   热基本块连续排列 → 减少icache miss
   冷基本块移到函数末尾 → 改善局部性
   热路径fall-through → 减少分支预测失误

2. 内联决策:
   热调用点更积极内联
   冷调用点不内联(减少代码膨胀)
   间接调用的去虚化(基于目标分布)

3. 循环优化:
   热循环更积极展开
   热循环的向量化阈值放宽
   冷循环保持紧凑

4. 代码分割(HotColdSplitting):
   热路径和冷路径分到不同section
   冷代码不污染icache

5. 寄存器分配:
   热路径优先分配寄存器
   冷路径允许更多溢出
```

---

## 19.2 MemProf：堆分配画像

### 19.2.1 MemProfContextDisambiguation：上下文敏感的堆优化

```
MemProf: 内存分配行为画像

采集信息:
  - 每个分配点的分配大小和频率
  - 访问模式(顺序/随机)
  - 生命周期(短命/长期)
  - 调用上下文(哪个调用链分配的)

上下文敏感优化:
  同一分配点在不同调用上下文可能有不同的行为:

  malloc() 被调用时:
    上下文A: 分配小对象, 短命, 只访问一次 → 栈分配
    上下文B: 分配大对象, 长期, 随机访问 → 保持堆分配

  MemProfContextDisambiguation:
  1. 收集每个调用上下文的分配画像
  2. 识别有利可图的优化机会
  3. 克隆函数, 为不同上下文生成不同版本

源码入口:
  llvm/lib/Transforms/IPO/MemProfContextDisambiguation.cpp
  llvm/lib/ProfileData/MemProf.cpp
```

---

## 19.3 ML驱动的编译决策

### 19.3.1 MLInlineAdvisor：机器学习内联策略

```
传统内联: 基于阈值的规则
  if (cost < threshold) inline();

ML内联: 基于特征预测
  输入: 函数特征向量(50+维)
  输出: 内联/不内联

特征示例:
  - 函数大小(指令数/基本块数)
  - 调用深度
  - 常量参数比例
  - 循环嵌套深度
  - 指令类型分布
  - 调用者/被调用者的历史内联情况

模型:
  - 训练: 强化学习(奖励=编译后程序性能)
  - 推理: 决策树或小型神经网络
  - 延迟: <0.1ms/决策(编译时间敏感)

源码入口:
  llvm/lib/Analysis/MLInlineAdvisor.cpp
  llvm/lib/Analysis/DevelopmentModeInlineAdvisor.cpp
```

### 19.3.2 MLRegAllocAdvisor：学习型寄存器分配

```
传统寄存器分配: 基于spill_cost的贪心策略
ML寄存器分配: 基于特征预测最优分配顺序和溢出选择

特征:
  - 活跃区间属性(长度/权重/干涉度)
  - 干涉图结构(度分布/聚类系数)
  - 当前分配状态(已用/空闲寄存器数)
  - 循环深度和PGO权重

训练:
  与内联类似, 使用强化学习
  奖励=减少的溢出load/store数量

源码入口:
  llvm/lib/CodeGen/MLRegAllocEvictAdvisor.cpp
  llvm/lib/CodeGen/MLRegAllocPriorityAdvisor.cpp
```

### 19.3.3 模型推理框架

```
ML模型在编译器中的部署:

训练阶段:
  CompilerGym → 收集(状态, 动作, 奖励) → 训练模型

部署阶段:
  ModelUnderTrainingRunner: 开发模式(边训练边推理)
  TFLiteUtils: 推理模式(TensorFlow Lite)
  ReleaseModeDecisionTree: 发布模式(决策树, 推理快)

约束:
  1. 推理延迟: <0.1ms (编译时间敏感)
  2. 模型大小: <1MB (嵌入编译器)
  3. 确定性: 相同输入→相同输出(可调试性)
  4. 可回退: ML模型失败时回退到启发式
```

---

## 19.4 AutoFDO + MLGO在工业界的实践

### 19.4.1 Google的MLGO：从启发式到学习的演进

```
MLGO: Google的ML驱动编译优化框架

历史:
  2018: MLInlineAdvisor首次在Google内部部署
  2020: MLGO论文发表(Osogami & Raymond)
  2021: MLRegAllocAdvisor部署
  2022: AutoFDO + MLGO组合优化

成果:
  - 内联: Chrome二进制大小减少1-3%, 性能提升0.5-2%
  - 寄存器分配: 溢出减少5-15%, 性能提升0.3-1%
  - 组合: 累计性能提升1-5%

训练数据:
  - Google内部大规模C++代码库
  - 数百万个函数的特征和性能数据
  - 使用分布式训练

部署方式:
  - 模型嵌入clang二进制
  - 通过环境变量启用: -mllvm -enable-ml-inliner=1
  - 自动回退: 模型不可用时使用启发式
```

### 19.4.2 与数据库学习型优化器的类比

| 维度 | MLGO | 数据库LBO(Learning-Based Optimizer) |
|------|------|----------------------------------|
| 优化目标 | 代码性能(运行时间) | 查询性能(执行时间) |
| 决策类型 | 内联/寄存器分配 | Join顺序/索引选择 |
| 训练方法 | 强化学习 | 强化学习/监督学习 |
| 特征来源 | IR结构/PGO | 查询计划/统计信息 |
| 推理延迟 | <0.1ms | <1ms |
| 部署模式 | 嵌入编译器 | 嵌入优化器 |

两者面对的核心挑战相同：**在有限的推理时间内，基于不完整的信息做出近似最优的决策**。

---

## 19.5 本章小结

本章从PGO到ML驱动优化：

1. **PGO**——插桩PGO(高精度)和采样PGO(低开销)，PGO驱动函数布局、内联、循环优化等。
2. **MemProf**——堆分配画像，上下文敏感的优化决策。
3. **ML驱动编译**——MLInlineAdvisor和MLRegAllocAdvisor，从启发式到学习的演进。
4. **AutoFDO+MLGO**——Google的工业实践，1-5%的累计性能提升。

下一章进入LTO——链接时优化的架构和实践。
