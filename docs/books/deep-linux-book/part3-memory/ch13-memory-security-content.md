# 第13章 内存安全与调试

> 源码锚点：`mm/kasan/`、`mm/kfence/`、`mm/kmsan/`、`mm/kmemleak.c`、`mm/page_owner.c`、`arch/x86/mm/mem_encrypt_amd.c`

内核内存漏洞是最危险的安全威胁——越界访问、Use-After-Free、未初始化读取可能导致提权或信息泄露。Linux提供了KASAN/KFENCE/KMSAN三大运行时检测工具和KMSAN/KMEMLEAK等调试工具，以及SME/SEV内存加密防御物理攻击。

## 13.1 KASAN：地址消毒

### shadow memory原理

KASAN(Kernel Address SANitizer)的核心是shadow memory——每8字节的实际内存对应1字节的影子内存，记录这8字节的可访问性：

```
实际内存:    [字节0-7] [字节8-15] [字节16-23] ...
影子内存:    [0x00   ] [0x00    ] [0x04     ] ...
              ↑全可访问  ↑全可访问  ↑只有0-3字节可访问
```

影子值的含义：
- **0x00**：全部8字节可访问
- **0x01-0x07**：只有前N字节可访问（部分对齐分配的尾部）
- **0xFE**：已释放的内存(redzone)
- **0xFx**：各种不可访问标记

1:8的映射比例使得shadow memory的开销为12.5%——对于拥有1TB物理内存的服务器，shadow memory占用128GB。

### x86 shadow映射建立

```c
// arch/x86/mm/kasan_init_64.c
// KASAN的shadow映射在内核启动早期建立
// 将整个内核地址空间的1/8映射为shadow memory
// KASAN_SHADOW_START → KASAN_SHADOW_END
```

x86_64的KASAN shadow区域位于`0xdffffc0000000000`到`0xdffffcffffffffff`，覆盖整个内核直接映射区和vmalloc区域。

### KASAN的插桩

编译器(GCC/Clang)在每次内存访问前插入检查代码：

```c
// 编译器插桩后的代码：
void *p = kmalloc(64, GFP_KERNEL);
p[0] = 1;
// 编译为：
// shadow_byte = *(shadow_addr(p));
// if (shadow_byte)  // 非零意味着可能有问题
//     __asan_loadN(p, 1);  // 详细检查并可能报错
// p[0] = 1;
```

插桩的性能开销约2-3倍——这使得KASAN不适合生产环境，但非常适合测试和模糊测试。

### KASAN的检测能力

| 漏洞类型 | 检测能力 | 原理 |
|---------|---------|------|
| 越界读/写 | 能 | redzone的shadow标记为不可访问 |
| Use-After-Free | 能 | 释放后shadow标记为0xFE |
| 越界下溢 | 能 | 分配前的redzone |
| 双重释放 | 部分 | quarantine延迟释放 |
| 未初始化读取 | 不能 | 需要KMSAN |

### quarantine：延迟释放

`mm/kasan/quarantine.c`延迟释放已释放的对象——将它们放入隔离区，标记为"已释放"但保留shadow memory。这使得UAF检测窗口更大——如果程序在隔离期内访问已释放对象，KASAN能检测到。

隔离区有大小限制——当超过限制时，最老的对象被真正释放。这平衡了检测能力和内存开销。

## 13.2 KFENCE：低开销采样检测

KASAN的性能开销使其不适合生产环境。KFENCE(Kernel Electric Fence)采用不同的策略——**采样检测**：只监控少量分配，但监控更彻底。

```c
// mm/kfence/core.c
// KFENCE的采样策略：
// 1. 每隔一定间隔(sampling interval)选择一个分配进行监控
// 2. 监控的分配被放在独立的页面中，两侧是guard page
// 3. 访问guard page触发页故障 → 检测到越界访问
```

KFENCE的内存布局：

```
[guard page] [对象] [guard page]
  ↑ 不可访问          ↑ 不可访问
  检测下溢            检测上溢
```

任何越界访问都会触及guard page，触发页故障被KFENCE捕获。与KASAN相比：
- **KASAN**：检测所有分配，但性能开销2-3倍
- **KFENCE**：只检测采样分配，性能开销<1%，但可能漏检

KFENCE的价值：可以在生产环境中持续运行，作为安全网捕获偶发的内存错误。结合模糊测试和KASAN（开发阶段）+ KFENCE（生产阶段），实现全生命周期的内存安全检测。

## 13.3 KMSAN：未初始化内存检测

KMSAN(Kernel Memory SANitizer)检测未初始化内存的读取——这是KASAN无法检测的漏洞类型。未初始化读取可能导致信息泄露（泄露内核栈内容到用户态）。

```c
// mm/kmsan/
// KMSAN的shadow memory：每1比特实际内存对应1比特shadow
// shadow=0：已初始化
// shadow=1：未初始化

// origin追踪：记录未初始化值的来源
// 每个未初始化的4字节块关联一个origin
// origin指向分配点的调用栈
```

KMSAN的shadow比例是1:1（每比特对应1比特），内存开销100%——比KASAN的12.5%高得多。KMSAN主要用于开发/测试阶段。

KMSAN的典型检测场景：
- 内核栈变量未初始化就copy_to_user → 信息泄露
- 结构体成员未初始化就传递给网络协议 → 信息泄露
- kmalloc的内存未清零就使用 → 不可预测行为

## 13.4 内存调试工具

### kmemleak：内存泄露检测

`mm/kmemleak.c`通过扫描内核内存查找可能的泄露：

```c
// 原理：
// 1. 跟踪所有kmalloc/vmalloc分配
// 2. 定期扫描内核内存，查找指向已分配对象的指针
// 3. 如果没有指针指向某个对象 → 疑似泄露
```

kmemleak的局限性：它无法检测通过计算得到的指针（如`ptr+offset`），也不能检测通过寄存器持有的指针（只扫描内存）。这导致误报和漏报。

### page_owner：页面所有者追踪

`mm/page_owner.c`记录每个物理页面的分配者——分配时的调用栈、GFP标志、分配顺序。这是分析内存使用的重要工具：

```
# /sys/kernel/debug/page_owner
Page allocated via order 0, gfp_mask 0x12(GFP_KERNEL|__GFP_HIGH)
...
Call stack:
  alloc_pages+0xXX
  slab_alloc+0xXX
  kmalloc+0xXX
  some_driver_init+0xXX
```

### page_poison：页面毒化

`mm/page_poison.c`在页面释放时填充特定模式(0x00或0xAA)，分配时检查模式是否被破坏——如果被破坏，说明有越界写或Use-After-Free。

## 13.5 内存加密：SME/SEV

### AMD SME/SEV

```c
// arch/x86/mm/mem_encrypt_amd.c
// SME(System Memory Encryption)：全系统内存加密
//   - 加密位(C-bit)在页表项中标记
//   - 加密对软件透明——CPU的内存控制器自动加解密
//   - 保护物理攻击（冷启动攻击、DMA攻击）

// SEV(Secure Encrypted Virtualization)：虚拟机级加密
//   - 每个VM有不同的加密密钥
//   - 宿主机无法读取VM的内存
//   - SEV-ES(Encrypt State)：加密VM的寄存器状态
//   - SEV-SNP(Secure Nested Paging)：防止内存映射攻击
```

SME/SEV的C-bit在页表项的第47位（或更高位）——当该位为1时，页面使用内存控制器加密。不同的VM使用不同的ASID(Address Space Identifier)，内存控制器根据ASID选择不同的加密密钥。

### Intel TDX

Intel的TDX(Trust Domain Extensions)是SEV的对等技术，在`arch/x86/coco/tdx/`中实现。TDX使用不同的硬件机制但目标相同——隔离虚拟机的内存，防止宿主机窥探。

### 机密计算的安全模型

SME/SEV/TDX代表了**机密计算**(Confidential Computing)的安全模型转变——从"信任操作系统"到"不信任操作系统"。在这个模型下，即使宿主机的内核被攻破，VM的内存仍然安全。这对AI推理服务有重要意义——模型参数和用户数据在云环境中需要端到端加密保护。

---

本章建立了对内核内存安全和调试的认知：KASAN通过shadow memory检测越界和UAF，KFENCE以低开销采样检测生产环境错误，KMSAN检测未初始化读取，kmemleak查找内存泄露，SME/SEV/TDX提供硬件级内存加密。这些工具从不同角度保障内核内存安全——开发阶段用KASAN/KMSAN全面检测，生产阶段用KFENCE持续监控，硬件加密防御物理攻击。第三篇到此结束，从物理内存管理到虚拟内存、页面回收、大页和安全，构成了对Linux内存子系统的完整认知。
