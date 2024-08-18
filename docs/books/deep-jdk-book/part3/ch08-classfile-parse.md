# 第 8 章 Class 文件解析

> 源码路径：`src/hotspot/share/classfile/classFileParser.cpp`、`src/hotspot/share/classfile/classFileStream.cpp`、`src/hotspot/share/classfile/fieldLayoutBuilder.cpp`、`src/hotspot/share/classfile/verifier.cpp`

Class 文件是 Java 平台无关性的基石。JVM 必须将二进制的 `.class` 流解析为内部的 `InstanceKlass` 数据结构——这个过程涉及常量池构建、字段布局、方法解析和字节码验证。本章从 `ClassFileParser` 入手，追踪完整的解析链路。

---

## 8.1 `classFileParser.cpp`：字节码解析全流程

### 8.1.1 ClassFileParser 的核心职责

`ClassFileParser` 是一个一次性对象——创建、解析、产出 `InstanceKlass`，然后销毁：

```cpp
// classFileParser.hpp:84
class ClassFileParser {
    const ClassFileStream* _stream;       // 输入流
    Symbol* _class_name;                 // 类名
    ClassLoaderData* _loader_data;        // 类加载器数据
    ConstantPool* _cp;                    // 解析产出的常量池
    Array<Method*>* _methods;             // 解析产出的方法数组
    InstanceKlass* _klass;               // 最终产出的 InstanceKlass
    FieldLayoutInfo* _field_info;         // 字段布局信息
    // ...
};
```

### 8.1.2 解析阶段总览

```
ClassFileParser::parseClassFile()
├── 1. 魔数与版本号检查
│   ├── 0xCAFEBABE 魔数
│   └── minor_version / major_version（JDK 27 = 71）
├── 2. 常量池解析
│   ├── parse_constant_pool()            → ConstantPool 对象
│   └── 常量池条目解析（Utf8/Class/NameAndType/Methodref/...）
├── 3. 类级信息解析
│   ├── access_flags                     → 公共/私有/抽象/最终等
│   ├── this_class / super_class         → 类名和父类名
│   └── interfaces                       → 实现的接口列表
├── 4. 字段解析
│   ├── parse_fields()                   → 字段信息收集
│   └── FieldLayoutBuilder               → 字段布局优化
├── 5. 方法解析
│   ├── parse_methods()                  → 方法数组
│   └── 方法字节码验证（stackMapTable）
├── 6. 属性解析
│   ├── InnerClasses                     → 内部类
│   ├── NestMembers / NestHost           → 巢穴属性
│   ├── Record                           → record 组件
│   ├── PermittedSubclasses              → sealed 类
│   └── SourceFile / Deprecated / ...
└── 7. InstanceKlass 创建
    ├── fill_instance_klass()            → 填充所有字段
    └── 返回完整的 InstanceKlass
```

### 8.1.3 常量池解析

常量池是 Class 文件中最复杂的结构，解析代码占 `ClassFileParser` 的相当比例：

```cpp
// classFileParser.cpp（简化）
void ClassFileParser::parse_constant_pool() {
    int cp_size = _stream->get_u2();  // 常量池条目数
    _cp = ConstantPool::allocate(_loader_data, cp_size);

    for (int index = 1; index < cp_size; index++) {
        u1 tag = _stream->get_u1();
        switch (tag) {
            case JVM_CONSTANT_Utf8:         // UTF-8 字符串
            case JVM_CONSTANT_Class:        // 类引用
            case JVM_CONSTANT_Fieldref:      // 字段引用
            case JVM_CONSTANT_Methodref:     // 方法引用
            case JVM_CONSTANT_InterfaceMethodref: // 接口方法引用
            case JVM_CONSTANT_NameAndType:   // 名称和类型
            case JVM_CONSTANT_MethodHandle:  // 方法句柄
            case JVM_CONSTANT_MethodType:    // 方法类型
            case JVM_CONSTANT_Dynamic:       // 动态常量（invokedynamic）
            case JVM_CONSTANT_InvokeDynamic: // invokedynamic 指令
            // ...
        }
    }
}
```

常量池索引从 1 开始（0 保留），long/double 类型占两个槽位。

---

## 8.2 `classFileStream.cpp`：类文件流的读取与校验

### 8.2.1 ClassFileStream

`ClassFileStream` 封装了 Class 文件的二进制数据，提供安全的读取方法：

```cpp
class ClassFileStream {
    const u1* _buffer_start;   // 数据起始
    const u1* _buffer_end;     // 数据结束
    const u1* _current;        // 当前读取位置
    const char* _source;       // 来源描述（文件路径/JAR名）

    u1 get_u1();               // 读取 1 字节
    u2 get_u2();               // 读取 2 字节（大端）
    u4 get_u4();               // 读取 4 字节（大端）
    void skip_u1(int length);  // 跳过 N 字节
};
```

每个读取方法都包含边界检查——如果读取超出流范围，抛出 `ClassFormatError`。

---

## 8.3 字段布局构建（`fieldLayoutBuilder.cpp`）

### 8.3.1 FieldLayoutBuilder 的工作

字段布局不是简单按声明顺序排列。`FieldLayoutBuilder` 执行以下优化：

1. **引用字段聚集**：将所有 oop 引用字段放在一起，减少 GC 扫描范围
2. **对齐优化**：long/double 字段对齐到 8 字节边界
3. **间隙填充**：用小字段（boolean/byte/short）填充对齐间隙
4. **继承字段**：父类字段排在前面，保持布局兼容性

```cpp
// fieldLayoutBuilder.cpp（简化流程）
void FieldLayoutBuilder::build_layout() {
    // 1. 计算父类字段布局的继承部分
    // 2. 分配引用字段（连续区域）
    // 3. 分配长整型/双精度字段（8 字节对齐）
    // 4. 分配整型/浮点字段（4 字节对齐）
    // 5. 分配短整型/字符字段（2 字节对齐）
    // 6. 分配字节/布尔字段（1 字节对齐）
    // 7. 填充对齐间隙
    // 8. 生成 oop_map（标记哪些偏移处包含引用）
}
```

---

## 8.4 `stackMapTable` 与字节码验证（`verifier.cpp`）

### 8.4.1 字节码验证的目的

字节码验证确保 Class 文件不会违反 JVM 安全约束：
- 类型安全：不会将 int 当作引用使用
- 栈一致性：操作数栈的深度和类型在每条指令处可预测
- 访问控制：不违反 private/protected 访问限制

### 8.4.2 StackMapTable

JDK 6+ 使用 `StackMapTable` 属性加速验证。编译器在 Class 文件中预计算了每个分支目标的栈帧类型映射：

```
StackMapTable:
  offset 0:   [ Locals: int, String ] [ Stack: ]
  offset 15:  [ Locals: int, String, List ] [ Stack: int ]
  offset 42:  [ Locals: int, String ] [ Stack: IOException ]
```

验证器只需检查这些预计算点的类型一致性，而不是模拟执行所有字节码路径——这大幅减少了验证时间。

### 8.4.3 验证器的实现

```cpp
// verifier.cpp
bool Verifier::verify(InstanceKlass* klass) {
    // 1. 结构性检查（常量池索引有效、操作数合法）
    // 2. 类型检查（使用 StackMapTable）
    //    - 检查每个分支目标的类型映射
    //    - 验证赋值兼容性
    // 3. 加载时约束检查（类型加载时验证）
}
```

如果验证失败，JVM 抛出 `VerifyError`。可以使用 `-Xverify:none` 跳过验证（仅调试用，生产环境极度危险）。

---

## 8.5 [专题] `record`、`sealed class`、`pattern matching` 的 class 文件表示

### 8.5.1 Record 类

JDK 16 引入的 `record` 类在 Class 文件中表示为：

- `access_flags` 中的 `ACC_RECORD` 标志（0x10000）
- `Record` 属性：列出 record 组件的名称和类型
- 自动生成的字段、构造器、getter、equals/hashCode/toString 方法

### 8.5.2 Sealed Class

JDK 17 引入的 `sealed` 类在 Class 文件中表示为：

- `access_flags` 中的 `ACC_SEALED` 标志（0x0800）
- `PermittedSubclasses` 属性：列出允许的子类全限定名

### 8.5.3 Pattern Matching

JDK 21 的模式匹配（`switch` 中的类型模式）不引入新的 Class 文件属性，而是通过编译器生成 `checkcast` 指令和条件分支实现。

---

## 小结

本章追踪了 Class 文件从二进制流到 `InstanceKlass` 的完整解析过程：

1. **ClassFileParser** 一次性解析器，产出完整的类元数据
2. **常量池**是最复杂的结构，承载了所有符号引用
3. **字段布局**经过优化重排序，减少 GC 扫描范围
4. **StackMapTable** 预计算的类型映射加速字节码验证
5. **现代 Java 特性**（record/sealed）通过新的 Class 文件属性表示
