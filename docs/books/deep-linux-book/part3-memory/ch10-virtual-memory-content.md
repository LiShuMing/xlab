# 第10章 虚拟内存与缺页

> 源码锚点：`mm/mmap.c`、`mm/vma.c`、`mm/memory.c`、`mm/rmap.c`、`mm/gup.c`、`mm/mprotect.c`、`mm/mseal.c`、`mm/madvise.c`

虚拟内存是操作系统最伟大的抽象——每个进程拥有独立的地址空间，通过页表映射到物理内存，按需分配，透明换页。本章深入VMA管理、页表操作、缺页处理和反向映射，理解虚拟内存的完整机制。

## 10.1 VMA：虚拟内存区域

### vm_area_struct

VMA(虚拟内存区域)描述进程地址空间中一段连续的虚拟地址范围，具有相同的属性（权限、映射文件等）：

```c
// include/linux/mm_types.h
struct vm_area_struct {
    unsigned long vm_start;           // 起始虚拟地址(含)
    unsigned long vm_end;             // 结束虚拟地址(不含)
    struct mm_struct *vm_mm;          // 所属地址空间
    pgprot_t vm_page_prot;            // 默认页保护属性
    unsigned long vm_flags;           // 标志(VM_READ/VM_WRITE/VM_EXEC等)
    struct file *vm_file;             // 映射的文件(匿名映射为NULL)
    unsigned long vm_pgoff;           // 文件偏移(页单位)
    struct vm_operations_struct *vm_ops;  // VMA操作集
    struct maple_tree *vm_mt;         // 所属的maple tree
};
```

VMA的典型用途：
- 代码段：`VM_READ | VM_EXEC`，映射ELF文件的.text段
- 数据段：`VM_READ | VM_WRITE`，映射ELF文件的.data段
- 堆：`VM_READ | VM_WRITE`，匿名映射，brk/sbrk扩展
- 栈：`VM_READ | VM_WRITE | VM_GROWSDOWN`，匿名映射，自动扩展
- mmap区：文件映射或匿名映射

### VMA管理：maple tree

Linux 7.0将VMA的索引结构从红黑树迁移到maple tree——一种基于B树的变体，支持高效的范围查询和区间操作：

```c
// mm/vma.c
// VMA查找：找到包含addr的VMA
struct vm_area_struct *find_vma(struct mm_struct *mm, unsigned long addr)

// VMA合并：相邻且属性兼容的VMA合并为一个
struct vm_area_struct *vma_merge(struct vma_iterator *vmi, ...)

// VMA分裂：将一个VMA在指定地址处分裂为两个
int split_vma(struct vma_iterator *vmi, struct vm_area_struct *vma, ...)
```

`vma_merge()`的条件：两个VMA必须相邻、具有相同的vm_flags、相同的文件映射和偏移、相同的匿名映射。满足条件时合并，减少VMA数量，降低管理开销。

## 10.2 mmap与地址空间布局

### 进程地址空间布局

x86_64进程的虚拟地址空间布局：

```
0x0000000000000000 ┌──────────────┐
                   │ 不可访问      │ ← NULL保护页
0x0000000000400000 ├──────────────┤
                   │ 代码段(.text) │ ← ELF映射
                   │ 数据段(.data) │
                   ├──────────────┤
                   │ 堆(brk)       │ ← 向上增长
                   │              │
0x7f...            ├──────────────┤
                   │ mmap区       │ ← 文件映射/匿名映射，向下增长
                   │              │
0x7f...fffxxxxx   ├──────────────┤
                   │ 栈           │ ← 向下增长
0x7f...ffff0000   ├──────────────┤
                   │ VDSO         │
0xffff...80000000 ├──────────────┤
                   │ 内核空间      │ ← 仅内核态可访问
0xffffffffffffffff └──────────────┘
```

`do_mmap()`分配虚拟地址范围并创建VMA：

```c
// mm/mmap.c (简化)
unsigned long do_mmap(struct file *file, unsigned long addr,
                      unsigned long len, unsigned long prot,
                      unsigned long flags, unsigned long pgoff)
{
    // 1. 参数检查
    // 2. 查找空闲虚拟地址(unmapped_area)
    // 3. 创建VMA
    // 4. 如果是文件映射，建立file->vm_file关联
    // 5. 如果是MAP_POPULATE，预分配页面
}
```

### mmap_lock

`mm->mmap_lock`是保护地址空间操作的读写锁——mmap/munmap/mprotect等操作需要写锁，缺页处理需要读锁。这个锁是数据库工作负载中的常见争用点——大量并发查询同时触发缺页时，读锁的竞争可能成为瓶颈。

## 10.3 页表管理

x86_64使用四级或五级页表：

```
虚拟地址: [P4D索引][PGD索引][PUD索引][PMD索引][PTE索引][页内偏移]
            │        │        │        │        │        │
            ▼        ▼        ▼        ▼        ▼        ▼
         P4D表 → PGD表 → PUD表 → PMD表 → PTE表 → 物理页
```

每个进程有自己的页表，`mm_struct->pgd`指向顶级页表。上下文切换时通过`switch_mm()`加载`CR3`寄存器切换页表。

页表项标志位：
- **Present**：页面在物理内存中
- **R/W**：可写
- **U/S**：用户态可访问
- **NX**：不可执行
- **Accessed**：已被访问（CPU自动设置）
- **Dirty**：已被写入（CPU自动设置）

Accessed位是页面回收的重要信号——内核定期扫描Accessed位来追踪页面的活跃程度，扫描后清除该位。

## 10.4 缺页异常处理

缺页异常是虚拟内存按需分配的触发点——页面首次访问时才分配物理页和建立页表映射。

### 缺页处理路径

```c
// arch/x86/mm/fault.c → mm/memory.c
do_page_fault(regs)
  → handle_mm_fault(vma, address, flags)
    → __handle_mm_fault(vma, address, flags)
      → handle_pte_fault(vmf)
        ├── PTE不存在：
        │   ├── 匿名页：do_anonymous_page()
        │   └── 文件页：do_fault()
        ├── PTE存在但写保护：
        │   └── do_wp_page()  ← COW处理
        └── NUMA页面：
            └── do_numa_page()
```

### 匿名页缺页：do_anonymous_page()

```c
// mm/memory.c (简化)
static vm_fault_t do_anonymous_page(struct vm_fault *vmf)
{
    // 读缺页：分配一个全零页面(可能是共享的zero page)
    if (!(vmf->flags & FAULT_FLAG_WRITE)) {
        page = my_zero_page();     // 全局共享的零页
        entry = pte_mkspecial(pfn_pte(my_zero_pfn, vma->vm_page_prot));
    } else {
        // 写缺页：分配新的物理页
        page = alloc_zeroed_user_highpage_movable(vma, vmf->address);
        entry = mk_pte(page, vma->vm_page_prot);
        entry = pte_sw_mkyoung(entry);
        entry = maybe_pte_mkwrite(pte_mkdirty(entry), vma);
    }
    set_pte_at(vma->vm_mm, vmf->address, vmf->pte, entry);
}
```

优化点：只读的匿名页缺页不分配物理页，而是映射到全局共享的零页——这是一个特殊的物理页，内容全零，被所有进程的只读匿名页共享。只有写入时才分配真正的物理页（触发写保护异常进入COW路径）。

### 写时复制(COW)：do_wp_page()

fork()后父子进程共享物理页，页表项标记为只读。任一方写入时触发写保护异常：

```c
// mm/memory.c (简化)
static vm_fault_t do_wp_page(struct vm_fault_t *vmf)
{
    // 如果页面只有一个映射(非共享)，直接修改页表权限即可
    if (page_ref_count(page) == 1) {
        entry = pte_mkyoung(pte_mkdirty(vmf->orig_pte));
        entry = maybe_pte_mkwrite(entry, vma);
        set_pte_at(mm, vmf->address, vmf->pte, entry);
        return 0;
    }
    // 多个映射：复制页面
    copy_page = alloc_zeroed_user_highpage_movable(vma, vmf->address);
    copy_user_page(copy_page, page, vmf->address);
    // 建立新映射
    entry = mk_pte(copy_page, vma->vm_page_prot);
    entry = maybe_pte_mkwrite(pte_mkdirty(entry), vma);
    set_pte_at(mm, vmf->address, vmf->pte, entry);
    // 减少旧页面引用计数
    page_remove_rmap(page, vma);
}
```

COW的快速路径优化：如果页面只有一个映射（`page_ref_count == 1`），无需复制，直接修改页表权限。这避免了fork()后子进程首次写入时总是复制页面的开销。

### NUMA缺页：do_numa_page()

NUMA系统的页面可能在错误的节点上——进程迁移到另一个NUMA节点后，其页面仍在旧节点上。NUMA缺页处理将这些页面迁移到本地节点：

```c
// 自动NUMA均衡：定期将PTE标记为PROT_NONE
// 进程访问时触发缺页 → do_numa_page() → 迁移页面到当前节点
```

## 10.5 反向映射(RMAP)

正向映射：虚拟地址→页表→物理页。反向映射：物理页→所有映射它的VMA/页表项。RMAP是页面回收的关键——回收一个物理页前，必须断开所有映射它的页表项。

```c
// mm/rmap.c
// 从物理页找到所有映射，逐个解除映射
void try_to_unmap(struct page *page, enum ttu_flags flags)
{
    // 遍历page->mapping中的所有VMA
    // 对每个VMA，查找对应的PTE
    // 解除PTE映射
}
```

RMAP的实现演进：早期Linux为每个物理页维护一个反向映射链表（非线性扩展），后来改为基于对象的反向映射——匿名页通过`anon_vma`找到所有映射的VMA，文件页通过`address_space`找到。`page_vma_mapped_walk()`遍历VMA的页表项，确认页表是否仍然映射该物理页。

## 10.6 GUP：get_user_pages

GUP是将用户虚拟地址转换为物理页引用的机制，是内核访问用户内存的标准接口：

```c
// mm/gup.c
// 快速路径：无锁页表遍历
int get_user_pages_fast(unsigned long start, int nr_pages, ...)
{
    // 1. 在RCU保护下遍历页表
    // 2. 找到PTE，获取struct page引用
    // 3. 如果遇到无法处理的情况，回退到慢速路径
}

// 慢速路径：获取mmap_lock，处理缺页
long get_user_pages_unlocked(unsigned long start, int nr_pages, ...)
```

### pin vs get

GUP有两种语义：
- **get(FOLL_GET)**：短期引用，页面可以被迁移/回收
- **pin(FOLL_PIN)**：长期引用（DMA），页面不能被迁移，物理地址必须稳定

FOLL_PIN用于DMA场景——设备正在DMA到该页面，如果页面被迁移，DMA写入错误位置。pin的页面会被`try_to_unmap()`跳过，不被迁移或回收。

## 10.7 内存操作与保护

### mprotect：修改VMA保护属性

```c
// mm/mprotect.c
// 修改VMA的读/写/执行权限
SYSCALL_DEFINE3(mprotect, unsigned long, start, size_t, len,
                unsigned long, prot)
{
    // 修改vm_flags和vm_page_prot
    // 更新页表项权限
    // 可能需要分裂VMA
}
```

### mseal：内存密封

Linux 7.0新增`mseal()`系统调用——密封VMA，防止其被修改：

```c
// mm/mseal.c
SYSCALL_DEFINE4(mseal, unsigned long, start, size_t, len,
                unsigned long, prot, unsigned long, flags)
{
    // 设置VMA的VM_SEALED标志
    // 密封后：不能mmap/munmap/mprotect/madvise修改该区域
}
```

mseal的设计目标：防御内存篡改攻击——攻击者无法通过修改VMA权限来注入代码。Chrome浏览器已经开始使用mseal密封关键内存区域。

### madvise：内存使用建议

```c
// mm/madvise.c
// 常用advice：
MADV_DONTNEED     // 丢弃页面内容，释放物理内存
MADV_HUGEPAGE     // 请求透明大页
MADV_NOHUGEPAGE   // 禁用透明大页
MADV_MERGEABLE    // 允许KSM合并
MADV_DONTFORK     // fork时不继承此VMA
```

`MADV_DONTNEED`是数据库和推理服务最常用的操作——释放不再需要的内存区域（如已处理完的请求缓冲区），立即归还物理页面。

---

本章建立了对虚拟内存核心机制的认知：VMA是地址空间的管理单元，页表实现虚拟到物理的映射，缺页处理实现按需分配，RMAP支持页面回收的逆映射，GUP连接用户内存与内核/设备，mseal提供内存安全保护。第11章将讨论这些页面的回收机制——当物理内存不足时如何决定回收哪些页面。
