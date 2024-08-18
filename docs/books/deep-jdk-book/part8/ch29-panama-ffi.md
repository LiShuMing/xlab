# 第 29 章 Foreign Function & Memory API（Panama）

> 源码路径：`src/java.base/share/classes/java/lang/foreign/`、`src/hotspot/share/prims/foreignGlobals.cpp`、`src/hotspot/share/prims/downcallLinker.cpp`、`src/hotspot/share/prims/upcallLinker.cpp`

Panama 是 JDK 22 正式发布的 Foreign Function & Memory API（FFM API），替代了 JNI 和 `sun.misc.Unsafe`。它提供了类型安全、低开销的外部函数调用和内存访问能力，是 Java 在 AI 推理领域与 GPU/NPU 交互的关键基础设施。本章深入 Panama 的 HotSpot 实现。

---

## 29.1 `scopedMemoryAccess / foreignGlobals`：外部内存访问

### 29.1.1 MemorySegment 与 Arena

```java
// Panama 的核心抽象
try (Arena arena = Arena.ofConfined()) {
    // 分配 100MB 的原生内存
    MemorySegment segment = arena.allocate(100 * 1024 * 1024, 8);

    // 写入数据
    segment.set(ValueLayout.JAVA_INT, 0, 42);
    segment.set(ValueLayout.JAVA_FLOAT, 4, 3.14f);

    // 读取数据
    int i = segment.get(ValueLayout.JAVA_INT, 0);

} // arena 关闭时自动释放所有关联的内存
```

### 29.1.2 Arena 的生命周期管理

```
Arena 类型：
  Arena.ofConfined()    → 单线程访问，arena 关闭时释放
  Arena.ofShared()      → 多线程访问，arena 关闭时释放
  Arena.ofAuto()        → 由 Cleaner 自动释放
  Arena.ofLimited()     → 不允许扩展的受限 arena
  Arena.global()        → 全局 arena，永不关闭

生命周期保证：
  - MemorySegment 绑定到 Arena
  - Arena 关闭后，所有关联的 MemorySegment 变为不可访问
  - 任何访问操作抛出 IllegalStateException
  - 这比 DirectByteBuffer 的 Cleaner 机制更可靠
```

### 29.1.3 foreignGlobals 的 HotSpot 实现

```cpp
// foreignGlobals.cpp
// Panama 在 HotSpot 中的全局状态管理
class ForeignGlobals {
    // ABI 相关的全局信息
    static const ABIDescriptor* _abi_descriptor;

    // 调用约定
    static const CallConv* _call_conv;

    // VMStorage 映射
    static VMStorage to_vm_storage(Register reg);
    static VMStorage to_vm_storage(XMMRegister reg);
};
```

---

## 29.2 `downcallLinker / upcallLinker`：跨语言调用

### 29.2.1 Downcall（Java → Native）

Downcall 是 Java 调用外部函数的过程：

```java
Linker linker = Linker.nativeLinker();

// 查找外部函数
SymbolLookup lookup = SymbolLookup.libraryLookup("libcrypto.so", Arena.ofAuto());
MemorySegment func = lookup.find("EVP_EncryptInit").orElseThrow();

// 创建 downcall 方法句柄
MethodHandle encrypt = linker.downcallHandle(
    func,
    FunctionDescriptor.of(
        ValueLayout.JAVA_INT,            // 返回值
        ValueLayout.ADDRESS,             // ctx
        ValueLayout.ADDRESS,             // cipher
        ValueLayout.ADDRESS,             // engine
        ValueLayout.ADDRESS,             // key
        ValueLayout.ADDRESS              // iv
    )
);

int result = (int) encrypt.invokeExact(ctx, cipher, engine, key, iv);
```

### 29.2.2 Downcall 的 HotSpot 实现

```cpp
// downcallLinker.cpp
// Panama 生成一个专门的 stub 代码来执行 downcall：
//
// 1. 从 Java 参数提取值
// 2. 按照 C ABI 放入正确的寄存器/栈位置
// 3. 调用目标函数
// 4. 将返回值转换为 Java 类型
// 5. 处理异常（如果有）

address DowncallLinker::generate_stub(FunctionDescriptor* fd) {
    // 生成机器码 stub
    // - 保存 callee-saved 寄存器
    // - 按照 ABI 布局参数
    // - call 目标地址
    // - 提取返回值
    // - 恢复寄存器
    // - 返回
}
```

### 29.2.3 Upcall（Native → Java）

Upcall 是外部函数回调 Java 代码的过程：

```java
// 创建 Java 回调的方法句柄
MethodHandle callback = MethodHandles.lookup().findStatic(
    MyHandler.class, "onData",
    MethodType.methodType(void.class, int.class, MemorySegment.class));

// 创建 upcall stub
MemorySegment upcallStub = linker.upcallStub(
    callback,
    FunctionDescriptor.ofVoid(
        ValueLayout.JAVA_INT,
        ValueLayout.ADDRESS),
    Arena.ofAuto());

// 将 upcallStub 传递给 C 函数作为函数指针
```

### 29.2.4 Upcall 的 HotSpot 实现

```cpp
// upcallLinker.cpp
// Panama 生成一个专门的 stub 代码来接收 upcall：
//
// 1. 从 C ABI 寄存器/栈位置提取参数
// 2. 转换为 Java 类型的参数
// 3. 通过 JNI 调用 Java 方法
// 4. 将 Java 返回值转换为 C ABI 格式
// 5. 返回给 C 调用者

address UpcallLinker::generate_upcall_stub(MethodHandle mh, BasicType* ret_type) {
    // 生成机器码 stub
    // - 保存 C ABI 的 callee-saved 寄存器
    // - 从寄存器/栈提取参数
    // - 构造 Java 参数数组
    // - 调用 Java 方法
    // - 提取返回值
    // - 恢复寄存器
    // - 返回
}
```

---

## 29.3 `nativeEntryPoint / vmstorage`：ABI 级别的桥接

### 29.3.1 VMStorage

`VMStorage` 是 Panama 对 ABI 位置（寄存器、栈槽）的抽象：

```java
// VMStorage 标识参数/返回值的存储位置
public final class VMStorage {
    final int type;     // REGISTER, STACK, X87, ...
    final int index;    // 寄存器号或栈偏移
    final short size;   // 大小（字节）
}
```

### 29.3.2 x86_64 的调用约定映射

```
C ABI (System V AMD64) → VMStorage 映射：

整数参数：
  rdi → VMStorage(REGISTER, RDI)
  rsi → VMStorage(REGISTER, RSI)
  rdx → VMStorage(REGISTER, RDX)
  rcx → VMStorage(REGISTER, RCX)

浮点参数：
  xmm0 → VMStorage(REGISTER, XMM0)
  xmm1 → VMStorage(REGISTER, XMM1)
  ...

返回值：
  rax → VMStorage(REGISTER, RAX)    // 整数返回
  xmm0 → VMStorage(REGISTER, XMM0)  // 浮点返回
```

### 29.3.3 NativeEntryPoint

`NativeEntryPoint` 描述了外部函数的入口点信息：

```java
public final class NativeEntryPoint {
    final long entry_point;           // 函数地址
    final MethodType method_type;     // Java 方法签名
    final FunctionDescriptor desc;    // C 函数签名
    final boolean needs_transition;   // 是否需要线程状态转换
}
```

---

## 29.4 [专题] Panama 调用 CUDA / ONNX Runtime 执行推理

### 29.4.1 调用 ONNX Runtime

```java
// 使用 Panama 调用 ONNX Runtime C API
Linker linker = Linker.nativeLinker();
SymbolLookup onnx = SymbolLookup.libraryLookup("libonnxruntime.so", Arena.ofAuto());

// OcrSessionOptionsCreate
MethodHandle createSessionOpts = linker.downcallHandle(
    onnx.find("OcrSessionOptionsCreate").orElseThrow(),
    FunctionDescriptor.of(ValueLayout.JAVA_INT, ValueLayout.ADDRESS));

// OcrRun
MethodHandle run = linker.downcallHandle(
    onnx.find("OcrRun").orElseThrow(),
    FunctionDescriptor.of(
        ValueLayout.JAVA_INT,            // Status
        ValueLayout.ADDRESS,             // Session
        ValueLayout.ADDRESS,             // RunOptions
        ValueLayout.ADDRESS,             // Input names
        ValueLayout.ADDRESS,             // Input values
        ValueLayout.JAVA_LONG,           // Input count
        ValueLayout.ADDRESS,             // Output names
        ValueLayout.JAVA_LONG,           // Output count
        ValueLayout.ADDRESS              // Output values
    ));
```

### 29.4.2 调用 CUDA Runtime

```java
// Panama 调用 CUDA
SymbolLookup cuda = SymbolLookup.libraryLookup("libcudart.so", Arena.ofAuto());

// cudaMalloc
MethodHandle cudaMalloc = linker.downcallHandle(
    cuda.find("cudaMalloc").orElseThrow(),
    FunctionDescriptor.of(
        ValueLayout.JAVA_INT,            // cudaError_t
        ValueLayout.ADDRESS,             // void** devPtr
        ValueLayout.JAVA_LONG));         // size_t size

// cudaMemcpy (Host → Device)
MethodHandle cudaMemcpyH2D = linker.downcallHandle(
    cuda.find("cudaMemcpy").orElseThrow(),
    FunctionDescriptor.of(
        ValueLayout.JAVA_INT,            // cudaError_t
        ValueLayout.ADDRESS,             // void* dst (device)
        ValueLayout.ADDRESS,             // void* src (host)
        ValueLayout.JAVA_LONG,           // size_t count
        ValueLayout.JAVA_INT));          // cudaMemcpyKind

// cudaLaunchKernel
MethodHandle cudaLaunch = linker.downcallHandle(
    cuda.find("cudaLaunchKernel").orElseThrow(),
    FunctionDescriptor.of(
        ValueLayout.JAVA_INT,            // cudaError_t
        ValueLayout.ADDRESS,             // const void* func
        ValueLayout.ADDRESS,             // dim3 gridDim
        ValueLayout.ADDRESS,             // dim3 blockDim
        ValueLayout.ADDRESS,             // void** args
        ValueLayout.JAVA_LONG,           // size_t sharedMem
        ValueLayout.JAVA_LONG));         // cudaStream_t stream
```

### 29.4.3 Panama vs JNI 的性能对比

```
调用开销对比（空函数调用）：

JNI:          ~15-30ns
Panama:       ~5-10ns
Java 方法:    ~5ns

Panama 更快的原因：
1. 直接生成调用 stub，无需 JNI 函数表查找
2. 无 JNI 句柄管理开销
3. 无线程状态转换（可选 needs_transition=false）
4. 参数直接按 ABI 布局，无需类型转换
```

---

## 小结

本章深入了 Panama FFM API 的实现：

1. **MemorySegment + Arena** 提供了比 DirectByteBuffer 更安全、更可控的原生内存管理
2. **Downcall** 生成专用的机器码 stub，调用开销比 JNI 低 2-3 倍
3. **Upcall** 允许 C 代码回调 Java 方法，无需手写 JNI 包装
4. **VMStorage** 抽象了跨架构的 ABI 位置，支持 x86_64、AArch64、RISC-V
5. **Panama 调用 CUDA/ONNX Runtime** 为 Java 推理服务提供了直接访问 GPU 的路径

下一章将深入 Vector API 与 SIMD 计算。
