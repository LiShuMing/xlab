# 第21章 体系结构感知编译：从硬件到软件的适配

## 21.1 缓存感知优化

### 21.1.1 数据预取：LoopDataPrefetch / InsertCodePrefetch

```
缓存预取的编译器支持:

LoopDataPrefetch:
  在循环中插入预取指令, 将下一次迭代需要的数据提前加载到缓存

  for (int i = 0; i < N; i++)
    sum += arr[i];  // 顺序访问模式

  → 编译器插入:
  for (int i = 0; i < N; i++) {
    __builtin_prefetch(&arr[i+8]);  // 提前8个元素预取
    sum += arr[i];
  }

  预取距离计算:
    prefetch_distance = cache_line_size * prefetch_iterations / element_size
    例: 64字节缓存行 × 8次迭代 / 4字节(int) = 128个元素

InsertCodePrefetch:
  在非循环代码中插入预取
  例: 函数调用前预取函数体(代码预取)

源码入口:
  llvm/lib/Transforms/Scalar/LoopDataPrefetch.cpp
  llvm/lib/CodeGen/InsertPrefetch.cpp

TTI接口:
  unsigned getPrefetchDistance();    // 预取距离
  unsigned getCacheLineSize();      // 缓存行大小
  unsigned getMinPrefetchStride();  // 最小预取步长
```

### 21.1.2 缓存分块：Loop tiling与缓存行对齐

```
缓存分块(Tiling): 将大循环分成适配缓存的小块

  原始矩阵乘法:
  for (i=0; i<1024; i++)
    for (j=0; j<1024; j++)
      for (k=0; k<1024; k++)
        C[i][j] += A[i][k] * B[k][j];
  // A的行: 4KB × 1024 = 4MB → 超出L2缓存!
  // B的列: 同样超出缓存

  分块后(64×64):
  for (ii=0; ii<1024; ii+=64)
    for (jj=0; jj<1024; jj+=64)
      for (kk=0; kk<1024; kk+=64)
        for (i=ii; i<ii+64; i++)
          for (j=jj; j<jj+64; j++)
            for (k=kk; k<kk+64; k++)
              C[i][j] += A[i][k] * B[k][j];
  // A的块: 4×64 = 256字节 → 在L1缓存中!
  // B的块: 64×4 = 256字节 → 在L1缓存中!

  编译器支持:
  - MLIR Affine Dialect: 自动tiling
  - Polly: 多面体tiling
  - LLVM IR: LoopInterchange + LoopUnrollAndJam
```

### 21.1.3 从体系结构看：为什么编译器需要理解Cache层级

```
典型CPU缓存参数:

Intel Skylake-SP:
  L1 I-Cache: 32KB, 8路, 64B行, 4周期延迟
  L1 D-Cache: 32KB, 8路, 64B行, 4周期延迟
  L2 Cache:   1MB,  16路, 64B行, 12周期延迟
  L3 Cache:   ~1.375MB/核, 11周期延迟(同socket)

AMD Zen3:
  L1 I-Cache: 32KB, 8路, 64B行, 4周期
  L1 D-Cache: 32KB, 8路, 64B行, 4周期
  L2 Cache:   512KB, 8路, 64B行, 12周期
  L3 Cache:   32MB共享,  ~40周期

编译器优化必须考虑:
  1. 缓存行大小: 决定预取和对齐策略
  2. 缓存容量: 决定tiling的块大小
  3. 关联度: 影响缓存冲突分析
  4. 延迟: 决定预取距离
  5. L3共享: 影响多线程代码的数据布局

  不理解Cache的编译器 = 不理解磁盘的数据库!
```

---

## 21.2 分支预测感知优化

### 21.2.1 BranchProbabilityInfo / BlockFrequencyInfo

```
分支概率估计:
  BPI(BranchProbabilityInfo): 估计每个条件分支的taken概率
  BFI(BlockFrequencyInfo): 估计每个基本块的执行频率

估计方法:
  1. 静态启发式(无PGO时):
     - 循环回边: taken概率 ~90%
     - strcmp==0: taken概率 ~50%
     - 错误检查(ptr==NULL): taken概率 ~1%
     - 后支配者: 根据CFG拓扑推导

  2. PGO驱动(有profile时):
     - 直接使用profile中的边频率
     - 精度远高于静态启发式

源码入口:
  llvm/lib/Analysis/BranchProbabilityInfo.cpp
  llvm/lib/Analysis/BlockFrequencyInfo.cpp
```

### 21.2.2 PGO驱动的布局优化：MachineBlockPlacement

```
基本块布局优化: 将热基本块连续排列

目标:
  1. 热路径fall-through(无跳转)
  2. 冷代码集中到函数末尾
  3. 减少icache miss和分支预测失误

算法(MachineBlockPlacement):
  1. 构建CFG的权重图(边权重=执行频率)
  2. 找到最热路径(最长权重路径)
  3. 沿最热路径排列基本块(fall-through)
  4. 递归处理未排列的块

  Before:                     After(PGO驱动):
  entry(1000)                 entry(1000)
    ├── hot_path(900)           ├── hot_path(900) ← fall-through!
    │   └── cold_error(10)      │   └── more_hot(850) ← fall-through!
    └── warm_path(80)           └── warm_path(80)
        └── more_hot(850)            └── cold_error(10) ← 移到末尾

分支预测失误代价的编译器建模:
  典型CPU: 分支预测失误惩罚 = 15-20个周期
  编译器模型: 布局改变的收益 = 减少的预测失误次数 × 15周期
```

---

## 21.3 内存一致性模型与编译器屏障

### 21.3.1 原子操作lowering：AtomicExpandPass

```
C++原子操作的编译器映射:

  C++11 memory_order            LLVM IR               X86-64指令
  ──────────────────────────────────────────────────────────────
  relaxed                       unordered              普通load/store
  acquire                       acquire                mov + mfence(或lock xadd)
  release                       release                mov + sfence(或lock xadd)
  acq_rel                       acq_rel                lock xadd
  seq_cst                       seq_cst                lock xadd + mfence

  AtomicExpandPass:
  - 将LLVM IR原子操作lowering为目标特定的指令序列
  - 处理目标不支持的操作(如CAS循环展开)
  - 插入必要的fence指令

  源码入口:
  llvm/lib/CodeGen/AtomicExpandPass.cpp

  不同架构的原子操作差异:
  X86-64: 强排序(TSO), 大多数原子操作免费
  AArch64: 弱排序, 需要显式dmb/isb指令
  RISC-V: 最弱排序, 需要fence指令
```

---

## 21.4 安全机制与编译器支持

### 21.4.1 CFI / KCFI / Shadow Stack / SafeStack

```
控制流完整性(CFI):
  -clang -fsanitize=cfi → 插入类型检查, 防止控制流劫持
  - KCFI(Kernel CFI): 内核版本的CFI, 使用类型哈希
  - 每个间接调用前插入类型检查

Shadow Stack:
  - 将返回地址存储在影子栈(独立内存区域)
  - 函数返回前比较栈上的返回地址和影子栈
  - 防止ROP(Return-Oriented Programming)攻击
  - Intel CET(Control-flow Enforcement Technology)的硬件支持

SafeStack:
  - 将易受攻击的变量(数组/buffer)移到单独栈
  - 安全变量(指针/返回地址)留在主栈
  - 降低栈溢出的攻击面

Sanitizer体系:
  ASan(Address Sanitizer):   检测越界/use-after-free
  MSan(Memory Sanitizer):    检测未初始化内存读取
  TSan(Thread Sanitizer):    检测数据竞争
  UBSan(Undefined Behavior): 检测UB(整数溢出/空指针等)

  源码入口:
  llvm/lib/Transforms/Instrumentation/AddressSanitizer.cpp
  llvm/lib/Transforms/Instrumentation/MemorySanitizer.cpp
  llvm/lib/Transforms/Instrumentation/ThreadSanitizer.cpp
```

---

## 21.5 特定微架构的编译适配

### 21.5.1 Store Forwarding Block避免

```
X86AvoidStoreForwardingBlocks:
  Intel CPU的store→load转发在以下情况阻塞:
  1. store的数据大小 ≠ load的数据大小
  2. store跨缓存行
  3. load跨越store的部分数据

  阻塞代价: 40-50个周期!

  编译器避免策略:
  1. 将store+load替换为寄存器传递
  2. 对齐store以避免跨缓存行
  3. 插入其他指令掩盖延迟
```

### 21.5.2 执行端口调度与宏融合(MacroFusion)

```
MacroFusion: X86将cmp+条件跳转融合为单条微操作

  cmp rax, rbx      ; 单独: 1微操作
  jle target         ; 单独: 1微操作
  → 融合后: 1微操作! (节省1个发射槽)

  编译器适配:
  MachineScheduler保持cmp和jle相邻
  如果中间插入其他指令 → 融合失效 → 性能下降

  X86MacroFusion Pass:
  检测可融合的指令对, 调整调度顺序使它们相邻
```

### 21.5.3 从CPU微架构手册到编译器调度模型

```
编译器适配微架构的工作流:

1. Intel发布优化手册(Optimization Manual)
   - 每代微架构的延迟/吞吐量/端口分配
   - 推荐的代码生成策略
   - 已知性能陷阱和规避方法

2. LLVM开发者阅读手册, 更新调度模型
   - X86ScheduleSkylake.td → X86ScheduleIceLake.td → ...
   - 新的指令延迟/端口映射
   - 新的优化策略(如新的融合规则)

3. 编译器测试验证
   - llvm-mca: 模拟指令调度, 检查端口压力
   - 性能基准测试: 验证调度模型的准确性
   - 自动化回归测试

4. 发布更新
   - 新的-mcpu=选项
   - 默认tune策略更新

这个循环每代微架构重复一次, 是编译器与硬件协同设计的典型范例
```

---

## 21.6 本章小结

本章从硬件到软件，解析了体系结构感知编译的五个维度：

1. **缓存感知**——预取、分块、缓存行对齐，编译器必须理解Cache层级。
2. **分支预测感知**——BPI/BFI概率估计、PGO驱动的MachineBlockPlacement。
3. **内存一致性模型**——原子操作lowering、fence插入、X86 vs ARM vs RISC-V的差异。
4. **安全机制**——CFI/Shadow Stack/Sanitizer，编译器对安全硬件特性的适配。
5. **微架构适配**——Store Forwarding Block避免、MacroFusion、从CPU手册到调度模型的工作流。

下一章进入LLM推理优化的编译器视角。
