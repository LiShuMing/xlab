# 第 21 章 `java.lang.invoke`：方法句柄与 Lambda

> 源码路径：`src/java.base/share/classes/java/lang/invoke/`、`src/hotspot/share/interpreter/interpreterRuntime.cpp`、`src/hotspot/share/prims/methodHandles.cpp`

`java.lang.invoke` 包是 Java 语言动态性的底层支撑——`invokedynamic` 指令、Lambda 表达式、方法句柄都依赖它。本章从 `MethodHandle` 到 `LambdaForm`，再到 `invokedynamic` 的完整链路，深入动态调用的 HotSpot 实现。

---

## 21.1 `MethodHandle` 体系与 `invokeExact` 的字节码生成

### 21.1.1 MethodHandle 的类型体系

```java
// MethodHandle 类型层次
MethodHandle (抽象)
├── DirectMethodHandle       // 直接方法句柄（invokevirtual/invokestatic 等）
├── BoundMethodHandle        // 绑定了接收者的方法句柄
├── AdapterMethodHandle      // 参数适配
└── WrapperMethodHandle      // 类型转换包装
```

### 21.1.2 invokeExact vs invoke

```java
MethodHandle mh = ...;

// invokeExact：精确类型匹配，无适配开销
mh.invokeExact(arg1, arg2);  // 方法签名必须完全匹配

// invoke：自动类型转换
mh.invoke(arg1, arg2);       // 自动进行参数适配
```

`invokeExact` 的字节码生成：

```
invokedynamic #bootstrap_method
→ 生成一个 Invokers.checkCustomized 调用点
→ 返回一个直接调用目标方法的 MethodHandle

编译后的字节码使用 invokevirtual 调用 MethodHandle.invokeExact
HotSpot 在解析时识别 MethodHandle 调用，生成优化的调用序列
```

### 21.1.3 MethodHandle 的 HotSpot 优化

HotSpot 对 `MethodHandle.invokeExact` 有特殊处理——不是通过反射调用，而是直接跳转到目标方法：

```cpp
// methodHandles.cpp
// 当 JIT 编译器遇到 MethodHandle 调用时
// 通过 MemberName 直接链接到目标方法
// 类似于内联缓存（Inline Cache）的效果
```

---

## 21.2 `LambdaForm / LambdaFormEditor`：Lambda 形式优化

### 21.2.1 LambdaForm

`LambdaForm` 是 MethodHandle 的内部表示——一种简单的 SSA 中间表示：

```java
// LambdaForm.java（简化）
class LambdaForm {
    Name[] names;       // 参数和操作
    int[]  types;       // 每个参数的类型
    Name   result;      // 结果

    // 示例：x + y 的 LambdaForm
    // names = [x, y, DMT_2_plus_I_I(x, y)]
    // result = names[2]
}
```

### 21.2.2 LambdaFormEditor

`LambdaFormEditor` 负责优化 LambdaForm——合并、简化、特化：

```java
// LambdaFormEditor.java
// 优化操作：
// 1. 常量折叠：如果参数是常量，在编译期计算
// 2. 死代码消除：移除未使用的参数
// 3. 合并：将多个连续操作合并为一个
// 4. 特化：根据参数类型生成更高效的代码
```

---

## 21.3 `InnerClassLambdaMetafactory`：Lambda 的内部类生成

### 21.3.1 Lambda 的编译

Java Lambda 表达式在编译时使用 `invokedynamic` 指令：

```java
// Java 代码
Runnable r = () -> System.out.println("hello");

// 编译后的字节码
invokedynamic #0:run:()Ljava/lang/Runnable;
BootstrapMethods:
  0: LambdaMetafactory.metafactory
     Method arguments:
       ()void
       lambda$main$0()  // 编译器生成的方法
       ()Runnable
```

### 21.3.2 内部类生成

`InnerClassLambdaMetafactory` 在运行时生成一个内部类：

```java
// 运行时生成的类（类似）
final class Main$$Lambda$1 implements Runnable {
    public void run() {
        Main.lambda$main$0();  // 调用编译器生成的方法
    }
}
```

生成过程使用 ASM 字节码库：

```
1. LambdaMetafactory.metafactory() 被调用
2. InnerClassLambdaMetafactory 生成字节码
3. 使用 Unsafe.defineClass() 加载生成的类
4. 返回生成的类的实例
```

### 21.3.3 捕获变量的 Lambda

```java
// 捕获变量 x
int x = 42;
IntSupplier s = () -> x;

// 生成的内部类
final class Main$$Lambda$1 implements IntSupplier {
    private final int arg$1;  // 捕获的 x

    Main$$Lambda$1(int x) {
        this.arg$1 = x;
    }

    public int getAsInt() {
        return this.arg$1;  // 返回捕获的 x
    }
}
```

---

## 21.4 `InvokerBytecodeGenerator`：方法句柄的字节码生成

### 21.4.1 字节码生成流程

`InvokerBytecodeGenerator` 将 LambdaForm 编译为字节码：

```
LambdaForm → 遍历 names 数组 → 生成对应的字节码指令

示例：x + y 的 LambdaForm
  names[0] = x (I)
  names[1] = y (I)
  names[2] = DMT_2_plus_I_I(x, y)

生成字节码：
  aload_1        // 加载 x
  aload_2        // 加载 y
  iadd           // 相加
  ireturn        // 返回
```

### 21.4.2 生成的方法名

```
生成的类名格式：
  java.lang.invoke.Invokers$Holder
  java.lang.invoke.LambdaForm$Holder
  java.lang.invoke.DirectMethodHandle$Holder

方法名格式：
  invokeExact_MT-<methodType>
  invoke_MT-<methodType>
  linkToTargetMethod_<signature>
```

---

## 21.5 `VarHandle`：变量句柄与内存访问模式

### 21.5.1 VarHandle 的功能

`VarHandle` 是 JDK 9 引入的变量句柄，提供对字段、数组元素的细粒度内存访问：

```java
VarHandle vh = MethodHandles.lookup().findVarHandle(
    MyClass.class, "field", int.class);

// 不同访问模式
vh.set(obj, 42);                // 普通写
vh.setVolatile(obj, 42);        // volatile 写
vh.setOpaque(obj, 42);          // opaque 写（无 StoreLoad）
vh.setRelease(obj, 42);         // release 写（StoreStore）
vh.compareAndSet(obj, 41, 42);  // CAS
vh.getAndAdd(obj, 1);           // 原子加
```

### 21.5.2 内存访问模式

| 模式 | 语义 | 屏障 |
|------|------|------|
| Plain | 普通读写 | 无 |
| Opaque | 保证可见性，不保证顺序 | LoadLoad + StoreStore |
| Release | 写后保证前面的写可见 | StoreStore |
| Acquire | 读后保证后面的读/写有序 | LoadLoad + LoadStore |
| Volatile | 完全的可见性和顺序保证 | 全屏障 |

### 21.5.3 VarHandle 的 HotSpot 实现

VarHandle 的 CAS 和原子操作直接映射到 HotSpot 的 `Unsafe` 方法：

```
VarHandle.compareAndSet()
  → VarHandleGuards.guard_LII_Z
    → Unsafe.compareAndSetInt()
      → AtomicAccess::cmpxchg()  // HotSpot C++ 层
        → lock cmpxchg           // x86 指令
```

---

## 21.6 [专题] `invokedynamic` 从 class 文件到 HotSpot 的完整链路

### 21.6.1 invokedynamic 的完整流程

```
1. 编译器生成 invokedynamic 指令
   invokedynamic #bootstrap_method_ref, #name_and_type

2. 首次执行时，HotSpot 调用 Bootstrap Method
   → 传入 MethodHandles.Lookup, 方法名, MethodType, 额外参数
   → 返回 CallSite（包含 MethodHandle）

3. CallSite 被链接到调用点
   → 后续调用直接使用 MethodHandle

4. ConstantCallSite：永久链接
   MutableCallSite：可以改变目标
   VolatileCallSite：可以改变目标，volatile 语义
```

### 21.6.2 Lambda 的 invokedynamic 链路

```
Java: () -> foo()

编译：invokedynamic #lambda$bootstrap

首次执行：
1. 解释器遇到 invokedynamic
2. 调用 LambdaMetafactory.metafactory()
3. metafactory 生成内部类字节码
4. 加载内部类，创建实例
5. 返回 ConstantCallSite（持有内部类的 MethodHandle）

后续执行：
1. 直接调用已链接的 MethodHandle
2. JIT 编译后，可能内联 Lambda 方法体
```

---

## 小结

本章深入了 `java.lang.invoke` 包的核心机制：

1. **MethodHandle** 是类型安全的动态调用机制，`invokeExact` 在 HotSpot 中被特殊优化
2. **LambdaForm** 是 MethodHandle 的 SSA 中间表示，可被优化和编译
3. **Lambda 表达式**通过 `invokedynamic` + `LambdaMetafactory` 在运行时生成内部类
4. **VarHandle** 提供了比 `volatile` 更细粒度的内存访问控制
5. **invokedynamic** 的完整链路从 Bootstrap Method 到 CallSite 链接，是 Java 动态性的核心

下一章将深入 `java.util.concurrent` 并发框架。
