# 第 16 章 Java 线程模型

> 源码路径：`src/hotspot/share/runtime/javaThread.cpp`、`src/hotspot/share/runtime/thread.cpp`、`src/hotspot/share/runtime/threadSMR.cpp`、`src/hotspot/os/linux/osThread_linux.cpp`

线程是 JVM 并发执行的基石。每个 Java 线程在 HotSpot 中对应一个 `JavaThread` 对象，该对象桥接了 Java 层的 `Thread` 对象和操作系统层的原生线程。本章深入线程的内部表示、生命周期管理和线程安全机制。

---

## 16.1 `javaThread.cpp`：Java 线程的 HotSpot 表示

### 16.1.1 JavaThread 的核心字段

```cpp
// javaThread.hpp
class JavaThread: public Thread {
    // Java 对象引用
    oop               _threadObj;          // Java 层 Thread 对象

    // 栈信息
    address           _stack_base;         // 栈的最高地址
    size_t            _stack_size;         // 栈大小
    JavaFrameAnchor   _anchor;             // 最近 Java 帧锚点

    // 执行状态
    JavaThreadState   _thread_state;       // 线程状态

    // 句柄区域
    HandleArea*       _handle_area;        // JNI 句柄分配区

    // 同步
    ObjectMonitor*    _current_pending_monitor;  // 等待中的监视器
    ObjectMonitor*    _current_waiting_monitor;  // wait 中的监视器

    // TLAB
    HeapWord*         _tlab_top;
    HeapWord*         _tlab_end;

    // 安全点
    volatile SafepointMechanism::State _polling_word;
    volatile SafepointMechanism::State _polling_page;
};
```

### 16.1.2 JavaThreadState 状态机

```
线程状态转换：

                    ┌──────────────────────┐
                    │  _thread_new         │  新创建
                    └──────┬───────────────┘
                           │ start()
                    ┌──────▼───────────────┐
         ┌─────────│ _thread_in_vm        │  执行 VM 内部代码
         │         └──────┬───────────────┘
         │                │
         │         ┌──────▼───────────────┐
         │         │  _thread_in_Java     │  执行 Java 代码
         │         └──────┬───────────────┘
         │                │
         │         ┌──────▼───────────────┐
         │         │ _thread_in_native    │  执行 JNI native 代码
         │         └──────┬───────────────┘
         │                │
         │         ┌──────▼───────────────┐
         │         │ _thread_blocked      │  阻塞（等待监视器/sleep/park）
         │         └──────┬───────────────┘
         │                │
         │         ┌──────▼───────────────┐
         └────────►│ _thread_terminated   │  已终止
                   └──────────────────────┘
```

### 16.1.3 线程的创建过程

```cpp
// thread.cpp（简化）
JavaThread::JavaThread(ThreadFunction entry_point, size_t stack_sz) {
    // 1. 初始化 JavaThread 字段
    initialize();

    // 2. 创建 OSThread
    os::create_thread(this, os::java_thread, stack_sz);

    // 3. 设置入口点
    set_entry_point(entry_point);
}
```

OS 线程创建后，在线程函数中执行 `JavaThread::run()`：

```cpp
// javaThread.cpp
void JavaThread::run() {
    // 1. 初始化线程本地存储
    this->initialize_thread_current();

    // 2. 记录栈信息
    this->record_stack_base_and_size();

    // 3. 注册到线程列表
    Threads::add(this);

    // 4. 执行 Java 的 Thread.run()
    this->entry_point()(this, this);

    // 5. 退出
    this->exit(false);
    delete this;
}
```

---

## 16.2 `thread.cpp / threads.cpp`：线程生命周期管理

### 16.2.1 线程列表

JVM 维护全局线程列表 `Threads`：

```cpp
// threads.hpp
class Threads: AllStatic {
    static JavaThread* _thread_list;    // 链表头
    static int         _number_of_threads;

    // 添加/移除线程
    static void add(JavaThread* p, bool force_daemon = false);
    static void remove(JavaThread* p);

    // 遍历
    static void threads_do(ThreadClosure* tc);
};
```

### 16.2.2 线程的生命周期

```
new JavaThread()
  │
  ▼
os::create_thread()          ← 创建 OS 线程
  │
  ▼
Thread.start() (Java)
  │
  ▼
os::start_thread()           ← 启动 OS 线程
  │
  ▼
JavaThread::run()            ← 线程入口
  │
  ▼
Threads::add()               ← 注册到全局列表
  │
  ▼
执行 Thread.run() (Java)
  │
  ▼
JavaThread::exit()           ← 退出
  │
  ▼
Threads::remove()            ← 从全局列表移除
  │
  ▼
delete JavaThread            ← 销毁
```

### 16.2.3 守护线程

守护线程（Daemon Thread）不影响 JVM 退出。当所有非守护线程终止后，JVM 调用 `java.lang.Shutdown.shutdown()` 然后退出：

```cpp
// threads.cpp
bool Threads::should_create_daemon() {
    // 检查是否还有非守护线程存活
    for (JavaThread* t = _thread_list; t; t = t->next()) {
        if (!t->is_daemon()) return true;
    }
    return false;
}
```

---

## 16.3 `threadSMR.cpp`：线程安全的 hazard pointer

### 16.3.1 SMR 的问题

遍历全局线程列表时，如果某个线程恰好被销毁，访问已释放的 `JavaThread` 对象会导致崩溃。传统的锁方案在安全点外的开销太大。

### 16.3.2 SMR（Safe Memory Reclamation）

HotSpot 使用 SMR 机制保护线程列表的并发访问：

```cpp
// threadSMR.hpp
class ThreadsSMRSupport {
    // Hazard pointer：标记正在使用的 JavaThread
    // 每个线程有自己的 hazard pointer
    static ThreadsList* _java_thread_list;

    // 添加 hazard pointer
    static void add_thread(JavaThread* thread);

    // 获取受保护的线程列表快照
    static ThreadsList* get_java_thread_list();

    // 释放线程（延迟直到没有 hazard pointer 引用）
    static void release_thread(JavaThread* thread);
};
```

SMR 的工作流程：

```
读取线程列表：
1. 获取 ThreadsList 快照（引用计数 +1）
2. 遍历快照（无需加锁）
3. 释放快照（引用计数 -1）

删除线程：
1. 从 ThreadsList 中移除线程
2. 将线程加入 _delete_list
3. 检查是否有线程持有该线程的 hazard pointer
4. 如果没有，立即释放；否则等待
```

### 16.3.3 删除日志

`_delete_list` 记录了待释放的线程，定期检查是否可以安全释放：

```cpp
// threadSMR.cpp
void ThreadsSMRSupport::smr_delete(JavaThread* thread) {
    // 将线程加入删除列表
    _delete_list->push(thread);

    // 尝试释放所有可安全释放的线程
    _delete_list->delete_stale();
}
```

---

## 16.4 `osThread`：OS 线程映射与调度亲和性

### 16.4.1 OSThread

`OSThread` 封装了操作系统原生线程：

```cpp
// osThread.hpp
class OSThread {
    pthread_t    _pthread_id;       // POSIX 线程 ID
    pid_t        _kernel_thread_id; // Linux 内核线程 ID（gettid()）
    sigset_t     _caller_sigmask;   // 信号掩码
    int          _priority;         // 线程优先级
};
```

### 16.4.2 线程调度亲和性

JVM 支持将线程绑定到特定 CPU 核：

```cpp
// os_linux.cpp
void os::set_thread_affinity(JavaThread* thread, int cpu_id) {
    cpu_set_t cpuset;
    CPU_ZERO(&cpuset);
    CPU_SET(cpu_id, &cpuset);
    pthread_setaffinity_np(thread->osthread()->pthread_id(),
                           sizeof(cpu_set_t), &cpuset);
}
```

GC 线程的亲和性对性能至关重要——将 GC 线程绑定到与 Java 线程相同的 NUMA 节点，减少跨节点访问。

---

## 16.5 [体系结构视角] 线程调度、Cache 一致性与 MESI 协议

### 16.5.1 线程调度对缓存的影响

操作系统线程调度器在 CPU 核之间迁移线程时，L1/L2 缓存的内容全部失效：

```
线程迁移的缓存惩罚：
1. 线程 A 在 Core 0 运行，L1 D-Cache 包含热点数据
2. 调度器将线程 A 迁移到 Core 1
3. Core 0 的 L1 D-Cache 内容无效（对线程 A 而言）
4. 线程 A 需要重新从 L3/内存加载数据

典型惩罚：100-500μs 的缓存预热期
```

### 16.5.2 MESI 协议与 Java 内存模型

x86 的缓存一致性协议是 MESI（Modified/Exclusive/Shared/Invalid）：

```
MESI 状态：
  M (Modified)：   只在本缓存行中，与内存不一致
  E (Exclusive)：  只在本缓存行中，与内存一致
  S (Shared)：     可能在多个缓存行中，与内存一致
  I (Invalid)：    无效

Java volatile 的映射：
  volatile 写 → CPU 执行 store + storeload 屏障
              → 使其他核的对应缓存行失效（MESI 的 I 状态）
  volatile 读 → CPU 执行 load
              → 如果缓存行无效，从内存/其他核加载（MESI 的 S 状态）
```

### 16.5.3 False Sharing

两个无关变量如果位于同一缓存行（64 字节），一个线程修改变量 A 会使另一个线程的变量 B 缓存失效：

```
缓存行布局：
┌───────────────────────────────────────────────────────┐
│ volatile int x (Core 0 写)  │  volatile int y (Core 1 写)  │
└───────────────────────────────────────────────────────┘
                  同一 64 字节缓存行

Core 0 写 x → Core 1 的整个缓存行失效 → Core 1 读 y 需要从 L3 加载
Core 1 写 y → Core 0 的整个缓存行失效 → Core 0 读 x 需要从 L3 加载

解决方案：@Contended 注解或手动填充
@Contended
class PaddedCounter {
    volatile int x;  // 独占一个缓存行
}
```

JDK 的 `@jdk.internal.vm.annotation.Contended` 注解让 JVM 在字段间插入填充，避免 false sharing。

---

## 小结

本章剖析了 JVM 的线程模型：

1. **JavaThread** 桥接 Java 层 Thread 对象和 OS 原生线程，维护栈、状态、TLAB 等信息
2. **线程状态机**定义了 `_thread_in_Java / _thread_in_native / _thread_blocked` 等关键状态
3. **SMR** 通过 hazard pointer 实现线程列表的并发安全访问
4. **OSThread** 封装操作系统线程，支持亲和性绑定
5. **MESI 协议** 映射到 Java 内存模型，volatile 写导致缓存行失效
6. **False Sharing** 是多线程性能的隐形杀手，`@Contended` 是 JVM 级的解决方案

下一章将深入同步原语——Monitor 与锁的实现。
