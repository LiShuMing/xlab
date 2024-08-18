# 第 20 章 `java.lang` 核心

> 源码路径：`src/java.base/share/classes/java/lang/`、`src/hotspot/share/classfile/javaClasses.cpp`

`java.lang` 是 Java 语言的基石包，包含了类型系统（`Object`、`Class`）、字符串（`String`）、线程（`Thread`）、引用（`Reference`）等核心类。这些类与 HotSpot 的实现深度耦合，理解它们的内部机制是深入 JVM 的必经之路。

---

## 20.1 `Object / Class / ClassLoader`：类型系统的 Java 入口

### 20.1.1 Object 的 HotSpot 映射

`java.lang.Object` 在 HotSpot 中对应 `instanceOopDesc`：

```cpp
// javaClasses.cpp
// Object 的字段布局（无实例字段）：
// markWord (8 bytes) + Klass* (4/8 bytes)
// 总计：12/16 字节（对齐到 8 字节）
```

Object 的 5 个方法均有 HotSpot 内部实现：

| 方法 | HotSpot 实现 |
|------|-------------|
| `hashCode()` | `ObjectSynchronizer::FastHashCode()` → 延迟计算，存入 markWord |
| `equals()` | 默认引用比较（`oopDesc::equals()`） |
| `getClass()` | 从 markWord / Klass* 指针获取 |
| `clone()` | `jvm_clone()` → 浅复制 |
| `wait/notify/notifyAll` | `ObjectMonitor::wait/notify` |

### 20.1.2 Class 对象的 HotSpot 映射

每个 `java.lang.Class` 对象对应一个 `InstanceKlass` 或 `ArrayKlass`：

```cpp
// javaClasses.cpp
oop java_lang_Class::klass_to_mirror(Klass* k) {
    return k->java_mirror();
}

Klass* java_lang_Class::mirror_to_klass(oop mirror) {
    return InstanceKlass::cast(mirror->klass())->java_mirror_to_klass();
}
```

`Class` 对象是一个特殊的 `InstanceOop`——它的实例数据存储了对应 `Klass` 的元信息：

```
java.lang.Class 实例布局：
┌─────────────────────────┐
│ markWord                │
│ Klass* (java.lang.Class)│
├─────────────────────────┤
│ _klass (目标 Klass*)    │  ← 指向对应的 InstanceKlass
│ _array_klass            │  ← 如果是数组类型
│ _oop_size               │  ← 实例大小
│ _static_oop_field_count │  ← 静态字段数
│ _init_lock              │  ← 初始化锁
│ _signers                │  ← 签名者
│ _pd                     │  ← ProtectionDomain
└─────────────────────────┘
```

### 20.1.3 ClassLoader 的 HotSpot 映射

每个 `ClassLoader` 对象对应一个 `ClassLoaderData`（第 9 章已详述）：

```cpp
// classLoaderData.hpp
ClassLoaderData* ClassLoaderData::class_loader_data(oop loader) {
    return loader->klass()->class_loader_data();
}
```

---

## 20.2 `String` 与字符串紧凑化（Compact Strings）

### 20.2.1 String 的内部表示

JDK 9+ 使用 Compact Strings，`String` 内部用 `byte[]` 而非 `char[]`：

```java
// String.java
public final class String {
    private final byte[] value;   // 存储字符串数据
    private final byte coder;     // 编码器：LATIN1(0) 或 UTF16(1)
    private int hash;             // 缓存的哈希值

    static final byte LATIN1 = 0;
    static final byte UTF16  = 1;
}
```

### 20.2.2 Compact Strings 的优化

```
纯 ASCII 字符串（大多数场景）：
  coder = LATIN1
  每个字符占 1 字节（而非 2 字节）
  内存节省 ~50%

包含非 ASCII 字符的字符串：
  coder = UTF16
  每个字符占 2 字节（与 JDK 8 相同）

判断逻辑：
  if (StringUTF16.hasNegatives(value)) {
      return new String(value, UTF16);  // 有非 ASCII → UTF16
  } else {
      return new String(value, LATIN1); // 纯 ASCII → LATIN1
  }
```

### 20.2.3 String 的 CDS 归档

字符串常量在 CDS 归档中被特殊处理：

```
归档阶段：
1. 遍历所有已加载的字符串常量
2. 将 byte[] 和 coder 字段序列化
3. 写入归档文件

使用阶段：
1. 从归档映射字符串
2. 直接使用，无需 new String()
3. 字符串哈希值预计算，无需运行时计算
```

---

## 20.3 `Thread / ThreadLocal / InheritableThreadLocal`

### 20.3.1 Thread 的 HotSpot 映射

Java `Thread` 对象持有 HotSpot `JavaThread` 的引用：

```java
// Thread.java
public class Thread {
    // HotSpot 私有字段
    private long eetop;  // 指向 JavaThread 的指针

    // 线程本地存储
    ThreadLocal.ThreadLocalMap threadLocals;
    ThreadLocal.ThreadLocalMap inheritableThreadLocals;
}
```

### 20.3.2 ThreadLocal 的实现

`ThreadLocal` 使用 `ThreadLocalMap`（自定义的哈希表）存储线程本地变量：

```java
// ThreadLocal.java
public T get() {
    Thread t = Thread.currentThread();
    ThreadLocalMap map = getMap(t);
    if (map != null) {
        ThreadLocalMap.Entry e = map.getEntry(this);
        if (e != null) return (T) e.value;
    }
    return setInitialValue();
}
```

`ThreadLocalMap` 使用**弱引用**引用 `ThreadLocal` 对象，避免 `ThreadLocal` 对象被线程阻止回收。但 `value` 是强引用——这是内存泄漏的根源（线程池中线程复用时，旧的 `ThreadLocal` value 不释放）。

### 20.3.3 InheritableThreadLocal

`InheritableThreadLocal` 在创建子线程时，将父线程的 `inheritableThreadLocals` 复制到子线程：

```java
// Thread.java 构造函数中
if (parent.inheritableThreadLocals != null) {
    this.inheritableThreadLocals =
        ThreadLocal.createInheritedMap(parent.inheritableThreadLocals);
}
```

注意：虚拟线程不会继承 `InheritableThreadLocal`（默认禁用），推荐使用 `ScopedValue`（JDK 21+）。

---

## 20.4 `Reference` 体系：Soft / Weak / Phantom / FinalReference

### 20.4.1 Reference 的层次

```
Reference (抽象)
├── SoftReference       → 内存不足时才回收
├── WeakReference       → 下次 GC 回收
│   └── WeakPair        → WeakHashMap 使用
├── PhantomReference    → 回收后通知（get() 总是 null）
└── FinalReference      → finalizer 机制（已废弃）
    └── Finalizer
```

### 20.4.2 Reference 的 HotSpot 处理

GC 在标记阶段发现引用指向的对象不可达时，按类型处理：

```
1. 软引用（SoftReference）：
   检查 -XX:SoftRefLRUPolicyMSPerMB（默认 1000ms/MB 堆空闲）
   如果空闲内存足够 → 保留
   如果空闲内存不足 → 加入待处理列表

2. 弱引用（WeakReference）：
   直接加入待处理列表（不管内存是否充足）

3. 虚引用（PhantomReference）：
   对象已被回收后加入待处理列表
   get() 始终返回 null

4. FinalReference：
   调用对象的 finalize() 方法
   JDK 18+ 已废弃 finalizer，推荐 Cleaner
```

### 20.4.3 ReferenceQueue 与 Cleaner

```java
// Cleaner 是 PhantomReference 的便捷包装
Cleaner.create(object, () -> {
    // 清理动作（对象被回收后执行）
    closeResource();
});
```

Cleaner 由 `CleanerImpl` 线程驱动，该线程从 ReferenceQueue 中取出已回收的引用，执行清理动作。

---

## 20.5 `StackTraceElement` 与异常机制

### 20.5.1 异常的 HotSpot 实现

异常对象的创建涉及栈遍历：

```cpp
// exceptions.cpp
void Exceptions::new_exception(JavaThread* thread, Symbol* name, ...) {
    // 1. 创建异常对象
    Handle h_exception = allocate_exception(thread, name, ...);

    // 2. 填充栈跟踪
    if (!thread->is_internal_build()) {
        java_lang_Throwable::fill_in_stack_trace(h_exception, ...);
    }
}
```

### 20.5.2 栈跟踪的创建过程

```
1. 获取当前线程的栈帧
2. 跳过异常处理相关的帧
3. 逐帧创建 StackTraceElement：
   - 类名、方法名、文件名、行号
   - 行号通过 nmethod 的行号表查询
4. 存储在 Throwable 的 backtrace 字段中
```

### 20.5.3 栈跟踪的性能影响

```
创建异常对象的成本：
  new Exception(): ~1-5μs（包含栈遍历）
  new Exception().fillInStackTrace(): 已在构造中调用
  new Exception().toString(): ~0.1μs（不含栈遍历）

优化：
  预创建异常（不填充栈跟踪）：
  -XX:-OmitStackTraceInFastThrow  # 关闭快速抛出（省略栈跟踪）

  对于频繁抛出的异常，HotSpot 会预分配异常对象，
  省略栈跟踪，直接抛出预分配的对象。
```

---

## 小结

本章剖析了 `java.lang` 的核心类：

1. **Object / Class** 与 HotSpot 的 `oopDesc / InstanceKlass` 深度映射
2. **Compact Strings** 将纯 ASCII 字符串的内存占用减半
3. **ThreadLocal** 的弱引用设计避免了 `ThreadLocal` 对象的泄漏，但 `value` 仍可能泄漏
4. **Reference** 体系在 GC 中按不同策略处理软/弱/虚引用
5. **异常机制**的栈跟踪创建涉及栈遍历，对性能敏感场景可使用快速抛出优化

下一章将深入 `java.lang.invoke`——方法句柄与 Lambda。
