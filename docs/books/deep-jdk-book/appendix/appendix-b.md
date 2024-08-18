# 附录 B：HotSpot 源码目录速查表

## 顶层目录

```
src/hotspot/
├── share/                    # 平台无关代码
│   ├── adlc/                # AD 文件编译器（C2 指令描述）
│   ├── asm/                 # 汇编器抽象
│   ├── c1/                  # C1 编译器
│   ├── cds/                 # Class Data Sharing
│   ├── classfile/           # 类文件解析和加载
│   ├── code/                # 代码缓存和 nmethod
│   ├── compiler/            # 编译策略和 CompileBroker
│   ├── gc/                  # 垃圾收集器
│   │   ├── serial/          #   Serial GC
│   │   ├── parallel/        #   Parallel GC
│   │   ├── g1/              #   G1 GC
│   │   ├── z/               #   ZGC
│   │   ├── shenandoah/      #   Shenandoah GC
│   │   ├── epsilon/         #   Epsilon GC（无操作）
│   │   └── shared/          #   GC 共享抽象
│   ├── interpreter/         # 解释器
│   ├── jfr/                 # Java Flight Recorder
│   ├── jvmci/               # JVM Compiler Interface
│   ├── logging/             # 统一日志框架
│   ├── memory/              # 内存管理基础设施
│   ├── metaspace/           # 元空间
│   ├── nmt/                 # Native Memory Tracking
│   ├── oops/                # 对象模型（oop 体系）
│   ├── opto/                # C2 编译器
│   ├── prims/               # 原生接口（JNI, JVMTI）
│   ├── runtime/             # 运行时（线程、锁、安全点）
│   ├── services/            # 管理服务（JMX, NMT）
│   └── utilities/           # 工具类
├── cpu/                      # CPU 架构相关代码
│   ├── x86/                 #   x86_64
│   ├── aarch64/             #   ARM 64 位
│   ├── arm/                 #   ARM 32 位
│   ├── ppc/                 #   PowerPC
│   ├── riscv/              #   RISC-V
│   ├── s390/               #   IBM s390
│   └── zero/               #   Zero 解释器（纯 C++）
└── os/                       # 操作系统相关代码
    ├── linux/               #   Linux
    ├── windows/             #   Windows
    ├── bsd/                 #   BSD
    ├── aix/                 #   AIX
    └── posix/               #   POSIX 共享代码
```

## 关键文件速查

| 子系统 | 文件 | 说明 |
|--------|------|------|
| 启动 | `share/prims/jni.cpp` | `JNI_CreateJavaVM` 入口 |
| 初始化 | `share/runtime/init.cpp` | 全局初始化阶段 |
| 线程 | `share/runtime/threads.cpp` | 线程创建和管理 |
| 堆 | `share/memory/universe.cpp` | 堆初始化 |
| GC | `share/gc/g1/g1CollectedHeap.cpp` | G1 堆实现 |
| 锁 | `share/runtime/objectMonitor.cpp` | 重量级锁 |
| 安全点 | `share/runtime/safepoint.cpp` | STW 机制 |
| 解释器 | `share/interpreter/templateInterpreter.cpp` | 模板解释器 |
| C1 | `share/c1/c1_GraphBuilder.cpp` | HIR 构建 |
| C2 | `share/opto/compile.cpp` | C2 编译入口 |
| 逃逸分析 | `share/opto/escape.cpp` | 逃逸分析 |
| 向量化 | `share/opto/superword.cpp` | 自动向量化 |
| 类加载 | `share/classfile/classFileParser.cpp` | 字节码解析 |
| CDS | `share/cds/archiveBuilder.cpp` | 归档构建 |
| JNI | `share/prims/jni.cpp` | JNI 函数表 |
| JVMTI | `share/prims/jvmti.cpp` | JVMTI 接口 |
| JFR | `share/jfr/recorder/jfrRecorder.cpp` | 飞行记录器 |
| NMT | `share/nmt/mallocTracker.cpp` | 原生内存追踪 |
