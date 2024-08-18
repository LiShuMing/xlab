# 附录 D：常用诊断工具与源码对应

## D.1 jcmd

`jcmd` 是 JDK 最重要的运行时诊断工具：

| 命令 | 对应源码 | 说明 |
|------|---------|------|
| `jcmd <pid> VM.flags` | `runtime/flags/jvmFlag.cpp` | 查看 JVM 标志 |
| `jcmd <pid> VM.command_line` | `runtime/arguments.cpp` | 查看命令行参数 |
| `jcmd <pid> VM.system_properties` | `runtime/arguments.cpp` | 查看系统属性 |
| `jcmd <pid> VM.native_memory` | `nmt/memTracker.cpp` | NMT 内存报告 |
| `jcmd <pid> VM.info` | `runtime/os.cpp` | VM 信息 |
| `jcmd <pid> GC.heap_info` | `gc/shared/collectedHeap.cpp` | 堆信息 |
| `jcmd <pid> GC.class_histogram` | `gc/shared/collectedHeap.cpp` | 类直方图 |
| `jcmd <pid> GC.finalizer_info` | `gc/shared/referenceProcessor.cpp` | Finalizer 信息 |
| `jcmd <pid> GC.run` | `gc/shared/collectedHeap.cpp` | 触发 GC |
| `jcmd <pid> Compiler.codecache` | `code/codeCache.cpp` | 代码缓存信息 |
| `jcmd <pid> Compiler.queue` | `compiler/compileBroker.cpp` | 编译队列 |
| `jcmd <pid> Thread.print` | `runtime/thread.cpp` | 线程栈转储 |
| `jcmd <pid> JFR.start` | `jfr/recorder/jfrRecorder.cpp` | 启动 JFR |
| `jcmd <pid> JFR.dump` | `jfr/recorder/storage/jfrStorage.cpp` | 导出 JFR 数据 |

## D.2 jfr

JFR 命令行工具：

```bash
# 打印 JFR 文件内容
jfr print --events CPULoad,GarbageCollection recording.jfr

# 查看 JFR 文件摘要
jfr summary recording.jfr

# 转换为 JSON
jfr print --json recording.jfr > recording.json
```

## D.3 jhsdb

`jhsdb` 是 HotSpot Serviceability Agent 的命令行前端：

```bash
# 附加到运行中的进程
jhsdb clhsdb --pid <pid>

# 常用 clhsdb 命令
universe              # 查看堆布局
heap dump             # 堆转储
inspect <addr>        # 检查对象
classdump <class>     # 类转储
printas oop <addr>    # 以 oop 格式打印

# GUI 模式
jhsdb hsdb --pid <pid>
```

## D.4 hsdis

`hsdis` 是 HotSpot 的反汇编插件，用于查看 JIT 生成的机器码：

```bash
# 安装 hsdis
# 从 https://github.com/iklam/hsdis-objdump 下载

# 使用
java -XX:+PrintAssembly -XX:+PrintCompilation -cp app.jar Main

# 仅反汇编特定方法
java -XX:+PrintAssembly -XX:CompileCommand=print,com/example/Main.compute
```

## D.5 jstack / jmap / jinfo

| 工具 | 命令 | 对应源码 |
|------|------|---------|
| `jstack` | `jstack <pid>` | `runtime/thread.cpp` |
| `jmap` | `jmap -heap <pid>` | `gc/shared/collectedHeap.cpp` |
| `jmap` | `jmap -histo <pid>` | `gc/shared/collectedHeap.cpp` |
| `jmap` | `jmap -dump:format=b,file=heap.bin <pid>` | 堆转储 |
| `jinfo` | `jinfo -flags <pid>` | `runtime/flags/jvmFlag.cpp` |

## D.6 async-profiler

`async-profiler` 是第三方性能分析器，使用 `AsyncGetCallTrace` API：

```bash
# CPU 分析
asprof -d 30 -f cpu.html <pid>

# 分配分析
asprof -d 30 -e alloc -f alloc.html <pid>

# 锁分析
asprof -d 30 -e lock -f lock.html <pid>

# Wall clock 分析
asprof -d 30 -e wall -f wall.html <pid>
```

## D.7 源码级调试的对应关系

| 观察点 | 工具 | 源码位置 |
|--------|------|---------|
| GC 暂停原因 | `-Xlog:gc*` | `gc/g1/g1CollectedHeap.cpp` |
| 编译事件 | `-XX:+PrintCompilation` | `compiler/compileBroker.cpp` |
| 逆优化 | `-XX:+PrintDeoptimization` | `runtime/deoptimization.cpp` |
| 类加载 | `-Xlog:class+load` | `classfile/classLoader.cpp` |
| 安全点 | `-Xlog:safepoint` | `runtime/safepoint.cpp` |
| 锁膨胀 | `-Xlog:monitorinflation` | `runtime/objectMonitor.cpp` |
| 内存分配 | `-Xlog:gc+alloc` | `gc/shared/collectedHeap.cpp` |
| 线程状态 | `jstack` | `runtime/javaThread.cpp` |
| 内联决策 | `-XX:+PrintInlining` | `opto/compile.cpp` |
