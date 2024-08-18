# 附录 E：x86 / AArch64 指令速查（JVM 常用指令子集）

## E.1 x86_64 常用指令

### E.1.1 数据移动

| 指令 | 格式 | 说明 | JVM 使用 |
|------|------|------|---------|
| `mov` | `mov rax, rbx` | 数据移动 | 字段访问、参数传递 |
| `movzx` | `movzx rax, bl` | 零扩展移动 | 字节码操作码读取 |
| `lea` | `lea rax, [rbx+rcx*4+16]` | 地址计算 | 数组元素寻址 |
| `xchg` | `xchg rax, [addr]` | 原子交换 | 锁实现 |
| `cmpxchg` | `lock cmpxchg [addr], rax` | 原子 CAS | 轻量级锁、并发原语 |

### E.1.2 算术运算

| 指令 | 格式 | 说明 | JVM 使用 |
|------|------|------|---------|
| `add` | `add rax, rbx` | 加法 | 整数运算 |
| `sub` | `sub rax, rbx` | 减法 | 整数运算 |
| `imul` | `imul rax, rbx` | 有符号乘法 | 整数乘法 |
| `idiv` | `idiv rbx` | 有符号除法 | 整数除法（慢，C2 尝试强度削减） |
| `inc` | `inc rax` | 加 1 | 循环计数器 |
| `neg` | `neg rax` | 取反 | 取反运算 |
| `shl / shr` | `shl rax, 3` | 移位 | 乘除优化（2 的幂） |

### E.1.3 浮点运算

| 指令 | 格式 | 说明 | JVM 使用 |
|------|------|------|---------|
| `addss / addps` | `addps xmm0, xmm1` | 浮点加法（标量/向量） | float 运算 |
| `addsd / addpd` | `addpd xmm0, xmm1` | 双精度加法（标量/向量） | double 运算 |
| `mulss / mulps` | `mulps xmm0, xmm1` | 浮点乘法 | float 乘法 |
| `vfmadd` | `vfmadd231ps xmm0,xmm1,xmm2` | 融合乘加 | Vector API FMA |
| `cvtsi2ss` | `cvtsi2ss xmm0, eax` | 整数→浮点转换 | 类型转换 |
| `cvttss2si` | `cvttss2si eax, xmm0` | 浮点→整数转换（截断） | 类型转换 |

### E.1.4 分支与控制流

| 指令 | 格式 | 说明 | JVM 使用 |
|------|------|------|---------|
| `cmp` | `cmp rax, rbx` | 比较 | 条件判断 |
| `test` | `test rax, rax` | 测试零 | null 检查 |
| `je / jne` | `je label` | 相等/不等跳转 | if 条件 |
| `jl / jg` | `jl label` | 小于/大于跳转 | 比较分支 |
| `jmp` | `jmp [table + rbx*8]` | 间接跳转 | 解释器 dispatch |
| `call / ret` | `call func` | 函数调用/返回 | 方法调用 |
| `pause` | `pause` | 自旋等待提示 | 自适应自旋锁 |

### E.1.5 内存屏障

| 指令 | 格式 | 说明 | JVM 使用 |
|------|------|------|---------|
| `mfence` | `mfence` | 全内存屏障 | volatile 写后（StoreLoad） |
| `sfence` | `sfence` | 写屏障 | StoreStore 屏障 |
| `lfence` | `lfence` | 读屏障 | LoadLoad 屏障（x86 不需要） |
| `lock addl` | `lock addl $0, [rsp]` | 锁前缀（等效 mfence） | volatile 写后（替代 mfence） |

### E.1.6 SIMD 向量指令（AVX2）

| 指令 | 格式 | 说明 | JVM 使用 |
|------|------|------|---------|
| `vmovdqa` | `vmovdqa ymm0, [addr]` | 对齐向量加载 | Vector API 加载 |
| `vpaddd` | `vpaddd ymm0, ymm1, ymm2` | 8×int 加法 | IntVector.add() |
| `vaddps` | `vaddps ymm0, ymm1, ymm2` | 8×float 加法 | FloatVector.add() |
| `vmulps` | `vmulps ymm0, ymm1, ymm2` | 8×float 乘法 | FloatVector.mul() |
| `vfmadd231ps` | `vfmadd231ps ymm0, ymm1, ymm2` | 8×float FMA | FloatVector.fma() |
| `vgatherdps` | `vgatherdps ymm0, [base + index]` | 向量 gather | scatter/gather 操作 |

---

## E.2 AArch64 常用指令

### E.2.1 数据移动与算术

| 指令 | 格式 | 说明 | JVM 使用 |
|------|------|------|---------|
| `mov` | `mov x0, x1` | 数据移动 | 字段访问 |
| `add` | `add x0, x1, x2` | 加法 | 整数运算 |
| `sub` | `sub x0, x1, x2` | 减法 | 整数运算 |
| `madd` | `madd x0, x1, x2, x3` | 乘加 | 乘法优化 |
| `sdiv / udiv` | `sdiv x0, x1, x2` | 除法 | 整数除法 |

### E.2.2 浮点与向量（NEON/SVE）

| 指令 | 格式 | 说明 | JVM 使用 |
|------|------|------|---------|
| `fadd` | `fadd v0.4s, v1.4s, v2.4s` | 4×float 加法 | FloatVector.add() |
| `fmul` | `fmul v0.4s, v1.4s, v2.4s` | 4×float 乘法 | FloatVector.mul() |
| `fmla` | `fmla v0.4s, v1.4s, v2.4s` | 4×float FMA | FloatVector.fma() |
| `scvtf` | `scvtf v0.4s, v1.4s` | int→float 转换 | 类型转换 |

### E.2.3 内存屏障

| 指令 | 格式 | 说明 | JVM 使用 |
|------|------|------|---------|
| `dmb ish` | `dmb ish` | 内共享域数据屏障 | volatile 屏障 |
| `dsb ish` | `dsb ish` | 内共享域数据同步 | StoreStore 屏障 |
| `isb` | `isb` | 指令同步屏障 | 流水线刷新 |

### E.2.4 原子操作

| 指令 | 格式 | 说明 | JVM 使用 |
|------|------|------|---------|
| `ldaxr` | `ldaxr x0, [x1]` | 独占加载（带获取语义） | LL/SC 实现 CAS |
| `stlxr` | `stlxr w0, x2, [x1]` | 独占存储（带释放语义） | LL/SC 实现 CAS |
| `ldaddal` | `ldaddal x0, x1, [x2]` | 原子加（LSE） | LongAdder |

---

## E.3 RISC-V 常用指令（V 扩展）

| 指令 | 格式 | 说明 | JVM 使用 |
|------|------|------|---------|
| `vsetvli` | `vsetvli x0, x1, e32, m1` | 设置向量长度 | 向量操作前配置 |
| `vle32.v` | `vle32.v v0, (x1)` | 向量加载 | Vector API 加载 |
| `vfadd.vv` | `vfadd.vv v0, v1, v2` | 向量浮点加法 | FloatVector.add() |
| `vfmul.vv` | `vfmul.vv v0, v1, v2` | 向量浮点乘法 | FloatVector.mul() |
| `vfmacc.vv` | `vfmacc.vv v0, v1, v2` | 向量 FMA | FloatVector.fma() |
