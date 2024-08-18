# 附录C opt/llc/mlir-opt实战手册

## 按Pass分类的常用命令

### 标量优化

```bash
# 死代码消除
opt -S -passes=dce input.ll -o output.ll
opt -S -passes=adce input.ll -o output.ll
opt -S -passes=bdce input.ll -o output.ll

# 公共子表达式消除
opt -S -passes=early-cse input.ll -o output.ll
opt -S -passes=gvn input.ll -o output.ll
opt -S -passes=newgvn input.ll -o output.ll

# 循环优化
opt -S -passes=licm input.ll -o output.ll
opt -S -passes=indvars input.ll -o output.ll
opt -S -passes=loop-unroll input.ll -o output.ll
opt -S -passes=loop-rotate input.ll -o output.ll
opt -S -passes=loop-strength-reduce input.ll -o output.ll

# SROA / SCCP / CFG
opt -S -passes=sroa input.ll -o output.ll
opt -S -passes=sccp input.ll -o output.ll
opt -S -passes=simplifycfg input.ll -o output.ll
opt -S -passes=jump-threading input.ll -o output.ll
```

### 过程间优化

```bash
opt -S -passes=inline input.ll -o output.ll
opt -S -passes=globalopt input.ll -o output.ll
opt -S -passes=globaldce input.ll -o output.ll
opt -S -passes=function-attrs input.ll -o output.ll
opt -S -passes=wholeprogramdevirt input.ll -o output.ll
```

### 向量化

```bash
opt -S -passes=loop-vectorize input.ll -o output.ll
opt -S -passes=slp-vectorizer input.ll -o output.ll
opt -S -passes=vector-combine input.ll -o output.ll
```

### InstCombine

```bash
opt -S -passes=instcombine input.ll -o output.ll
```

### 完整优化流水线

```bash
opt -S -O0 input.ll -o output.ll
opt -S -O1 input.ll -o output.ll
opt -S -O2 input.ll -o output.ll
opt -S -O3 input.ll -o output.ll
opt -S -Os input.ll -o output.ll
opt -S -Oz input.ll -o output.ll
```

## 调试选项

```bash
# Pass级可观测性
opt -S -O2 -print-after-all input.ll 2>pipeline.txt
opt -S -O2 -print-before=licm -print-after=licm input.ll
opt -S -O2 -print-before-all input.ll 2>before_all.txt

# 特定Pass调试(需要assertion构建)
opt -S -O2 -debug-only=licm input.ll 2>licm_debug.txt
opt -S -O2 -debug-only=instcombine input.ll 2>ic_debug.txt
opt -S -O2 -debug-only=gvn input.ll 2>gvn_debug.txt
opt -S -O2 -debug-only=loop-vectorize input.ll 2>vec_debug.txt

# 统计信息
opt -S -O2 -stats input.ll 2>&1 | head -50

# 验证
opt -S -O2 -verify-each input.ll -o output.ll

# 后端调试
llc -debug-only=isel input.ll 2>isel_debug.txt
llc -debug-only=regalloc input.ll 2>regalloc_debug.txt
llc -debug-only=pre-RA-sched input.ll 2>sched_debug.txt
llc -print-after-all input.ll 2>backend_all.txt

# 机器码性能分析
llvm-mca -mcpu=skylake input.s
llvm-mca -mcpu=cortex-a78 input.s
```

## 分析结果dump方法

```bash
# 支配树
opt -passes='print<domtree>' input.ll -disable-output 2>domtree.txt

# 循环信息
opt -passes='print<loops>' input.ll -disable-output 2>loops.txt

# SCEV分析
opt -passes='print<scalar-evolution>' input.ll -disable-output 2>scev.txt

# 别名分析
opt -passes='print<aa>' input.ll -disable-output 2>aa.txt

# MemorySSA
opt -passes='print<memoryssa>' input.ll -disable-output 2>mssa.txt

# 调用图
opt -passes='print<callgraph>' input.ll -disable-output 2>cg.txt

# 分支概率
opt -passes='print<block-freq>' input.ll -disable-output 2>bfi.txt

# 依赖分析
opt -passes='print<da>' input.ll -disable-output 2>da.txt
```

## mlir-opt实战

```bash
# 基本运行
mlir-opt input.mlir -o output.mlir

# 方言转换
mlir-opt --convert-linalg-to-loops input.mlir -o output.mlir
mlir-opt --convert-scf-to-cf input.mlir -o output.mlir
mlir-opt --convert-cf-to-llvm input.mlir -o output.mlir
mlir-opt --convert-func-to-llvm input.mlir -o output.mlir
mlir-opt --convert-arith-to-llvm input.mlir -o output.mlir
mlir-opt --convert-vector-to-llvm input.mlir -o output.mlir
mlir-opt --convert-memref-to-llvm input.mlir -o output.mlir

# 优化Pass
mlir-opt --canonicalize input.mlir -o output.mlir
mlir-opt --cse input.mlir -o output.mlir
mlir-opt --linalg-fuse-input-operands input.mlir -o output.mlir

# 验证
mlir-opt --verify-diagnostics input.mlir

# 转换到LLVM IR
mlir-translate --mlir-to-llvmir output.mlir -o output.ll
```
