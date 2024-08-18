# 第26章 跟踪与性能分析

> 源码锚点：`kernel/trace/`、`kernel/kprobes.c`、`tools/perf/`

可观测性是系统性能优化和问题诊断的基础——"不能测量就不能优化"。Linux提供了丰富的跟踪和性能分析工具：ftrace追踪函数调用，perf采样硬件事件，eBPF实现自定义跟踪。掌握这些工具是内核开发者和DBA的核心技能。

## 26.1 ftrace：函数跟踪

### function tracer

ftrace(function tracer)是内核最基础的跟踪工具——通过`-pg`编译选项在每个函数入口插入调用`mcount`/`__fentry__`，运行时替换为跟踪调用：

```
函数入口 → __fentry__() → 检查是否启用跟踪
  → 启用：记录函数名/时间戳/调用栈到trace buffer
  → 禁用：直接返回(单条跳转指令，开销极小)
```

ftrace的动态补丁机制：通过修改函数入口的指令实现在线启用/禁用——禁用时开销仅一条`nop`指令。

### function_graph tracer

function_graph tracer记录函数调用和返回——构建完整的调用图：

```
入口：记录函数名、时间戳
返回：计算耗时、记录缩进

  func_a() {            // 耗时100us
    func_b() {          // 耗时30us
      func_c();         // 耗时10us
    }                   // func_b返回
    func_d();           // 耗时50us
  }
```

function_graph直观展示调用层次和时间分布——快速定位性能热点。

### TRACE_EVENT宏

内核使用`TRACE_EVENT`宏定义tracepoint——静态插桩点，比kprobe更高效：

```c
// 定义tracepoint
TRACE_EVENT(sched_switch,
    TP_PROTO(struct task_struct *prev, struct task_struct *next),
    TP_ARGS(prev, next),
    TP_STRUCT__entry(
        __field(pid_t, prev_pid)
        __field(pid_t, next_pid)
    ),
    TP_fast_assign(
        __entry->prev_pid = prev->pid;
        __entry->next_pid = next->pid;
    ),
    TP_printk("prev_pid=%d next_pid=%d", __entry->prev_pid, __entry->next_pid)
);
```

tracepoint在不启用时开销仅一次条件跳转(jump_label)——几乎为零。启用后记录结构化数据到trace buffer——比printf风格的调试输出更高效。

### trace buffer

trace buffer是per-CPU的环形缓冲区——跟踪数据写入本CPU的buffer，无锁。用户通过`/sys/kernel/debug/tracing/trace`读取——seq_file接口顺序输出。

### kprobes：动态探针

`kernel/kprobes.c`实现kprobe/kretprobe——在任意内核函数入口/出口插入探针：

```
kprobe注册：
  1. 保存目标指令
  2. 将目标指令替换为int3(0xCC)
  3. CPU执行到int3 → 异常处理 → kprobe处理函数
  4. 执行原始指令(单步执行)
  5. 继续执行

kretprobe：
  1. 函数入口替换返回地址为kretprobe trampoline
  2. 函数返回时 → trampoline → 记录返回值和耗时
  3. 跳回原始返回地址
```

kprobe的局限：基于int3断点——每次命中触发异常，开销约1-5μs。高频函数(如调度器)不适合kprobe。

## 26.2 perf：硬件性能计数器

### PMU(Performance Monitoring Unit)

现代CPU内建PMU——统计硬件事件：周期数、指令数、缓存命中/缺失、分支预测等。perf通过`perf_event_open()`系统调用配置PMU：

```c
// 配置PMU计数器
struct perf_event_attr attr = {
    .type = PERF_TYPE_HARDWARE,
    .config = PERF_COUNT_HW_CPU_CYCLES,  // 统计CPU周期
    .sample_period = 1000000,             // 每100万周期采样一次
};
```

### 采样模式：perf record

perf record基于采样的性能分析——每N个事件采样一次调用栈：

```
perf record -g ./my_program
  → PMU每100万周期产生一次中断
  → 中断处理中记录当前调用栈
  → 运行结束后生成perf.data
```

采样频率决定了精度和开销的平衡——频率越高精度越好，但开销越大。默认频率99Hz——在精度和开销间取平衡。

### 火焰图

perf record采集的调用栈数据可以用FlameGraph工具生成火焰图——x轴是调用栈的宽度(采样次数)，y轴是调用深度，颜色随机。火焰图一眼看出时间花在哪里——最宽的"火焰"是性能热点。

### off-CPU分析

on-CPU分析(默认perf)看CPU时间花在哪里，off-CPU分析看等待时间花在哪里：

```
perf sched record   → 记录调度事件
perf sched latency  → 每个任务的调度延迟

offcpu分析：
  → 进程在哪里被阻塞？锁竞争？I/O等待？页面错误？
```

数据库慢查询的off-CPU分析至关重要——很多时候瓶颈不是CPU不够快，而是等待锁或I/O。

### 缓存分析

```bash
perf stat -e cache-misses,cache-references,L1-dcache-loads,L1-dcache-miss \
          ./my_program
```

缓存缺失率直接影响性能——L3缓存缺失的延迟约100ns，而L1命中仅1ns。perf可以精确定位哪些代码路径导致缓存缺失。

## 26.3 BPF跟踪工具链

### bpftrace：一行式BPF跟踪

bpftrace是高级BPF跟踪语言——一行命令实现复杂的跟踪：

```bash
# 追踪所有open系统调用
bpftrace -e 'tracepoint:syscalls:sys_enter_open { printf("%s %s\n", comm, str(args->filename)) }'

# 追踪函数耗时分布
bpftrace -e 'kprobe:ext4_file_write { @start[tid] = nsecs }
             kretprobe:ext4_file_write /@start[tid]/ { @ns = hist(nsecs - @start[tid]); delete(@start[tid]) }'
```

bpftrace自动处理BPF程序的编译、加载、附着——用户只需描述"追踪什么"和"输出什么"。

### BCC(BPF Compiler Collection)

BCC提供Python/BPF工具集——比bpftrace更灵活，适合复杂场景：

```python
# BCC示例：追踪锁竞争
b = BPF(text='''
int trace_mutex_lock(struct pt_regs *ctx) {
    u64 ts = bpf_ktime_get_ns();
    lock_start.update(&pid, &ts);
}
int trace_mutex_unlock(struct pt_regs *ctx) {
    u64 *tsp = lock_start.lookup(&pid);
    if (tsp) {
        u64 delta = bpf_ktime_get_ns() - *tsp;
        dist.increment(bpf_log2l(delta));
    }
}
''')
```

### libbpf：CO-RE工具链

libbpf是BPF程序的C库——支持CO-RE(Compile Once - Run Everywhere)。编写BPF程序时使用vmlinux.h的类型定义(基于BTF)，libbpf在加载时自动重定位——同一BPF程序在不同内核版本上运行。

## 26.4 性能分析方法论

### 一条慢查询的内核态时间分析

数据库慢查询的诊断流程——从用户态到内核态逐层深入：

**步骤1：perf record -g 定位热点函数**
```
perf record -g -p <pid> sleep 10
perf report
→ 发现30%时间在ext4_file_write → 写WAL日志
```

**步骤2：off-CPU分析找到等待点**
```
bpftrace -e 'profile:hz:99 /pid == <pid>/ { @[ustack] = count() }'
offcpu分析发现50%时间在schedule() → 等待I/O完成
```

**步骤3：bpftrace追踪锁竞争**
```
bpftrace -e 'kprobe:mutex_lock /pid == <pid>/ { @lock[arg0] = nsecs }
             kretprobe:mutex_lock /@lock[arg0]/ { @ns[arg0] = hist(nsecs - @lock[arg0]) }'
→ 发现Buffer Pool mutex竞争严重
```

**步骤4：io_uring completion延迟分析**
```
bpftrace追踪io_uring完成路径：
  io_uring_submit → blk_mq_submit_bio → nvme_queue_rq → 完成中断
  → 发现NVMe完成延迟P99为200μs → 硬件问题或队列深度不足
```

### Latency分布直方图

使用bpftrace的`hist()`函数生成延迟分布直方图：

```
@ns:
[256, 512)     123 |@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@    |
[512, 1K)       45 |@@@@@@@@@@@@                            |
[1K, 2K)        12 |@@@                                     |
[2K, 4K)         3 |@                                       |
[4K, 8M)         1 |                                        |
```

直方图比平均值更有价值——P99延迟可能比平均值高10倍，只有直方图能揭示尾延迟问题。

> **数据库视角**：数据库性能问题的内核态分析。数据库性能问题的80%可以在用户态定位(慢查询日志、explain分析)，但剩下20%需要深入内核——I/O延迟、锁竞争、调度延迟、内存压力。perf + bpftrace的组合是DBA的"透视镜"——从用户态的慢查询日志出发，逐层深入内核，找到真正的瓶颈。

---

本章建立了对内核跟踪与性能分析的完整认知：ftrace追踪函数调用和调用图，kprobe在任意位置插入探针，perf利用PMU进行采样和计数分析，eBPF工具链(bpftrace/BCC)实现自定义跟踪。性能分析的关键不是工具——而是方法论：从热点定位到等待分析到锁竞争到I/O延迟，层层深入找到根本原因。
