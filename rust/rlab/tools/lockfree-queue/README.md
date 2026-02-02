# Lock-free Queue - 无锁队列实现

用于学习并发编程和原子操作的线程安全队列实现。

## 项目结构

```
tools/lockfree-queue/
├── src/
│   ├── lib.rs        # 公共类型和工具函数
│   ├── mpmc.rs       # 多生产者多消费者队列 (MPMC)
│   └── mpsc.rs       # 多生产者单消费者队列 (MPSC)
├── examples/
│   ├── mpmc_demo.rs  # MPMC 队列演示
│   ├── mpsc_demo.rs  # MPSC 队列演示
│   └── compare.rs    # 性能对比
└── benches/
    └── queue_bench.rs # Criterion 基准测试
```

## 两种队列实现

### 1. MPMC Queue (`MpmcQueue<T>`)
- **多生产者多消费者**：多个线程可以同时 push 和 pop
- **算法**：Michael-Scott 无锁队列算法
- **使用场景**：线程池任务队列、事件总线

```rust
use lockfree_queue::MpmcQueue;

let queue = MpmcQueue::<i32>::new();
queue.push(42).unwrap();
let value = queue.pop().unwrap();
```

### 2. MPSC Queue (`MpscQueue<T>`)
- **多生产者单消费者**：多个生产者，但只能有一个消费者
- **优化**：消费者不需要原子操作，性能更好
- **使用场景**：日志收集、消息分发

```rust
use lockfree_queue::MpscQueue;

let queue = MpscQueue::<i32>::new();
queue.push(42).unwrap();
let value = queue.pop().unwrap();
```

## 核心概念

### 1. 原子操作 (Atomic Operations)

```rust
use std::sync::atomic::{AtomicUsize, Ordering};

let counter = AtomicUsize::new(0);

// Relaxed: 最宽松的顺序，只保证原子性
counter.fetch_add(1, Ordering::Relaxed);

// Acquire: 用于加载，确保看到其他线程的 Release 写入
let value = counter.load(Ordering::Acquire);

// Release: 用于存储，确保其他线程的 Acquire 能看到此写入
counter.store(1, Ordering::Release);

// AcqRel: 读用 Acquire，写用 Release
// 用于 CAS 等读-修改-写操作
counter.compare_exchange(old, new, Ordering::AcqRel, Ordering::Acquire);

// SeqCst: 顺序一致性，最严格的顺序
// 所有线程看到的操作顺序一致
counter.store(1, Ordering::SeqCst);
```

### 2. 内存序 (Memory Ordering)

```
线程 A:                      线程 B:
x.store(1, Release)          if y.load(Acquire) == 1:
y.store(1, Release)              assert!(x.load(Relaxed) == 1)

Release-Acquire 保证：如果 B 看到 y=1，则一定也能看到 x=1
```

| Ordering | 含义 | 用途 |
|----------|------|------|
| `Relaxed` | 只保证原子性 | 计数器、标志位 |
| `Acquire` | 获取语义，后续的读能看到其他线程的写 | 锁的获取 |
| `Release` | 释放语义，之前的写能被其他线程看到 | 锁的释放 |
| `AcqRel` | Acquire + Release | CAS 操作 |
| `SeqCst` | 顺序一致 | 需要全局顺序的场景 |

### 3. Compare-And-Swap (CAS)

CAS 是无锁算法的核心操作：

```rust
// 伪代码：原子地比较并交换
fn compare_exchange(&self, expected: T, new: T) -> Result<T, T> {
    if self.value == expected {
        self.value = new;
        Ok(expected)
    } else {
        Err(self.value)
    }
}
```

在无锁队列中的应用：

```rust
// Push 操作的核心逻辑
loop {
    let tail = self.tail.load(Acquire);
    let next = unsafe { (*tail).next.load(Acquire) };
    
    if next.is_null() {
        // 尝试将新节点链接到尾部
        match unsafe {
            (*tail).next.compare_exchange(
                null_mut(), 
                new_node, 
                AcqRel,   // 成功时用 AcqRel
                Acquire   // 失败时用 Acquire
            )
        } {
            Ok(_) => break,  // 成功！
            Err(_) => continue,  // 失败，重试
        }
    }
}
```

### 4. ABA 问题

**问题描述**：
```
线程 A: 读取指针 P -> 节点 A
线程 B: 修改 P -> 节点 B -> 节点 A (重新分配)
线程 A: CAS 成功（因为 P 又指向了 A），但队列结构已变！
```

**解决方案**：
1. **Tagged pointers**: 在指针中加入版本号
2. **Hazard pointers**: 延迟释放被其他线程访问的节点
3. **Epoch-based reclamation**: 按代回收内存

本实现使用简单方案：节点一旦被 pop，就不会重新入队，避免 ABA。

## 算法详解

### Michael-Scott 队列算法

```
初始状态:
Head -> [Dummy] <- Tail

Push 操作:
1. 创建新节点
2. CAS tail.next 从 null 指向新节点
3. CAS tail 指向新节点

Pop 操作:
1. 读取 head
2. 读取 head.next
3. 如果 head == tail，队列为空
4. CAS head 指向 head.next
5. 返回数据
```

### MPSC 优化

```rust
// MPMC: 消费者需要原子操作
let head = self.head.load(Acquire);
self.head.compare_exchange(old, new, AcqRel, Acquire)

// MPSC: 消费者可以直接访问（单线程）
let head = *self.head.get();  // 非原子！
*self.head.get() = new_head;   // 非原子！
```

## 性能对比

运行 `cargo run --example compare`：

```
=== Single Producer ===
std::sync::mpsc:  15ms (6.7M ops/sec)
MPMC (lockfree):  22ms (4.5M ops/sec)
MPSC (lockfree):  18ms (5.6M ops/sec)

=== Two Producers ===
std::sync::mpsc:  28ms (3.6M ops/sec)
MPMC (lockfree):  35ms (2.9M ops/sec)
MPSC (lockfree):  25ms (4.0M ops/sec)
```

**结论**：
- `std::sync::mpsc` 经过高度优化，通常最快
- MPSC 在单消费者场景下比 MPMC 快 20-30%
- 无锁队列在高竞争下表现更好（无阻塞）

## 使用示例

### 基础用法

```bash
cd tools/lockfree-queue

# 运行 MPMC 演示
cargo run --example mpmc_demo

# 运行 MPSC 演示
cargo run --example mpsc_demo

# 运行性能对比
cargo run --example compare

# 运行测试
cargo test

# 运行基准测试
cargo bench
```

### 线程池集成

```rust
use lockfree_queue::MpmcQueue;
use std::thread;

fn main() {
    let queue = Arc::new(MpmcQueue::<Box<dyn Fn() + Send>>::new());
    
    // Worker threads
    for _ in 0..4 {
        let q = Arc::clone(&queue);
        thread::spawn(move || {
            loop {
                if let Ok(task) = q.pop() {
                    task();
                }
            }
        });
    }
    
    // Submit tasks
    queue.push(Box::new(|| println!("Task 1"))).unwrap();
    queue.push(Box::new(|| println!("Task 2"))).unwrap();
}
```

## 学习要点

### 1. 为什么需要内存序？

```rust
// 错误：没有同步
let x = AtomicUsize::new(0);
let y = AtomicUsize::new(0);

// 线程 1
x.store(1, Relaxed);  // 写 x
y.store(1, Relaxed);  // 写 y

// 线程 2
while y.load(Relaxed) == 0 {}  // 等待 y
assert_eq!(x.load(Relaxed), 1);  // 可能失败！
```

**原因**：编译器和 CPU 可能重排指令，`x=1` 可能还没写入内存。

```rust
// 正确：使用 Release/Acquire
// 线程 1
x.store(1, Relaxed);
y.store(1, Release);  // Release: 保证之前的写入对其他线程可见

// 线程 2
while y.load(Acquire) == 0 {}  // Acquire: 保证能看到 Release 前的写入
assert_eq!(x.load(Relaxed), 1);  // 现在一定成功
```

### 2. 伪共享 (False Sharing)

```rust
// 错误：两个原子变量在同一缓存行
struct Counter {
    count1: AtomicUsize,  // 64 bytes cache line
    count2: AtomicUsize,  // 同一缓存行
}

// 线程 1 修改 count1，线程 2 修改 count2
// 导致缓存行在两个 CPU 之间来回传递（乒乓效应）
```

```rust
// 正确：使用对齐防止伪共享
#[repr(align(64))]
struct PaddedAtomic(AtomicUsize);

struct Counter {
    count1: PaddedAtomic,  // 独立的缓存行
    count2: PaddedAtomic,  // 独立的缓存行
}
```

### 3. 无锁 vs 有锁

| 特性 | 有锁 (Mutex) | 无锁 (Lock-free) |
|------|-------------|-----------------|
| 实现复杂度 | 简单 | 复杂 |
| 性能（低竞争） | 好 | 稍差 |
| 性能（高竞争） | 可能阻塞 | 更好 |
| 实时性 | 可能延迟（优先级反转） | 更确定 |
| 正确性验证 | 相对容易 | 很难 |

## 参考资料

- [Michael-Scott Queue Paper](https://www.cs.rochester.edu/u/scott/papers/1996_PODC_queues.pdf)
- [Rust Atomics and Locks](https://marabos.nl/atomics/)
- [C++ Memory Model](https://en.cppreference.com/w/cpp/atomic/memory_order)
- [Lock-Free Programming](https://preshing.com/20120612/an-introduction-to-lock-free-programming/)
