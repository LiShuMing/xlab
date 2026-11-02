# C++ 面试题精编

> 本文整理了 C++ 开发岗位面试中的高频问题，涵盖内存管理、面向对象、STL、智能指针、C++11 新特性等核心知识点。

---

## 一、内存管理

### 1.1 C++ 内存布局

C++ 程序的内存分为以下几个区域：

| 内存区域 | 说明 | 特点 |
|---------|------|------|
| **栈区 (Stack)** | 存储局部变量、函数参数 | 自动分配/释放，速度快，空间有限 |
| **堆区 (Heap)** | 动态分配的内存 | 手动管理，空间大，易产生碎片 |
| **全局/静态存储区** | 全局变量、静态变量 | 程序启动时分配，结束时释放 |
| ├─ BSS 段 | 未初始化的全局/静态变量 | 初始化为 0 |
| ├─ 数据段 (Data) | 已初始化的全局/静态变量 | 有初始值 |
| **代码段 (Text)** | 程序代码 | 只读 |
| **常量存储区** | 字符串常量等 | 只读 |

### 1.2 new 与 malloc 的区别

| 特性 | new | malloc |
|------|-----|--------|
| **类型安全** | 是，返回正确类型指针 | 否，返回 void* 需强制转换 |
| **构造函数** | 自动调用 | 不调用 |
| **析构函数** | delete 时自动调用 | 需手动调用 |
| **失败处理** | 抛出 bad_alloc 异常 | 返回 NULL |
| **内存大小** | 编译器自动计算 | 需手动指定 |
| **重载** | 可以重载 | 不能重载 |

**new 底层实现**：
1. 调用 `operator new` 分配内存（内部使用 malloc 或系统调用）
2. 在分配的内存上调用构造函数
3. 返回正确类型的指针

### 1.3 内存分配机制：brk vs mmap

glibc 的内存分配器（ptmalloc）根据请求大小选择不同策略：

| 分配方式 | 适用场景 | 特点 |
|---------|---------|------|
| **brk** | 小内存分配 (< 128KB) | 扩展堆顶，不立即归还系统 |
| **mmap** | 大内存分配 (≥ 128KB) | 独立内存映射，可立即归还 |

**为什么 brk 分配的内存 free 时不立即归还给系统？**

1. **性能优化**：减少系统调用开销，提高后续分配效率
2. **减少碎片**：避免频繁收缩/扩展堆导致的碎片化
3. **内存复用**：保留的内存可被后续分配复用

### 1.4 内存碎片管理

**内部碎片**：分配的内存块大于实际需要的大小（如按页分配时）
**外部碎片**：空闲内存分散，无法满足大块连续分配需求

**malloc 管理碎片的策略**：
- **分级分配器（Segregated Free Lists）**：按大小分类管理
- **空闲块合并（Coalescing）**：释放时合并相邻空闲块
- **分配算法**：First-Fit、Best-Fit、Next-Fit
- **内存块拆分**：大块拆分为小块满足分配需求

### 1.5 空类的大小

```cpp
class Empty {};
// sizeof(Empty) == 1
```

**为什么是 1 字节而不是 0？**
- C++ 标准要求每个对象必须有唯一的内存地址
- 如果大小为 0，多个对象可能分配到同一地址，导致混淆

**含虚函数的类**：
```cpp
class VirtualClass {
    virtual void foo();
};
// sizeof(VirtualClass) == 4(32位) 或 8(64位)
// 因为包含虚函数表指针（vptr）
```

---

## 二、面向对象与多态

### 2.1 虚函数机制详解

**虚函数表（vtable）工作原理**：

```cpp
class A {
public:
    virtual void foo() { cout << "A::foo" << endl; }
};

class B : public A {
public:
    void foo() override { cout << "B::foo" << endl; }
    virtual void bar() { cout << "B::bar" << endl; }
};

class C : public A {
    // 没有新虚函数，也没有重写 foo
};
```

**内存布局**：

| 类 | 对象内存布局 | 虚函数表内容 |
|---|------------|------------|
| A | vptr | A::foo |
| B | vptr | B::foo, B::bar |
| C | vptr | A::foo |

**调用过程**：
1. 通过对象指针找到 vptr
2. 通过 vptr 找到 vtable
3. 在 vtable 中查找函数地址
4. 调用实际函数

### 2.2 构造函数与析构函数

**构造函数不能是虚函数**：
- 虚函数依赖 vptr，而 vptr 在构造函数中才初始化
- 构造时对象类型还未完全确定

**析构函数应该是虚函数**：
```cpp
class Base {
public:
    virtual ~Base() {}  // 基类析构函数必须是虚函数
};

Base* p = new Derived();
delete p;  // 如果 ~Base 不是虚函数，Derived 的析构函数不会调用！
```

### 2.3 重写、重载、隐藏的区别

| 概念 | 英文 | 条件 | 特点 |
|------|------|------|------|
| **重载** | Overload | 同一作用域，函数名相同，参数不同 | 编译期绑定 |
| **重写** | Override | 派生类重写基类虚函数 | 运行期绑定（多态）|
| **隐藏** | Hide | 派生类定义与基类同名的非虚函数 | 基类函数被隐藏 |

### 2.4 多重继承与虚继承

**菱形继承问题**：
```cpp
class A { public: int x; };
class B : public A {};
class C : public A {};
class D : public B, public C {};  // D 中有两份 A::x
```

**解决方案：虚继承**
```cpp
class B : virtual public A {};
class C : virtual public A {};
class D : public B, public C {};  // D 中只有一份 A::x
```

---

## 三、智能指针

### 3.1 三种智能指针对比

| 智能指针 | 所有权 | 特点 | 适用场景 |
|---------|--------|------|---------|
| **unique_ptr** | 独占 | 不可复制，可移动 | 明确独占资源 |
| **shared_ptr** | 共享 | 引用计数 | 共享所有权 |
| **weak_ptr** | 弱引用 | 不增加引用计数 | 解决循环引用 |

### 3.2 shared_ptr 的实现原理

```cpp
template<typename T>
class shared_ptr {
    T* ptr;           // 指向对象的指针
    int* ref_count;   // 引用计数（堆上分配）
public:
    shared_ptr(T* p) : ptr(p), ref_count(new int(1)) {}

    ~shared_ptr() {
        if (--(*ref_count) == 0) {
            delete ptr;
            delete ref_count;
        }
    }

    shared_ptr(const shared_ptr& other)
        : ptr(other.ptr), ref_count(other.ref_count) {
        ++(*ref_count);
    }
};
```

**引用计数变化时机**：
- `+1`：构造、拷贝构造、赋值
- `-1`：析构、被赋值、reset

### 3.3 循环引用问题

```cpp
class B;
class A {
    shared_ptr<B> b_ptr;
};
class B {
    shared_ptr<A> a_ptr;  // 循环引用！
};

// 解决方案：使用 weak_ptr
class B {
    weak_ptr<A> a_ptr;  // 不增加引用计数
};
```

### 3.4 unique_ptr 的使用技巧

```cpp
// 1. 传递 unique_ptr 给函数
void process(unique_ptr<int> ptr) { }
void process_ref(const unique_ptr<int>& ptr) { }  // 只读
void process_raw(int* ptr) { }  // 解引用后传递

// 2. 修改 unique_ptr
unique_ptr<int> p = make_unique<int>(10);
p.reset(new int(20));      // 释放旧对象，管理新对象
int* raw = p.release();    // 释放所有权，返回原始指针
delete raw;  // 必须手动释放

// 3. 转移所有权
unique_ptr<int> p2 = std::move(p);  // p 变为空
```

---

## 四、STL 容器

### 4.1 常用容器对比

| 容器 | 底层结构 | 插入/删除 | 查找 | 特点 |
|------|---------|----------|------|------|
| **vector** | 动态数组 | 尾部 O(1)，中间 O(n) | O(n) | 连续内存，支持随机访问 |
| **list** | 双向链表 | O(1) | O(n) | 插入删除快，不支持随机访问 |
| **deque** | 分段数组 | 头尾 O(1)，中间 O(n) | O(n) | 双端队列 |
| **set/map** | 红黑树 | O(log n) | O(log n) | 有序，去重 |
| **unordered_set/map** | 哈希表 | 平均 O(1)，最坏 O(n) | 平均 O(1) | 无序，去重 |
| **priority_queue** | 堆（通常用 vector）| O(log n) | 顶部 O(1) | 优先级队列 |

### 4.2 vector 的扩容机制

```cpp
// push_back 时间复杂度分析
// - 普通情况：O(1)
// - 容量不足扩容：O(n)（需要复制所有元素）
// - 平均时间复杂度：O(1)（均摊分析）
```

**扩容策略**：
- GCC：2 倍扩容
- VS：1.5 倍扩容
- 扩容后迭代器全部失效

**迭代器失效场景**：
| 操作 | 失效迭代器 |
|------|-----------|
| push_back | 所有（如果触发扩容）|
| pop_back | end |
| insert/erase | 插入/删除点及之后的所有迭代器 |
| resize/reserve | 所有 |

### 4.3 map 的底层实现

**红黑树 vs AVL 树 vs B+ 树**：

| 特性 | 红黑树 | AVL 树 | B+ 树 |
|------|--------|--------|-------|
| 平衡性 | 弱平衡（黑高相同）| 严格平衡 | 多路平衡 |
| 查找 | O(log n) | O(log n) | O(log n) |
| 插入/删除 | O(log n)，旋转少 | O(log n)，旋转多 | O(log n) |
| 适用场景 | 内存中频繁修改 | 查找为主 | 磁盘存储 |

**为什么 map 用红黑树不用 AVL 树？**
- 红黑树插入/删除旋转次数更少
- 实际应用中性能差异不大
- STL 早期实现选择，沿用至今

---

## 五、C++11/14/17 新特性

### 5.1 右值引用与移动语义

```cpp
class Buffer {
    char* data;
    size_t size;
public:
    // 拷贝构造（深拷贝）
    Buffer(const Buffer& other)
        : data(new char[other.size]), size(other.size) {
        memcpy(data, other.data, size);
    }

    // 移动构造（窃取资源）
    Buffer(Buffer&& other) noexcept
        : data(other.data), size(other.size) {
        other.data = nullptr;  // 重要！
        other.size = 0;
    }
};
```

**使用场景**：
- 临时对象作为函数参数
- 函数返回大对象
- STL 容器操作（push_back、insert 等自动使用移动）

### 5.2 Lambda 表达式

```cpp
// 基本语法：[捕获列表](参数列表) -> 返回类型 { 函数体 }

// 值捕获
int x = 10;
auto f1 = [x]() { return x; };  // x 是拷贝

// 引用捕获
auto f2 = [&x]() { x++; };  // x 是引用

// 隐式捕获
auto f3 = [=]() { return x; };  // 值捕获所有
auto f4 = [&]() { x++; };       // 引用捕获所有

//  mutable：允许修改值捕获的变量
auto f5 = [x]() mutable { x++; return x; };
```

### 5.3 其他重要特性

| 特性 | 说明 | 示例 |
|------|------|------|
| **auto** | 类型自动推导 | `auto it = vec.begin();` |
| **nullptr** | 空指针常量 | `int* p = nullptr;` |
| **constexpr** | 编译期常量 | `constexpr int size = 100;` |
| **初始化列表** | 统一初始化 | `vector<int> v{1, 2, 3};` |
| **范围 for** | 遍历容器 | `for (auto& x : vec)` |
| **类型别名** | using 替代 typedef | `using IntPtr = int*;` |
| **变参模板** | 模板参数包 | `template<typename... Args>` |

---

## 六、多线程与并发

### 6.1 线程同步机制

| 机制 | 特点 | 适用场景 |
|------|------|---------|
| **mutex** | 互斥锁，独占访问 | 保护临界区 |
| **recursive_mutex** | 可重入锁 | 同一线程多次加锁 |
| **shared_mutex** | 读写锁 | 读多写少 |
| **condition_variable** | 条件变量 | 等待/通知机制 |
| **atomic** | 原子操作 | 简单数据类型 |

### 6.2 原子操作 vs 锁

```cpp
// 原子操作 - 效率高
atomic<int> counter;
counter.fetch_add(1);  // 无锁，硬件支持

// 互斥锁 - 通用但开销大
mutex mtx;
int counter = 0;
lock_guard<mutex> lock(mtx);
counter++;
```

**性能对比**：
- 原子操作：无上下文切换，开销最小
- 自旋锁：忙等待，适合短临界区
- 互斥锁：阻塞等待，适合长临界区

### 6.3 死锁的产生与避免

**死锁四个必要条件**：
1. 互斥条件
2. 占有并等待
3. 不可抢占
4. 循环等待

**避免策略**：
- 锁的顺序一致
- 使用 `std::lock` 同时加多个锁
- 使用超时锁 `try_lock_for`
- 避免在持有锁时调用外部代码

---

## 七、其他重要知识点

### 7.1 字节对齐

```cpp
struct Example {
    char a;     // 1 byte
    // 3 bytes padding
    int b;      // 4 bytes
    short c;    // 2 bytes
    // 2 bytes padding
};
// sizeof(Example) == 12 (不是 7)
```

**为什么需要字节对齐？**
- 硬件效率：CPU 总线一次读取 4/8 字节，对齐后可一次读取
- 指令集要求：某些 CPU 要求特定类型必须对齐

### 7.2 const 关键字的各种用法

```cpp
// 1. const 变量
const int a = 10;

// 2. const 指针
const int* p1;      // 指向常量的指针（值不能改）
int* const p2;      // 常量指针（指向不能改）
const int* const p3; // 指向常量的常量指针

// 3. const 成员函数
class Foo {
    int x;
public:
    int get() const {  // 不修改成员变量
        return x;
    }
};

// 4. const 引用参数
void process(const string& str);  // 避免拷贝，不修改原值
```

### 7.3 类型转换运算符

| 运算符 | 用途 | 安全性 |
|--------|------|--------|
| **static_cast** | 相关类型转换 | 编译期检查 |
| **dynamic_cast** | 多态类型向下转换 | 运行期检查，失败返回 nullptr |
| **const_cast** | 添加/移除 const | 可能不安全 |
| **reinterpret_cast** | 底层位重新解释 | 危险，慎用 |

### 7.4 RAII 思想

**Resource Acquisition Is Initialization**（资源获取即初始化）

```cpp
// 文件句柄管理
class FileHandle {
    FILE* fp;
public:
    FileHandle(const char* path, const char* mode) {
        fp = fopen(path, mode);
        if (!fp) throw runtime_error("打开失败");
    }

    ~FileHandle() {
        if (fp) fclose(fp);  // 确保关闭
    }

    // 禁止拷贝
    FileHandle(const FileHandle&) = delete;
    FileHandle& operator=(const FileHandle&) = delete;
};

// 使用
void process() {
    FileHandle file("data.txt", "r");  // 构造时打开
    // 使用 file...
}  // 析构时自动关闭，即使发生异常
```

---

## 八、推荐书单

| 书籍 | 难度 | 说明 |
|------|------|------|
| 《C++ Primer》| 入门 | 全面学习 C++ |
| 《深度探索 C++ 对象模型》| 进阶 | 理解对象内存布局 |
| 《Effective C++》| 进阶 | 55 条编程建议 |
| 《More Effective C++》| 进阶 | 更多编程技巧 |
| 《STL 源码剖析》| 高级 | 深入理解 STL 实现 |
| 《C++ 并发编程实战》| 高级 | 多线程编程 |

---

> 📌 **面试技巧**：C++ 面试重视基础，尤其是内存管理、多态机制、STL 原理。建议深入理解底层实现，而非仅停留在使用层面。
