# 第5章 启动：从BIOS到idle进程

> 源码锚点：`arch/x86/kernel/head_64.S`、`arch/x86/kernel/setup.c`、`init/main.c`、`init/initramfs.c`、`init/do_mounts.c`、`init/init_task.c`

Linux的启动是一场从混沌到秩序的旅程——从BIOS上电的自检，到内核解压、逐子系统初始化，再到第一个用户进程诞生。本章追踪这条链路的每一个关键步骤，理解内核如何从"什么都不存在"建立起完整的运行时环境。

## 5.1 实模式→保护模式→长模式

### BIOS/UEFI的预处理

按下电源键后，CPU从固件约定的复位向量(Reset Vector)开始执行。传统BIOS从0xFFFFFFF0执行，UEFI从固件中的EFI入口点执行。固件的职责：

1. **POST(Power-On Self-Test)**：硬件自检，检测CPU、内存、关键I/O
2. **ACPI表构建**：构建RSDP/RSDT/XSDT等表，描述硬件拓扑和电源管理信息
3. **SMBIOS表构建**：系统硬件信息描述
4. **引导设备选择**：根据BIOS/UEFI设置选择启动设备
5. **加载引导程序**：从启动设备加载GRUB2/systemd-boot等引导程序

引导程序(如GRUB2)负责：
- 读取内核映像(vmlinuz)和initramfs到内存
- 设置`boot_params`结构(包含e820内存映射、命令行参数、initrd位置等)
- 将`boot_params`的物理地址放入`%rsi`寄存器
- 跳转到内核入口点

### 精读 head_64.S：从长模式到C代码

x86_64内核的实际入口点在`arch/x86/kernel/head_64.S`，但内核映像从压缩状态开始——`arch/x86/boot/compressed/head_64.S`先执行解压，然后跳转到解压后的`startup_64`。

**`startup_64`**——内核的第一个符号：

```asm
// arch/x86/kernel/head_64.S
SYM_CODE_START_NOALIGN(startup_64)
    mov	%rsi, %r15          // 保存boot_params指针到%r15

    leaq	__top_init_kernel_stack(%rip), %rsp  // 设置临时栈

    // 设置GS基址为0（boot CPU使用init数据段）
    movl	$MSR_GS_BASE, %ecx
    xorl	%eax, %eax
    xorl	%edx, %edx
    wrmsr

    call	__pi_startup_64_setup_gdt_idt  // 建立GDT和IDT

    // 切换到__KERNEL_CS代码段——确保IRET工作
    pushq	$__KERNEL_CS
    leaq	.Lon_kernel_cs(%rip), %rax
    pushq	%rax
    lretq
```

`startup_64`的关键操作：
1. **保存boot_params**：`%rsi`由引导程序传入，存入`%r15`避免被C函数调用覆盖
2. **设置栈**：使用链接器定义的`__top_init_kernel_stack`作为临时栈顶
3. **清零GS基址**：boot CPU在per-CPU区域建立前使用init数据段
4. **建立GDT/IDT**：调用`__pi_startup_64_setup_gdt_idt()`设置早期描述符表
5. **切换到内核代码段**：通过`lretq`远跳转到`__KERNEL_CS`，确保后续IRET指令正常工作

接下来是页表修复和CR3切换：

```asm
    // 计算内核的物理地址到虚拟地址偏移
    leaq	common_startup_64(%rip), %rdi
    subq	.Lcommon_startup_64(%rip), %rdi

    // 修复页表中的物理地址（内核可能被加载到非编译地址）
    movq	%r15, %rsi
    call	__pi___startup_64

    // 加载early_top_pgt到CR3
    leaq	early_top_pgt(%rip), %rcx
    addq	%rcx, %rax
    movq	%rax, %cr3

    // 跳转到common_startup_64的虚拟地址
    jmp	*.Lcommon_startup_64(%rip)
```

`__pi___startup_64()`修复页表中所有物理地址——内核编译时假定加载到`__START_KERNEL_map`，但实际可能被KASLR偏移到其他位置。修复后切换到`early_top_pgt`，这是内核的第一个页表，包含恒等映射(Identity Mapping)和内核映射。

**`common_startup_64`**——boot CPU和AP(应用处理器)的汇合点：

```asm
SYM_INNER_LABEL(common_startup_64, SYM_L_LOCAL)
    // CR4配置：保留PAE和LA57位，清除PGE以刷新全局TLB
    movl	$(X86_CR4_PAE | X86_CR4_LA57), %edx
    movq	%cr4, %rcx
    andl	%edx, %ecx
    btsl	$X86_CR4_PSE_BIT, %ecx
    movq	%rcx, %cr4
    btsl	$X86_CR4_PGE_BIT, %ecx
    movq	%rcx, %cr4

    // SMP：读取APIC ID确定CPU编号
    movq	__per_cpu_offset(,%rcx,8), %rdx   // 获取per-CPU偏移

    // 设置栈——从current_task获取
    movq	current_task(%rdx), %rax
    movq	TASK_threadsp(%rax), %rsp

    // 设置GDT
    lgdt	(%rsp)

    // 设置GS基址为per-CPU偏移
    movl	$MSR_GS_BASE, %ecx
    movl	%edx, %eax
    shrq	$32, %rdx
    wrmsr

    // 建立早期IDT
    call	early_setup_idt

    // 启用系统调用(SCE)和NX位
    movl	$MSR_EFER, %ecx
    rdmsr
    btsl	$_EFER_SCE, %eax
    btsl	$_EFER_NX, %eax
    wrmsr

    // 设置CR0
    movl	$CR0_STATE, %eax
    movq	%rax, %cr0

    // 清零EFLAGS
    pushq $0
    popfq

    // 跳转到C代码入口
    movq	%r15, %rdi          // 传入boot_params
    callq	*initial_code(%rip) // → x86_64_start_kernel
```

`initial_code`指向`x86_64_start_kernel`——这是内核的第一个C函数。至此，汇编阶段完成：CPU在64位长模式，分页已启用，栈已设置，可以执行C代码了。

**早期异常处理**——`early_idt_handler_array`：

```asm
SYM_CODE_START(early_idt_handler_array)
    i = 0
    .rept NUM_EXCEPTION_VECTORS
        .if ((EXCEPTION_ERRCODE_MASK >> i) & 1) == 0
            pushq $0       // 无错误码的异常：压入dummy 0
        .endif
        pushq $i           // 压入向量号
        jmp early_idt_handler_common
    .endr
SYM_CODE_END(early_idt_handler_array)
```

早期异常处理非常简陋——只保存寄存器，调用`do_early_exception()`，如果返回则通过`restore_regs_and_return_to_kernel`恢复执行。在启动早期，任何异常通常都意味着严重错误。

### 精读 setup.c：x86平台初始化

`x86_64_start_kernel()`经过简短的x86特定设置后调用`x86_64_start_reservations()`，后者最终调用`start_kernel()`。但在此之前，`setup_arch()`负责x86架构的完整初始化：

```c
// arch/x86/kernel/setup.c
void __init setup_arch(char **cmdline_p)
{
    // 1. 命令行处理
    strscpy(command_line, boot_command_line, COMMAND_LINE_SIZE);
    *cmdline_p = command_line;

    // 2. 早期陷阱和CPU初始化
    idt_setup_early_traps();
    early_cpu_init();
    early_ioremap_init();

    // 3. 解析boot_params
    parse_boot_params();

    // 4. 早期内存保留——在e820加入memblock之前
    early_reserve_memory();

    // 5. e820内存映射发现！
    e820__memory_setup();
    parse_setup_data();

    // 6. 解析早期内核参数
    parse_early_param();

    // 7. EFI初始化
    if (efi_enabled(EFI_BOOT))
        efi_init();

    // 8. ACPI表初始化
    acpi_boot_table_init();
    early_acpi_boot_init();

    // 9. 计算max_pfn
    max_pfn = e820__end_of_ram_pfn();

    // 10. e820→memblock：建立物理内存分配器
    e820__memblock_setup();

    // 11. 内核内存映射建立
    init_mem_mapping();

    // 12. initrd保留
    reserve_initrd();

    // 13. NUMA初始化
    initmem_init();

    // 14. crashkernel保留
    arch_reserve_crashkernel();

    // 15. 分页初始化
    x86_init.paging.pagetable_init();
    kasan_init();
}
```

`setup_arch()`的关键步骤解释：

**e820内存映射**：BIOS/UEFI通过`e820`系统调用（或UEFI等价接口）告诉操作系统物理内存的布局。e820返回的不是一个简单的"内存有多大"，而是一个区间列表——每个区间标注类型(RAM/Reserved/ACPI/NVS等)。`e820__memory_setup()`解析这些区间，`e820__memblock_setup()`将RAM区间注册到`memblock`分配器。

**为什么需要`early_reserve_memory()`在e820→memblock之前**？因为内核映像本身、boot_params、initrd等区域必须被保留，否则memblock分配器可能把它们分配出去导致数据被覆盖。

**`init_mem_mapping()`**：建立物理内存的内核直接映射(direct mapping)，即从`PAGE_OFFSET`开始的线性映射。这是内核访问所有物理内存的窗口。

## 5.2 start_kernel()：逐阶段初始化

### 精读 init/main.c

`start_kernel()`是架构无关的内核初始化主函数，在`setup_arch()`之后执行，逐步建立内核的各个子系统：

```c
// init/main.c
asmlinkage __visible __init __no_sanitize_address __noreturn __no_stack_protector
void start_kernel(void)
{
    char *command_line;
    char *after_dashes;

    set_task_stack_end_magic(&init_task);   // 栈溢出检测
    smp_setup_processor_id();               // 识别boot CPU
    debug_objects_early_init();
    cgroup_init_early();                    // cgroup早期初始化

    local_irq_disable();                    // 关中断！
    early_boot_irqs_disabled = true;

    boot_cpu_init();                        // 激活boot CPU
    page_address_init();
    setup_arch(&command_line);              // x86架构初始化(上一节)

    mm_core_init_early();                   // 早期内存管理
    jump_label_init();                      // 静态键初始化
    static_call_init();                     // 静态调用初始化
    early_security_init();

    setup_boot_config();                    // bootconfig解析
    setup_command_line(command_line);       // 保存命令行
    setup_nr_cpu_ids();                     // CPU数量
    setup_per_cpu_areas();                  // per-CPU区域分配
    smp_prepare_boot_cpu();                 // boot CPU的per-CPU设置
    early_numa_node_init();                 // 早期NUMA节点

    print_kernel_cmdline(saved_command_line);
    parse_early_param();                    // 解析早期参数
    after_dashes = parse_args("Booting kernel", ...);  // 解析内核参数

    // ---- 内存与调度器初始化 ----
    setup_log_buf(0);
    vfs_caches_init_early();
    mm_core_init();                         // 伙伴系统初始化
    maple_tree_init();
    ftrace_init();
    sched_init();                           // 调度器初始化！

    // ---- 中断与时间子系统 ----
    early_irq_init();
    init_IRQ();
    tick_init();
    timers_init();
    hrtimers_init();
    softirq_init();
    timekeeping_init();
    time_init();

    // ---- 开中断 ----
    early_boot_irqs_disabled = false;
    local_irq_enable();

    // ---- 控制台与锁 ----
    console_init();
    lockdep_init();
    locking_selftest();

    // ---- 进程与文件系统 ----
    fork_init();                            // fork子系统初始化
    proc_caches_init();                     // 进程相关slab缓存
    vfs_caches_init();                      // VFS缓存初始化
    cgroup_init();                          // cgroup完整初始化

    // ---- 进入rest_init ----
    rest_init();
}
```

`start_kernel()`的初始化顺序有严格的依赖关系：

1. **先内存后调度**：`mm_core_init()`必须在`sched_init()`之前——调度器需要分配内存
2. **先调度后中断**：`sched_init()`必须在中断子系统之前——中断处理可能触发调度
3. **开中断的时机**：在调度器和中断子系统都就绪后才开中断(`local_irq_enable()`)
4. **cgroup两次初始化**：`cgroup_init_early()`在调度器之前（允许早期cgroup操作），`cgroup_init()`在所有子系统就绪后（完整cgroup功能）

### 0号进程：init_task

内核的第一个进程不是被"创建"的——它是静态定义的：

```c
// init/init_task.c
struct task_struct init_task __aligned(L1_CACHE_BYTES) = {
    .__state    = 0,                        // TASK_RUNNING
    .stack      = init_stack,
    .flags      = PF_KTHREAD,               // 内核线程
    .prio       = MAX_PRIO - 20,            // 优先级120
    .static_prio = MAX_PRIO - 20,
    .policy     = SCHED_NORMAL,
    .mm         = NULL,                     // 无用户地址空间
    .active_mm  = &init_mm,                 // 借用init_mm
    .real_parent = &init_task,              // 父进程是自己
    .parent     = &init_task,
    .comm       = INIT_TASK_COMM,           // "swapper"
    ...
};
EXPORT_SYMBOL(init_task);
```

`init_task`是进程0，即idle进程。它的关键特征：
- **静态定义**：编译时就存在于内核映像中，不是由`fork()`创建
- **PF_KTHREAD**：标记为内核线程，没有用户态地址空间
- **mm=NULL, active_mm=&init_mm**：idle进程没有自己的`mm_struct`，借用`init_mm`访问内核空间
- **real_parent指向自己**：没有父进程
- **comm为"swapper"**：每个CPU的idle进程都叫"swapper/N"

每个CPU都有自己的idle进程——boot CPU的idle是`init_task`，其他CPU的idle在SMP启动时由`fork_idle()`创建。

### rest_init()：创建1号和2号进程

`start_kernel()`的最后一行调用`rest_init()`，这里创建两个关键的内核线程：

```c
// init/main.c
static noinline void __ref __noreturn rest_init(void)
{
    struct task_struct *tsk;
    int pid;

    rcu_scheduler_starting();

    // 创建1号进程：kernel_init（用户态init的前身）
    pid = user_mode_thread(kernel_init, NULL, CLONE_FS);

    // 将init钉在boot CPU上，直到sched_init_smp()
    rcu_read_lock();
    tsk = find_task_by_pid_ns(pid, &init_pid_ns);
    tsk->flags |= PF_NO_SETAFFINITY;
    set_cpus_allowed_ptr(tsk, cpumask_of(smp_processor_id()));
    rcu_read_unlock();

    numa_default_policy();

    // 创建2号进程：kthreadd（所有内核线程的父进程）
    pid = kernel_thread(kthreadd, NULL, NULL, CLONE_FS | CLONE_FILES);
    rcu_read_lock();
    kthreadd_task = find_task_by_pid_ns(pid, &init_pid_ns);
    rcu_read_unlock();

    system_state = SYSTEM_SCHEDULING;
    complete(&kthreadd_done);   // 通知kernel_init：kthreadd已就绪

    // boot CPU的idle进程开始调度循环
    schedule_preempt_disabled();
    cpu_startup_entry(CPUHP_ONLINE);  // 进入idle循环，永不返回
}
```

三个进程的角色：
- **进程0 (init_task/swapper)**：boot CPU的idle进程，`cpu_startup_entry()`后进入无限idle循环
- **进程1 (kernel_init→/sbin/init)**：先以内核线程运行，最终execve为用户态init进程
- **进程2 (kthreadd)**：内核线程守护进程，所有后续内核线程由它创建

注意创建顺序：**必须先创建init再创建kthreadd**，因为init需要获得PID 1。但init在启动过程中可能需要创建内核线程（如执行initrd中的脚本），所以必须等待kthreadd就绪——通过`kthreadd_done`完成量同步。

## 5.3 initramfs与根文件系统

### initramfs解压：精读 init/initramfs.c

initramfs是内核内置或由引导程序加载的早期用户空间，包含挂载真正根文件系统所需的工具和驱动。`init/initramfs.c`负责将其解压到rootfs：

```c
// init/initramfs.c
static int __init populate_rootfs(void)
{
    initramfs_cookie = async_schedule_domain(do_populate_rootfs, NULL,
                                             &initramfs_domain);
    usermodehelper_enable();
    if (!initramfs_async)
        wait_for_initramfs();
    return 0;
}
rootfs_initcall(populate_rootfs);
```

`populate_rootfs()`通过`rootfs_initcall`在内核初始化后期被调用。它异步执行`do_populate_rootfs()`：

```c
static void __init do_populate_rootfs(void *unused, async_cookie_t cookie)
{
    // 1. 解压内置initramfs（编译时链接进内核的）
    char *err = unpack_to_rootfs(__initramfs_start, __initramfs_size);
    if (err)
        panic_show_mem("%s", err);

    if (!initrd_start || IS_ENABLED(CONFIG_INITRAMFS_FORCE))
        goto done;

    // 2. 解压外部initrd（由引导程序加载的）
    err = unpack_to_rootfs((char *)initrd_start, initrd_end - initrd_start);
    if (err) {
        // 如果解压失败且配置了BLK_DEV_RAM，回退为块设备模式
        #ifdef CONFIG_BLK_DEV_RAM
        populate_initrd_image(err);
        #endif
    }

done:
    security_initramfs_populated();

    // 3. 释放initrd占用的内存
    if (!do_retain_initrd && initrd_start && !kexec_free_initrd())
        free_initrd_mem(initrd_start, initrd_end);

    initrd_start = 0;
    initrd_end = 0;
}
```

**initramfs vs initrd**：两者经常被混淆，但有本质区别：

| 特征 | initramfs | initrd |
|------|-----------|--------|
| 格式 | cpio归档(可能压缩) | 磁盘映像(ext2/minix) |
| 挂载方式 | 直接解压到rootfs | 通过loop块设备挂载 |
| 驱动需求 | 无需任何文件系统驱动 | 需要ext2等驱动 |
| 灵活性 | 高，纯文件操作 | 低，需要块设备模拟 |
| 现代用法 | 标准方式 | 已过时 |

`unpack_to_rootfs()`是解压的核心——它是一个状态机，逐条解析cpio格式的归档：

```c
// init/initramfs.c
static __initdata int (*actions[])(void) = {
    [Start]     = do_start,
    [Collect]   = do_collect,
    [GotHeader] = do_header,
    [SkipIt]    = do_skip,
    [GotName]   = do_name,
    [CopyFile]  = do_copy,
    [GotSymlink]= do_symlink,
    [Reset]     = do_reset,
};

static long __init write_buffer(char *buf, unsigned long len)
{
    byte_count = len;
    victim = buf;
    while (!actions[state]())    // 驱动状态机
        ;
    return len - byte_count;
}
```

状态机流程：`Start → Collect → GotHeader → GotName → CopyFile/GotSymlink → Reset → Start`

- **`do_header()`**：解析cpio头，提取文件名、权限、大小、uid/gid等信息
- **`do_name()`**：根据文件类型创建文件/目录/设备节点/管道
- **`do_copy()`**：写入文件内容
- **`do_symlink()`**：创建符号链接

`do_name()`中的`TRAILER!!!`检测值得注意——cpio归档以`TRAILER!!!`标记结束：

```c
static int __init do_name(void)
{
    state = SkipIt;
    next_state = Reset;

    if (strcmp(collected, "TRAILER!!!") == 0) {
        free_hash();
        return 0;
    }
    // 创建文件/目录/设备节点...
}
```

### 根文件系统挂载：精读 init/do_mounts.c

initramfs解压完成后，`kernel_init()`（1号进程）继续执行，最终挂载真正的根文件系统：

```c
// init/do_mounts.c
void __init prepare_namespace(void)
{
    if (root_delay) {
        ssleep(root_delay);
    }

    wait_for_device_probe();     // 等待设备探测完成
    md_run_setup();              // MD(软RAID)设置

    if (saved_root_name[0])
        ROOT_DEV = parse_root_device(saved_root_name);  // 解析root=参数

    initrd_load();               // 加载initrd（如果作为块设备）

    if (root_wait)
        wait_for_root(saved_root_name);

    mount_root(saved_root_name); // 挂载根文件系统
    devtmpfs_mount();            // 挂载devtmpfs

    // pivot_root：切换到新根文件系统
    if (init_pivot_root(".", ".")) {
        pr_err("VFS: Failed to pivot into new rootfs\n");
        return;
    }
    if (init_umount(".", MNT_DETACH)) {
        pr_err("VFS: Failed to unmount old rootfs\n");
        return;
    }
}
```

`prepare_namespace()`的核心流程：
1. 等待存储设备就绪——异步设备探测可能需要数秒
2. 解析`root=`内核参数确定根设备
3. 如果使用initrd，加载initrd
4. 挂载根文件系统
5. **pivot_root**切换到新根——将initramfs移到新根下的一个子目录，然后卸载

`mount_root()`根据根设备类型选择挂载方式：

```c
void __init mount_root(char *root_device_name)
{
    // 网络根文件系统
    if (ROOT_DEV == Root_NFS) {
        mount_nfs_root();
        return;
    }
    // 通用块设备（支持PARTUUID等）
    if (ROOT_DEV == Root_Generic) {
        mount_root_generic(root_device_name, ...);
        return;
    }
    // 传统块设备
    mount_block_root(root_device_name);
}
```

`mount_root_generic()`支持通过`root=PARTUUID=xxx`指定根分区——它会遍历系统中所有块设备的分区，匹配UUID。这是现代Linux最常用的根设备指定方式，比`root=/dev/sda2`更稳定（设备名可能因探测顺序变化）。

### 1号进程的诞生

`kernel_init()`在`prepare_namespace()`之后执行：

```c
// init/main.c
static int __ref kernel_init(void *unused)
{
    // 等待kthreadd就绪
    wait_for_completion(&kthreadd_done);

    kernel_init_freeable();   // SMP初始化、设备驱动初始化等

    // 释放__init段内存
    system_state = SYSTEM_FREEING_INITMEM;
    free_initmem();
    mark_readonly();          // 设置内核代码段只读

    system_state = SYSTEM_RUNNING;

    // 尝试执行init进程
    if (ramdisk_execute_command) {
        ret = run_init_process(ramdisk_execute_command);  // 默认"/init"
        if (!ret) return 0;
    }
    if (execute_command) {
        ret = run_init_process(execute_command);          // "init="参数
        if (!ret) return 0;
        panic("Requested init %s failed", execute_command);
    }

    // 按优先级尝试
    if (!try_to_run_init_process("/sbin/init") ||
        !try_to_run_init_process("/etc/init") ||
        !try_to_run_init_process("/bin/init") ||
        !try_to_run_init_process("/bin/sh"))
        return 0;

    panic("No working init found.");
}
```

`kernel_init()`从内核线程变为用户态init的关键是`run_init_process()`，它调用`kernel_execve()`执行init程序——这是exec系统调用的内核内部版本。执行后，1号进程的地址空间从内核态切换到用户态，正式成为用户进程init。

init的搜索优先级：
1. `rdinit=`参数指定的initrd中的init（默认`/init`）
2. `init=`参数指定的init
3. `CONFIG_DEFAULT_INIT`编译时默认值
4. `/sbin/init` → `/etc/init` → `/bin/init` → `/bin/sh`

如果全部失败，内核panic——没有init，系统无法运行。

### kernel_init_freeable()：SMP和驱动初始化

```c
static noinline void __init kernel_init_freeable(void)
{
    smp_prepare_cpus(setup_max_cpus);  // 准备其他CPU
    workqueue_init();
    do_pre_smp_initcalls();             // early initcalls
    smp_init();                         // 启动其他CPU！
    sched_init_smp();                   // SMP调度器初始化
    do_basic_setup();                   // 核心initcalls

    wait_for_initramfs();               // 等待initramfs解压完成
    console_on_rootfs();                // 打开/dev/console

    // 检查initrd中是否有/init
    if (init_eaccess(ramdisk_execute_command) != 0) {
        ramdisk_execute_command = NULL;
        prepare_namespace();            // 挂载真正的根文件系统
    }
}
```

`do_basic_setup()`调用所有`device`级别及以下的initcall——这是大部分设备驱动初始化的地方。initcall按级别执行：

```c
static const char *initcall_level_names[] = {
    "pure",      // 0: 最早期，不依赖任何子系统
    "core",      // 1: 核心子系统
    "postcore",  // 2: 核心子系统之后
    "arch",      // 3: 架构相关
    "subsys",    // 4: 子系统
    "fs",        // 5: 文件系统
    "device",    // 6: 设备驱动
    "late",      // 7: 最晚初始化
};
```

每个驱动的初始化函数通过`module_init()`/`fs_initcall()`/`device_initcall()`等宏注册到对应的级别。`do_one_initcall()`逐个调用，并在调用前后检查抢占计数和中断状态——如果驱动在initcall中开中断或修改抢占计数但未恢复，会发出警告。

### initcall的执行追踪

内核提供`initcall_debug`参数追踪每个initcall的执行时间：

```
kernel: calling  clksrc_init+0x0/0x12 @ 1
kernel: initcall clksrc_init+0x0/0x12 returned 0 after 15 usecs
```

这在排查启动慢的问题时非常有用——哪个驱动初始化耗时最长一目了然。

---

本章追踪了Linux从上电到第一个用户进程的完整链路：固件→引导程序→内核解压→`startup_64`→`start_kernel()`→`rest_init()`→`kernel_init()`→`/sbin/init`。0号idle进程静态存在于内核映像中，1号init进程从内核线程execve为用户态，2号kthreadd守护所有后续内核线程。理解启动链路是理解内核初始化顺序的基础——每个子系统的初始化时机都不是随意的，而是由依赖关系严格决定的。第6章将深入进程的内部表示和生命周期。
