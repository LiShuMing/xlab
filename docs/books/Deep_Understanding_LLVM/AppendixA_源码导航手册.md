# 附录A 源码导航手册

## 目录树 + 每个子目录的一句话功能说明

```
llvm-project/
├── llvm/                  # LLVM核心——编译器基础设施
│   ├── include/llvm/      # 公共头文件(API定义)
│   │   ├── IR/            # IR核心: Value, Type, Instruction, Function, Module
│   │   ├── Analysis/      # 分析Pass接口: DominatorTree, SCEV, AA, MemorySSA
│   │   ├── Transforms/    # 变换Pass接口: Scalar, IPO, Vectorize, InstCombine
│   │   ├── CodeGen/       # 后端接口: SelectionDAG, GlobalISel, RegAlloc, Sched
│   │   ├── Target/        # 目标后端接口: TTI, TLI, TargetMachine
│   │   ├── Passes/        # Pass管理器接口: PassBuilder
│   │   ├── Support/       # 基础设施: Allocator, StringRef, Error, Debug
│   │   └── ADT/           # 抽象数据类型: DenseMap, SmallVector, StringMap
│   ├── lib/               # 实现文件
│   │   ├── IR/            # IR核心实现(~18K行)
│   │   ├── Analysis/      # 分析Pass实现(DomTree 16K, SCEV 16K, AA 2K, MSSA 3K)
│   │   ├── Transforms/    # 变换Pass实现(Scalar 35K, IPO 15K, Vectorize 48K, InstCombine 36K)
│   │   ├── CodeGen/       # 后端实现(SelDAG 51K, RegAlloc 6K, Sched 10K)
│   │   ├── Target/        # 30+目标后端(X86 2556K, AArch64 1100K, RISC-V 200K)
│   │   ├── Passes/        # Pass管理器实现(PassBuilder 3K, Pipelines 3K)
│   │   ├── MC/            # 机器码层(汇编/反汇编/目标文件)
│   │   ├── LTO/           # 链接时优化
│   │   ├── Bitcode/       # IR位码读写(Writer 6K, Reader 9K)
│   │   ├── ExecutionEngine/ # JIT编译(ORC JIT)
│   │   ├── ProfileData/   # PGO/MemProf/SampleProf
│   │   ├── Linker/        # IR链接器
│   │   └── CAS/           # 内容寻址存储
│   └── tools/             # 命令行工具
│       ├── opt/           # IR优化器
│       ├── llc/           # 后端代码生成
│       ├── lli/           # JIT解释器
│       ├── llvm-as/       # .ll → .bc
│       ├── llvm-dis/      # .bc → .ll
│       ├── llvm-mc/       # 机器码汇编器
│       ├── llvm-mca/      # 机器码性能分析
│       └── llvm-ar/       # 归档工具
├── clang/                 # C/C++/Obj-C前端
│   ├── include/clang/     # Clang头文件
│   └── lib/               # Clang实现
│       ├── Lex/           # 词法分析
│       ├── Parse/         # 语法分析
│       ├── Sema/          # 语义分析
│       ├── AST/           # 抽象语法树
│       ├── CodeGen/       # AST → LLVM IR(关键桥梁!)
│       ├── Driver/        # 编译驱动
│       └── Frontend/      # 前端基础设施
├── mlir/                  # 多层中间表示框架
│   ├── include/mlir/      # MLIR头文件
│   └── lib/               # MLIR实现
│       ├── IR/            # 核心实现(Operation, Dialect, Region)
│       ├── Dialect/       # 40+方言实现
│       ├── Conversion/    # 84个转换Pass
│       ├── Transforms/    # 通用变换(Canonicalize, CSE, Inliner)
│       └── Target/        # MLIR→LLVM/GPU/SPIRV目标
├── lld/                   # 链接器(ELF/Mach-O/COFF/WASM)
├── lldb/                  # 调试器
├── flang/                 # Fortran前端
├── compiler-rt/           # 运行时库(sanitizer/profiling/builtins)
├── libcxx/                # C++标准库实现
├── libcxxabi/             # C++ ABI库
├── libunwind/             # 异常处理与栈展开
├── openmp/                # OpenMP运行时
├── offload/               # OpenMP GPU offload
├── polly/                 # 多面体优化
├── bolt/                  # 二进制优化
└── libc/                  # C标准库(LLVM实现)
```

## 关键.def文件索引

| .def文件 | 用途 | 条目数 |
|---------|------|-------|
| `llvm/include/llvm/IR/Instruction.def` | IR指令定义 | 69条指令 |
| `llvm/include/llvm/IR/Intrinsics.td` | 目标无关内联函数 | ~800+ |
| `llvm/include/llvm/IR/IntrinsicsX86.td` | X86内联函数 | ~2000+ |
| `llvm/include/llvm/IR/Metadata.def` | 元数据类型 | ~50+ |
| `llvm/include/llvm/IR/FixedPoint.def` | 定点运算 | ~20 |
| `llvm/include/llvm/Support/AtomicOrdering.h` | 原子排序 | 7种 |

## 按功能分类的文件名→用途映射

| 功能 | 关键文件 | 说明 |
|------|---------|------|
| SSA核心 | `Value.h`, `User.h`, `Use.h`, `Instruction.h` | def-use链 |
| 类型系统 | `Type.h`, `DerivedTypes.h`, `Constants.h` | 类型/常量 |
| IR容器 | `Module.h`, `Function.h`, `BasicBlock.h` | 四层容器 |
| 优化流水线 | `PassBuilder.h`, `PassBuilderPipelines.cpp` | Pass编排 |
| 标量优化 | `Scalar/DCE.cpp`, `GVN.cpp`, `LICM.cpp`, `SROA.cpp` | 标量变换 |
| 过程间优化 | `IPO/Inliner.cpp`, `FunctionAttrs.cpp`, `WholeProgramDevirt.cpp` | 跨函数 |
| 向量化 | `Vectorize/LoopVectorize.cpp`, `SLPVectorizer.cpp` | SIMD |
| 指令选择 | `SelectionDAGBuilder.cpp`, `DAGCombiner.cpp` | IR→机器指令 |
| 寄存器分配 | `RegAllocGreedy.cpp`, `LiveIntervals.cpp` | 虚→实映射 |
| 指令调度 | `MachineScheduler.cpp`, `MachinePipeliner.cpp` | 流水线优化 |
| 代码发射 | `AsmPrinter.cpp`, `MCCodeEmitter.cpp` | 机器码生成 |
