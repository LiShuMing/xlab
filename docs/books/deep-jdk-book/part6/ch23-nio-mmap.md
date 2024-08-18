# 第 23 章 NIO 与内存映射

> 源码路径：`src/java.base/share/classes/java/nio/`、`src/java.base/unix/native/libnio/`

Java NIO（Non-blocking I/O）提供了高效的 I/O 抽象——直接缓冲区、内存映射文件、多路复用器。这些机制在 LLM 推理服务的 KV Cache 管理和数据传输中扮演关键角色。本章深入 NIO 的内部实现。

---

## 23.1 `java.nio.Buffer` 体系与 `DirectByteBuffer`

### 23.1.1 Buffer 的层次

```
Buffer (抽象)
├── ByteBuffer
│   ├── HeapByteBuffer        // 堆上的 byte 缓冲区
│   ├── DirectByteBuffer      // 堆外的直接缓冲区
│   └── MappedByteBuffer      // 内存映射文件缓冲区
├── CharBuffer
├── IntBuffer
├── FloatBuffer
└── ...
```

### 23.1.2 Buffer 的核心字段

```java
// Buffer.java
public abstract class Buffer {
    private long address;      // 直接缓冲区的内存地址
    private int  capacity;     // 容量
    private int  limit;        // 读写上限
    private int  position;     // 当前位置
    private int  mark;         // 标记位置
}
```

### 23.1.3 DirectByteBuffer 的实现

`DirectByteBuffer` 使用 `Unsafe.allocateMemory()` 在 Java 堆外分配内存：

```java
// DirectByteBuffer.java（简化）
class DirectByteBuffer extends MappedByteBuffer {
    private final Cleaner cleaner;  // GC 回收时释放原生内存

    DirectByteBuffer(int cap) {
        // 1. 分配原生内存
        long addr = UNSAFE.allocateMemory(cap);

        // 2. 创建 Cleaner（PhantomReference）释放内存
        cleaner = Cleaner.create(this, new Deallocator(addr, cap));
    }
}

class Deallocator implements Runnable {
    public void run() {
        UNSAFE.freeMemory(address);  // GC 回收时释放
    }
}
```

DirectByteBuffer 的优势：
1. **零拷贝**：I/O 操作直接读写原生内存，无需在堆和内核之间复制
2. **GC 友好**：大缓冲区不在 Java 堆中，不增加 GC 扫描压力
3. **对齐友好**：可按页对齐，适合大页和 mmap

DirectByteBuffer 的劣势：
1. **分配/释放慢**：`malloc/free` 比 TLAB 分配慢 100 倍
2. **回收不确定**：依赖 GC 触发 Cleaner，可能延迟释放
3. **内存泄漏**：如果 DirectByteBuffer 对象还在但不再使用，原生内存不会释放

---

## 23.2 `libnio`：NIO 的 Native 实现

### 23.2.1 JNI 调用层次

```
Java 层：
  DirectByteBuffer.allocate()
    → Unsafe.allocateMemory()

  FileChannel.read(ByteBuffer)
    → IOUtil.read(FileDescriptor, ByteBuffer, ...)

Native 层（libnio.so）：
  Java_sun_nio_ch_IOUtil_read()
    → read(fd, buf, len)       // POSIX read

  FileChannel.transferTo()
    → sendfile(fd_out, fd_in, offset, count)  // 零拷贝
```

### 23.2.2 直接缓冲区的 I/O 路径

```
堆缓冲区的 I/O 路径：
  Java 堆 → 临时 DirectByteBuffer → 内核缓冲区 → 磁盘
  复制 2 次

直接缓冲区的 I/O 路径：
  DirectByteBuffer → 内核缓冲区 → 磁盘
  复制 1 次

内存映射的 I/O 路径：
  用户空间直接访问内核映射的页
  复制 0 次（CPU 直接访问页缓存）
```

---

## 23.3 `MappedByteBuffer` 与 `mmap` 的映射

### 23.3.1 MappedByteBuffer 的创建

```java
// 通过 FileChannel 创建映射
MappedByteBuffer mbb = FileChannel.open(path, StandardOpenOption.READ)
    .map(FileChannel.MapMode.READ_ONLY, 0, size);
```

### 23.3.2 mmap 的 JNI 实现

```c
// FileChannelImpl.c（简化）
JNIEXPORT jlong JNICALL
Java_sun_nio_ch_FileChannelImpl_map0(JNIEnv *env, jobject this,
    jint prot, jlong off, jlong len) {
    void *mapAddress;
    int protections = ...;  // PROT_READ, PROT_READ|PROT_WRITE, ...

    mapAddress = mmap64(
        NULL,                   // 让内核选择地址
        len,
        protections,
        MAP_SHARED,             // 共享映射
        fdval(env, fdo),        // 文件描述符
        off                     // 偏移量
    );

    return ((jlong)(intptr_t)mapAddress);
}
```

### 23.3.3 MappedByteBuffer 的特性

| 特性 | 说明 |
|------|------|
| 零拷贝 | 用户空间直接访问文件页缓存 |
| 懒加载 | 只有访问的页才从磁盘加载 |
| 自动同步 | OS 的页缓存机制管理脏页回写 |
| 大文件支持 | 映射 GB 级文件无需全部加载 |
| 释放困难 | `Cleaner` 依赖 GC，无显式 unmap API |

### 23.3.4 映射模式的比较

| 模式 | `mmap` 标志 | 写入行为 |
|------|------------|---------|
| `READ_ONLY` | `PROT_READ, MAP_SHARED` | 写入抛异常 |
| `READ_WRITE` | `PROT_READ\|PROT_WRITE, MAP_SHARED` | 写入自动回写文件 |
| `PRIVATE` | `PROT_READ\|PROT_WRITE, MAP_PRIVATE` | 写入不回写（CoW） |

---

## 23.4 Selector / EPoll 的 JNI 封装

### 23.4.1 Selector 的架构

```
Selector
├── 通道注册（SelectionKey）
├── 多路复用（select/poll/epoll）
└── 事件分发（readyOps）
```

Linux 上默认使用 epoll：

```java
// EPollSelectorProvider.java
public class EPollSelectorProvider extends SelectorProviderImpl {
    public AbstractSelector openSelector() {
        return new EPollSelectorImpl(this);
    }
}
```

### 23.4.2 epoll 的 JNI 实现

```c
// EPoll.c（简化）
// 创建 epoll 实例
JNIEXPORT jint JNICALL
Java_sun_nio_ch_EPoll_epollCreate(JNIEnv *env, jclass c) {
    return epoll_create(256);
}

// 注册事件
JNIEXPORT void JNICALL
Java_sun_nio_ch_EPoll_epollCtl(JNIEnv *env, jclass c,
    jint epfd, jint opcode, jint fd, jint events) {
    struct epoll_event event;
    event.events = events;
    event.data.fd = fd;
    epoll_ctl(epfd, opcode, fd, &event);
}

// 等待事件
JNIEXPORT jint JNICALL
Java_sun_nio_ch_EPoll_epollWait(JNIEnv *env, jclass c,
    jint epfd, jlong address, jint numfds, jint timeout) {
    struct epoll_event *events = (struct epoll_event *)address;
    return epoll_wait(epfd, events, numfds, timeout);
}
```

### 23.4.3 epoll 的触发模式

```
水平触发（LT，默认）：
  只要 fd 有数据可读，epoll_wait 总是返回
  适合：每次只读部分数据的场景

边缘触发（ET）：
  只在 fd 状态变化时通知一次
  适合：每次必须读完所有数据的场景
  Java NIO 不支持 ET 模式

Netty 的 epoll transport：
  Netty 自己封装了 epoll ET 模式，性能更高
  但 JDK NIO 只支持 LT 模式
```

---

## 23.5 [AI 时代思考] 零拷贝与 LLM 推理中的 KV Cache 传输优化

### 23.5.1 KV Cache 的传输瓶颈

LLM 推理中，KV Cache 的传输是关键瓶颈：

```
典型数据量：
  单个请求的 KV Cache：10-100MB
  并发 100 个请求：1-10GB 的 KV Cache 数据

传输路径（无优化）：
  GPU 显存 → CUDA memcpy → CPU 内存 → Java 堆 → 序列化 → 网络
  复制 3-4 次，延迟 ~100ms

优化路径（零拷贝）：
  GPU 显存 → CUDA IPC → 共享内存 → mmap → DirectByteBuffer → 网络
  复制 1 次，延迟 ~10ms
```

### 23.5.2 Java 中的零拷贝方案

```java
// 方案 1：FileChannel.transferTo（sendfile）
fileChannel.transferTo(0, size, socketChannel);

// 方案 2：MappedByteBuffer（mmap）
MappedByteBuffer mbb = fileChannel.map(READ_ONLY, 0, size);
socketChannel.write(mbb);

// 方案 3：DirectByteBuffer + 共享内存
long addr = UNSAFE.allocateMemory(size);
// ... 填充数据 ...
DirectByteBuffer buf = new DirectByteBuffer(addr, size);
socketChannel.write(buf);
```

### 23.5.3 Panama Foreign Memory API 的优势

Panama 的 `MemorySegment` 比 `DirectByteBuffer` 更适合管理 KV Cache：

```java
// Panama 方式
try (Arena arena = Arena.ofShared()) {
    MemorySegment kvCache = arena.allocate(100 * 1024 * 1024);  // 100MB

    // 零拷贝传输
    // MemorySegment 可以直接与 FileChannel 交互
    // 支持 Arena 管理生命周期
    // 支持线程安全访问
}
```

优势：
1. **显式生命周期**：Arena 管理释放，不依赖 GC
2. **更大的映射**：支持超过 2GB 的映射（DirectByteBuffer 限制）
3. **更安全的访问**：边界检查、空指针检查
4. **更好的对齐**：支持自定义对齐

---

## 小结

本章深入了 Java NIO 的内部实现：

1. **DirectByteBuffer** 在堆外分配内存，I/O 零拷贝，但分配/释放慢
2. **mmap 映射**使用户空间直接访问文件页缓存，无需 read/write 系统调用
3. **epoll** 多路复用是高并发 I/O 的基础，Java NIO 默认使用 LT 模式
4. **零拷贝**对 LLM 推理的 KV Cache 传输至关重要，可减少 10 倍延迟
5. **Panama MemorySegment** 是 DirectByteBuffer 的现代替代，更适合大内存管理

第六篇到此完成。第七篇将深入运行时服务——JNI、JVMTI、JFR、NMT。
