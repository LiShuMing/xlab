# C++/OLAP 面试问题详解

> 来源文档：`interview-questions.md`
> 整理时间：2026-03-04
> 目标：融会贯通，深度理解

---

## Part 1: C++ 核心

### 1.1 内存管理

#### 1.1.1 C++ 内存布局

**问题**：C++ 程序的内存空间是如何分布的？

**详解**：

```
高地址
+----------------------+
|       Stack          |  栈区：函数参数、局部变量、返回地址
|         ↓            |  向下增长，由编译器自动管理
+----------------------+
|         ↑            |
|       free           |  空闲内存
|         ↓            |
+----------------------+
|       Heap           |  堆区：动态分配 (malloc/new)
|                      |  向上增长，需手动管理
+----------------------+
|   Uninitialized Data |  BSS 段：未初始化全局/静态变量
|      (BSS)           |  程序启动时清零
+----------------------+
|   Initialized Data   |  数据段：已初始化全局/静态变量
|      (Data)          |  包含 const 全局变量
+----------------------+
|       Code           |  代码段：机器指令
|      (Text)          |  只读，防止意外修改
+----------------------+
|      Constants       |  常量区：字符串字面量等
+----------------------+
低地址
```

**各段详解**：

| 段名 | 内容 | 管理方式 | 生命周期 |
|------|------|----------|----------|
| 栈 (Stack) | 局部变量、函数参数、返回地址 | 编译器自动 | 函数作用域 |
| 堆 (Heap) | 动态分配对象 | 程序员手动 | 手动释放 |
| BSS 段 | 未初始化全局变量、静态变量 | 系统 | 程序整个生命周期 |
| 数据段 | 已初始化全局变量、静态变量 | 系统 | 程序整个生命周期 |
| 代码段 | 可执行指令 | 只读 | 程序整个生命周期 |
| 常量区 | 字符串字面量、const 变量 | 只读 | 程序整个生命周期 |

**示例代码**：

```cpp
int global_init = 10;        // 数据段
int global_uninit;           // BSS 段
static int static_init = 5;  // 数据段
static int static_uninit;    // BSS 段

void func() {
    int local = 20;          // 栈区
    int* heap = new int(30); // 堆区
}

const char* str = "hello";   // str 在数据段，"hello" 在常量区
```

---

#### 1.1.2 new 和 malloc 的区别

**问题**：C++ 中 new 和 malloc 有什么本质区别？

**详解**：

| 特性 | new/delete | malloc/free |
|------|------------|-------------|
| 本质 | 运算符 | 库函数 |
| 来源 | C++ 语言特性 | C 标准库 |
| 类型安全 | 是，返回具体类型 | 否，返回 void* |
| 构造函数 | 自动调用 | 不调用 |
| 析构函数 | 自动调用 | 不调用 |
| 大小计算 | 自动计算 | 需手动指定 |
| 失败处理 | 抛异常 | 返回 nullptr |
| 数组支持 | new[]/delete[] | 无特殊支持 |

**底层实现**：

```cpp
// new 的底层实现（概念性）
template<typename T>
T* new_impl() {
    // 1. 调用 operator new 分配原始内存（底层可能调用 malloc）
    void* raw_mem = operator new(sizeof(T));

    // 2. 在分配的内存上构造对象
    T* obj = static_cast<T*>(raw_mem);
    construct(obj);  // 调用构造函数

    return obj;
}

// malloc 的底层实现
void* malloc(size_t size) {
    // 1. 查找合适的空闲块
    // 2. 拆分空闲块（如果必要）
    // 3. 更新元数据
    // 4. 返回用户可用指针
}
```

**内存分配流程**：

```
new int[100] 执行流程：
1. 调用 operator new[] 计算所需大小 (100 * sizeof(int) + 元数据)
2. 底层调用 malloc 或系统调用 (brk/mmap)
3. 返回原始内存指针
4. 对每个元素调用构造函数

malloc(100 * sizeof(int)) 执行流程：
1. 查找空闲链表
2. 分配内存块
3. 返回指针
4. 不调用任何构造函数
```

---

#### 1.1.3 brk 和 mmap 的区别

**问题**：malloc 底层使用 brk 和 mmap 的区别？如何选择？

**详解**：

```
内存分配阈值（glibc 默认）：128KB

小内存 (< 128KB) → brk
大内存 (>= 128KB) → mmap
```

**brk 方式**：
```
进程数据段末尾（堆顶）向上移动
优点：
- 分配速度快
- 适合频繁小对象分配
- 内存页可复用

缺点：
- free 后不立即归还系统
- 只能从堆顶释放
- 容易产生碎片

内存布局：
[已有数据] [已分配] [空闲] [堆顶 brk]
                    ↑
                   free 后保留
```

**mmap 方式**：
```
在进程地址空间映射新的内存区域
优点：
- free 后立即归还系统
- 减少堆碎片
- 适合大块内存

缺点：
- 系统调用开销大
- TLB 失效可能

内存布局：
[堆区] ... [内存空洞] [mmap 映射区 1] [mmap 映射区 2]
```

**代码示例**：

```cpp
// 小内存 - 使用 brk
char* p1 = (char*)malloc(1024);      // 1KB，brk
char* p2 = (char*)malloc(100 * 1024); // 100KB，brk

// 大内存 - 使用 mmap
char* p3 = (char*)malloc(200 * 1024); // 200KB，mmap

// 释放行为
free(p1);  // 保留在进程中，不归还
free(p3);  // 调用 munmap，归还系统
```

**阈值调整**：

```cpp
#include <malloc.h>

// 获取当前阈值
size_t threshold = mallinfo2().mmap_threshold;

// 设置阈值（单位：字节）
mallopt(M_MMAP_THRESHOLD, 256 * 1024);  // 设置为 256KB
```

---

#### 1.1.4 为什么 free 后不立即归还系统

**问题**：使用 brk 分配内存时，free 后为什么不立即归还给操作系统？

**详解**：

**原因一：性能优化**

```
系统调用开销对比：
- 用户态 malloc/free: ~10-100 纳秒
- 内核态 brk/sbrk:  ~1000+ 纳秒

频繁归还再申请 = 频繁系统调用 = 性能急剧下降
```

**场景模拟**：
```cpp
// 反例：如果每次都归还
for (int i = 0; i < 10000; ++i) {
    char* p = (char*)malloc(64);
    // ... 使用
    free(p);  // 如果这里调用 brk 归还
}
// 结果：20000 次系统调用，性能极差

// 正例：保留空闲块
for (int i = 0; i < 10000; ++i) {
    char* p = (char*)malloc(64);  // 从空闲链表直接获取
    // ... 使用
    free(p);  // 放入空闲链表，不调用 brk
}
// 结果：0 次系统调用，性能优秀
```

**原因二：减少碎片化**

```
外部碎片问题：
[已用][空闲 8B][已用][空闲 8B][已用][空闲 8B]...
总空闲 = 80KB，但无法分配 16KB 连续块

如果立即归还：
- 堆变得支离破碎
- 大块分配失败率增加

延迟归还策略：
- 保留空闲块在进程中
- 内存管理器可合并相邻空闲块
- 提高后续分配成功率
```

**原因三：内存复用**

```
典型应用模式：
while (running) {
    Data* d = new Data();  // 分配
    process(d);
    delete d;  // 释放
}

如果保留内存：
- 下次 new Data() 可复用同一块内存
- 减少内存分配器工作量
- 提高缓存命中率
```

**glibc 的延迟释放策略**：

```
1. 内存块放入空闲链表（fastbins、smallbins、largebins）
2. 只有堆顶连续大块空闲时，才调用 sbrk 归还
3. 使用 M_TRIM_THRESHOLD 控制何时归还

mallopt(M_TRIM_THRESHOLD, 128 * 1024);
// 当堆顶空闲块 >= 128KB 时，才归还给系统
```

---

#### 1.1.5 频繁 malloc 小块内存的问题

**问题**：频繁申请和释放小块内存会导致什么问题？

**详解**：

**问题一：内存碎片化**

```
内部碎片（Internal Fragmentation）：
- 分配的块比实际需要大
- 原因：对齐要求、元数据开销

示例：
请求 8 字节 → 实际分配 16 字节（8 字节用户数据 + 8 字节元数据）
内部碎片 = 8 字节（50% 浪费）

外部碎片（External Fragmentation）：
- 空闲内存分散在不连续的小块中
- 总空闲足够，但无法分配大块

示例：
[已用 8B][空闲 8B][已用 8B][空闲 8B][已用 8B][空闲 8B]
总空闲 = 24B，但无法分配 16B 连续块
```

**问题二：管理开销增加**

```
malloc 元数据开销：
- 每个块需要 8-16 字节元数据（大小、状态、前后向指针）
- 小块内存：元数据占比可达 50%-100%

示例：分配 8 字节
[8B 元数据][8B 用户数据]
元数据占比 = 50%

时间开销：
- 每次 malloc/free 需要遍历空闲链表
- 更新元数据、合并/拆分块
- 频繁操作导致 CPU 缓存失效
```

**问题三：系统调用增加**

```
当空闲链表无法满足请求时：
- 触发 brk 扩展堆顶
- 或 mmap 创建新映射
- 系统调用开销是用户态操作的 10-100 倍
```

**解决方案：内存池**

```cpp
class MemoryPool {
private:
    struct Block {
        Block* next;
    };

    Block* free_list;
    size_t block_size;

public:
    MemoryPool(size_t size, size_t count)
        : block_size(size) {
        // 一次性分配大块内存
        char* memory = (char*)malloc(size * count + sizeof(Block*));
        free_list = reinterpret_cast<Block*>(memory);

        // 构建空闲链表
        Block* current = free_list;
        for (size_t i = 0; i < count - 1; ++i) {
            current->next = reinterpret_cast<Block*>(
                reinterpret_cast<char*>(current) + size
            );
            current = current->next;
        }
        current->next = nullptr;
    }

    void* allocate() {
        if (!free_list) return nullptr;
        Block* block = free_list;
        free_list = free_list->next;
        return block;
    }

    void deallocate(void* ptr) {
        Block* block = reinterpret_cast<Block*>(ptr);
        block->next = free_list;
        free_list = block;
    }
};

// 使用
MemoryPool pool(64, 1000);  // 预分配 1000 个 64 字节块
void* p = pool.allocate();   // O(1) 时间
pool.deallocate(p);          // O(1) 时间
```

---

#### 1.1.6 malloc 如何管理内存碎片

**问题**：malloc 是如何管理内存碎片的？

**详解**：

**glibc 的分级分配器（Segregated Free Lists）**

```
空闲块按大小分类存储：

fastbins (快速分配箱):
- 大小：16-64 字节（32 位系统）
- 结构：LIFO 栈
- 特点：最快，不合并

smallbins:
- 大小：64-512 字节
- 每个 bin 存储相同大小的块
- 特点：O(1) 查找

largebins:
- 大小：512 字节以上
- 按大小范围分组
- 特点：需要查找合适块

unsorted bin:
- 临时存储刚释放的块
- 下次分配时再分类
```

**内存布局示意**：

```
堆内存布局：
[已分配块][空闲块 (fastbin)][已分配块][空闲块 (smallbin)]

空闲链表组织：
fastbins[0] → [16B 块 1] → [16B 块 2] → nullptr
fastbins[1] → [24B 块 1] → nullptr
smallbins[4] → [128B 块 1] ↔ [128B 块 2] ↔ ...
```

**空闲块合并（Coalescing）**

```
释放时的合并策略：

释放块 P 时：
1. 检查物理相邻的下一个块是否空闲
   - 是：合并 P 和下一块
2. 检查物理相邻的前一个块是否空闲
   - 是：合并前一块和 P（可能已合并下一块）

边界标记法（Boundary Tag）：
[块头部：大小|状态][用户数据][块尾部：大小|状态]
                      ↑
                   前一块的尾部在此
```

**分配策略**：

```
First-Fit（首次适配）:
- 找到第一个足够大的空闲块
- 优点：快
- 缺点：容易产生小碎片

Best-Fit（最佳适配）:
- 找到大小最接近的空闲块
- 优点：剩余碎片小
- 缺点：需要遍历更多块

Next-Fit（下次适配）:
- 从上次查找位置继续
- 优点：分布更均匀
- 缺点：可能错过合适块

glibc 实际使用组合策略
```

**内存块拆分**：

```
请求 20 字节，最小块大小 16 字节：

空闲块：[32 字节空闲]

拆分后：
[16 字节元数据 + 用户数据][16 字节新空闲块]

拆分条件：
- 剩余部分 >= 最小块大小
- 否则整块分配（产生内部碎片）
```

**延迟归还系统**：

```
只有满足以下条件时才归还：
1. 堆顶（top chunk）连续空闲
2. 空闲大小 >= M_TRIM_THRESHOLD（默认 128KB）

好处：
- 避免频繁的 brk 调用
- 快速响应后续分配请求
```

---

### 1.2 智能指针

#### 1.2.1 三种智能指针的区别

**问题**：C++11 中三种智能指针的区别和使用场景？

**详解**：

| 类型 | 所有权 | 引用计数 | 线程安全 | 使用场景 |
|------|--------|----------|----------|----------|
| `unique_ptr` | 独占 | 无 | 否（但可安全转移） | 独占资源、转移语义 |
| `shared_ptr` | 共享 | 有 | 计数原子，内容非原子 | 共享资源、引用计数 |
| `weak_ptr` | 弱引用 | 无 | 否 | 打破循环引用、观察对象 |

**内存布局**：

```
shared_ptr 结构：
[shared_ptr 对象]
    ↓
[控制块 control_block]
    - 引用计数 (use_count)
    - 弱引用计数 (weak_count)
    - 删除器 (deleter)
    - 指向管理对象
    ↓
[实际管理对象 T]

weak_ptr 结构：
[weak_ptr 对象]
    ↓
[指向同一控制块]
    - 可检查对象是否存在
    - 不增加引用计数
```

**引用计数变化时机**：

```cpp
std::shared_ptr<int> p1 = std::make_shared<int>(42);
// 控制块创建，use_count = 1, weak_count = 0

{
    std::shared_ptr<int> p2 = p1;  // 拷贝构造，use_count = 2
    std::shared_ptr<int> p3 = p1;  // 拷贝构造，use_count = 3

    std::weak_ptr<int> w1 = p1;    // 创建 weak_ptr，weak_count = 1
    std::weak_ptr<int> w2 = p2;    // weak_count = 2
}
// p2, p3 析构，use_count 减 2，回到 1
// weak_ptr 不影响 use_count

p1.reset();  // p1 释放，use_count = 0
// 对象被销毁，但控制块还在（因为有 weak_ptr）
// weak_count 仍为 2

w1.reset();  // weak_count = 1
w2.reset();  // weak_count = 0
// 控制块最终被释放
```

---

#### 1.2.2 循环引用问题

**问题**：shared_ptr 循环引用如何解决？

**详解**：

**循环引用示意**：

```cpp
class B;  // 前向声明

class A {
public:
    std::shared_ptr<B> b;
    ~A() { std::cout << "A 析构\n"; }
};

class B {
public:
    std::shared_ptr<A> a;
    ~B() { std::cout << "B 析构\n"; }
};

void test() {
    auto a = std::make_shared<A>();
    auto b = std::make_shared<B>();

    a->b = b;  // a 持有 b，b 的引用计数 +1
    b->a = a;  // b 持有 a，a 的引用计数 +1

    // 离开作用域：
    // a 析构，a 的引用计数 -1，但仍为 1（b 持有）
    // b 析构，b 的引用计数 -1，但仍为 1（a 持有）
    // 结果：a 和 b 都不会被释放，内存泄漏！
}
```

**使用 weak_ptr 解决**：

```cpp
class B;

class A {
public:
    std::shared_ptr<B> b;
    ~A() { std::cout << "A 析构\n"; }
};

class B {
public:
    std::weak_ptr<A> a;  // 弱引用，不增加计数
    ~B() { std::cout << "B 析构\n"; }

    // 需要访问 A 时
    void useA() {
        if (auto sp = a.lock()) {  // 提升为 shared_ptr
            // 使用 sp->...
        } else {
            // A 已经被释放
        }
    }
};

void test() {
    auto a = std::make_shared<A>();
    auto b = std::make_shared<B>();

    a->b = b;     // a 持有 b
    b->a = a;     // b 弱引用 a，不增加计数

    // 离开作用域：
    // a 析构，a 的引用计数 = 0，A 被销毁
    // b 析构，b 的引用计数 = 0，B 被销毁
    // 正确释放！
}
```

**典型场景：父子节点**

```cpp
class Child;

class Parent {
public:
    std::vector<std::shared_ptr<Child>> children;
};

class Child {
public:
    std::weak_ptr<Parent> parent;  // 子节点对父节点用 weak_ptr
};
```

---

### 1.3 对象模型与多态

#### 1.3.1 空类大小

**问题**：C++ 空类的最小占用空间是多少？为什么？

**详解**：

```cpp
class Empty {};
static_assert(sizeof(Empty) == 1);

class EmptyWithVirtual {
    virtual void foo() {}
};
// sizeof(EmptyWithVirtual) = 8 (64 位系统，虚表指针)
```

**为什么是 1 字节而不是 0 字节**：

```
原因 1：保证对象地址唯一性
class Empty {};
Empty e1, e2;
// 如果 sizeof(Empty) = 0，则 &e1 和 &e2 可能相同
// 这违反了"每个对象有唯一地址"的原则

原因 2：支持指针运算
Empty arr[3];
Empty* p = &arr[0];
p++;  // 如果 sizeof=0，p++ 后地址不变，无法指向下一个元素

原因 3：支持数组
Empty arr[5];
// 需要 5 个不同的地址，每个至少占 1 字节
```

**为什么不是大于 1 字节**：

```
- 1 字节是最小可寻址单位
- 再多就是浪费
- 编译器会做字节对齐，但空类本身只需 1 字节
```

---

#### 1.3.2 虚函数表机制

**问题**：虚函数是如何实现的？请说明虚表的工作原理。

**详解**：

**虚表结构**：

```
类 A 有一个虚函数 foo():

A 对象内存布局 (64 位系统)：
+------------------+
| vptr (8 字节)     |  指向虚函数表
+------------------+
| 成员变量         |
+------------------+

A 的虚函数表：
+------------------+
| &A::foo          |
+------------------+
```

**继承情况**：

```cpp
class A {
public:
    virtual void foo() { cout << "A::foo\n"; }
};

class B : public A {
public:
    virtual void bar() { cout << "B::bar\n"; }
};

class C : public A {
public:
    virtual void foo() override { cout << "C::foo\n"; }
};
```

**内存布局**：

```
A 对象：[vptr_A] → A 虚表：[&A::foo]

B 对象：[vptr_B] → B 虚表：[&A::foo, &B::bar]
                    ↑继承自 A    ↑B 新增

C 对象：[vptr_C] → C 虚表：[&C::foo]  // 重写 A 的 foo
                    ↑指向 C 的实现
```

**虚函数调用过程**：

```cpp
A* p = new B();
p->foo();  // 调用 A::foo

执行过程：
1. 通过 p 找到 B 对象
2. 读取 vptr_B，找到 B 的虚表
3. 查找 foo 在虚表中的位置（索引 0）
4. 跳转到 &A::foo 执行
```

**为什么构造函数不能是虚函数**：

```
原因：虚表指针在构造函数中初始化

对象构造顺序：
1. 分配内存
2. 初始化虚表指针（指向当前构造类的虚表）
3. 执行构造函数体

如果构造函数是虚函数：
- 调用虚函数需要虚表指针
- 但虚表指针还没初始化
- 鸡生蛋问题！

实际行为：
- 基类构造时，虚表指针指向基类虚表
- 派生类构造时，虚表指针被更新为指向派生类虚表
- 构造期间多态不起作用
```

**为什么析构函数应该是虚函数**：

```cpp
class Base {
public:
    ~Base() { cout << "~Base\n"; }
};

class Derived : public Base {
    char* buffer;
public:
    Derived() { buffer = new char[1024]; }
    ~Derived() {
        cout << "~Derived\n";
        delete[] buffer;  // 如果不调用这里，内存泄漏！
    }
};

void test() {
    Base* p = new Derived();
    delete p;  // 如果~Base 不是虚函数，只调用~Base
}
// 结果：~Derived 没被调用，buffer 泄漏！

修正：
class Base {
public:
    virtual ~Base() = default;  // 虚析构
};
// delete p 会正确调用~Derived，然后自动调用~Base
```

---

#### 1.3.3 指针常量 vs 常量指针

**问题**：指针常量和常量指针的区别？

**详解**：

```cpp
// 指针常量 (pointer to const)
// 读作：指向 const 的指针
const int* ptr1;
int const* ptr1;  // 等价写法

// 含义：ptr1 指向的值不能通过 ptr1 修改
int value = 10;
const int* ptr1 = &value;
*ptr1 = 20;  // 错误！不能通过 ptr1 修改
value = 20;  // 正确！可以直接修改
ptr1 = &value;  // 正确！ptr1 本身可以改变指向


// 常量指针 (const pointer)
// 读作：const 指针
int* const ptr2 = &value;

// 含义：ptr2 本身不能改变指向，但可以通过 ptr2 修改值
*ptr2 = 30;  // 正确！可以修改指向的值
int other = 40;
ptr2 = &other;  // 错误！ptr2 是常量，不能改变指向


// 常量指针指向常量
const int* const ptr3 = &value;

// 含义：既不能修改指向，也不能通过 ptr3 修改值
*ptr3 = 50;  // 错误！
ptr3 = &other;  // 错误！
```

**记忆技巧**：

```
const 在*左边 → 指向常量
const 在*右边 → 指针常量
const 在*两边 → 都常量

从右往左读：
const int* p → p 是指向 const int 的指针
int* const p → p 是 const 指针，指向 int
```

---

### 1.4 RAII 与资源管理

#### 1.4.1 RAII 思想

**问题**：RAII 是什么？如果打开文件失败如何处理？

**详解**：

**RAII (Resource Acquisition Is Initialization)**

```
核心思想：
- 资源获取即初始化
- 资源生命周期绑定对象生命周期
- 构造函数获取资源，析构函数释放资源
- 无需手动释放，异常安全
```

**示例：文件描述符包装**：

```cpp
class FileDescriptor {
private:
    int fd;
    bool valid;

public:
    explicit FileDescriptor(const char* path, int flags)
        : fd(-1), valid(false) {
        fd = open(path, flags);
        if (fd == -1) {
            // 打开失败，抛出异常
            throw std::system_error(errno, std::generic_category(),
                                   "Failed to open file");
        }
        valid = true;
    }

    ~FileDescriptor() {
        if (valid) {
            close(fd);  // 自动关闭
        }
    }

    // 禁止拷贝
    FileDescriptor(const FileDescriptor&) = delete;
    FileDescriptor& operator=(const FileDescriptor&) = delete;

    // 允许移动
    FileDescriptor(FileDescriptor&& other) noexcept
        : fd(other.fd), valid(other.valid) {
        other.valid = false;  // 防止其他对象析构时关闭
    }

    int get() const { return fd; }
    bool isValid() const { return valid; }
};

// 使用
void readFile() {
    try {
        FileDescriptor fd("/path/to/file", O_RDONLY);
        // 使用 fd.get() 读取
        // 离开作用域自动 close，即使抛出异常
    } catch (const std::system_error& e) {
        // 处理打开失败
        std::cerr << "Open failed: " << e.what() << std::endl;
    }
    // fd 在这里自动关闭
}
```

**打开失败的处理策略**：

```
1. 抛出异常（推荐）
   - 构造函数中 open 失败抛异常
   - 对象未完全构造，不会调用析构
   - 调用方捕获并处理

2. 设置错误标志
   - 成员变量标记 valid = false
   - 提供 isValid() 方法检查
   - 析构函数检查 valid 再 close

3. 返回 optional
   - C++17 std::optional<FileDescriptor>
   - 无值表示失败
```

---

### 1.5 C++11/14/17/20 特性

#### 1.5.1 移动语义

**问题**：移动语义的原理是什么？

**详解**：

**左值 vs 右值**：

```cpp
int x = 42;       // 左值，有名字，可取地址
int& lref = x;    // 左值引用

int&& rref = 42;  // 右值引用，绑定到临时值

// 右值分类
std::move(x);     // 将左值转为右值（xvalue）
42;               // 纯右值（prvalue）
```

**移动构造函数**：

```cpp
class Buffer {
private:
    char* data;
    size_t size;

public:
    // 拷贝构造（深拷贝）
    Buffer(const Buffer& other)
        : size(other.size) {
        data = new char[size];
        std::copy(other.data, other.data + size, data);
        std::cout << "拷贝构造\n";
    }

    // 移动构造（资源窃取）
    Buffer(Buffer&& other) noexcept
        : data(other.data), size(other.size) {
        other.data = nullptr;  // 重要！防止重复释放
        other.size = 0;
        std::cout << "移动构造\n";
    }

    ~Buffer() {
        delete[] data;
    }
};

// 使用
Buffer createBuffer() {
    Buffer tmp(1024);
    return tmp;  // 返回值优化或移动
}

Buffer b1 = createBuffer();  // 移动构造，不拷贝数据
```

**std::move 的本质**：

```cpp
// std::move 实现（简化）
template<typename T>
typename std::remove_reference<T>::type&& move(T&& t) noexcept {
    return static_cast<typename std::remove_reference<T>::type&&>(t);
}

// 本质：强制类型转换为右值引用
// 不移动任何东西！只是允许移动

std::string s = "hello";
std::string t = std::move(s);
// s 进入"有效但未指定"状态
// 可以销毁 s，但不能使用 s 的值
```

---

#### 1.5.2 Lambda 表达式

**问题**：Lambda 表达式的捕获规则？

**详解**：

```cpp
int x = 1, y = 2, z = 3;

// 值捕获（拷贝）
auto f1 = [x, y]() {
    return x + y;  // x, y 是原变量的副本
};

// 引用捕获
auto f2 = [&x, &y]() {
    x++; y++;  // 修改原变量
};

// 混合捕获
auto f3 = [x, &y]() {
    x++; y++;  // x 是副本，y 是引用
};

// 引用捕获所有
auto f4 = [&](int a) {
    return x + y + a + z;  // 所有外部变量都是引用
};

// 值捕获所有
auto f5 = [=](int a) {
    return x + y + a + z;  // 所有外部变量都是副本
};

// C++14 初始化捕获
auto f6 = [w = x + y]() {
    return w * 2;  // w 是计算后的新变量
};

// 移动捕获（C++14）
std::unique_ptr<int> p = std::make_unique<int>(42);
auto f7 = [p = std::move(p)]() {
    return *p;  // p 被移动到 lambda 内部
};

// this 捕获
class A {
    int value = 10;
public:
    auto getFunc() {
        return [this]() {  // 捕获 this 指针
            return value;  // 等价于 this->value
        };
    }
};
```

**捕获列表规则**：

```
[x]      - 值捕获 x
[&x]     - 引用捕获 x
[=]      - 值捕获所有使用到的变量
[&]      - 引用捕获所有使用到的变量
[this]   - 捕获 this 指针
[x, &y]  - 混合捕获
[=, &z]  - 默认值捕获，但 z 引用捕获
[&, x]   - 默认引用捕获，但 x 值捕获
```

---

## Part 2: 操作系统与系统编程

### 2.1 进程与线程

#### 2.1.1 进程和线程的区别

**问题**：进程和线程的本质区别是什么？

**详解**：

| 特性 | 进程 | 线程 |
|------|------|------|
| 资源拥有 | 独立的地址空间 | 共享进程资源 |
| CPU 调度 | 不是调度单位 | 是调度基本单位 |
| 通信方式 | IPC（管道、消息队列、共享内存） | 直接读写共享数据 |
| 切换开销 | 大（TLB 刷新、页表切换） | 小（只切换寄存器和栈） |
| 创建开销 | fork/exec 或 CreateProcess | pthread_create |
| 独立性 | 强，崩溃不影响其他进程 | 弱，崩溃可能导致整个进程终止 |
| 文件描述符 | 独立 | 共享 |

**线程共享的资源**：

```
同一进程内的线程共享：
- 代码段（程序指令）
- 数据段（全局变量）
- 堆（动态分配的内存）
- 文件描述符
- 信号处理函数
- 当前工作目录

线程私有的资源：
- 栈（函数调用帧）
- 寄存器（程序计数器、栈指针等）
- 线程局部存储（TLS）
- 错误码（errno）
```

**内存布局对比**：

```
进程内存布局：
+------------------+
|     代码段       |
+------------------+
|     数据段       |
+------------------+
|       堆         |
+------------------+
|   共享库映射     |
+------------------+
|  线程 1 栈 (向下)  |
+------------------+
|  线程 2 栈 (向下)  |
+------------------+
|  线程 3 栈 (向下)  |
+------------------+
```

---

#### 2.1.2 线程同步方式

**问题**：线程同步方式有哪些？哪种效率最高？

**详解**：

**同步方式对比**：

| 方式 | 原理 | 优点 | 缺点 | 适用场景 |
|------|------|------|------|----------|
| 互斥锁 | 独占访问 | 简单易用 | 有上下文切换 | 一般临界区 |
| 自旋锁 | 忙等待 | 无上下文切换 | 浪费 CPU | 锁持有时间短 |
| 读写锁 | 读共享写独占 | 读多写少高效 | 写锁饥饿 | 读多写少 |
| 条件变量 | 等待通知 | 灵活 | 需配合锁 | 条件等待 |
| 原子操作 | 硬件指令 | 最高效 | 只能简单操作 | 计数器、标志位 |

**效率分析**：

```
原子操作 > 自旋锁 (短时) > 互斥锁 (无竞争) > 互斥锁 (有竞争)

原子操作最高效的原因：
1. 硬件级别支持（CAS、LL/SC 指令）
2. 无需陷入内核
3. 无线程阻塞/唤醒
4. 无上下文切换

但局限性：
- 只能用于简单数据（计数器、标志位）
- 复杂逻辑需要组合多个原子操作，难度高
```

**代码示例**：

```cpp
// 1. 互斥锁
std::mutex mtx;
mtx.lock();
critical_section();
mtx.unlock();

// 2. 自旋锁（C++11 实现）
class SpinLock {
    std::atomic<bool> flag{false};
public:
    void lock() {
        bool expected = false;
        while (!flag.compare_exchange_weak(expected, false)) {
            // 忙等待
            expected = false;
        }
    }
    void unlock() { flag.store(false); }
};

// 3. 原子操作（最高效）
std::atomic<int> count{0};
count.fetch_add(1, std::memory_order_relaxed);
```

---

#### 2.1.3 死锁

**问题**：死锁产生的条件？如何预防和调试？

**详解**：

**死锁四条件（同时满足）**：

```
1. 互斥条件：资源一次只能被一个线程占用
2. 请求与保持：线程持有资源的同时请求其他资源
3. 不剥夺：已获得的资源不能被强制剥夺
4. 循环等待：存在循环等待链 A→B→C→A
```

**死锁示例**：

```cpp
std::mutex mtx_a, mtx_b;

void thread1() {
    mtx_a.lock();
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
    mtx_b.lock();  // 可能死锁
    // ...
    mtx_b.unlock();
    mtx_a.unlock();
}

void thread2() {
    mtx_b.lock();
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
    mtx_a.lock();  // 与 thread1 顺序相反，死锁！
    // ...
    mtx_a.unlock();
    mtx_b.unlock();
}
```

**预防方法**：

```
1. 破坏循环等待：按顺序加锁
   - 给锁编号，总是先小号后大号
   - 使用 std::lock() 原子获取多把锁

2. 破坏请求与保持：一次性申请所有资源
   - 申请前检查所有资源是否可用
   - 不可用时不持有任何资源

3. 破坏不剥夺：允许超时
   - 使用 try_lock_for/try_lock_until
   - 超时后释放已持有的锁

4. 破坏互斥条件：使用无锁数据结构
   - 原子操作
   - 无锁队列
```

**预防代码**：

```cpp
// 方法 1：std::lock 原子获取
void safe_lock() {
    std::lock(mtx_a, mtx_b);  // 原子获取，不会死锁
    std::lock_guard<std::mutex> lock1(mtx_a, std::adopt_lock);
    std::lock_guard<std::mutex> lock2(mtx_b, std::adopt_lock);
}

// 方法 2：按顺序加锁
void ordered_lock() {
    if (&mtx_a < &mtx_b) {
        mtx_a.lock(); mtx_b.lock();
    } else {
        mtx_b.lock(); mtx_a.lock();
    }
}

// 方法 3：超时尝试
void try_lock_with_timeout() {
    if (mtx_a.try_lock_for(std::chrono::seconds(1))) {
        if (mtx_b.try_lock_for(std::chrono::seconds(1))) {
            // 成功获取两把锁
            mtx_b.unlock();
        }
        mtx_a.unlock();
    }
}
```

**GDB 调试死锁**：

```bash
# 附加到进程
gdb -p <pid>

# 查看所有线程
info threads

# 查看每个线程的调用栈
thread apply all bt

# 查找锁等待
# 如果线程停在 pthread_cond_wait 或 futex，可能在等待锁

# 查看互斥锁状态
print *(pthread_mutex_t*)&mtx_a
```

---

### 2.2 I/O 模型

#### 2.2.1 五种 I/O 模型

**问题**：比较阻塞、非阻塞、I/O 多路复用、信号驱动、异步 I/O

**详解**：

**模型对比**：

```
以 recv 为例：

1. 阻塞 I/O (blocking I/O)
   应用进程                    内核
   |---- recv() ------------>|
   |                         | 等待数据到达
   |                         |<---- 数据到达 ----
   |                         | 拷贝到用户空间
   |<--- 返回数据 -----------|
   特点：recv 调用一直阻塞，直到数据到达并拷贝完成

2. 非阻塞 I/O (non-blocking I/O)
   |---- recv() ------------>|
   |<--- EAGAIN -------------| 数据未到达，立即返回错误
   |                         |
   |---- recv() ------------>| 轮询
   |<--- EAGAIN -------------|
   |                         |<---- 数据到达 ----
   |---- recv() ------------>|
   |<--- 返回数据 -----------|
   特点：数据未到达时立即返回，需要轮询

3. I/O 多路复用 (I/O multiplexing)
   |---- select() ---------->|
   |                         | 等待多个 fd 中的任何一个就绪
   |<--- 就绪通知 -----------|
   |---- recv() ------------>|
   |<--- 返回数据 -----------|
   特点：一次等待多个 fd，需要两次系统调用

4. 信号驱动 I/O (signal driven I/O)
   |---- 启用信号驱动 ------>|
   |---- 继续执行其他任务 ----|
   |                         |<---- 数据到达 ----
   |<--- SIGIO 信号 ---------|
   |---- recv() ------------>|
   |<--- 返回数据 -----------|
   特点：内核就绪时发送信号，异步通知

5. 异步 I/O (asynchronous I/O)
   |---- aio_read() -------->|
   |---- 继续执行其他任务 ----|
   |                         | 等待数据、拷贝数据
   |<--- 完成通知 -----------|
   特点：内核完成所有操作后通知，真正的异步
```

**为什么 epoll 性能最好**：

```
select/poll 的问题：
1. 每次调用都要传递所有 fd 给内核（拷贝开销）
2. 内核需要遍历所有 fd 检查状态（O(n) 复杂度）
3. FD 数量限制（select 默认 1024）

epoll 的优势：
1. 只需一次 epoll_ctl 注册 fd
2. epoll_wait 只返回就绪的 fd（O(1) 复杂度）
3. 无 FD 数量限制
4. 使用红黑树 + 就绪链表管理 fd
```

---

#### 2.2.2 epoll 的 LT 和 ET 模式

**问题**：epoll 的水平触发和边沿触发有什么区别？

**详解**：

**水平触发 (Level Triggered, LT)**：

```
特点：
- 只要 fd 可读，会一直通知
- 默认模式
- 可靠性高

场景：
读取数据：
1. epoll_wait 返回 fd 可读
2. 读了 100 字节（但还有 100 字节）
3. 下次 epoll_wait 还会返回该 fd 可读
4. 继续读，直到读完

优点：
- 不会漏读数据
- 编程简单

缺点：
- 可能重复通知
- 效率稍低
```

**边沿触发 (Edge Triggered, ET)**：

```
特点：
- 只在状态变化时通知一次
- 必须设置 EPOLLET
- 性能高

场景：
读取数据：
1. epoll_wait 返回 fd 可读（状态变化）
2. 必须一次性读完所有数据（循环读取）
3. 如果只读了一部分，epoll_wait 不会再通知
4. 直到下一次数据到达（新的状态变化）

必须循环读取：
void handle_read_et(int fd) {
    char buf[1024];
    while (true) {
        ssize_t n = read(fd, buf, sizeof(buf));
        if (n == -1) {
            if (errno == EAGAIN) break;  // 读完
            // 处理错误
        }
        if (n == 0) break;  // 连接关闭
        // 处理数据
    }
}

优点：
- 减少通知次数
- 性能更高

缺点：
- 编程复杂
- 容易漏读数据
```

**模式选择**：

```
使用 LT：
- 可靠性要求高
- 不想处理复杂逻辑
- 连接数不多

使用 ET：
- 高性能要求
- 连接数多（C10K 问题）
- 能确保一次性读完
```

---

## Part 3: 网络与协议

### 3.1 TCP 连接管理

#### 3.1.1 三次握手

**问题**：TCP 为什么需要三次握手？

**详解**：

**三次握手过程**：

```
客户端                    服务器
  |                         |
  |---- SYN (seq=x) ------>|  1. 客户端发送 SYN
  |                         |    进入 SYN_RECV
  |                         |
  |<--- SYN (seq=y) -------|  2. 服务器响应 SYN+ACK
  |     ACK (ack=x+1) ---->|    进入 ESTABLISHED
  |                         |
  |---- ACK (ack=y+1) ---->|  3. 客户端确认
  |                         |    进入 ESTABLISHED
```

**为什么是三次而不是两次**：

```
原因 1：确认双方收发能力
- 第一次：客户端发，服务器收（客户端发能力，服务器收能力）
- 第二次：服务器发，客户端收（服务器发能力，客户端收能力）
- 第三次：客户端发，服务器收（再次确认）

原因 2：同步初始序列号
- 双方都需要知道对方的初始序列号
- 序列号用于保证数据顺序和可靠性

原因 3：防止历史连接干扰
场景：
1. 客户端发送 SYN1，网络拥堵延迟
2. 客户端超时，重发 SYN2，完成连接并关闭
3. 如果没有第三次握手：
   - 延迟的 SYN1 到达服务器
   - 服务器误以为新连接，分配资源
   - 造成资源浪费

有第三次握手：
- 服务器响应 SYN1
- 客户端不认可（已不是期望的连接）
- 发送 RST 重置连接
```

**TIME_WAIT 详解**：

```
四次挥手后，主动关闭方进入 TIME_WAIT 状态：

持续时间：2 * MSL (Maximum Segment Lifetime)
- MSL：报文最大生存时间，通常 30 秒 -2 分钟
- TIME_WAIT：1-4 分钟

为什么需要 2*MSL：

1. 确保最后的 ACK 能到达
   - 如果 ACK 丢失，被动方会重传 FIN
   - 主动方在 TIME_WAIT 期间能收到并重传 ACK
   - 2*MSL 确保往返一次的时间

2. 防止历史连接干扰
   - 等待 2*MSL 确保所有该连接的报文都消失
   - 新连接不会受到旧连接报文干扰

为什么是主动关闭方进入：
- 主动方发送 ACK 后，不知道 ACK 是否到达
- 被动方收到 ACK 后进入 CLOSED，不需要等待
```

---

#### 3.1.2 TCP 可靠传输

**问题**：TCP 如何保证可靠传输？

**详解**：

```
1. 序列号 (Sequence Number)
   - 每个字节都有唯一序列号
   - 接收方按序重组
   - 解决乱序问题

2. 确认机制 (ACK)
   - 累计确认：ACK 号 = 期望收到的下一个字节
   - 例如 ACK=1000 表示 0-999 都收到了

3. 重传机制
   a) 超时重传：
      - 发送后启动定时器
      - 超时未收到 ACK 则重传

   b) 快速重传：
      - 收到 3 个重复 ACK
      - 立即重传，不等超时

4. 流量控制 (滑动窗口)
   - 接收方通告窗口大小
   - 发送方不超过窗口
   - 防止接收方缓冲区溢出

5. 拥塞控制
   a) 慢启动：
      - 初始 cwnd=1 或 2
      - 每 RTT 翻倍增长
      - 直到 ssthresh

   b) 拥塞避免：
      - 达到 ssthresh 后
      - 每 RTT 线性增长 (+1)

   c) 快重传/快恢复：
      - 收到 3 个重复 ACK
      - cwnd 减半，进入拥塞避免
      - 不回到慢启动

6. 校验和 (Checksum)
   - 检测数据损坏
   - 错误则丢弃

7. 重复检测
   - 序列号判断是否重复
   - 丢弃重复段
```

---

### 3.2 HTTP/HTTPS

#### 3.2.1 HTTP 与 HTTPS 的区别

**问题**：HTTP 和 HTTPS 的区别？HTTPS 的加密原理？

**详解**：

| 特性 | HTTP | HTTPS |
|------|------|-------|
| 协议层 | 应用层 | HTTP + TLS/SSL |
| 端口 | 80 | 443 |
| 加密 | 无 | 对称加密 |
| 证书 | 无 | 需要 CA 证书 |
| 性能 | 快 | 握手慢，传输接近 |

**HTTPS 握手过程**：

```
客户端                    服务器
  |                         |
  |---- ClientHello ------>|  支持的加密套件
  |                         |
  |<--- ServerHello -------|  选择的加密套件
  |     Certificate ------>|  服务器证书（含公钥）
  |                         |
  | 验证证书（CA、有效期）   |
  |                         |
  |---- ClientKeyExchange ->|  随机数（用公钥加密）
  |                         |    只有服务器能解密
  |                         |
  |<--- ServerHelloDone ---|
  |                         |
  |==== 双方用随机数生成对称密钥 ===|
  |                         |
  |==== 开始对称加密通信 ====|
```

**为什么对称加密密钥安全**：

```
1. 随机数 ClientRandom 用服务器公钥加密
   - 只有服务器私钥能解密
   - 中间人拿不到随机数

2. 证书验证
   - 证书由 CA 签名
   - 客户端验证签名确认证书真实
   - 防止中间人伪造证书

3. 密钥派生
   - 双方用随机数 + 其他参数生成对称密钥
   - 中间人不知道随机数，无法生成密钥
```

---

## Part 4: 数据库

### 4.1 索引与 B+ 树

#### 4.1.1 为什么用 B+ 树

**问题**：数据库为什么用 B+ 树不用红黑树？

**详解**：

**树高对比**：

```
假设 100 万条数据：

红黑树（二叉树）：
- 树高：log2(1000000) ≈ 20
- 每次查找最多 20 次 IO

B+ 树（假设 100 叉）：
- 树高：log100(1000000) = 3
- 每次查找最多 3 次 IO

磁盘 IO 是瓶颈：
- 内存访问：~100 纳秒
- 磁盘 IO: ~10 毫秒
- 相差 10 万倍！
```

**范围查询**：

```
红黑树：
1. 找到起始节点 O(log n)
2. 中序遍历获取后续节点
3. 需要多次树遍历

B+ 树：
1. 找到起始叶子 O(log n)
2. 沿叶子节点链表顺序读取
3. 只需一次树查找
```

**磁盘块对齐**：

```
B+ 树节点大小 = 磁盘页大小（通常 4KB 或 8KB）
- 一次 IO 读取整个节点
- 充分利用磁盘带宽

红黑树节点小：
- 节点分散在不同页
- 多次 IO 才能完成查找
```

**B+ 树 vs B 树**：

```
B 树：
- 内部节点也存储数据
- 查找可能在内部节点结束

B+ 树：
- 内部节点只存索引
- 所有数据在叶子节点
- 叶子节点有链表连接

B+ 树优势：
1. 内部节点更小，可容纳更多索引项
2. 范围查询只需遍历叶子链表
3. 查询性能稳定
```

**B+ 树每层节点数**：

```
假设：
- 页大小：16KB
- 键大小：8 字节
- 指针大小：8 字节

每个节点可容纳键数：
16KB / (8 + 8) = 1024 个

100 万数据的 B+ 树：
- 根节点：1 个
- 第二层：1024 个
- 第三层：1024 * 1024 = 104 万（足够存叶子）
- 树高：3 层
```

---

## Part 5: 分布式系统

### 5.1 Raft 协议

#### 5.1.1 脑裂处理

**问题**：Raft 如何处理脑裂问题？

**详解**：

**脑裂场景**：

```
集群：A, B, C, D, E (5 节点)
正常情况：A 是 Leader

网络分区：
[A, B] ---网络中断--- [C, D, E]

两边都认为自己是主：
- [A, B]: A 认为自己是 Leader（不知道被分区）
- [C, D, E]: C 选举成为新 Leader（多数派）
```

**Raft 的解决方案**：

```
1. 多数派原则
   - 选举需要 N/2+1 票（5 节点需要 3 票）
   - 只有 [C, D, E] 能选到 3 票
   - [A, B] 只有 2 票，选举失败

2. Leader 自动降级
   - A 收不到多数派的心跳确认
   - 知道有更高任期的 Leader
   - 自动降级为 Follower

3. 日志提交保证
   - 只有多数派确认的日志才提交
   - [A, B] 的日志未提交
   - 网络恢复后回滚未提交日志
```

**客户端提交数据何时返回成功**：

```
正确做法：大多数副本复制完成后返回

流程：
1. Leader 接收客户端请求
2. 追加到本地日志
3. 并行发送给所有 Follower
4. 收到多数派确认后标记提交
5. 应用到状态机
6. 返回客户端成功

为什么不是所有副本：
- 等待所有副本太慢
- 一个节点失败就卡住
- 多数派已保证一致性

为什么不是 Leader 本地就返回：
- 如果 Leader 宕机，数据丢失
- 不满足持久性保证
```

---

## Part 6: 项目与系统设计

### 6.1 OLAP 查询引擎设计

**问题**：设计一个实时 OLAP 查询引擎

**详解**：

**核心组件**：

```
┌─────────────────────────────────────────────┐
│              查询解析器                      │
│         SQL Parser → AST                    │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│              查询优化器                      │
│    逻辑优化 → 物理优化 → 代价估算            │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│              执行计划生成器                   │
│         生成执行计划 DAG                      │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│              向量化执行引擎                   │
│    ColumnBatch → Vectorized Operator        │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│              存储引擎                        │
│   列式存储 → 编码压缩 → 索引 → 缓存          │
└─────────────────────────────────────────────┘
```

**关键设计点**：

1. 列式存储
   - 每列独立存储
   - 适合分析查询（只读需要的列）
   - 编码压缩（字典、RLE、Delta）

2. 向量化执行
   - 一次处理一批数据（如 1024 行）
   - SIMD 指令加速
   - 减少函数调用开销

3. 查询优化
   - 谓词下推（尽早过滤）
   - 列裁剪（只读需要的列）
   - 聚合下推

4. 分布式执行
   - 数据分片
   - 并行查询
   - 结果汇聚

5. 缓存策略
   - 数据缓存（LRU）
   - 结果缓存
   - 索引缓存

---

## 附录 A：复习优先级

### P0 - 必掌握（高频基础）

1. C++ 内存布局
2. new/malloc 区别，brk/mmap
3. 智能指针（unique/shared/weak）
4. 虚函数表机制
5. 进程 vs 线程
6. 线程同步方式
7. select/poll/epoll 区别
8. TCP 三次握手四次挥手
9. B+ 树 vs 红黑树
10. 事务 ACID、隔离级别

### P1 - 应理解（进阶提升）

1. RAII 资源管理
2. 移动语义
3. 死锁预防
4. epoll LT/ET 模式
5. TCP 可靠传输、拥塞控制
6. malloc 内存管理
7. Raft 协议
8. Lambda 表达式

### P2 - 可了解（深度扩展）

1. 虚函数表具体实现
2. glibc 内存分配器源码
3. Reactor/Proactor 模式
4. 大页内存优化
5. 分布式事务方案
6. C++20 Concepts/Ranges

---

## 附录 B：原文档精华摘录

### B.1 推荐书籍

| 类别 | 书名 | 说明 |
|------|------|------|
| C++ 入门 | 《C++ Primer Plus》 | 哪怕觉得自己 C++ 再行，也建议至少把这本书过一遍 |
| C++ 进阶 | 《深度探索 C++ 对象模型》 | 读完这本书你应该可以在简历上写一个「熟悉 C++」 |
| C++ 实践 | 《Effective C++》 | 改善程序与设计的 55 个具体做法，对 C++ 编码帮助挺大 |
| 系统基础 | 《深入理解计算机系统》 | 神书，不用我多推荐了 |
| 操作系统 | 《现代操作系统》 | 上面那本看不懂可以先看看这本书 |
| 网络 | 《计算机网络自顶向下方法》 | 网络学习首选 |

### B.2 高频面试题精选

#### C++ 基础

- 三种智能指针（引用计数什么时候增加）
- 指针常量 vs 常量指针
- RAII 思想：如果打开文件描述符失败了一般怎么处理
- new 和 malloc 的区别，new 具体是怎么分配内存的
- brk 和 mmap 的区别，什么时候选择 brk/mmap，内存阈值是多少
- 使用 brk 分配内存时，free 为什么不会立即归还给系统
- 频繁 malloc 小块内存会出现什么问题
- malloc 怎么管理内存碎片
- C++ 对象的最小占用空间是多少，为什么是 1 字节
- 虚函数是如何实现的（虚表、虚指针）
- 构造函数能被声明为虚函数吗，为什么
- 析构函数需要被声明为虚函数吗，为什么
- 多态的实现（重写和重载，虚函数表）
- const 关键字的用法
- 字节对齐的原理

#### STL 容器

- vector/list/map 的底层实现，增删改查复杂度
- vector 的 push_back 时间复杂度
- vector 的扩容机制（1.5 倍或 2 倍）
- map 的存储原理（红黑树）
- unordered_map 的底层实现（哈希表）
- STL 六大容器
- 遍历中删除元素的正确方式
- 迭代器失效的场景

#### 操作系统

- 操作系统如何做线程调度
- 线程安全问题（i++ 的问题，如何避免）
- 全局 map 能否用原子操作解决并发
- CPU 缓存与内存的区别，MESI 协议
- 虚拟内存的作用
- 物理内存和虚拟内存的区别
- 内核态和用户态的区别及切换
- 进程间通信的方式
- 线程上下文切换原理
- 僵尸进程及处理方法
- 线程数等于核心数就一定最好吗

#### 网络编程

- DNS 解析过程
- TCP 数据包大小限制（1500 字节/1460 字节）
- TCP server 端调用 close 后 client 继续发送数据的情况
- poll 和 epoll 的区别
- libevent 原理
- C++ 实现 reactor 模式
- muduo 库的多线程实现
- epoll 的 ET 模式好在哪
- 为什么用 epoll，不用 epoll 有哪些区别
- select/poll/epoll 的 FD 限制
- socket 通信的具体过程（socket, bind, listen, accept）
- backlog 的默认值
- 一台服务器能支持的最大 TCP 连接数
- TCP 拥塞控制，慢启动和快重传的触发条件
- UDP 如何实现可靠传输

#### 数据库

- 数据库锁
- MySQL 使用的引擎（InnoDB vs MyISAM）
- 索引的数据结构，为什么不用红黑树
- B+ 树每层设置多少节点
- redo log 和 undo log
- Redis 缓存击穿、穿透、雪崩及解决方法
- Redis 几种类型所用的数据结构
- SQL 查找分页 limit

#### 分布式系统

- Raft 协议，脑裂的情况如何解决
- 日志复制的具体过程
- CAP 理论
- 外部客户端提交数据什么时候返回成功

#### 编译链接

- 运行一个 main 函数的过程（从预处理到栈帧处理）
- 编译器做了什么事情
- 静态链接和动态链接
- 栈帧的细节（保存了什么，使用什么数据结构和算法）
- 预处理怎么去掉注释的

#### 调试与工具

- 怎么检查内存泄漏
- valgrind 怎么使用，报表是什么样的
- gdb 调试方法
- 死锁用 gdb 怎么调试
- core dump 原因
- 常用 Linux 命令
- 远程怎样查看端口连没连接
- tcpdump 抓包
- 如何查询服务器瓶颈

#### 项目相关

- 日志的设计，宕机了怎么处理，数据丢失怎么办
- JSON 做序列化方案的原因，还有其他方案吗
- 项目里最难的地方是什么
- 线程池怎么创建和销毁
- 有限状态机的缺点
- 为什么用红黑树管理定时器，还有什么其他方式

### B.3 快速问答

| 问题 | 答案 |
|------|------|
| unique_ptr 怎么修改 | reset、release、std::move、修改指针内容 |
| 头文件保护有哪些方式 | #ifndef 保护、#pragma once |
| struct 与 class 区别 | 默认访问权限（public vs private） |
| 子类的析构函数会调用父类吗 | 会自动调用父类析构函数 |
| 友元函数的作用 | 允许非成员函数访问类的私有成员 |
| 观察者模式 | 一对多依赖，主题变化通知所有观察者 |
| C++11 的特性 | 右值引用、移动语义、Lambda、智能指针、auto 等 |
| 派生类可以转成基类吗 | 可以（向上转型），基类转派生类需要 dynamic_cast |
| 强制类型转换 | static_cast、dynamic_cast、const_cast、reinterpret_cast |
| 多线程共享什么 | 堆、全局变量、代码段、文件描述符 |
| 线程私有的是什么 | 栈、寄存器、线程局部存储 (TLS) |
| 函数栈空间多大 | 默认通常 1M-8M（可配置） |
| TCP 为何不能 2 次握手 | 无法确认双方收发能力，可能历史连接干扰 |
| 关闭为何要 4 次挥手 | TCP 全双工，每端独立关闭，允许半关闭状态 |
| TIME_WAIT 时间 | 2 * MSL（约 1-4 分钟） |
| TIME_WAIT 在哪一端 | 主动关闭方 |
| 大端小端的区别 | 大端：高位在低地址；小端：低位在低地址 |
| 网络序是什么 | 大端序 |
| HTTP 状态码 304/403/500 | 304 未修改，403 禁止访问，500 服务器错误 |
| HTTP 方法有哪些 | GET、POST、PUT、DELETE、HEAD、OPTIONS、PATCH |
| 100 本书每次取 1-5 本，怎么取到最后一本 | 先取 4 本，之后每次取 (6 - 对方取的数量) |

### B.4 代码检查清单

```cpp
// 遍历容器删除元素
for (auto it = v.begin(); it != v.end(); ) {
    if (should_delete(*it)) {
        it = v.erase(it);  // 利用返回值
    } else {
        ++it;
    }
}

// 单例模式（C++11 线程安全）
class Singleton {
public:
    static Singleton& instance() {
        static Singleton s;  // 静态局部对象，线程安全
        return s;
    }
};

// 智能指针传递
void func(std::unique_ptr<T> p);   // 按值传递（移动）
void func(std::unique_ptr<T>& p);  // 按引用传递
void func(const std::shared_ptr<T>& p);  // 共享指针按引用

// 虚析构函数
class Base {
public:
    virtual ~Base() = default;  // 虚析构
};
```

### B.5 面经来源

- [字节跳动社招三面面经](https://github.com/0voice/interview_experience/blob/main/字节跳动社招三面面经/字节跳动社招三面面经)
- [牛客网面试中心](https://www.nowcoder.com/interview/center)

---

## 附录 C：快速索引

### 按主题分类的问题索引

| 编号 | 问题 | 位置 |
|------|------|------|
| 1.1.1 | C++ 内存布局 | Part 1.1.1 |
| 1.1.2 | new 和 malloc 的区别 | Part 1.1.2 |
| 1.1.3 | brk 和 mmap 的区别 | Part 1.1.3 |
| 1.1.4 | free 后为什么不归还系统 | Part 1.1.4 |
| 1.1.5 | 频繁 malloc 小块内存的问题 | Part 1.1.5 |
| 1.1.6 | malloc 如何管理碎片 | Part 1.1.6 |
| 1.2.1 | 三种智能指针 | Part 1.2 |
| 1.2.2 | 循环引用问题 | Part 1.2 |
| 1.3.1 | 空类大小 | Part 1.3 |
| 1.3.2 | 虚函数表机制 | Part 1.3 |
| 1.3.3 | 指针常量 vs 常量指针 | Part 1.3 |
| 1.4.1 | RAII 思想 | Part 1.4 |
| 1.5.1 | 移动语义 | Part 1.5 |
| 1.5.2 | Lambda 表达式 | Part 1.5 |
| 2.1.1 | 进程和线程的区别 | Part 2.1 |
| 2.1.2 | 线程同步方式 | Part 2.1 |
| 2.1.3 | 死锁问题 | Part 2.1 |
| 2.2.1 | 五种 I/O 模型 | Part 2.2 |
| 2.2.2 | epoll LT/ET 模式 | Part 2.2 |
| 3.1.1 | TCP 三次握手 | Part 3.1 |
| 3.1.2 | TCP 可靠传输 | Part 3.1 |
| 3.2.1 | HTTP vs HTTPS | Part 3.2 |
| 4.1.1 | B+ 树索引 | Part 4.1 |
| 5.1.1 | Raft 脑裂处理 | Part 5.1 |
| 6.1 | OLAP 引擎设计 | Part 6.1 |

---

*本文档持续更新，建议结合实际代码理解和实践*
*最后更新：2026-03-04*
