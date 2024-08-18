# 第 24 章 JNI：Java 与 Native 的桥梁

> 源码路径：`src/hotspot/share/prims/jni.cpp`、`src/hotspot/share/runtime/jniHandles.cpp`、`src/hotspot/share/prims/jniFastGetField.cpp`、`src/hotspot/share/prims/nativeLookup.cpp`

JNI（Java Native Interface）是 Java 与 C/C++ 代码交互的标准接口。它是 Java 与操作系统、硬件设备、高性能库（如 CUDA、ONNX Runtime）之间的桥梁。本章从 JNI 函数表出发，追踪引用管理、字段访问和符号解析的完整链路。

---

## 24.1 `prims/jni.cpp`：JNI 函数表与实现

### 24.1.1 JNI 函数表

JNI 函数表是一个巨大的函数指针数组，每个 JNI 函数对应一个条目：

```cpp
// jni.cpp
static const struct JNINativeInterface jni_NativeInterface = {
    NULL,                       // reserved0
    NULL,                       // reserved1
    NULL,                       // reserved2
    NULL,                       // reserved3

    // 版本和类操作
    JNI_GetVersion,
    JNI_DefineClass,
    JNI_FindClass,

    // 对象操作
    JNI_AllocObject,
    JNI_NewObject,
    JNI_NewObjectV,
    JNI_NewObjectA,

    // 方法调用
    JNI_CallObjectMethod,
    JNI_CallVoidMethod,
    // ... 200+ 函数

    // 字段访问
    JNI_GetFieldID,
    JNI_GetIntField,
    JNI_SetIntField,
    // ...

    // 数组操作
    JNI_GetIntArrayElements,
    JNI_ReleaseIntArrayElements,
    // ...
};
```

### 24.1.2 JNI 调用的开销

```
JNI 调用的开销来源：
1. 从 JNI 函数表查找函数指针：~2ns
2. 参数类型转换（jint → int, jobject → oop）：~5ns
3. JNI 句柄解析（jobject → oop）：~5ns
4. 安全检查（访问权限、空指针）：~5ns

总计：~15-30ns/次（不含实际 native 代码执行）

对比：
  Java 方法调用：~5-10ns
  JNI 调用开销是 Java 调用的 3-5 倍
```

### 24.1.3 JNI 临界区（Critical Region）

`GetPrimitiveArrayCritical` / `GetStringCritical` 提供对原生数据的直接指针访问，但会禁用 GC：

```cpp
// jni.cpp
jint* JNICALL JNI_GetIntArrayElements(JNIEnv *env, jintArray array, jboolean *isCopy) {
    // 1. 获取数组对象的底层 C 数组指针
    // 2. 如果数组在堆中不是连续的（如压缩 oop），需要复制
    // 3. 返回指针
}

jint* JNICALL JNI_GetPrimitiveArrayCritical(JNIEnv *env, jintArray array, jboolean *isCopy) {
    // 1. 禁止 GC（进入临界区）
    // 2. 返回直接指针（不复制）
    // 3. 调用者必须在 ReleasePrimitiveArrayCritical 之前完成操作
    // 4. 临界区内不能调用任何可能阻塞的 JNI 函数
}
```

---

## 24.2 `jniHandles`：全局/局部引用管理

### 24.2.1 JNI 引用的类型

| 引用类型 | 创建 | 生命周期 | GC 行为 |
|---------|------|---------|---------|
| 局部引用 | 默认创建 | 一次 native 调用 | 调用返回后自动释放 |
| 全局引用 | `NewGlobalRef` | 手动 `DeleteGlobalRef` | 阻止对象回收 |
| 弱全局引用 | `NewWeakGlobalRef` | 手动 `DeleteWeakGlobalRef` | 不阻止回收 |

### 24.2.2 局部引用的管理

局部引用存储在 `JNIHandleBlock` 中：

```cpp
// jniHandles.hpp
class JNIHandleBlock {
    oop          _handles[block_size];  // oop 引用数组
    JNIHandleBlock* _next;              // 链表
    int          _top;                  // 当前使用位置
};
```

每个 JavaThread 有自己的 `JNIHandleBlock` 链表。native 方法返回时，当前 `JNIHandleBlock` 的 `_top` 被重置，所有局部引用自动释放。

### 24.2.3 全局引用的管理

全局引用存储在全局的 `JNIHandleBlock` 链表中：

```cpp
// jniHandles.cpp
jobject JNIHandles::make_global(oop obj) {
    // 在全局 handle block 中分配一个槽位
    // 返回槽位的地址作为 jobject
    return _global_handles->allocate_handle(obj);
}

void JNIHandles::destroy_global(jobject handle) {
    // 将槽位置为 NULL，允许 GC 回收对象
    *handle = NULL;
}
```

**全局引用泄漏**是 JNI 最常见的内存泄漏——如果忘记调用 `DeleteGlobalRef`，对象永远不会被 GC 回收。

---

## 24.3 `jniFastGetField`：快速字段访问

### 24.3.1 快速路径

HotSpot 为常见的字段访问提供了优化路径，避免 JNI 函数表查找：

```cpp
// jniFastGetField.cpp
// 为 int/long/float/double/object 字段生成快速访问代码
// 直接从对象偏移量读取值，不走 JNI 函数表

address JNI_FastGetField::generate_fast_get_int_field() {
    // 生成机器码：
    // 1. 从 jobject 解析出 oop
    // 2. 加上字段偏移量
    // 3. 直接读取值
    // 4. 返回

    // 如果 GC 正在进行（safepoint），回退到慢速路径
}
```

### 24.3.2 安全点检查

快速字段访问需要检查是否在安全点——因为 GC 可能正在移动对象：

```asm
; x86_64 快速字段访问（简化）
mov rax, [obj + offset]      ; 读取 safepoint 标志
test rax, rax
jnz  slow_path               ; 如果在安全点，走慢速路径
mov rax, [obj + field_offset] ; 直接读取字段
ret
```

---

## 24.4 `nativeLookup.cpp`：Native 方法符号解析

### 24.4.1 符号解析规则

当 Java 代码首次调用 native 方法时，JVM 需要找到对应的 C 函数：

```
标准命名规则：
  Java_<包名>_<类名>_<方法名>

示例：
  java.lang.System.registerNatives()
  → Java_java_lang_System_registerNatives

重载方法的命名：
  Java_<包名>_<类名>_<方法名>__<参数签名>

示例：
  java.lang.Object.hashCode()
  → Java_java_lang_Object_hashCode

  java.lang.String.charAt(int)
  → Java_java_lang_String_charAt__I
```

### 24.4.2 动态注册

除了标准命名规则，native 方法可以使用 `RegisterNatives` 动态注册：

```c
// 在 JNI_OnLoad 中注册
JNIEXPORT jint JNICALL JNI_OnLoad(JavaVM *vm, void *reserved) {
    JNINativeMethod methods[] = {
        {"nativeMethod", "(I)I", (void *)my_native_implementation},
    };
    env->RegisterNatives(cls, methods, 1);
    return JNI_VERSION_1_2;
}
```

动态注册的优势：
1. 函数名自由命名
2. 减少符号表查找开销
3. 支持运行时选择实现

---

## 24.5 [专题] Panama Foreign Function & Memory API

### 24.5.1 Panama vs JNI

Panama（JDK 22+ 正式）是 JNI 的现代替代：

| 特性 | JNI | Panama |
|------|-----|--------|
| 类型安全 | 手动 | 自动生成 |
| 调用开销 | ~15-30ns | ~5-10ns |
| 内存管理 | 手动 | Arena 管理 |
| 回调（upcall） | 复杂 | 简单 |
| 代码生成 | javah/jextract | jextract 自动生成 |

### 24.5.2 Downcall（Java → Native）

```java
// Panama 方式调用 C 函数
Linker linker = Linker.nativeLinker();
SymbolLookup stdlib = linker.defaultLookup();

MethodHandle strlen = linker.downcallHandle(
    stdlib.find("strlen").orElseThrow(),
    FunctionDescriptor.of(ValueLayout.JAVA_LONG,
                          ValueLayout.ADDRESS)
);

long len = (long) strlen.invokeExact(str.toCString());
```

### 24.5.3 Upcall（Native → Java）

```java
// Panama 方式实现 C 回调
MethodHandle callback = MethodHandles.lookup().findStatic(
    MyClass.class, "onEvent",
    MethodType.methodType(void.class, int.class));

MemorySegment upcallStub = linker.upcallStub(
    callback,
    FunctionDescriptor.ofVoid(ValueLayout.JAVA_INT),
    Arena.ofAuto());
```

### 24.5.4 Panama 调用 CUDA 执行推理

```java
// 使用 Panama 调用 CUDA Runtime API
Linker linker = Linker.nativeLinker();
SymbolLookup cuda = SymbolLookup.libraryLookup("libcudart.so", Arena.ofAuto());

MethodHandle cudaMalloc = linker.downcallHandle(
    cuda.find("cudaMalloc").orElseThrow(),
    FunctionDescriptor.of(ValueLayout.JAVA_INT,
                          ValueLayout.ADDRESS,  // void** devPtr
                          ValueLayout.JAVA_LONG) // size_t size
);

MethodHandle cudaMemcpy = linker.downcallHandle(
    cuda.find("cudaMemcpy").orElseThrow(),
    FunctionDescriptor.of(ValueLayout.JAVA_INT,
                          ValueLayout.ADDRESS,  // void* dst
                          ValueLayout.ADDRESS,  // void* src
                          ValueLayout.JAVA_LONG, // size_t count
                          ValueLayout.JAVA_INT)  // cudaMemcpyKind
);
```

---

## 小结

本章深入了 JNI 的完整机制：

1. **JNI 函数表**包含 200+ 函数，每次调用有 15-30ns 的开销
2. **局部引用**在 native 调用返回时自动释放，**全局引用**需要手动释放
3. **快速字段访问**通过生成机器码绕过 JNI 函数表，但有安全点检查
4. **符号解析**支持标准命名和动态注册两种方式
5. **Panama** 是 JNI 的现代替代，调用开销更低，类型安全更好
6. **Panama 调用 CUDA** 为 Java 推理服务提供了直接访问 GPU 的路径

下一章将深入 JVMTI 与 Agent 机制。
