# GitPerf - High Performance Git

## 网站信息
- **URL**: https://gitperf.com/
- **记录时间**: 2026-04-28
- **类型**: Git 性能优化技术书籍

## 书籍简介
Git 看起来是一个版本控制工具，但它同时也是一个内容寻址数据库、文件系统缓存、图遍历器和传输协议。

本书介绍这些层面及其性能成本，从 objects、refs、index 和历史遍历开始，逐步扩展到 packfiles、维护、稀疏工作树、部分克隆、传输、仓库规模、诊断、配置和恢复。

**目标读者**: 需要 Git 在仓库、历史和团队规模增长时保持高性能的工程师：
- 构建和 CI 工程师
- Monorepo 负责人
- 开发者体验团队
- 调试复杂 Git 行为的技术人员

---

## 目录结构

### Section 0 · Introduction (引言)
- [Introduction](chapter-00.html)

### Section I · Foundations (基础)
*为什么 Git 会变慢、Git 存储什么、refs 和 index 如何引导*

1. [Why Git Performance Matters](chapter-01.html) - Git 性能的重要性
2. [Git's Core Data Model](chapter-02.html) - Git 核心数据模型
3. [Refs, HEAD, Reflogs, Index](chapter-03.html) - 引用、HEAD、引用日志、索引

### Section II · History and Rewrite (历史与重写)
*Git 如何遍历历史，重写命令如何重塑历史而不改变提交*

4. [Revisions and History Traversal](chapter-04.html) - 修订与历史遍历
5. [Merge, Rebase, Cherry-Pick, Rewrite](chapter-05.html) - 合并、变基、拣选、重写

### Section III · Storage and Local Scale (存储与本地规模)
*对象存储、索引成本、维护及缩小本地状态的技术*

6. [Loose Objects, Packfiles, Delta Compression](chapter-06.html) - 松散对象、打包文件、增量压缩
7. [The Index as a Performance Structure](chapter-07.html) - 索引作为性能结构
8. [Commit-Graph, Bloom Filters, MIDX, Bitmaps](chapter-08.html) - 提交图、布隆过滤器、MIDX、位图
9. [Git GC and Maintenance](chapter-09.html) - Git 垃圾回收与维护
10. [Sparse-Checkout and Sparse-Index](chapter-10.html) - 稀疏检出与稀疏索引

### Section IV · Large-Repo Operations, Transport, and Scale (大仓库操作、传输与规模)
*克隆形状、传输策略、worktrees 并行工作、仓库大小和引用规模*

11. [Partial Clone and Promisor Remotes](chapter-11.html) - 部分克隆与承诺远程
12. [Scalar, Prefetch, Large Repositories](chapter-12.html) - Scalar、预取、大型仓库
13. [Worktrees](chapter-13.html) - 工作树
14. [Clone, Fetch, Push, Protocol v2](chapter-14.html) - 克隆、拉取、推送、协议 v2
15. [Bundles and Bundle URIs](chapter-15.html) - 捆绑与捆绑 URI
16. [Reducing Repository Size](chapter-16.html) - 减小仓库大小
17. [Large Ref Sets: Files, Packed-Refs, Reftable, and git refs](chapter-17.html) - 大引用集

### Section V · Diagnosis and Recovery (诊断与恢复)
*如何检测 Git、找到慢的层、应用高杠杆设置、仓库出错时恢复*

18. [Instrumenting Git](chapter-18.html) - Git 检测
19. [Finding and Fixing Slow Git](chapter-19.html) - 查找和修复慢 Git
20. [Configuration Playbook](chapter-20.html) - 配置手册
21. [Recovery and Repair](chapter-21.html) - 恢复与修复

### Back Matter (附录)
- [Epilogue: Git in the Agent Loop](epilogue.html) - 后记：代理循环中的 Git
- [Appendix: Compatibility Guidance](appendix-version-requirements.html) - 附录：兼容性指南
- [Appendix: Approaches to Virtualized Working Trees](appendix-virtualized-working-trees.html) - 附录：虚拟化工作树方法
- [Glossary of Git Terms](glossary.html) - Git 术语表
- [Download the full book as a PDF](pdf.html) - 下载完整 PDF

---

## 核心主题
- Git 内部数据结构与性能关系
- 大规模仓库优化策略
- 诊断与故障排除方法
- 配置调优最佳实践
- 仓库恢复技术

## 适用场景
- 大型 Monorepo 管理
- CI/CD 流水线性能优化
- Git 服务器运维
- 开发者工具链优化
