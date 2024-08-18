# 第 9 章 类加载器体系

> 源码路径：`src/hotspot/share/classfile/classLoader.cpp`、`src/hotspot/share/classfile/classLoaderData.cpp`、`src/hotspot/share/classfile/systemDictionary.cpp`、`src/hotspot/share/classfile/dictionary.cpp`

类加载是 Java 安全模型和模块化系统的基础。JVM 的类加载器体系不仅实现了双亲委派，还管理着类加载器的生命周期、类的查找缓存和并发安全。本章深入 HotSpot 的类加载器实现。

---

## 9.1 `classLoader.cpp`：双亲委派的 HotSpot 实现

### 9.1.1 类路径条目

JVM 的类路径由三种条目组成：

```cpp
class ClassPathEntry {
    ClassPathDirEntry    // 目录：扫描 .class 文件
    ClassPathZipEntry    // JAR/ZIP：查找压缩条目
    ClassPathImageEntry  // jimage：模块化运行时映像
};
```

类路径的遍历顺序：
1. **Bootstrap Class Path**：`rt.jar` / `modules` jimage
2. **Extension Class Path**（已废弃）：`lib/ext/`
3. **Application Class Path**：`-cp` / `-classpath` 指定

### 9.1.2 双亲委派的实现

双亲委派不是在 JVM C++ 层强制实现的，而是通过 Java 层的 `ClassLoader.loadClass()` 方法：

```java
// java.lang.ClassLoader（简化）
protected Class<?> loadClass(String name, boolean resolve) {
    // 1. 检查是否已加载
    Class<?> c = findLoadedClass(name);
    if (c == null) {
        // 2. 委派给父加载器
        if (parent != null) {
            c = parent.loadClass(name, false);
        } else {
            c = findBootstrapClassOrNull(name);
        }
        // 3. 父加载器找不到，自己找
        if (c == null) {
            c = findClass(name);
        }
    }
    return c;
}
```

HotSpot 层通过 `SystemDictionary::resolve_or_null()` 支持这一流程——当 Java 层调用 `findLoadedClass` 时，JVM 查询 `ClassLoaderData` 的 `Dictionary`。

---

## 9.2 `classLoaderData.cpp`：加载器数据结构与生命周期

### 9.2.1 ClassLoaderData 的角色

每个类加载器对应一个 `ClassLoaderData`，它持有：

```cpp
class ClassLoaderData {
    oop               _class_loader;      // Java 层的 ClassLoader 对象
    Dictionary*       _dictionary;        // 已加载类的字典
    MetaspaceArena*   _non_class_space;   // 非 Klass 元空间
    MetaspaceArena*   _class_space;       // Klass 元空间（压缩 Klass）
    DependencyContext  _dependencies;      // 依赖关系
};
```

`ClassLoaderData` 是 GC 管理类加载器生命周期的关键——当 `ClassLoader` 对象不可达时，GC 会标记对应的 `ClassLoaderData` 为「死」的，然后卸载其加载的所有类。

### 9.2.2 类加载器图（ClassLoaderDataGraph）

```cpp
class ClassLoaderDataGraph {
    // 全局链表，持有所有 ClassLoaderData 节点
    static ClassLoaderData* _head;

    // GC 遍历所有加载器
    static void loaded_class_do(KlassClosure* closure);

    // GC 卸载不可达的加载器
    static void do_unloading();
};
```

---

## 9.3 `systemDictionary.cpp`：类型解析与符号表

### 9.3.1 SystemDictionary 的职责

`SystemDictionary` 不是传统的字典——它是类解析的协调者：

```cpp
class SystemDictionary {
    // 解析类（如果未加载则触发加载）
    static Klass* resolve_or_fail(Symbol* name, Handle loader, bool throw_error, TRAPS);
    static Klass* resolve_or_null(Symbol* name, Handle loader, TRAPS);

    // 查找已加载的类（不触发加载）
    static InstanceKlass* find_instance_klass(Symbol* name, Handle loader);

    // 定义新加载的类
    static InstanceKlass* define_class(Symbol* name, Handle loader, ClassFileStream* stream);
};
```

### 9.3.2 类解析的并发控制

类加载使用「占位符」（Placeholder）机制防止并发重复加载：

```
线程 A 加载 com.example.Foo:
1. 获取 SystemDictionary_lock
2. 在 _placeholders 中插入 (Foo, LoaderA)
3. 释放锁，执行实际的类加载
4. 加载完成，获取锁
5. 在 LoaderA 的 Dictionary 中插入 Foo
6. 从 _placeholders 中移除 Foo
7. 唤醒等待的线程

线程 B 同时请求 Foo:
1. 获取 SystemDictionary_lock
2. 发现 _placeholders 中已有 Foo
3. 等待线程 A 完成
4. 被唤醒后从 Dictionary 中获取 Foo
```

这个机制同时检测了类循环依赖（ClassCircularityError）——如果线程 A 在加载 Foo 时需要加载 Foo 自身，`_placeholders` 中已有记录，检测到循环。

---

## 9.4 `dictionary.cpp`：已加载类的查找与并发安全

### 9.4.1 Dictionary 的实现

`Dictionary` 是每个 `ClassLoaderData` 专属的并发哈希表：

```cpp
class Dictionary {
    // 哈希桶数组
    DictionaryEntry* _buckets[DEFAULT_HASH_TABLE_SIZE];

    // 查找：根据类名和加载器
    InstanceKlass* find_class(unsigned int hash, Symbol* name);

    // 添加：加载完成后插入
    void add_klass(unsigned int hash, Symbol* name, InstanceKlass* klass);
};
```

读取操作不加锁（依赖内存序保证），写入操作持有 `SystemDictionary_lock`。这是安全的，因为：
- 条目只在类加载器存活期间存在
- 条目在发布前必须完全构造（写排序保证）

---

## 9.5 模块化系统（`moduleEntry / packageEntry`）

### 9.5.1 JPMS 在 HotSpot 中的实现

JDK 9 的模块系统（JPMS）在 HotSpot 中由以下类支撑：

```cpp
class ModuleEntry {
    Symbol* _name;              // 模块名（如 java.base）
    oop     _module;            // Java 层的 Module 对象
    ClassLoaderData* _loader;   // 所属加载器
};

class PackageEntry {
    Symbol* _name;              // 包名（如 java.lang）
    ModuleEntry* _module;       // 所属模块
};
```

模块系统影响类解析的关键点：
- 类加载时需要检查 `package` 是否 `export` 给请求者
- `add-exports` / `add-opens` 可以打破模块边界
- `--module-path` 替代了传统的 `class path`

---

## 小结

本章剖析了 JVM 的类加载器体系：

1. **双亲委派**在 Java 层实现，HotSpot 通过 `SystemDictionary` 支撑
2. **ClassLoaderData** 是类加载器在 JVM 内部的表示，持有元空间和类字典
3. **占位符机制**防止并发重复加载和检测循环依赖
4. **Dictionary** 是不加锁读取的并发哈希表
5. **模块系统**通过 `ModuleEntry / PackageEntry` 实现访问控制
