# 附录 C：JVM 参数速查（按子系统分类）

## 内存与堆

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `-Xms` | 物理内存/64 | 初始堆大小 |
| `-Xmx` | 物理内存/4 | 最大堆大小 |
| `-Xss` | 平台相关 | 线程栈大小 |
| `-XX:MetaspaceSize` | 20MB | 初始元空间大小 |
| `-XX:MaxMetaspaceSize` | 无限制 | 最大元空间大小 |
| `-XX:CompressedClassSpaceSize` | 1GB | 压缩类空间大小 |
| `-XX:NewRatio` | 2 | Young/Old 比例 |
| `-XX:SurvivorRatio` | 8 | Eden/Survivor 比例 |
| `-XX:+UseCompressedOops` | 堆<32GB | 压缩普通对象指针 |
| `-XX:+UseCompressedClassPointers` | 开启 | 压缩类指针 |
| `-XX:+UseCompactObjectHeaders` | 关闭 | 紧凑对象头（JDK 27） |

## GC

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `-XX:+UseG1GC` | JDK 9+ 默认 | 使用 G1 GC |
| `-XX:+UseZGC` | 关闭 | 使用 ZGC |
| `-XX:+ZGenerational` | 关闭 | ZGC 分代模式 |
| `-XX:+UseShenandoahGC` | 关闭 | 使用 Shenandoah GC |
| `-XX:+UseParallelGC` | 关闭 | 使用 Parallel GC |
| `-XX:+UseSerialGC` | 关闭 | 使用 Serial GC |
| `-XX:MaxGCPauseMillis` | 200 | G1 目标最大暂停时间 |
| `-XX:G1HeapRegionSize` | 自动 | G1 Region 大小 |
| `-XX:InitiatingHeapOccupancyPercent` | 45 | G1 触发并发标记的堆占用率 |
| `-XX:SoftRefLRUPolicyMSPerMB` | 1000 | 软引用存活时间 |
| `-XX:+AlwaysPreTouch` | 关闭 | 启动时预填充堆 |
| `-XX:+DisableExplicitGC` | 关闭 | 禁止 `System.gc()` |
| `-XX:+UseLargePages` | 关闭 | 使用大页 |

## JIT 编译

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `-XX:+TieredCompilation` | 开启 | 分层编译 |
| `-XX:TieredStopAtLevel` | 4 | 分层编译最高级别 |
| `-XX:CompileThreshold` | 10000 | 无分层编译时的编译阈值 |
| `-XX:CompileThresholdScaling` | 1.0 | 编译阈值缩放因子 |
| `-XX:ReservedCodeCacheSize` | 240MB | 代码缓存最大大小 |
| `-XX:InitialCodeCacheSize` | 2MB | 代码缓存初始大小 |
| `-XX:+PrintCompilation` | 关闭 | 打印编译事件 |
| `-XX:+CITime` | 关闭 | 打印编译时间统计 |
| `-XX:MaxInlineSize` | 35 | 最大内联方法大小 |
| `-XX:FreqInlineSize` | 325 | 热点方法最大内联大小 |

## 线程与并发

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `-XX:ParallelGCThreads` | log2(CPU) | 并行 GC 线程数 |
| `-XX:ConcGCThreads` | ParallelGCThreads/4 | 并发 GC 线程数 |
| `-XX:C1CompilerCount` | log2(CPU) | C1 编译线程数 |
| `-XX:C2CompilerCount` | log2(CPU) | C2 编译线程数 |
| `-XX:+UseBiasedLocking` | JDK 15 关闭 | 偏向锁 |

## 可观测性

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `-XX:NativeMemoryTracking` | off | NMT 模式 |
| `-Xlog:gc*` | 无 | GC 日志 |
| `-XX:+PrintSafepointStatistics` | 关闭 | 安全点统计 |
| `-XX:StartFlightRecording` | 无 | 启动 JFR |
| `-XX:+UnlockDiagnosticVMOptions` | 关闭 | 解锁诊断选项 |
| `-XX:+PrintIdealGraph` | 关闭 | C2 Ideal Graph 输出 |

## CDS/AOT

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `-Xshare:on` | 自动 | 强制使用 CDS |
| `-Xshare:dump` | — | 创建 CDS 归档 |
| `-XX:SharedArchiveFile` | 默认路径 | CDS 归档文件路径 |
| `-XX:ArchiveClassesAtExit` | 无 | 动态 CDS 归档 |
| `-XX:+AOTClassLinking` | 关闭 | AOT 类链接 |
