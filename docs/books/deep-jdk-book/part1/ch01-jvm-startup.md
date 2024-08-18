# 第 1 章 JVM 启动全流程：从 `java` 命令到 `main()` 执行

> 源码路径：`src/java.base/share/native/libjli/java.c`、`src/hotspot/share/prims/jni.cpp`、`src/hotspot/share/runtime/threads.cpp`、`src/hotspot/share/runtime/init.cpp`、`src/hotspot/share/runtime/arguments.cpp`

当我们在终端键入 `java -Xmx4g -jar app.jar` 并按下回车，到应用 `main()` 方法的第一行代码执行，中间经历了什么？这是理解整个 JVM 运行机制的起点。本章将从源码出发，逐行追踪这条启动链路。

---

## 1.1 `libjli/java.c`：JVM 启动器源码剖析

### 1.1.1 入口函数 `JLI_Launch`

`java` 命令对应的 C 语言入口并非 `main()`，而是 `JLI_Launch()`。这个函数定义在 `src/java.base/share/native/libjli/java.c` 中，是所有 JDK 工具（`java`、`javac`、`javadoc` 等）的共享启动入口。

```c
// java.c:226
JNIEXPORT int JNICALL
JLI_Launch(int argc, char ** argv,
        int jargc, const char** jargv,
        int appclassc, const char** appclassv,
        const char* fullversion,
        const char* dotversion,
        const char* pname,
        const char* lname,
        jboolean javaargs,
        jboolean cpwildcard,
        jboolean javaw,
        jint ergo)
```

`JLI_Launch` 的核心执行流程分为 5 个阶段：

**阶段 1：创建执行环境**

```c
// java.c:273
CreateExecutionEnvironment(&argc, &argv,
                           jdkroot, sizeof(jdkroot),
                           jvmpath, sizeof(jvmpath),
                           jvmcfg, sizeof(jvmcfg));
```

`CreateExecutionEnvironment` 是平台相关的函数（定义在 `java.c` 的平台分支中），它完成三件事：
1. 确定 JDK 安装根目录（`jdkroot`）
2. 定位 JVM 动态库路径（`jvmpath`，如 `lib/server/libjvm.so`）
3. 读取 `jvm.cfg` 配置文件确定使用哪个 JVM 变体（server / client）

`jvm.cfg` 的解析由 `ReadKnownVMs()` 完成，它识别 `KNOWN`、`ALIASED_TO`、`IF_SERVER_CLASS` 等指令。在现代 JDK 中，默认只有一个 server 变体。

**阶段 2：加载 JVM 动态库**

```c
// java.c:285
if (!LoadJavaVM(jvmpath, &ifn)) {
    return(6);
}
```

`LoadJavaVM` 通过 `dlopen` 加载 `libjvm.so`，然后通过 `dlsym` 查找两个关键函数指针：

```c
ifn.CreateJavaVM = (CreateJavaVM_t)dlsym(libjvm, "JNI_CreateJavaVM");
ifn.GetDefaultJavaVMInitArgs = (GetDefaultJavaVMInitArgs_t)dlsym(libjvm, "JNI_GetDefaultJavaVMInitArgs");
```

`InvocationFunctions` 结构体保存了这两个函数指针，这是启动器与 JVM 之间唯一的接口契约。

**阶段 3：解析命令行参数**

```c
// java.c:315
if (!ParseArguments(&argc, &argv, &mode, &what, &ret)) {
    return(ret);
}
```

`ParseArguments` 将命令行参数分为三类：
- **启动器参数**：`-jar`、`-cp`、`-m`、`--source` 等，由启动器自身消费
- **JVM 参数**：`-Xmx`、`-Xms`、`-Xss`、`-XX:...` 等，通过 `AddOption()` 收集到 `options` 数组中传递给 JVM
- **应用参数**：主类名/JAR 名及其后的参数

启动模式（`mode`）有四种：

| 模式 | 值 | 含义 |
|------|------|------|
| `LM_CLASS` | 1 | 执行指定类 (`java com.example.Main`) |
| `LM_JAR` | 2 | 执行 JAR 文件 (`java -jar app.jar`) |
| `LM_MODULE` | 3 | 执行模块 (`java -m module/main`) |
| `LM_SOURCE` | 4 | 执行源文件 (`java --source 21 App.java`) |

值得注意的是 `-Xss`/`-Xmx`/`-Xms` 的处理：启动器不仅将它们传递给 JVM，还自行解析以确定创建 JVM 线程所需的栈大小：

```c
// java.c:989-1011
if (JLI_StrCCmp(str, "-Xss") == 0) {
    jlong tmp;
    if (parse_size(str + 4, &tmp)) {
        threadStackSize = tmp;
        if (threadStackSize > 0 && threadStackSize < (jlong)STACK_SIZE_MINIMUM) {
            threadStackSize = STACK_SIZE_MINIMUM;  // 64KB 最小值
        }
    }
}
```

`STACK_SIZE_MINIMUM` 定义为 64KB——这是 JVM 能够拒绝过小 `-Xss` 值的最低门槛。

**阶段 4：在新线程中启动 JVM**

```c
// java.c:330
return JVMInit(&ifn, threadStackSize, argc, argv, mode, what, ret);
```

`JVMInit` 是平台相关的。在 Linux/POSIX 上，它调用 `ContinueInNewThread`，后者通过 `CallJavaMainInNewThread` 创建一个新线程来执行 `JavaMain`。

为什么不在主线程（primordial thread）中直接运行？源码注释给出了答案：

```c
// java.c:204-207
/*
 * Running Java code in primordial thread caused many problems.
 * We will create a new thread to invoke JVM. See 6316197 for more information.
 */
```

原始线程的栈大小和信号掩码不可控，在某些平台上会导致问题。创建新线程可以精确控制栈大小，并避免原始线程的信号处理干扰。

**阶段 5：`JavaMain`——JVM 的真正入口**

```c
// java.c:468
int JavaMain(void* _args)
{
    JavaMainArgs *args = (JavaMainArgs *)_args;
    // ...
    JavaVM *vm = 0;
    JNIEnv *env = 0;

    // 初始化 JVM
    if (!InitializeJVM(&vm, &env, &ifn)) {
        JLI_ReportErrorMessage(JVM_ERROR1);
        exit(1);
    }

    // 加载主类
    mainClass = LoadMainClass(env, mode, what);

    // 调用 main 方法
    if (isStaticMain) {
        if (noArgMain) {
            ret = invokeStaticMainWithoutArgs(env, mainClass);
        } else {
            ret = invokeStaticMainWithArgs(env, mainClass, mainArgs);
        }
    } else {
        // 实例 main 方法（JDK 21+ 新特性）
        if (noArgMain) {
            ret = invokeInstanceMainWithoutArgs(env, mainClass);
        } else {
            ret = invokeInstanceMainWithArgs(env, mainClass, mainArgs);
        }
    }

    LEAVE();  // DetachCurrentThread + DestroyJavaVM
}
```

JDK 21 引入了简化 `main` 方法声明的特性——`main()` 可以是实例方法且无需参数。`JavaMain` 中通过 `isStaticMain` 和 `noArgMain` 两个标志组合出四种调用路径，按优先级尝试：
1. `static void main(String[] args)` —— 传统入口
2. `static void main()` —— 无参静态入口
3. `void main(String[] args)` —— 实例方法入口
4. `void main()` —— 无参实例入口

`LEAVE()` 宏执行清理：先 `DetachCurrentThread`（触发未捕获异常处理器），再 `DestroyJavaVM`（等待所有非守护线程结束后销毁 JVM）。

---

## 1.2 `CreateJavaVM`：JNI 规范与 HotSpot 入口

### 1.2.1 `InitializeJVM`：构建 JNI 调用参数

回到启动器侧，`InitializeJVM` 函数将启动器收集的选项组装为 `JavaVMInitArgs` 结构：

```c
// java.c:1471
static jboolean InitializeJVM(JavaVM **pvm, JNIEnv **penv,
                              InvocationFunctions *ifn)
{
    JavaVMInitArgs args;
    memset(&args, 0, sizeof(args));
    args.version  = JNI_VERSION_1_2;
    args.nOptions = numOptions;
    args.options  = options;
    args.ignoreUnrecognized = JNI_FALSE;

    r = ifn->CreateJavaVM(pvm, (void **)penv, &args);
    JLI_MemFree(options);
    return r == JNI_OK;
}
```

注意 `ignoreUnrecognized = JNI_FALSE`——任何 JVM 不认识的选项都会导致启动失败。这与 JNI 嵌入式用法不同，嵌入者通常设为 `JNI_TRUE` 以容忍未知选项。

### 1.2.2 `JNI_CreateJavaVM`：跨入 HotSpot 世界

`ifn->CreateJavaVM` 指向的函数就是 `JNI_CreateJavaVM`，定义在 `src/hotspot/share/prims/jni.cpp:3710`：

```c
_JNI_IMPORT_OR_EXPORT_ jint JNICALL JNI_CreateJavaVM(JavaVM **vm,
                                                      void **penv,
                                                      void *args) {
    jint result = JNI_ERR;
#if defined(_WIN32) && !defined(USE_VECTORED_EXCEPTION_HANDLING)
    __try {
#endif
        result = JNI_CreateJavaVM_inner(vm, penv, args);
#if defined(_WIN32) && !defined(USE_VECTORED_EXCEPTION_HANDLING)
    } __except(topLevelExceptionFilter(...)) {
        // Windows SEH 保护
    }
#endif
    return result;
}
```

Windows 平台使用 SEH（Structured Exception Handling）包裹，防止 JVM 崩溃时进程异常终止。

### 1.2.3 `JNI_CreateJavaVM_inner`：单例保证与核心委托

```c
// jni.cpp:3569
static jint JNI_CreateJavaVM_inner(JavaVM **vm, void **penv, void *args) {
    // 原子操作保证单例——同一进程只能创建一个 JVM
    if (AtomicAccess::xchg(&vm_created, IN_PROGRESS) != NOT_CREATED) {
        return JNI_EEXIST;
    }

    // 防止 destroy 后重建
    if (AtomicAccess::xchg(&safe_to_recreate_vm, 0) == 0) {
        return JNI_ERR;
    }

    bool can_try_again = true;
    result = Threads::create_vm((JavaVMInitArgs*) args, &can_try_again);

    if (result == JNI_OK) {
        *vm = (JavaVM *)(&main_vm);
        *(JNIEnv**)penv = thread->jni_environment();
        AtomicAccess::release_store(&vm_created, COMPLETE);
        // ...
    }
}
```

两个关键的原子变量保证 JVM 实例的唯一性：
- `vm_created`：状态机 `NOT_CREATED → IN_PROGRESS → COMPLETE`，使用 `AtomicAccess::xchg` 做互斥
- `safe_to_recreate_vm`：一旦 JVM 创建成功又销毁，不允许在同一个进程中再次创建

成功时，返回给调用者的是：
- `*vm`：指向全局 `main_vm`（`JavaVM` 结构体实例）的指针
- `*penv`：主线程的 `JNIEnv` 指针，后续所有 JNI 调用的入口

---

## 1.3 `init.cpp`：JVM 全局初始化链路

`Threads::create_vm()` 是 JVM 初始化的核心函数（`threads.cpp:451`），它编排了所有子系统的初始化顺序。而 `init.cpp` 定义了这些子系统初始化的分组函数。

### 1.3.1 `Threads::create_vm` 的初始化阶段总览

```
Threads::create_vm()
├── Phase 0: 基础设施准备
│   ├── VM_Version::early_initialize()     // CPU 特性早期探测
│   ├── ThreadLocalStorage::init()         // 线程本地存储
│   ├── ostream_init()                     // 输出流
│   ├── os::init()                         // 操作系统初始化
│   ├── Arguments::parse(args)             // 参数解析
│   ├── MemTracker::initialize()           // NMT 初始化
│   ├── Arguments::apply_ergo()            // 人体工程学
│   └── os::init_2()                       // OS 二次初始化
├── Phase 1: vm_init_globals()             // 全局数据结构
│   ├── check_ThreadShadow()
│   ├── basic_types_init()
│   ├── eventlog_init()
│   ├── mutex_init()                       // 互斥锁系统
│   ├── universe_oopstorage_init()
│   ├── perfMemory_init()
│   └── ExternalsRecorder_init()
├── Phase 2: init_globals()                // 核心子系统
│   ├── bytecodes_init()                   // 字节码定义
│   ├── classLoader_init1()                // 类加载器
│   ├── codeCache_init()                   // 代码缓存
│   ├── VM_Version_init()                  // CPU 特性完整探测
│   ├── universe_init()                    // 堆初始化！
│   ├── continuations_init()               // 协程
│   ├── interpreter_init_stub()            // 解释器桩
│   └── SharedRuntime::generate_stubs()
├── Phase 3: init_globals2()               // 编译与运行时
│   ├── universe2_init()                   // 加载原始类
│   ├── javaClasses_init()                 // Java 类初始化
│   ├── interpreter_init_code()            // 解释器模板
│   ├── compileBroker_init()               // 编译器启动
│   ├── compiler_stubs_init()              // 编译器桩
│   └── final_stubs_init()
├── Phase 4: VMThread 创建
│   └── VMThread::create() + os::start_thread()
├── Phase 5: Java 世界初始化
│   ├── initialize_java_lang_classes()     // java.lang.* 初始化
│   ├── set_init_completed()               // 标记初始化完成
│   ├── call_initPhase2()                  // 模块系统初始化
│   └── call_initPhase3()                  // 安全管理器、系统类加载器
└── Phase 6: 服务启动
    ├── CompileBroker::compilation_init()  // JIT 编译器
    ├── ServiceThread::initialize()        // 服务线程
    ├── MonitorDeflationThread::initialize()
    └── Management::initialize()           // JMX
```

### 1.3.2 初始化依赖关系的关键约束

从源码中可以提炼出几条关键的依赖链：

**1. `codeCache_init` → `VM_Version_init` → `universe_init`**

```c
// init.cpp:135-142
codeCache_init();
VM_Version_init();              // depends on codeCache_init for emitting code
// ...
jint status = universe_init();  // dependent on codeCache_init and preuniverse_stubs_init
```

`VM_Version_init` 需要向 `CodeCache` 中写入探测代码来检测 CPU 特性（如 AVX2、AVX-512 等），因此必须在 `codeCache_init` 之后。而堆的初始化（`universe_init`）需要知道压缩 oop 的范围，这取决于 CPU 地址空间特性。

**2. `universe_init` → `interpreter_init_stub` → `interpreter_init_code`**

解释器的初始化分为两步：先生成桩代码（stub），等类加载完成后再生成完整的字节码模板。这种两阶段设计确保解释器在类加载过程中就可以运行少量代码。

**3. `init_globals` vs `init_globals2` 的分界线**

`init_globals2`（`init.cpp:181`）在 `CompileBroker` 初始化之前需要完成 Java 类的初始化。这是因为编译器需要能够反射查询类的信息。分两阶段是为了在编译器启动前确保所有基础设施就绪。

### 1.3.3 `_init_completed` 标志与初始化屏障

```c
// init.cpp:247-265
static volatile bool _init_completed = false;

bool is_init_completed() {
    return AtomicAccess::load_acquire(&_init_completed);
}

void set_init_completed() {
    assert(Universe::is_fully_initialized(), "Should have completed initialization");
    MonitorLocker ml(InitCompleted_lock, Monitor::_no_safepoint_check_flag);
    AtomicAccess::release_store(&_init_completed, true);
    ml.notify_all();
}
```

`_init_completed` 使用 `AtomicAccess::load_acquire` / `release_store` 实现发布-订阅语义。其他线程可以通过 `wait_init_completed()` 阻塞等待初始化完成。这个标志在多处被检查——例如，在初始化完成前抛出异常需要走特殊路径，因为异常处理依赖的类可能尚未加载。

---

## 1.4 `arguments.cpp`：JVM 参数解析与校验机制

### 1.4.1 参数解析的三个阶段

`Arguments::parse(args)` 内部将参数解析分为三个阶段：

**阶段 1：`parse_vm_init_args`——原始参数解析**

将 `JavaVMInitArgs` 中的选项逐个解析，分为：
- `-X` 前缀选项（如 `-Xmx4g`、`-Xint`）
- `-XX:` 前缀选项（如 `-XX:+UseG1GC`、`-XX:MaxHeapSize=4g`）
- `-D` 系统属性（如 `-Djava.class.path=...`）

**阶段 2：`apply_ergo`——人体工程学自动调优**

JVM 的「人体工程学」（Ergonomics）是根据运行环境自动选择最优参数的机制：

```c
// threads.cpp:506
jint ergo_result = Arguments::apply_ergo();
```

人体工程学决定的关键参数包括：
- **GC 选择**：根据堆大小和 CPU 数量选择 GC 算法
- **堆大小**：如果未指定 `-Xmx`，根据物理内存自动计算
- **编译器选择**：根据 CPU 核数决定是否启用分层编译
- **线程栈大小**：平台相关的默认值

**阶段 3：约束校验**

```c
// threads.cpp:510-518
if (!JVMFlagLimit::check_all_ranges()) {
    return JNI_EINVAL;
}
bool constraint_result = JVMFlagLimit::check_all_constraints(
    JVMFlagConstraintPhase::AfterErgo);
```

参数的约束分两类：
- **范围约束**：如 `MaxHeapSize` 必须大于 `InitialHeapSize`
- **语义约束**：如 `UseZGC` 和 `UseSerialGC` 不能同时启用

### 1.4.2 JVM Flag 体系

JDK 27 的 Flag 系统定义在 `runtime/flags/jvmFlag.hpp` 中，每个 Flag 声明时携带类型、默认值、约束和文档：

```c
// globals.hpp 示例（简化）
product(size_t, MaxHeapSize, 0,                                   \
        "Maximum size of the Java heap")                           \
        range(0, max_uintx)                                        \
        constraint(MaxHeapSizeConstraintFunc, AfterErgo)
```

Flag 的分类：
- **product**：产品构建可用，最常见
- **develop**：仅 debug 构建可用
- **diagnostic**：需要 `-XX:+UnlockDiagnosticVMOptions`
- **experimental**：需要 `-XX:+UnlockExperimentalVMOptions`
- **manageable**：运行时可通过 JMX 动态修改

### 1.4.3 参数解析中的关键细节

**`-Xms` 与 `-Xmx` 的默认值**

当用户未指定时，人体工程学的默认行为：
- `-Xms`：物理内存 / 64（最小 8MB）
- `-Xmx`：物理内存 / 4（最大 32GB 以下可使用压缩 oop）

**执行模式**

```c
Arguments::Mode Arguments::_mode = _mixed;
```

默认 `_mixed` 模式（混合模式：解释 + JIT）。`-Xint` 强制纯解释，`-Xcomp` 强制首次执行就编译。

---

## 1.5 `thread.cpp`：主线程的诞生与 `Threads::create_vm()`

### 1.5.1 主线程的创建

在 `Threads::create_vm()` 中，主线程的创建发生在所有子系统初始化之前：

```c
// threads.cpp:572-587
JavaThread* main_thread = new JavaThread();
main_thread->set_thread_state(_thread_in_vm);
main_thread->initialize_thread_current();
MemTracker::NmtVirtualMemoryLocker::set_safe_to_use();
main_thread->record_stack_base_and_size();
main_thread->register_thread_stack_with_NMT();
main_thread->set_active_handles(JNIHandleBlock::allocate_block());

const int64_t main_thread_tid = ThreadIdentifier::next();
guarantee(main_thread_tid == 3, "Must equal the PRIMORDIAL_TID used in Threads.java");
main_thread->set_monitor_owner_id(main_thread_tid);
```

主线程的 `tid` 被硬编码为 3——这是 JDK 内部协议。`tid=1` 和 `tid=2` 预留给内部使用，`tid=3` 是第一个用户可见的线程 ID。

`new JavaThread()` 的构造过程：
1. 分配 OSThread（封装 OS 原生线程对象）
2. 分配 Java 栈空间
3. 初始化 `JavaFrameAnchor`（栈帧锚点）
4. 创建 `MonitorChunk` 链表

### 1.5.2 `Threads::create_vm` 的启动阶段

从 `threads.cpp:451` 开始，`create_vm` 函数按照严格的顺序编排了约 60 个初始化步骤。以下是关键里程碑：

| 时间点 | 初始化步骤 | 意义 |
|--------|-----------|------|
| 早期 | `VM_Version::early_initialize()` | 探测 CPU 特性，影响后续所有决策 |
| 早期 | `os::init()` + `os::init_2()` | 内存页大小、处理器数、信号处理 |
| 中期 | `universe_init()` | **堆的创建——JVM 最核心的数据结构** |
| 中期 | `interpreter_init_stub()` | 解释器可以执行字节码 |
| 中期 | `universe2_init()` | 加载 `Object`、`Class` 等原始类 |
| 晚期 | `set_init_completed()` | 初始化完成标志，其他线程可以继续 |
| 晚期 | `VMThread::create()` | VMThread 开始运行，安全点机制就绪 |
| 末期 | `call_initPhase2/3()` | Java 层模块系统和安全管理器初始化 |

### 1.5.3 VMThread 的启动

VMThread 是 JVM 内部最重要的线程之一，负责执行所有需要全局安全点的操作：

```c
// threads.cpp:648-667
VMThread::create();
VMThread* vmthread = VMThread::vm_thread();

if (!os::create_thread(vmthread, os::vm_thread)) {
    vm_exit_during_initialization("Cannot create VM thread.");
}

{
    MonitorLocker ml(Notify_lock);
    os::start_thread(vmthread);
    while (!vmthread->is_running()) {
        ml.wait();  // 等待 VMThread 就绪
    }
}
```

启动器使用 `Notify_lock` 等待 VMThread 进入运行状态。VMThread 启动后会进入 `loop()` 循环，等待 `VMOperation` 队列中的任务。

### 1.5.4 `main()` 方法的调用链

JVM 初始化完成后，回到 `JavaMain` 函数，执行以下步骤调用 `main()`：

1. **`LoadMainClass`**：通过 `LauncherHelper.checkAndLoadMain()` 加载主类
2. **`GetApplicationClass`**：获取真正的应用类（可能不同于 mainClass，如 JavaFX 场景）
3. **`CreateApplicationArgs`**：将 C 字符串数组转换为 Java `String[]`
4. **调用 main 方法**：根据 `isStaticMain` 和 `noArgMain` 选择四种调用方式之一

```c
// java.c:636-648
if (isStaticMain) {
    if (noArgMain) {
        ret = invokeStaticMainWithoutArgs(env, mainClass);
    } else {
        ret = invokeStaticMainWithArgs(env, mainClass, mainArgs);
    }
} else {
    if (noArgMain) {
        ret = invokeInstanceMainWithoutArgs(env, mainClass);
    } else {
        ret = invokeInstanceMainWithArgs(env, mainClass, mainArgs);
    }
}
```

对于传统的 `static void main(String[] args)`，最终通过 JNI 调用：

```c
jmethodID mainID = (*env)->GetStaticMethodID(env, mainClass, "main",
                                "([Ljava/lang/String;)V");
(*env)->CallStaticVoidMethod(env, mainClass, mainID, mainArgs);
```

此时，JVM 完整的执行引擎已就绪：解释器可以执行字节码，JIT 编译器随时准备编译热点代码，GC 在后台守护堆内存，用户的 Java 应用正式开始运行。

---

## 1.6 [体系结构视角] 启动阶段的 CPU 分支预测与 I-Cache 行为

### 1.6.1 启动阶段的分支预测特性

JVM 启动是一个典型的「冷启动」场景——对于 CPU 的分支预测器而言，所有代码路径都是首次执行，预测准确率极低。

**条件分支的预测惩罚**

在 `ParseArguments`、`Arguments::parse` 等函数中，大量 `if-else` 链对命令行参数进行匹配。这些分支具有以下特征：
- 每个分支在一次启动中只执行一次（one-shot）
- 分支方向不可预测（取决于用户输入）
- CPU 的两级自适应预测器（2-bit saturating counter + global history）在此完全失效

现代 CPU（如 Intel Sunny Cove / AMD Zen 5）对分支预测误判的惩罚约为 15-20 个时钟周期。在启动阶段，这意味着大量的流水线冲刷。

**JVM 的应对策略**

JVM 在启动关键路径上并没有特别的优化——因为启动只发生一次，分支预测惩罚是不可避免的。但有两点值得注意：

1. `VM_Version::early_initialize()` 中的 CPU 特性探测代码使用 `cpuid` 指令，这条指令是**串行化指令**，会清空流水线。因此它被安排在最早的阶段执行，避免在热路径上影响性能。

2. `Threads::create_vm()` 中的初始化顺序不是随意的——它遵循了依赖关系，但也考虑了代码局部性。紧密耦合的初始化步骤在源码中物理相邻，有助于指令缓存的利用。

### 1.6.2 I-Cache 行为与启动延迟

JVM 启动加载的代码量巨大：`libjvm.so` 在典型构建中超过 30MB。然而启动阶段只执行其中很小一部分代码。

**I-Cache 足迹分析**

| 阶段 | 主要代码 | 估算 I-Cache 足迹 |
|------|---------|-------------------|
| 启动器 (`libjli`) | 参数解析、JVM 加载 | < 100KB |
| `JNI_CreateJavaVM` | 互斥检查、线程创建 | ~50KB |
| `vm_init_globals` | 互斥锁、事件日志 | ~200KB |
| `init_globals` | 字节码、类加载器、堆 | ~1MB |
| `init_globals2` | 编译器、运行时 | ~2MB |
| Java 类初始化 | `java.lang.*` 加载 | ~500KB |

**关键观察**：`init_globals` 和 `init_globals2` 阶段是 I-Cache 压力最大的区间。此时 CPU 需要在堆初始化、解释器生成、编译器启动之间跳转，代码的工作集远超 L1 I-Cache（通常 32-64KB），甚至可能超过 L2（256KB-1MB）。

**CDS/AOT 的 I-Cache 优化**

CDS（Class Data Sharing）通过将类的元数据预先归档到内存映射文件中，显著减少了启动阶段的代码路径：
- 无 CDS：类加载需要解析字节码 → 验证 → 链接，每步都涉及大量条件逻辑
- 有 CDS：直接从归档映射，路径接近线性

AOT（Ahead-of-Time）链接进一步缩短了路径，`aotLinkedClassBulkLoader` 跳过了类解析的分支密集代码。

### 1.6.3 对 AI 推理服务冷启动的启示

LLM 推理服务的冷启动延迟是一个关键指标。如果推理服务使用 Java 实现（如基于 ONNX Runtime Java API 的推理引擎），JVM 启动时间可能占总冷启动时间的 30-50%。

优化思路：

1. **CDS + AOT 归档**：将推理框架的所有类预归档，消除类加载的 I-Cache 压力
2. **`-Xshare:on`**：强制使用 CDS，若归档不可用则启动失败（避免退化为慢路径）
3. **`-XX:InitialCodeCacheSize`**：预分配代码缓存，避免运行时扩容
4. **分层编译延迟**：`-XX:-TieredCompilation` 或 `-XX:TieredStopAtLevel=1`，减少编译器线程的 I-Cache 竞争
5. **EagerAppCDS / Leyden**：JDK 的 Project Leyden 正在探索更激进的 AOT 编译，将启动路径编译为原生代码

从体系结构角度看，冷启动优化的本质是**将不可预测的分支密集路径转化为可预测的线性路径**——这与 CPU 流水线的设计哲学完全一致。

---

## 小结

本章追踪了从 `java` 命令到 `main()` 执行的完整链路：

1. **启动器**（`libjli/java.c`）负责参数解析、JVM 库加载和线程创建
2. **JNI 入口**（`JNI_CreateJavaVM`）保证单例，委托给 `Threads::create_vm()`
3. **全局初始化**（`init.cpp`）按严格依赖顺序初始化所有子系统
4. **参数解析**（`arguments.cpp`）支持三级处理：解析 → 人体工程学 → 约束校验
5. **主线程**在初始化早期创建，贯穿整个 JVM 生命周期
6. **体系结构视角**：启动是分支预测和 I-Cache 的最差场景，CDS/AOT 是从硬件层面缓解这一问题的工程方案

下一章将深入操作系统适配层，看 JVM 如何在 Linux/Windows/POSIX 之间建立统一的抽象。
