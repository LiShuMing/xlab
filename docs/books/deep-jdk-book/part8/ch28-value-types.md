# 第 28 章 Value Types（Valhalla）的预研

> 源码路径：`src/hotspot/share/oops/markWord.hpp`、`src/hotspot/share/oops/objLayout.cpp`、`src/hotspot/share/oops/oopsHierarchy.hpp`

Value Types（Project Valhalla）是 Java 平台最重要的未来特性之一——它将引入「扁平化」的值类型对象，消除当前对象模型中指针间接和头部开销的问题。虽然 Valhalla 尚未正式发布，但 JDK 27 的源码中已蕴含了为 Value Types 预留的线索。本章分析这些线索，展望 Value Types 对 JVM 的影响。

---

## 28.1 Value Types 对对象模型的冲击

### 28.1.1 当前对象模型的问题

每个 Java 对象都有固定的开销：

```
当前对象布局（64 位，UseCompressedOops）：
┌─────────────────────────┐
│ markWord (8 bytes)       │  ← 锁、哈希、GC 年龄
├─────────────────────────┤
│ Klass* (4 bytes)         │  ← 类型元数据
├─────────────────────────┤
│ 实际字段数据              │  ← 有效的负载数据
└─────────────────────────┘

开销：12 字节头 + 对齐填充
最小对象大小：16 字节

问题：
1. 一个只含 1 个 int 字段的对象，有效负载 4 字节，开销 12 字节，利用率 25%
2. 对象数组中每个元素是一个引用（4 字节），还需要一次指针跳转
3. 数千个 Point(x,y) 对象，每个 16 字节 + 8 字节引用 = 24 字节
   而两个 int 只需 8 字节
```

### 28.1.2 Value Types 的目标

```
Value Types 的核心目标：
1. 扁平化：值类型对象没有对象头，直接内联在容器中
2. 无标识：值类型没有身份哈希、锁等标识相关特性
3. 默认不可变：值类型默认不可修改（类似 record）
4. 多态：支持接口和泛型

预期效果：
  Point(int x, int y) 作为值类型：
  - 数组中连续存储：[x1,y1,x2,y2,...]  而非 [ref1→(h,x1,y1), ref2→(h,x2,y2), ...]
  - 字段中内联存储：直接嵌入父对象  而非 额外的堆分配
  - 无对象头开销
```

---

## 28.2 `objLayout.cpp` 中的扁平化线索

### 28.2.1 紧凑头（Compact Object Headers）

JDK 27 引入的紧凑头是 Value Types 的前奏：

```cpp
// markWord.hpp（JDK 27）
// 紧凑头：将 Klass* 压入 markWord
64 位 markWord（紧凑头）：
┌──────────────────────────────────┬──────┬──────┬──────┬──────┐
│ klass:22     hash:31             │ gap:4│age:4 │fwd:1 │lock:2│
└──────────────────────────────────┴──────┴──────┴──────┴──────┘

启用：-XX:+UseCompactObjectHeaders
效果：每个对象省去 8 字节的 Klass* 字段
```

紧凑头为 Value Types 铺路——如果 Klass* 可以压缩到 markWord 中，那么值类型就无需独立的 Klass* 字段，进一步减少头部开销。

### 28.2.2 对象布局的扩展点

```cpp
// objLayout.cpp
// FieldLayoutBuilder 预留了值类型字段的布局逻辑
// 值类型字段的扁平化布局需要：
// 1. 内联分配空间（不创建独立对象）
// 2. 无对象头
// 3. GC 扫描时识别内联的 oop 引用

// 当前代码中的预留注释：
// TODO: Value type field flattening support
```

### 28.2.3 扁平化对字段布局的影响

```
传统布局：
class Line {
    Point start;   // 引用，8 字节 + 间接访问
    Point end;     // 引用，8 字节 + 间接访问
}
Line 对象：markWord(8) + Klass*(4) + start_ref(4) + end_ref(4) + pad(4) = 24 字节

扁平化布局：
value class Line {
    Point start;   // 内联，8 字节（2 个 int）
    Point end;     // 内联，8 字节（2 个 int）
}
Line 对象：markWord(8) + Klass*(4) + start.x(4) + start.y(4) + end.x(4) + end.y(4) = 28 字节

关键差异：无间接指针，缓存友好
```

---

## 28.3 对 `oopsHierarchy` 的影响分析

### 28.3.1 新的 oop 类型

Value Types 需要新的 oop 类型层次：

```
当前 oop 层次：
oop
├── instanceOop        // 普通对象
├── arrayOop           // 数组
│   ├── objArrayOop    // 对象数组
│   └── typeArrayOop   // 基本类型数组
└── stackChunkOop      // 虚拟线程栈块

Valhalla 预期的 oop 层次：
oop
├── instanceOop
├── arrayOop
│   ├── objArrayOop
│   ├── typeArrayOop
│   └── valueArrayOop   // 新增：值类型数组（扁平存储）
├── stackChunkOop
└── flatOop?             // 新增：扁平化的值类型对象？
```

### 28.3.2 GC 的影响

Value Types 的扁平化对 GC 有深远影响：

```
1. 标记：
   扁平化的值类型没有独立的 markWord
   → 无法独立标记
   → 必须作为容器对象的一部分标记

2. 移动：
   值类型内联在容器中，不能独立移动
   → GC 移动容器时，值类型随之移动
   → 值类型中的 oop 引用需要更新

3. 压缩：
   值类型数组中的元素是连续存储的
   → GC 压缩时需要更新数组内的所有 oop 引用
   → 这比对象数组更复杂（对象数组只需更新引用）

4. 读屏障（ZGC/Shenandoah）：
   值类型中的 oop 引用也需要读屏障
   → 需要新的屏障机制处理内联引用
```

### 28.3.3 值类型数组的内存布局

```
对象数组（当前）：
[objArrayOop]
  markWord | Klass* | length | ref0 | ref1 | ref2 | ...
                                      ↓     ↓     ↓
                                   [oop0] [oop1] [oop2]
                                   每个元素需要一次指针跳转

值类型数组（Valhalla）：
[valueArrayOop]
  markWord | Klass* | length | v0.x | v0.y | v1.x | v1.y | ...
  连续存储，无指针跳转，缓存友好
```

---

## 小结

本章预研了 Value Types 对 JVM 的影响：

1. **当前对象模型**的有效负载率低（小对象仅 25%），是 Value Types 的驱动力
2. **紧凑头**（JDK 27）是 Value Types 的前奏，为减少头部开销铺路
3. **扁平化布局**要求 FieldLayoutBuilder 支持内联字段
4. **GC 需要新的机制**处理内联值类型中的 oop 引用
5. **值类型数组**的连续存储消除了指针跳转，显著提升缓存利用率

下一章将深入 Panama——Foreign Function & Memory API。
