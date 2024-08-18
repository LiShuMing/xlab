# 第7章 过程间优化(IPO)：跨越函数边界

## 7.1 内联决策框架

### 7.1.1 InlineCost代价估算公式

**源码**：`llvm/lib/Analysis/InlineCost.cpp`（~3000行）

内联是LLVM最重要的过程间优化——它将函数调用替换为函数体，消除调用开销并暴露新的优化机会。

内联决策的核心是代价估算：

```
InlineCost计算:
  成本 = 函数体成本 - 调用消除成本 - 常量参数折减

函数体成本(每条指令的权重):
  普通指令: 5       load/store: 5-40    call: 25-200
  分支:     5       select:    5         PHI:  2
  alloca:   0       调试信息:  0

调用消除成本:
  每个参数的传递成本: 5-15
  返回值处理:         5
  调用本身:           25-200

常量参数折减(最重要的启发式):
  如果调用点传入了常量参数:
  - 函数体中的分支可能变成确定的 → 删除死分支
  - 函数体中的计算可能折叠     → 删除冗余计算
  - 折减量 ≈ 被常量"激活"的死代码量

阈值(默认):
  O2: -inline-threshold=275 (指令成本单位)
  O3: 更高(更激进的内联)
  Oz: -inline-threshold=75 (几乎不内联)
```

### 7.1.2 InlineAdvisor：默认策略 vs ML驱动

```
内联策略的层次:

InlineAdvisor (接口)
├── DefaultInlineAdvisor     ← 基于阈值的传统策略
│   └── InlineCost::shouldInline() → 是/否
│
├── MLInlineAdvisor          ← ML驱动策略(第19章详解)
│   ├── ModelUnderTrainingRunner
│   └── 输入: 函数特征 → 输出: 内联决策
│
└── ReleaseModeDecisionTree  ← 训练好的决策树(推理快)
```

**默认策略的关键启发式**：

```c++
// 始终内联的条件(不考虑阈值):
1. 函数体只有一条指令(ret val / ret void)
2. 递归调用的直接递归(限制深度)
3. alwaysinline属性标注的函数
4. 调用点在热路径(PGO标记为hot)

// 永不内联的条件:
1. neverinline属性标注的函数
2. 函数太大(超过限制)
3. 递归层次太深
4. 调用点在冷路径(PGO标记为cold)
```

**数据库类比**：内联决策 ≈ 子查询展开 vs 物化——内联(展开)消除函数调用开销但增加代码大小，物化(不内联)保持代码紧凑但保留调用开销。两者的权衡核心相同：**调用/物化的开销 vs 代码/存储的膨胀**。

### 7.1.3 SCC遍历顺序与内联策略

内联在SCC(强连通分量)层次上执行，遵循自底向上的拓扑序：

```
调用图:
  main → A → B → A    (SCC: {A, B})
  main → C → D         (C, D各自独立)

处理顺序:
  1. SCC{D}: 先处理D(叶节点)
  2. SCC{C}: 处理C(可能内联D)
  3. SCC{A,B}: 处理A和B(递归组)
     - 递归函数的内联有限制(不会无限展开)
     - DevirtSCCRepeatedPass可能多次迭代

自底向上的好处:
  - 内联C→D时, D已经优化过了(有更好的InlineCost估算)
  - 内联A→B时, B的循环、常量传播已经完成
```

---

## 7.2 函数属性推断

### 7.2.1 FunctionAttrs：readnone / norecurse / willreturn

**源码**：`llvm/lib/Transforms/IPO/FunctionAttrs.cpp`（2570行）

FunctionAttrs通过分析函数体推断其属性，属性推断后可以启用更多优化：

```
推断的属性及其优化效果:

readonly  : 函数不写内存
  → 可以消除重复调用(CSE): f(x) + f(x) → 2*f(x)一次调用
  → 可以外提循环内的调用(LICM)

readnone  : 函数不读也不写内存
  → 可以消除结果未使用的调用
  → 可以任意重排调用顺序

norecurse : 函数不递归调用自身
  → 静态分析可以确定调用深度
  → 某些安全分析需要此属性

willreturn: 函数保证返回(不会无限循环)
  → 可以消除调用后的死代码
  → 保证分析的有界性

nounwind  : 函数不抛出异常
  → 可以消除异常处理的代码路径
  → 简化控制流图

noundef   : 参数/返回值不是undef/poison
  → 启用更激进的优化(如值范围推导)
```

**推断算法**：

```
对于函数F:
  readonly推断:
    如果F的所有指令都不写内存(没有store/call非readonly函数)
    → 标记F为readonly

  readnone推断:
    如果F是readonly且不读内存(没有load/call非readnone函数)
    → 标记F为readnone

  norecurse推断:
    如果F的调用图中没有环(通过CGSCC分析)
    → 标记F为norecurse
```

### 7.2.2 Attributor框架：抽象属性的不动点迭代

**源码**：`llvm/lib/Transforms/IPO/Attributor.cpp`（4177行）

Attributor是一个更强大的属性推断框架，使用不动点迭代同时推断多种属性：

```
Attributor的设计:
  AbstractAttribute (接口)
  ├── AAIsDead           : 函数/基本块是否死代码
  ├── AANoUnwind         : 是否不抛异常
  ├── AANoRecurse        : 是否不递归
  ├── AANoSync           : 是否不同步
  ├── AAWillReturn       : 是否保证返回
  ├── AAMustProgress     : 是否保证前进
  ├── AANoFree           : 是否不释放内存
  ├── AANoReturn         : 是否不返回(如abort)
  ├── AANonNull          : 参数/返回值是否非空
  ├── AANoAlias          : 参数是否不别名
  ├── AADereferenceable  : 参数是否可解引用
  └── ...更多属性

  不动点迭代:
  1. 初始化所有抽象属性为"未知"
  2. 对每个属性调用update():
     - 检查函数体, 可能将属性状态从"未知"推进到"确定"
     - 状态变化时通知依赖此属性的其他属性
  3. 重复步骤2直到没有属性状态变化(不动点)
  4. 将确定的属性附加到函数/参数上
```

---

## 7.3 全局优化与死全局消除

### 7.3.1 GlobalOpt

**源码**：`llvm/lib/Transforms/IPO/GlobalOpt.cpp`（2863行）

GlobalOpt优化全局变量的使用方式：

```
优化1: 常量全局变量的内部化
  @G = internal constant i32 42   → 所有使用点替换为i32 42

优化2: 只被一个函数使用的全局变量 → 局部变量
  @G = internal global i32 0      → 在函数内用alloca替代

优化3: 全局变量的初始化优化
  @G = global [100 x i32] zeroinitializer  → memset
  @G = global {i32, float} {i32 1, float 2.0}  → 常量折叠

优化4: 全局构造函数优化
  __cxx_global_var_init → 直接初始化(如果可能)
```

### 7.3.2 GlobalDCE / ConstantMerge

```
GlobalDCE: 删除没有使用者的全局变量/函数
  如果函数F在整个模块中没有call/rev引用 → 删除
  如果全局变量G没有被load/store引用 → 删除

ConstantMerge: 合并相同的常量全局变量
  @C1 = constant [4 x i32] [i32 1, i32 2, i32 3, i32 4]
  @C2 = constant [4 x i32] [i32 1, i32 2, i32 3, i32 4]
  → 合并为一个, @C2使用@C1
```

---

## 7.4 虚函数去虚化：WholeProgramDevirt + LowerTypeTests

### 7.4.1 类型元数据遍历与间接调用消除

**源码**：`llvm/lib/Transforms/IPO/WholeProgramDevirt.cpp`（2694行）

C++虚函数调用是性能的常见瓶颈——间接调用无法内联、无法优化。WholeProgramDevirt在LTO期间利用整个程序信息消除虚函数调用：

```
虚函数调用:
  vtable[2](obj)  →  间接调用, 目标在运行时确定

去虚化策略:
1. 单实现去虚化(Single Implementation):
   如果类型元数据表明只有一个可能的实现:
     vtable[2](obj)  →  直接调用 ConcreteClass::method()

2. 位集去虚化(Bitset):
   如果所有实现都是"轻量"的(如return 0):
     vtable[2](obj)  →  直接内联 return 0

3. 虚表布局优化:
   重新排列虚表条目, 使常用方法位于同一缓存行
```

```
Before Devirt:                      After Devirt:
  %vptr = load ptr, ptr %obj          %vptr = load ptr, ptr %obj
  %method = load ptr, ptr %vptr+16    ; eliminated
  call void %method(%obj)             call void @Shape::draw(%obj)  ; 直接调用!
```

去虚化后，间接调用变为直接调用，可以进一步内联——这往往带来10-100倍的性能提升。

---

## 7.5 函数特化(FunctionSpecialization)

**源码**：`llvm/lib/Transforms/IPO/FunctionSpecialization.cpp`（1263行）

函数特化是IPSCCP的扩展——当函数被传入不同的常量参数时，为每组常量创建专门的函数版本：

```
原始代码:
  int process(int* arr, int mode) {
    if (mode == 0) return sort(arr);
    if (mode == 1) return search(arr);
    return scan(arr);
  }
  process(data, 0);  // 调用1: mode=0
  process(data, 1);  // 调用2: mode=1

特化后:
  int process_mode0(int* arr) {     // 特化版本1
    return sort(arr);               // 死代码消除!
  }
  int process_mode1(int* arr) {     // 特化版本2
    return search(arr);             // 死代码消除!
  }
  process_mode0(data);              // 直接调用特化版本
  process_mode1(data);
```

**数据库类比**：函数特化 ≈ 参数化查询的预编译——不同参数值的查询有不同的最优执行计划，预编译为专用版本比通用计划更高效。

---

## 7.6 热冷分割与代码外提

### 7.6.1 HotColdSplitting

**源码**：`llvm/lib/Transforms/IPO/HotColdSplitting.cpp`（834行）

HotColdSplitting将函数中的冷代码（不常执行的路径，如错误处理）移到单独的函数中：

```
Before:                              After:
int parse(const char* s) {           int parse(const char* s) {
  // 热路径: 快速解析                    // 热路径: 快速解析
  if (likely(valid(s)))                  if (likely(valid(s)))
    return fast_parse(s);                  return fast_parse(s);
  // 冷路径: 错误处理                    return parse_cold(s);  // 调用冷函数
  return slow_error_handling(s);      }
}
                                      // 冷函数: 单独存放, 不污染缓存
                                      int parse_cold(const char* s) {
                                        return slow_error_handling(s);
                                      }
```

**体系结构锚点**：热冷分割的核心收益是**改善指令缓存利用率**。现代CPU的L1 I-Cache只有32-64KB，函数中混合的冷热代码会导致热路径的缓存行被冷代码占据。将冷代码移到单独的函数，热路径的代码更紧凑，缓存命中率更高。

### 7.6.2 IROutliner

IROutliner在函数间寻找相同的指令序列，将它们提取为共享函数：

```
函数A:                               函数B:
  %x = add i32 %a, %b                  %y = add i32 %c, %d
  %z = mul i32 %x, 2                   %w = mul i32 %y, 2
  ret i32 %z                           ret i32 %w

→ 提取共享函数:
  define internal i32 @outlined(i32 %p1, i32 %p2) {
    %r1 = add i32 %p1, %p2
    %r2 = mul i32 %r1, 2
    ret i32 %r2
  }
  ; A和B都调用 outlined()
```

**数据库类比**：IROutliner ≈ 共享子表达式提取——多个查询中的相同计算只执行一次。

---

## 7.7 本章小结

本章跨越函数边界，理解了6组过程间优化：

1. **内联决策**：InlineCost代价估算、默认阈值策略和ML驱动策略的对比、SCC遍历顺序的影响。
2. **函数属性推断**：从简单的FunctionAttrs到不动点迭代的Attributor框架，属性推断为后续优化打开空间。
3. **全局优化**：GlobalOpt的全局变量局部化、GlobalDCE的死全局消除、ConstantMerge的常量合并。
4. **去虚化**：WholeProgramDevirt利用全程序信息将虚函数调用变为直接调用，是C++性能优化的关键。
5. **函数特化**：为不同常量参数创建专用版本，消除通用代码中的条件分支。
6. **热冷分割与代码外提**：HotColdSplitting改善指令缓存，IROutliner减少代码重复。

下一章进入自动向量化——从标量到SIMD的编译器魔法。
