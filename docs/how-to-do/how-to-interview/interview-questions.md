# 面试题整理索引

> 本文档汇总了技术面试中的各类题目，按主题分类整理，方便系统复习。

---

## 📚 文档导航

| 文档 | 内容 | 适用场景 |
|------|------|---------|
| [C++ 面试题](./cpp-interview-questions.md) | 内存管理、面向对象、STL、智能指针、C++11 新特性 | C++ 开发岗位 |
| [操作系统与网络](./os-network-interview-questions.md) | 进程线程、内存管理、TCP/IP、IO 模型 | 后端开发岗位 |
| [数据库面试题](./database-interview-questions.md) | MySQL、Redis、索引、事务、性能优化 | 所有开发岗位 |
| [算法与设计题](./algorithm-interview-questions.md) | 数据结构、算法、系统设计、海量数据 | 所有技术岗位 |

---

## 📋 快速检索

### 按技术栈

**C++ 基础**
- [内存布局](./cpp-interview-questions.md#一内存管理) - 栈、堆、全局区、代码段
- [new vs malloc](./cpp-interview-questions.md#12-new-与-malloc-的区别) - 区别与底层实现
- [虚函数机制](./cpp-interview-questions.md#二面向对象与多态) - vtable、vptr、多态原理
- [智能指针](./cpp-interview-questions.md#三智能指针) - unique_ptr、shared_ptr、weak_ptr
- [STL 容器](./cpp-interview-questions.md#四stl-容器) - vector、map、底层实现
- [C++11 新特性](./cpp-interview-questions.md#五c111417-新特性) - 右值引用、移动语义、Lambda

**操作系统**
- [进程 vs 线程](./os-network-interview-questions.md#11-进程-vs-线程) - 区别与通信方式
- [进程间通信](./os-network-interview-questions.md#13-进程间通信ipc) - 管道、消息队列、共享内存
- [虚拟内存](./os-network-interview-questions.md#二内存管理) - 原理与页面置换
- [内核态 vs 用户态](./os-network-interview-questions.md#23-内核态-vs-用户态) - 切换时机与开销

**计算机网络**
- [TCP vs UDP](./os-network-interview-questions.md#32-tcp-vs-udp) - 区别与适用场景
- [三次握手四次挥手](./os-network-interview-questions.md#33-tcp-三次握手与四次挥手) - 原理与状态转换
- [TCP 可靠传输](./os-network-interview-questions.md#34-tcp-可靠传输机制) - 序列号、确认应答、重传
- [IO 模型](./os-network-interview-questions.md#四io-模型) - select、poll、epoll 对比
- [HTTP/HTTPS](./os-network-interview-questions.md#六http-协议) - 协议演进与加密过程

**数据库**
- [InnoDB vs MyISAM](./database-interview-questions.md#11-存储引擎对比) - 存储引擎选择
- [B+ 树索引](./database-interview-questions.md#12-索引原理) - 原理与优化
- [事务与隔离级别](./database-interview-questions.md#二事务与并发控制) - ACID、脏读、幻读
- [MVCC](./database-interview-questions.md#23-mvcc-多版本并发控制) - 实现原理
- [Redis 数据结构](./database-interview-questions.md#五redis) - 使用场景与持久化

**算法与设计**
- [链表操作](./algorithm-interview-questions.md#一基础数据结构题) - 反转、判环、合并
- [二叉树](./algorithm-interview-questions.md#12-二叉树) - 遍历、LCA
- [排序算法](./algorithm-interview-questions.md#二经典算法) - 快排、归并、堆排
- [动态规划](./algorithm-interview-questions.md#22-动态规划) - 背包、LIS
- [海量数据](./algorithm-interview-questions.md#三海量数据处理) - Top K、去重、一致性哈希
- [系统设计](./algorithm-interview-questions.md#四系统设计题) - LRU、线程池、秒杀系统

---

## 🎯 面试准备建议

### 1. 基础知识（必会）

无论面试什么岗位，以下内容是基础：

- **数据结构**：数组、链表、树、哈希表的基本操作与复杂度
- **算法**：排序、二分查找、递归、动态规划的基本思想
- **计算机网络**：TCP 三次握手、HTTP 协议
- **操作系统**：进程线程区别、虚拟内存

### 2. 岗位专项

| 岗位 | 重点复习 |
|------|---------|
| C++ 后端 | C++ 内存管理、STL 源码、多线程、网络编程 |
| Java 后端 | JVM、并发包、Spring、MySQL 优化 |
| 算法工程师 | 机器学习基础、深度学习框架、算法题 |
| 基础架构 | 分布式系统、存储引擎、性能优化 |

### 3. 项目准备

面试时项目经历很重要，建议准备：

- 项目的背景与目标
- 你在项目中的角色与职责
- 遇到的技术挑战与解决方案
- 使用的技术栈与选型理由
- 项目的量化成果（性能提升、QPS 等）

### 4. 算法题练习

推荐刷题路径：

1. **入门**（1-2 周）：LeetCode 前 100 题，熟悉常见题型
2. **进阶**（2-4 周）：LeetCode 200 题，掌握动态规划、图论
3. **冲刺**（1-2 周）：公司真题，模拟面试环境

---

## 🔗 相关资源

### 经典书籍

**计算机基础**
- 《深入理解计算机系统》（CSAPP）
- 《现代操作系统》
- 《计算机网络：自顶向下方法》

**C++**
- 《C++ Primer》
- 《深度探索 C++ 对象模型》
- 《Effective C++》
- 《STL 源码剖析》

**算法**
- 《算法导论》
- 《剑指 Offer》
- 《编程珠玑》

**数据库**
- 《MySQL 技术内幕：InnoDB 存储引擎》
- 《Redis 设计与实现》
- 《高性能 MySQL》

### 在线资源

- [LeetCode](https://leetcode.cn/) - 算法题练习
- [牛客网](https://www.nowcoder.com/) - 笔试面试题库
- [CS-Notes](http://www.cyc2018.xyz/) - 技术面试知识汇总

---

> 📌 **原始资料**
>
> 原始面试题集合见 [interview-questions(raw).md](./interview-questions(raw).md)，本索引基于原始资料整理优化而成。
