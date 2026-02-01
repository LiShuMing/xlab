# Thread Pool - 学习用线程池实现

一个模仿 Rayon 设计的简单线程池实现，用于学习线程池的核心概念、常见问题和性能设计。

## 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                      ThreadPool                              │
│  ┌─────────────────┐  ┌─────────────────────────────────┐   │
│  │  Task Sender    │──│  mpsc::Sender<Message>          │   │
│  └─────────────────┘  └─────────────────────────────────┘   │
│                          │                                   │
│                          ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  Shared Receiver (Mutex<mpsc::Receiver<Message>>)       ││
│  └─────────────────────────────────────────────────────────┘│
│                          │                                   │
│           ┌──────────────┼──────────────┐                   │
│           ▼              ▼              ▼                   │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │  Worker 0   │ │  Worker 1   │ │  Worker N   │           │
│  │ pool-work-0 │ │ pool-work-1 │ │ pool-work-N │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
└─────────────────────────────────────────────────────────────┘
```

## 核心组件

### 1. ThreadPool (主池)
- 管理线程池的生命周期
- 提供任务提交接口 `execute()`
- 协调优雅关闭

### 2. ThreadPoolBuilder (构建器)
- 可配置线程数量
- 可设置线程栈大小
- 可自定义线程名称前缀

### 3. Worker (工作线程)
- 从共享队列获取任务
- 执行并完成任务
- 响应终止信号

### 4. Message (消息类型)
- `Work(Task)`: 执行任务
- `Terminate`: 终止工作线程

## 线程池常见问题及解决方案

### 1. **任务分配策略**
**问题**: 如何高效地将任务分配给工作线程？

**本实现**: 使用简单的共享队列（mpsc channel）
```rust
// 所有工作线程共享同一个 receiver
let receiver = Arc::new(Mutex::new(receiver));
```

**Rayon 方案**: 使用 work-stealing 队列
- 每个线程有自己的本地队列
- 空闲线程从其他线程"窃取"任务
- 减少锁竞争，提高吞吐量

### 2. **锁竞争**
**问题**: 多个工作线程竞争同一个锁

**本实现的权衡**:
- 使用 `Mutex` 保护 receiver
- 锁的持有时间很短（仅 recv() 调用）
- 代码简单，适合学习

**优化方向**:
```rust
// 当前实现：锁竞争激烈
let message = receiver.lock().unwrap().recv();

// 优化方案：work-stealing deque
task = local_queue.pop_back()  // 无锁
    .or_else(|| steal_from_others())  // 偶尔锁竞争
```

### 3. **优雅关闭**
**问题**: 如何确保所有任务完成后才关闭线程池？

**本实现方案**:
```rust
impl Drop for ThreadPool {
    fn drop(&mut self) {
        // 1. 关闭 sender，触发 channel 关闭
        drop(self.sender.take());
        
        // 2. 等待所有工作线程完成
        for worker in &mut self.workers {
            if let Some(thread) = worker.thread.take() {
                thread.join().unwrap();
            }
        }
    }
}
```

### 4. **线程数量选择**
**问题**: 应该创建多少个工作线程？

**默认策略**:
```rust
num_threads = num_cpus::get()  // 逻辑 CPU 数量
```

**考虑因素**:
- **CPU 密集型任务**: 线程数 = CPU 核心数
- **IO 密集型任务**: 线程数 > CPU 核心数（允许线程等待 IO 时其他线程执行）
- **混合型任务**: 需要实际测试调优

### 5. **任务粒度**
**问题**: 多小的任务不适合线程池？

**性能示例**:
```rust
// ❌ 不好的例子：任务太小，开销超过收益
for i in 0..10000 {
    pool.execute(|| { i * i });
}

// ✅ 好的例子：任务足够大，并行收益明显
for chunk in data.chunks(1000) {
    pool.execute(|| { process_chunk(chunk) });
}
```

## 性能对比

### CPU 密集型任务（斐波那契计算）
```
System has 8 CPUs

--- Sequential Execution ---
Time: 2.3s

--- Thread Pool Execution (8 threads) ---
Time: 520ms
Speedup: 4.4x
```

### 小任务开销问题
```
Small tasks (sequential):  15μs
Small tasks (thread pool): 2.3ms  ← 150x slower!
```

**结论**: 线程池不适合执行时间 < 1ms 的任务

## 使用方法

### 基础用法
```rust
use thread_pool::ThreadPool;

fn main() {
    let pool = ThreadPool::new(4).unwrap();
    
    pool.execute(|| {
        println!("Hello from thread pool!");
    }).unwrap();
    
    pool.shutdown();
}
```

### 使用 Builder 配置
```rust
use thread_pool::ThreadPoolBuilder;

let pool = ThreadPoolBuilder::new()
    .num_threads(8)
    .stack_size(2 * 1024 * 1024)
    .name_prefix("compute".to_string())
    .build()
    .unwrap();
```

### 运行示例
```bash
# 基础示例
cargo run --example basic

# 性能分析示例
cargo run --example performance

# 基准测试
cargo bench
```

## 代码结构

```
tools/thread-pool/
├── Cargo.toml
├── README.md
├── src/
│   ├── lib.rs          # 主模块，ThreadPool 实现
│   ├── builder.rs      # ThreadPoolBuilder 构建器
│   └── worker.rs       # Worker 工作线程
├── examples/
│   ├── basic.rs        # 基础用法示例
│   └── performance.rs  # 性能分析示例
└── benches/
    └── thread_pool_bench.rs  # Criterion 基准测试
```

## 学习要点

1. **线程安全**: `Send` + `Sync` trait 的理解
2. **锁的使用**: 何时加锁、如何减少锁竞争
3. **Channel 通信**: mpsc 模式在并发中的应用
4. **资源管理**: RAII 模式在线程池中的应用
5. **性能权衡**: 简单实现 vs 高性能实现的取舍

## 与 Rayon 的区别

| 特性 | 本实现 | Rayon |
|------|--------|-------|
| 任务分配 | 共享队列 (锁) | Work-stealing (无锁) |
| 任务依赖 | 不支持 | 支持 join/scope |
| 递归并行 | 不支持 | 支持 |
| 代码复杂度 | 简单 (~300行) | 复杂 (数千行) |
| 适用场景 | 学习、简单任务 | 生产环境 |

## 参考资料

- [Rayon 源码](https://github.com/rayon-rs/rayon)
- [The Rust Programming Language - 并发](https://doc.rust-lang.org/book/ch16-00-concurrency.html)
- [Work-Stealing 论文](https://www.dre.vanderbilt.edu/~schmidt/PDF/work-stealing.pdf)
