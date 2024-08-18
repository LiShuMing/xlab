# 《深入LLVM：从体系结构到AI时代的编译器基础设施》

## 全书设计理念

以**"硬件感知的编译优化"**为主线，以**源码追踪**为方法，打通三条知识链路：
- 编译器优化 vs 数据库查询优化（理论同源：代价模型、搜索空间、启发式）
- 体系结构约束 → 编译器适配 → 性能收益（自底向上理解优化为何如此设计）
- 传统编译 → MLIR/AI编译 → LLM推理优化（渐进演化脉络）

---

## 第一篇：基石 — LLVM架构全景与IR本质

### 第1章 编译器的三段式哲学：从查询引擎到LLVM

- 1.1 三段式编译 vs 数据库查询处理的类比
  - 前端(Parser)→IR→优化器→执行引擎 ≈ SQL Parse→Logical Plan→Optimizer→Physical Plan
  - SSA与关系代数的同构性：def-use chain ≈ 数据血缘
  - Pass Pipeline ≈ Optimizer Rule Engine
- 1.2 LLVM项目全景：源码目录结构与组件关系
  - `llvm/`, `clang/`, `mlir/`, `lld/`, `flang/`, `offload/` 各组件定位
  - 源码导航：从顶层CMake到各子项目的入口
- 1.3 从一行C代码到可执行文件：完整编译流程追踪
  - `clang -ccc-print-phases` 揭示的编译阶段
  - 以`sum_array`为例：C++ → Clang AST → LLVM IR → SelectionDAG → MachineInstr → MC → ELF

### 第2章 LLVM IR：类型化SSA的精妙设计

- 2.1 为什么是SSA？——从理论到工程实现
  - SSA的理论优势与LLVM的选择
  - Value→User→Instruction：def-use链的内存布局（`Value.h:Use`机制）
  - `Instruction.def`：X-macro指令表的工程智慧
- 2.2 类型系统：从typed pointer到opaque pointer的演进
  - Type继承体系：`Type.h` → `DerivedTypes.h`
  - IntegerType / FunctionType / StructType / VectorType / ScalableVectorType
  - 指针类型革命：为什么LLVM走向opaque pointer
- 2.3 常量与元数据：编译期信息的载体
  - Constant层次：ConstantInt → ConstantExpr → UndefValue → PoisonValue
  - Metadata体系：`Metadata.def` → MDNode → !tbaa / !prof / !noalias
  - DebugInfo：DICompileUnit → DISubprogram → DILocalVariable
- 2.4 Module-Function-BasicBlock-Instruction：四层IR容器
  - Module的全局视野：GlobalVariable / Function / GlobalAlias
  - DataLayout：体系结构的信息注入点（`DataLayout.h`对优化的影响）
  - LLVMContext：IR世界的上下文
- 2.5 IR构建与验证
  - IRBuilder + ConstantFolder + InstSimplifyFolder
  - Verifier：325KB的IR不变量守卫者（`Verifier.cpp`逐条规则解析）
  - PatternMatch：模式匹配DSL（`PatternMatch.h`）

### 第3章 IR的三种面貌：内存、文本与位码

- 3.1 内存表示：C++对象的拓扑
  - `Value.cpp` / `Instruction.cpp` / `Function.cpp` 关键方法追踪
- 3.2 文本表示(.ll)：人类可读的汇编
  - `AsmWriter.cpp`：IR的序列化逻辑
  - .ll语法完整手册：从模块声明到指令操作数
- 3.3 位码表示(.bc)：紧凑的二进制格式
  - `BitcodeWriter.cpp` / `BitcodeReader.cpp`：编码/解码
  - 位码格式与版本兼容性
- 3.4 实战工具链
  - `opt`：IR优化器的100种用法
  - `llc`：后端代码生成
  - `llvm-dis` / `llvm-as`：格式互转
  - `-print-after-all` / `-debug-only`：Pass级可观测性

---

## 第二篇：优化 — IR变换的算法与工程

### 第4章 Pass基础设施：优化的编排与执行框架

- 4.1 New Pass Manager架构
  - `PassManager<IRUnit>` / `AnalysisManager<IRUnit>` 模板体系
  - IRUnit层次：Module → CGSCC → Function → Loop
  - Analysis Invalidation机制：增量式分析维护
  - Inner/OuterAnalysisManagerProxy：跨层次分析传播
- 4.2 PassBuilder与流水线构建
  - `PassBuilder.h` / `PassBuilder.cpp` / `PassBuilderPipelines.cpp` 三文件解析
  - O0/O1/O2/O3/Os/Oz的渐进式Pass列表
  - `-passes=`语法与自定义流水线
- 4.3 SCC遍历与CGSCC Pass Manager
  - `LazyCallGraph`构建与SCC分解
  - `DevirtSCCRepeatedPass`：迭代去虚化
- 4.4 从数据库优化器视角看Pass Manager
  - Rule-based vs Cost-based：Pass的启发式本质
  - 优化顺序的搜索空间：为什么Pass顺序至关重要
  - Cascades Optimizer vs Pass Pipeline：两种优化编排范式

### 第5章 标量优化：逐指令的变换艺术

- 5.1 死代码消除三兄弟：DCE / ADCE / BDCE
  - 算法差异：平凡 vs 激进 vs 位追踪
  - 源码追踪：`Scalar/DCE.cpp` / `ADCE.cpp` / `BDCE.cpp`
- 5.2 公共子表达式消除：EarlyCSE / GVN / NewGVN
  - EarlyCSE：简单值编号的快速路径
  - GVN：全局值编号 + 部分冗余消除(PRE)
  - NewGVN：另一种算法实现的差异
  - 与数据库去重的类比：值编号 ≈ hash distinct
- 5.3 循环不变量外提(LICM)
  - 不变性判定：LoopInfo + AliasAnalysis + MemorySSA
  - 安全性检查：别名、异常、循环副作用
  - `Scalar/LICM.cpp` 源码深度追踪
- 5.4 聚合体标量替换(SROA)
  - Alloca切片分析：partition算法
  - promoteMemToReg：Briggs-Cooper算法
  - `Scalar/SROA.cpp`：LLVM最重要的优化之一
- 5.5 稀疏条件常量传播(SCCP)
  - ValueLatticeElement格结构与状态转移
  - SparseSolver工作表算法
  - `Scalar/SCCP.cpp` + `Analysis/SparsePropagation.h`
- 5.6 CFG化简：SimplifyCFG / JumpThreading / CorrelatedValuePropagation
  - 块合并、不可达块删除、switch优化
  - 跳转线程：条件传播驱动的路径复制
  - 与数据库谓词下推的类比
- 5.7 循环优化族：Rotation / Unroll / IndVarSimplify / LSR
  - LoopRotation：guard + latch旋转
  - LoopUnroll：代价模型与展开因子选择
  - IndVarSimplify：归纳变量规范化
  - LSR(Loop Strength Reduction)：SCEV驱动的地址计算优化

### 第6章 InstCombine：系统化的窥孔优化工程

- 6.1 Worklist驱动架构
  - `InstructionCombining.cpp`主循环
  - Visitor模式与Worklist管理策略
- 6.2 代数简化规则全景
  - AddSub / AndOrXor / MulDivRem / Shifts 四大类
  - 每类3+具体变换规则与源码追踪
- 6.3 类型cast优化：InstCombineCasts
  - sext/zext/trunc/bitcast冗余消除
- 6.4 比较指令优化：InstCombineCompares
  - icmp/fcmp值范围推理
- 6.5 Demanded Bits分析
  - `InstCombineSimplifyDemanded.cpp`
  - 高位到低位的需求传播算法
- 6.6 工程启示：如何将规则引擎做得可扩展
  - 与数据库表达式简化的对比

### 第7章 过程间优化(IPO)：跨越函数边界

- 7.1 内联决策框架
  - InlineCost代价估算公式
  - InlineAdvisor：默认策略 vs ML驱动(`MLInlineAdvisor.cpp`)
  - SCC遍历顺序与内联策略
  - 与数据库子查询展开/物化的类比
- 7.2 函数属性推断
  - FunctionAttrs：readnone / norecurse / willreturn
  - Attributor框架：抽象属性的不动点迭代
- 7.3 全局优化与死全局消除
  - GlobalOpt / GlobalDCE / ConstantMerge
- 7.4 虚函数去虚化：WholeProgramDevirt + LowerTypeTests
  - 类型元数据遍历与间接调用消除
- 7.5 函数特化(FunctionSpecialization)
  - IPSCCP驱动的函数克隆
- 7.6 热冷分割与代码外提
  - HotColdSplitting / IROutliner
  - 与数据库执行计划分区的类比

### 第8章 自动向量化：从标量到SIMD

- 8.1 LoopVectorize：合法性分析
  - LoopAccessInfo：依赖距离与运行时检查
  - 向量化代价模型(TTI接口)
- 8.2 VPlan：向量化的内部IR
  - VPlan构建 → 变换 → 执行管线
  - VPInstruction / VPRecipeBase / VPlanSLP
- 8.3 SLPVectorizer：超字级并行
  - 种子收集与指令聚类算法
- 8.4 后向量化优化：VectorCombine
- 8.5 可伸缩向量：SVE/RISC-V V的编译器支持
  - ScalableVectorType与vscale机制
  - 从体系结构视角看：为什么硬件走向可伸缩向量

---

## 第三篇：后端 — IR到机器码的硬件适配之路

### 第9章 关键分析算法：优化决策的算力引擎

- 9.1 DominatorTree：Lengauer-Tarjan与增量更新
  - 半支配者与迭代支配者计算
  - 增量更新：插入/删除边后的高效维护
- 9.2 ScalarEvolution：循环变量的符号计算
  - SCEV表达式层次：SCEVConstant → SCEVAddRecExpr → SCEVUnknown
  - 闭式表达式构造：从指令到SCEV的推导链
  - SCEV在LSR/LoopVectorize中的关键应用
- 9.3 别名分析(AliasAnalysis)：多策略融合
  - BasicAA + GlobalsAA + SCEVAA + TBAA + ScopedNoAliasAA
  - AAResults::alias()的分发逻辑
- 9.4 MemorySSA：内存的SSA形式
  - MemoryDef / MemoryUse / MemoryPhi
  - Walker优化查询：clobber查找算法
  - MemorySSA在LICM/DSE中的使用
- 9.5 代价模型：TargetTransformInfo / TargetLibraryInfo
  - TTI：连接优化器与后端的桥梁
  - X86 TTI (353KB) 深度解析：向量化代价、指令代价

### 第10章 指令选择：从IR到机器指令的桥梁

- 10.1 SelectionDAG：DAG-based指令选择
  - SDNode / SDValue / ISD opcodes 层次体系
  - `SelectionDAGBuilder.cpp`：IR→DAG构建(510KB)
  - Legalize → Combine → Select 三阶段详解
  - `DAGCombiner.cpp`：LLVM最大文件的窥孔优化(1210KB)
- 10.2 GlobalISel：新一代指令选择框架
  - IRTranslator → Legalizer → RegBankSelect → InstructionSelect
  - G_*通用操作码设计哲学
  - CombinerHelper模式匹配
  - GISel vs SelectionDAG对比
- 10.3 TableGen：指令描述的DSL
  - .td文件语法：Instruction / Register / Pattern / SchedMachineModel
  - TableGen代码生成：从.td到C++的自动转换
  - 实例：X86指令定义与模式匹配规则

### 第11章 寄存器分配：虚拟到物理的映射

- 11.1 寄存器分配问题：NP-完全与启发式
  - LiveInterval：活跃区间分析
  - 溢出代价模型与分配评分
- 11.2 三种分配算法
  - RegAllocFast：快速局部分配
  - RegAllocGreedy：贪心全局分配(111KB源码)
  - RegAllocPBQP：分区布尔二次规划
- 11.3 ML驱动的寄存器分配
  - `MLRegAllocEvictAdvisor.cpp` / `MLRegAllocPriorityAdvisor.cpp`
  - 从启发式到学习的演进
- 11.4 不同体系结构的寄存器压力差异
  - X86(16 GPR) vs AArch64(31 GPR) vs RISC-V(31 GPR)
  - 对溢出频率和代码质量的量化影响

### 第12章 指令调度与代码发射

- 12.1 调度问题：流水线冒险与指令级并行
  - 数据冒险 / 结构冒险 / 控制冒险
  - ScheduleDAG / ScheduleDAGInstrs / ScheduleDAGSDNodes
- 12.2 调度算法
  - List Scheduling / VLIW Scheduling / Modulo Scheduling(软件流水)
  - `MachinePipeliner.cpp`：软件流水实现
- 12.3 机器模型(SchedMachineModel)
  - 延迟/吞吐量/执行端口的TableGen描述
  - X86调度模型演进：Broadwell → Ice Lake → Sapphire Rapids
  - 从体系结构视角看：为什么调度模型要匹配微架构
- 12.4 代码发射
  - MC层：`MCAsmBackend` / `MCCodeEmitter` / `MCObjectWriter`
  - AsmPrinter：MachineInstr → 汇编文本
  - ELF/Mach-O/WASM目标文件格式

### 第13章 目标后端：体系结构适配实战

- 13.1 后端通用架构：每个Target的目录模板
  - ISelLowering / ISelDAGToDAG / InstrInfo / RegisterInfo / FrameLowering
  - Subtarget机制：同一ISA不同微架构的差异处理
- 13.2 X86后端：CISC的编译器工程
  - X86ISelLowering.cpp (2556KB!)：最大文件的工程解读
  - AVX/SSE/AVX-512向量化路径
  - X86特有Pass：CmovConversion / AvoidStoreForwardingBlocks / DomainReassignment
- 13.3 AArch64后端：RISC与SVE
  - 固定指令长度的简化效应
  - SVE可伸缩向量的编译支持
  - AArch64特有Pass：A57FPLoadBalancing / LoadStoreOptimizer
- 13.4 RISC-V后端：模块化ISA的编译策略
  - 基础ISA + 扩展的组合式后端
  - RISC-V V向量扩展的指令选择
- 13.5 调用约定：ABI的编译器实现
  - X86-64 System V vs AArch64 AAPCS64 vs RISC-V ABI
  - `CallingConv.td`：调用约定的TableGen描述

---

## 第四篇：MLIR — 多层IR的编译新范式

### 第14章 MLIR核心：可扩展编译基础设施

- 14.1 为什么需要MLIR？——LLVM IR的局限与突破
  - 单层IR的表达力瓶颈
  - AI编译、硬件综合、HPC的差异化需求
- 14.2 核心数据结构：Operation / Dialect / Region / Block
  - Operation：MLIR的基本单元(内存布局与生命周期)
  - Dialect：可扩展命名空间(注册/发现/解析机制)
  - Region & Block：嵌套IR结构(与LLVM IR的本质区别)
  - 与LLVM IR Value/Instruction的对比映射
- 14.3 类型系统：从简单到富类型
  - tensor / memref / vector 三种张量类型的语义差异
  - ShapedType层次与动态形状支持
- 14.4 Attribute与Properties
  - 编译期元数据的表达与传递

### 第15章 Dialect生态：从高层语义到低层代码

- 15.1 核心Dialect详解
  - Arith / Func / SCF / CF：基础设施方言
  - MemRef / Tensor：内存与张量
  - Linalg：结构化线性代数(深度学习编译核心!)
  - Affine：仿射循环(多面体优化)
  - GPU / SPIRV / NVVM / ROCDL：异构计算
- 15.2 Pattern Rewriting：模式重写引擎
  - RewritePattern / PatternRewriter / benefit排序
  - Declarative Rewrites与PDLL
- 15.3 Dialect Conversion：方言间的渐进式降低
  - ConversionTarget / TypeConverter / applyFullConversion
  - 84个转换Pass的组织逻辑(`mlir/lib/Conversion/`)
- 15.4 Linalg优化流水线：Tiling → Fusion → Vectorization → Bufferization
  - 数据库执行计划优化的类比：逻辑算子 → 物理算子
  - Transform Dialect：声明式转换策略

### 第16章 MLIR实战：AI编译器的完整路径

- 16.1 深度学习编译栈全景
  - PyTorch/TF → Torch/TF Dialect → Linalg → SCF+Affine → LLVM IR → Machine Code
  - IREE / Torch-MLIR / XLA的MLIR实践
- 16.2 从算子到硬件：Linalg到GPU的完整Lowering
  - matmul示例：Linalg → Tiling → Vector → GPU → PTX/GCN
- 16.3 稀疏张量编译(SparseTensor Dialect)
- 16.4 量化编译(Quant Dialect)

---

## 第五篇：前沿 — AI时代与硬件感知编译

### 第17章 GPU异构编译：SIMT世界的编译器适配

- 17.1 GPU执行模型与编译差异
  - SIMT vs 标量：Warp/Wavefront执行模型
  - GPU内存层次：寄存器 → 共享内存 → 全局内存
  - 地址空间(0-5)在LLVM IR中的表示
- 17.2 NVPTX后端
  - CUDA C++ → Clang → LLVM IR → NVPTX → PTX → SASS
  - NVPTX特有优化：AllocaHoisting / ImageOptimizer / NVVMReflect
- 17.3 AMDGPU后端
  - HIP → Clang → LLVM IR → AMDGPU → GCN ISA → HSACO
  - AMDGPU特有优化：PromoteAlloca / AnnotateUniformValues / ExecMasking
- 17.4 OpenMP Offload机制
  - `offload/` 目录架构
  - target region的编译流程与运行时调度
- 17.5 GPU vs CPU优化策略差异总结
  - Branch Divergence处理
  - Memory Coalescing感知
  - Shared Memory利用

### 第18章 JIT编译与运行时代码生成

- 18.1 LLVM JIT架构演进
  - MCJIT → ORC JIT v1 → ORC JIT v2
- 18.2 ORC JIT v2深度解析
  - `ExecutionEngine/Orc/` 核心组件
  - LLJIT / CompileOnDemandLayer / IRTransformLayer
  - IndirectionUtils：惰性编译的跳板机制
  - ReOptimizeLayer：运行时重新优化
- 18.3 JIT在数据库中的应用
  - 查询编译：表达式JIT / 整行JIT / Vectorized vs Compiled
  - PostgreSQL JIT / Velox / Presto的LLVM JIT实践
  - 从编译器视角看：为什么数据库需要运行时代码生成
- 18.4 JIT在LLM推理中的应用
  - 动态shape的编译优化
  - Kernel fusion的运行时决策
  - TVM / TensorRT / torch.compile 的JIT策略

### 第19章 Profile-Guided与ML驱动优化

- 19.1 PGO(Profile-Guided Optimization)
  - 插桩PGO：`InstrProfiling` / `PGOInstrumentation`
  - 采样PGO：`SampleProfile` / `AutoFDO`
  - `ProfileData/` 目录：GCOV / IndexedInstrProf / SampleProf
- 19.2 MemProf：堆分配画像
  - `MemProfContextDisambiguation`：上下文敏感的堆优化
- 19.3 ML驱动的编译决策
  - MLInlineAdvisor：机器学习内联策略
  - MLRegAllocAdvisor：学习型寄存器分配
  - 模型推理框架：`ModelUnderTrainingRunner` / `TFLiteUtils`
- 19.4 AutoFDO + MLGO在工业界的实践
  - Google的MLGO：从启发式到学习的演进
  - 与数据库学习型优化器的类比：LBO vs MLGO

### 第20章 LTO与链接时优化

- 20.1 LTO架构
  - Full LTO vs ThinLTO：设计权衡
  - `llvm/lib/LTO/` / `llvm/lib/Linker/` 核心逻辑
  - `ThinLTOCodeGenerator.cpp`：索引式并行优化
- 20.2 跨模块优化机会
  - 跨模块内联与常量传播
  - WholeProgramDevirt在LTO中的角色
- 20.3 Caching与增量编译
  - ThinLTO缓存机制
  - CAS(Content Addressable Storage)：`llvm/lib/CAS/` 的新基础设施

### 第21章 体系结构感知编译：从硬件到软件的适配

- 21.1 缓存感知优化
  - 数据预取：`LoopDataPrefetch` / `InsertCodePrefetch`
  - 缓存分块：Loop tiling与缓存行对齐
  - 从体系结构看：为什么编译器需要理解Cache层级
- 21.2 分支预测感知优化
  - `BranchProbabilityInfo` / `BlockFrequencyInfo`
  - PGO驱动的布局优化：`MachineBlockPlacement`
  - 分支预测失误代价的编译器建模
- 21.3 内存一致性模型与编译器屏障
  - 原子操作lowering：`AtomicExpandPass`
  - Memory model从C++到硬件的映射
- 21.4 安全机制与编译器支持
  - CFI / KCFI / Shadow Stack / SafeStack
  - Sanitizer体系：ASan / MSan / TSan / UBSan
  - 编译器对安全硬件特性的适配(Intel CET, PAC, BTI)
- 21.5 特定微架构的编译适配
  - Store Forwarding Block避免(X86AvoidStoreForwardingBlocks)
  - 执行端口调度与宏融合(MacroFusion)
  - 从CPU微架构手册到编译器调度模型

### 第22章 LLM推理优化：编译器视角

- 22.1 LLM推理的计算特征
  - Transformer算子图：Attention / FFN / KV Cache
  - 内存带宽瓶颈 vs 计算瓶颈：roofline模型分析
  - 与数据库查询执行的类比：IO-bound vs CPU-bound
- 22.2 LLM算子的编译优化
  - Flash Attention的编译器实现思路
  - KV Cache的内存布局优化
  - GEMM/GEMV的自动向量化与tiling
- 22.3 动态shape与自适应编译
  - MLIR的动态shape支持：tensor<*xf32>
  - Sequence length / Batch size变化的编译策略
  - JIT vs AOT的权衡
- 22.4 量化与混合精度
  - W8A8 / W4A16 / FP8量化的编译器路径
  - Linalg + Quant Dialect的量化流水线
- 22.5 分布式推理的编译器支持
  - Tensor Parallelism / Pipeline Parallelism的IR表达
  - Shard Dialect / MPI Dialect
- 22.6 主流LLM推理框架的编译器架构对比
  - vLLM / TensorRT-LLM / TGI / llama.cpp
  - 它们如何使用LLVM/MLIR

### 第23章 Agent与编译器：自适应优化的未来

- 23.1 Agent驱动的编译优化
  - 编译决策作为MDP：状态(程序特征) → 动作(优化选择) → 奖励(加速比)
  - AutoTVM / Ansor / CompilerGym的探索
- 23.2 程序表征学习
  - IR2Vec / ProGraML / CodeBERT：从IR到向量
  - `llvm/lib/Analysis/IR2Vec.cpp` 源码解析
- 23.3 程序合成的编译器路径
  - 从自然语言到IR的生成：LLM作为编译前端
  - CIR(MLIR Clang IR) / CIRCT(硬件综合)的新范式
- 23.4 展望：AI原生编译器
  - 学习型代价模型替代手工启发式
  - 端到端可微编译管线
  - 硬件-编译器协同设计

---

## 附录

### 附录A 源码导航手册
- 目录树 + 每个子目录的一句话功能说明
- 关键.def文件索引与用途
- 按功能分类的文件名→用途映射

### 附录B 核心数据结构速查
- Value / Type / SCEV / MemorySSA / SDNode / Operation 类层次图
- 每个数据结构：头文件 / 关键方法 / 关系图

### 附录C opt/llc/mlir-opt实战手册
- 按Pass分类的常用命令
- 调试选项：`-debug-only` / `-print-after-all` / `-stats`
- 分析结果dump方法

### 附录D 自定义Pass模板
- New Pass Manager模板：Analysis Pass + Transform Pass
- PassBuilder注册方法
- MLIR Pass模板

### 附录E 体系结构速查(面向编译器工程师)
- X86-64 / AArch64 / RISC-V 关键特性对比
- 缓存层次 / TLB / 分支预测器 / 执行端口
- SIMD指令集演进：SSE → AVX → AVX2 → AVX-512 / NEON → SVE / RISC-V V

### 附录F 数据库优化器与编译器优化概念映射表

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

---

## 全书写作规范

1. **源码可追踪**：每个技术论断标注源文件路径+类/函数名
2. **三级深度**：What(概览) → How(机制) → Where(源码)
3. **IR实例驱动**：每个优化Pass配有before/after IR + `opt`命令
4. **体系结构锚点**：每章至少一处连接硬件特性的解释
5. **数据库类比**：适时用数据库概念类比降低学习门槛
6. **AI连接**：第五篇每章连接LLM推理/Agent的实际需求

---

## 源码基线与变更追踪

书稿内容基于以下LLVM源码版本分析，源码更新后可能导致文件路径、行数、类名等引用失效：

- **Commit**: `13cae27e9e99ab2ca865e9670c9aaa6106d87cb7`
- **日期**: 2026-04-16 05:10:25 +0000
- **分支**: main
- **远程**: https://github.com/llvm/llvm-project.git
- **最新提交信息**: Revert "[flang][cuda] Avoid false positive on multi device symbol with components" (#192393)

### 变更检测方法

```bash
# 查看基线以来的所有新提交
git log 13cae27e9..HEAD --oneline

# 重点关注的目录(书稿高频引用)
git log 13cae27e9..HEAD --oneline -- llvm/lib/IR/ llvm/include/llvm/IR/
git log 13cae27e9..HEAD --oneline -- llvm/lib/Transforms/ llvm/include/llvm/Transforms/
git log 13cae27e9..HEAD --oneline -- llvm/lib/CodeGen/ llvm/include/llvm/CodeGen/
git log 13cae27e9..HEAD --oneline -- llvm/lib/Analysis/ llvm/include/llvm/Analysis/
git log 13cae27e9..HEAD --oneline -- llvm/lib/Passes/ llvm/include/llvm/Passes/
git log 13cae27e9..HEAD --oneline -- mlir/lib/ mlir/include/mlir/
git log 13cae27e9..HEAD --oneline -- llvm/lib/Target/X86/ llvm/lib/Target/AArch64/ llvm/lib/Target/RISCV/
git log 13cae27e9..HEAD --oneline -- llvm/lib/Bitcode/ llvm/lib/ExecutionEngine/ llvm/lib/LTO/ llvm/lib/ProfileData/

# 更新基线(确认书稿同步更新后执行)
# 将下方commit替换为新的HEAD commit
```

### 需要同步更新的书稿内容

| 变更类型 | 影响范围 | 更新策略 |
|---------|---------|---------|
| 文件路径变更 | 所有章节的源码引用 | 全局搜索替换旧路径 |
| 行数变化 | 所有标注行数的引用 | 重新grep确认行号 |
| 类/函数重命名 | 类层次图、方法引用 | 更新类名和方法名 |
| 新增Pass/指令 | Instruction.def、PassBuilderPipelines | 更新计数和描述 |
| 新增Dialect | 第14-16章 | 补充新方言说明 |
| 目标后端变更 | 第13章 | 更新后端描述 |
| API签名变更 | 附录B速查表 | 更新方法签名 |

### 写作进度

| 章节 | 状态 | 文件 |
|------|------|------|
| 第1章 编译器的三段式哲学 | ✅ 完成 | Chapter01_三段式哲学.md |
| 第2章 LLVM IR类型化SSA | ✅ 完成 | Chapter02_IR类型化SSA的精妙设计.md |
| 第3章 IR的三种面貌 | ✅ 完成 | Chapter03_IR的三种面貌.md |
| 第4章 Pass基础设施 | ✅ 完成 | Chapter04_Pass基础设施.md |
| 第5章 标量优化 | ✅ 完成 | Chapter05_标量优化.md |
| 第6章 InstCombine | ✅ 完成 | Chapter06_InstCombine.md |
| 第7章 过程间优化(IPO) | ✅ 完成 | Chapter07_过程间优化.md |
| 第8章 自动向量化 | ✅ 完成 | Chapter08_自动向量化.md |
| 第9章 关键分析算法 | ✅ 完成 | Chapter09_关键分析算法.md |
| 第10章 指令选择 | ✅ 完成 | Chapter10_指令选择.md |
| 第11章 寄存器分配 | ✅ 完成 | Chapter11_寄存器分配.md |
| 第12章 指令调度与代码发射 | ✅ 完成 | Chapter12_指令调度与代码发射.md |
| 第13章 目标后端 | ✅ 完成 | Chapter13_目标后端.md |
| 第14章 MLIR核心 | ✅ 完成 | Chapter14_MLIR核心.md |
| 第15章 Dialect生态 | ✅ 完成 | Chapter15_Dialect生态.md |
| 第16章 MLIR实战 | ✅ 完成 | Chapter16_MLIR实战.md |
| 第17章 GPU异构编译 | ✅ 完成 | Chapter17_GPU异构编译.md |
| 第18章 JIT编译 | ✅ 完成 | Chapter18_JIT编译.md |
| 第19章 Profile-Guided与ML驱动优化 | ✅ 完成 | Chapter19_Profile-Guided与ML驱动优化.md |
| 第20章 LTO与链接时优化 | ✅ 完成 | Chapter20_LTO与链接时优化.md |
| 第21章 体系结构感知编译 | ✅ 完成 | Chapter21_体系结构感知编译.md |
| 第22章 LLM推理优化 | ✅ 完成 | Chapter22_LLM推理优化.md |
| 第23章 Agent与编译器 | ✅ 完成 | Chapter23_Agent与编译器.md |
| 附录A 源码导航手册 | ✅ 完成 | AppendixA_源码导航手册.md |
| 附录B 核心数据结构速查 | ✅ 完成 | AppendixB_核心数据结构速查.md |
| 附录C opt/llc/mlir-opt实战 | ✅ 完成 | AppendixC_opt_llc_mlir-opt实战手册.md |
| 附录D 自定义Pass模板 | ✅ 完成 | AppendixD_自定义Pass模板.md |
| 附录E 体系结构速查 | ✅ 完成 | AppendixE_体系结构速查.md |
| 附录F 数据库-编译器概念映射 | ✅ 完成 | AppendixF_数据库与编译器概念映射.md |

### 待改进项

- [ ] 各章补充更多before/after IR实例和opt命令
- [ ] 第5章SROA补充partition算法的详细步骤
- [ ] 第8章VPlan补充VPlanBuilder的源码追踪
- [ ] 第9章SCEV补充更多闭式表达式推导示例
- [ ] 第10章GlobalISel补充CombinerHelper的规则列表
- [ ] 第16章补充IREE的完整编译流水线示例
- [ ] 第22章补充Flash Attention的MLIR实现细节
- [ ] 源码更新后批量校验引用的行数和路径
