# 附录B 核心数据结构速查

## 类层次图

### Value继承体系

```
Value
├── Argument                    : 函数参数
├── BasicBlock                  : 基本块(也是Value——可作为跳转目标)
├── Function : GlobalValue      : 函数
│   └── GlobalValue
│       ├── GlobalVariable      : 全局变量
│       ├── GlobalAlias         : 全局别名
│       └── GlobalIFunc         : 间接函数
├── Instruction : User          : 指令
│   ├── BinaryOperator          : 二元运算(add/sub/mul/...)
│   ├── CmpInst                 : 比较(icmp/fcmp)
│   ├── CallInst                : 函数调用
│   ├── LoadInst                : 内存加载
│   ├── StoreInst               : 内存存储
│   ├── AllocaInst              : 栈分配
│   ├── GetElementPtrInst       : 地址计算
│   ├── PHINode                 : SSA合并
│   ├── SelectInst              : 条件选择
│   ├── BranchInst              : 分支
│   ├── ReturnInst              : 返回
│   └── ... (69种指令)
├── Constant : User             : 常量(也是User!)
│   ├── ConstantInt             : 整数常量
│   ├── ConstantFP              : 浮点常量
│   ├── ConstantExpr            : 常量表达式
│   ├── UndefValue              : 未定义值
│   │   └── PoisonValue         : 毒值
│   ├── ConstantPointerNull     : 空指针
│   ├── ConstantArray           : 数组常量
│   ├── ConstantStruct          : 结构体常量
│   ├── ConstantVector          : 向量常量
│   └── BlockAddress            : 基本块地址
└── InlineAsm                   : 内联汇编
```

### Type继承体系

```
Type (不可变, 唯一化)
├── PrimitiveTypes
│   ├── VoidTy, LabelTy, MetadataTy, TokenTy
│   ├── HalfTy, BFloatTy, FloatTy, DoubleTy
│   ├── X86_FP80Ty, FP128Ty, PPC_FP128Ty
│   └── X86_AMXTy
├── IntegerType                 : 任意位宽整数(i1-i8388608)
├── FunctionType                : 函数签名(返回+参数+vararg)
├── PointerType                 : opaque pointer(ptr)
├── StructType                  : 结构体(命名/字面, packed)
├── ArrayType                   : 数组([N x T])
├── VectorType
│   ├── FixedVectorType         : 固定向量(<4 x i32>)
│   └── ScalableVectorType      : 可伸缩向量(<vscale x 4 x i32>)
├── TypedPointerType            : 类型化指针(仅GPU)
└── TargetExtType               : 目标扩展类型
```

### SCEV表达式层次

```
SCEV (唯一化, 不可变)
├── SCEVConstant                : 常量
├── SCEVUnknown                 : 不可分析的值
├── SCEVAddRecExpr              : 递归加法 {start, +, step}<loop>
├── SCEVAddExpr                 : 加法 A + B
├── SCEVMulExpr                 : 乘法 A * B
├── SCEVUDivExpr                : 无符号除法
├── SCEVZeroExtendExpr          : 零扩展
├── SCEVSignExtendExpr          : 符号扩展
├── SCEVTruncateExpr            : 截断
├── SCEVPtrToIntExpr            : 指针→整数
└── SCEVMinMaxExpr              : min/max
```

### MLIR Operation层次

```
Operation (一切皆Operation)
├── arith.addi, arith.addf, arith.muli, ...
├── func.func, func.call, func.return
├── scf.for, scf.if, scf.while, scf.yield
├── cf.br, cf.cond_br
├── linalg.matmul, linalg.conv, linalg.generic
├── affine.for, affine.if, affine.load, affine.store
├── gpu.launch, gpu.thread_id, gpu.barrier
├── vector.contract, vector.transfer_read/write
├── memref.alloc, memref.load, memref.store
├── tensor.extract, tensor.insert, tensor.empty
└── (40+ Dialect, 1000+ Operation类型)
```

## 每个数据结构：头文件 / 关键方法 / 关系图

| 数据结构 | 头文件 | 关键方法 | 关系 |
|---------|--------|---------|------|
| Value | `llvm/IR/Value.h` | `use_begin()`, `replaceAllUsesWith()`, `getType()` | User和Constant的基类 |
| User | `llvm/IR/User.h` | `getOperand()`, `setOperand()`, `operands()` | Value的子类, 持有Use[] |
| Instruction | `llvm/IR/Instruction.h` | `getOpcode()`, `getParent()`, `eraseFromParent()` | User的子类, 在BasicBlock中 |
| BasicBlock | `llvm/IR/BasicBlock.h` | `getTerminator()`, `getSinglePredecessor()` | Value的子类, 持有Instruction链表 |
| Function | `llvm/IR/Function.h` | `getEntryBlock()`, `getArgument()`, `getCallingConv()` | GlobalValue的子类 |
| Module | `llvm/IR/Module.h` | `getFunctionList()`, `getDataLayout()`, `getTargetTriple()` | 最外层容器 |
| DominatorTree | `llvm/IR/Dominators.h` | `dominates()`, `getNode()`, `getRootNode()` | 分析结果 |
| SCEV | `llvm/Analysis/ScalarEvolution.h` | `getSCEV()`, `getBackedgeTakenCount()` | 分析结果 |
| MemorySSA | `llvm/Analysis/MemorySSA.h` | `getMemoryAccess()`, `getWalker()` | 分析结果 |
| AAResults | `llvm/Analysis/AliasAnalysis.h` | `alias()`, `isNoAlias()`, `modRef()` | 分析结果 |
