# 第27章 安全子系统

> 源码锚点：`security/security.c`、`security/selinux/`、`security/bpf/hooks.c`、`security/landlock/`、`arch/x86/coco/`

安全是操作系统的基本职责——控制谁可以访问什么资源。Linux的安全子系统从LSM框架到SELinux到机密计算，构建了多层次的安全防护体系。

## 27.1 LSM框架

### Linux Security Module框架

LSM(Linux Security Module)是Linux安全模块的框架——在内核关键操作点插入安全检查钩子：

```c
// security/security.c
// LSM钩子示例：
// security_inode_permission()  → 检查文件访问权限
// security_file_open()         → 检查文件打开权限
// security_socket_connect()    → 检查网络连接权限
// security_task_kill()         → 检查信号发送权限
```

LSM钩子的调用链：内核操作(如`vfs_open`) → 调用`security_file_open()` → 遍历所有注册的LSM模块 → 每个模块检查自己的策略 → 任一模块拒绝则操作失败。

### 安全模块堆叠

Linux 5.1引入LSM堆叠——多个LSM模块同时生效：

```
安全操作 → LSM钩子
  → SELinux检查  → 通过
  → BPF LSM检查  → 通过
  → Landlock检查 → 拒绝 → 操作失败
```

堆叠允许不同LSM各司其职——SELinux提供基线策略，BPF LSM提供动态策略，Landlock提供非特权沙箱。

### 主要LSM模块

- **SELinux**：基于安全上下文的强制访问控制(MAC)——最成熟的LSM
- **AppArmor**：基于路径的MAC——比SELinux简单，配置更直观
- **BPF LSM**：用eBPF程序实现安全策略——运行时动态加载
- **Landlock**：非特权用户的安全沙箱——普通进程可以创建自己的安全策略
- **IPE**(Integrity Policy Enforcement)：完整性策略执行——确保只运行可信代码
- **LoadPin**：限制内核模块只能从特定文件系统加载
- **Yama**：限制ptrace的使用——防止调试器附加

## 27.2 SELinux

### 安全上下文与策略

SELinux为每个进程和文件分配安全上下文(Security Context)：

```
用户:角色:类型:级别
system_u:system_r:httpd_t:s0     → Web服务器进程
system_u:object_r:httpd_log_t:s0 → Web服务器日志文件
```

SELinux策略定义了哪些类型(type)可以访问哪些类型——类型强制(Type Enforcement)模型：

```
allow httpd_t httpd_log_t:file { write append };  // httpd进程可以写日志
dontaudit httpd_t user_home_t:file { read };       // 静默拒绝(不记录)
```

### AVC(Access Vector Cache)

SELinux的权限检查需要查策略数据库——开销较大。AVC缓存已检查的决策——相同的(源类型, 目标类型, 权限)查询直接返回缓存结果。

### 类型强制模型

SELinux的核心是类型强制——一切访问控制基于类型：

- 进程有类型(httpd_t, mysqld_t, user_t)
- 文件有类型(httpd_content_t, mysql_db_t)
- 策略定义类型间的访问规则

类型强制实现最小权限——即使root进程，如果类型不允许，也无法越权访问。

> **数据库视角**：数据库进程的SELinux策略配置。数据库(如PostgreSQL/MySQL)需要访问数据文件、日志文件、网络端口、共享内存等。SELinux为数据库定义专用类型(mysqld_t/postgresql_t)和对应的文件类型——即使数据库进程被攻破，攻击者也只能访问数据库相关的文件，无法读取其他服务的数据。

## 27.3 密钥管理

### 内核密钥环

`security/keys/`实现内核密钥环——分层管理密钥：

```
线程密钥环 → 进程密钥环 → 会话密钥环 → 用户密钥环

// 密钥类型：
// user:  任意用户数据
// encrypted: 加密存储的密钥
// trusted: TPM保护的密钥
// logon: 仅内核可访问(如cifs密码)
```

密钥环用于存储加密密钥、Kerberos票据等敏感数据——比环境变量或配置文件更安全，因为密钥不暴露在/proc/pid/environ中。

## 27.4 机密计算

### 为什么需要机密计算

云计算场景下，数据在云厂商的机器上处理——云管理员或恶意租户可能窃取数据。机密计算(Confidential Computing)通过硬件加密保护运行中的数据——即使物理机管理员也无法窥视。

### AMD SEV/SEV-ES/SEV-SNP

`arch/x86/coco/sev/`实现AMD SEV(Secure Encrypted Virtualization)：

- **SEV**：虚拟机内存加密——每台VM有独立的加密密钥，hypervisor无法读取VM内存
- **SEV-ES**(Encrypted State)：加密CPU寄存器状态——VMEXIT时寄存器加密，hypervisor无法读取
- **SEV-SNP**(Secure Nested Paging)：完整性保护——防止hypervisor篡改VM内存(重放、别名攻击)

SEV-SNP的内存完整性保证：每页有版本号——hypervisor不能将旧页面的内容替换到新页面(回滚攻击)，也不能将同一物理页映射到两个VM(别名攻击)。

### Intel TDX

`arch/x86/coco/tdx/`实现Intel TDX(Trust Domain Extensions)：

- **TD(Trust Domain)**：类似SEV的加密虚拟机
- **CPU状态加密**：TDX模块管理TD的CPU状态——VMM无法直接读写
- **内存加密**：TDX使用MKTME(Multi-Key Total Memory Encryption)——每个TD独立的加密密钥
- **远程证明**：TD可以向远程方证明自己运行在可信环境中

### 机密计算的安全模型

机密计算改变了安全模型——信任基础从"整个软件栈"缩小到"CPU+TD内部代码"：

```
传统云安全：信任hypervisor + OS + 应用
机密计算：  只信任CPU硬件 + TD内部代码

攻击面缩减：
  - 不信任hypervisor(VMM)
  - 不信任宿主机OS
  - 不信任云管理员
  - 只信任CPU硬件的完整性
```

> **AI视角**：推理服务多租户场景的安全隔离。AI推理服务通常在GPU上运行——多个租户共享GPU，模型参数是核心资产。机密计算 + cgroup的联合方案：TDX保护模型参数不被其他租户窥视，cgroup限制GPU/内存资源不互相干扰。NVIDIA的H100 GPU已支持CC(Confidential Computing)模式——GPU内的数据也被加密保护。

---

本章建立了对Linux安全子系统的完整认知：LSM框架提供可插拔的安全模块接口，SELinux实现强制访问控制，BPF LSM实现动态安全策略，Landlock允许非特权用户创建沙箱，机密计算(SEV-SNP/TDX)通过硬件加密保护运行中的数据。安全是纵深防御——从LSM的访问控制到机密计算的硬件保护，每一层都是下一层的后盾。
