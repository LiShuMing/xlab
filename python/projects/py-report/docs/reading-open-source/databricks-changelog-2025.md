我是一名拥有 10 年以上经验的资深研发工程师，目前是顶尖开源 OLAP 数据库（StarRocks）的核心开发者与 Committer。我的日常技术栈围绕 C++、高并发、分布式系统、向量化执行以及底层性能压榨。同时，我也在积极拥抱 AI 时代，探索 LLM、RAG 和前沿编程语言（如 Rust、Haskell）。
参考 Databricks的如下release notes，总结其在2025年重大feature/optimzation及新的场景支持，分析该产品的产品商业定位及市场卖点;结合历史资料（历史release node)、博客介绍相关评论， 从技术、产品、商业话的视角，分析并洞察其产品在该年的定位及迭代方向的重点变化。
参考其release notes:
- https://docs.databricks.com/gcp/en/release-notes/product
- https://docs.databricks.com/gcp/en/release-notes/product
按照博客的方式输出一篇介绍、思考的报告类文章：
输出时注意：
- 内容尽量详实，通过引用原release note中的commit/link来说明相关的功能feature；
- 语言流畅、减少空话，尽量言之有物，结合相关feature的blog或者PR文章进行补充相关的概念或者名词；
- 在专业名词或者属于该产品的技术名词，请使用英文备注，并附上英文链接。

---
我是一名拥有 10 年以上经验的资深研发工程师，目前是顶尖开源 OLAP 数据库（[StarRocks](https://github.com/StarRocks/starrocks)）的核心开发者与 Committer。我的日常技术栈围绕 C++、高并发、分布式系统、向量化执行以及底层性能压榨。同时，我也在积极拥抱 AI 时代，探索 LLM、RAG 和前沿编程语言（如 Rust、Haskell）。

请参考 Databricks(spark的商业化公司) 的官方 Release Notes，同时结合历史版本记录、官方博客、技术文章及社区讨论：

**分析维度要求如下：**

1. **重大 Feature 与场景支持**：总结近年来（重点聚焦最近 2–3 个大版本）最重要的功能特性与新场景支持，优先关注对 HTAP、分布式事务、存储引擎、SQL 兼容性等方向有实质影响的变化；

2. **执行引擎 / 存储引擎 / 性能优化动向**：重点梳理执行引擎、Optimizer（优化器）在向量化执行、下推优化、统计信息、自适应查询执行（AQE）等方面的演进；结合 Databricks的 HTAP 架构特点，分析其在 TP 与 AP 融合上的技术取舍；

3. **自动化与运维智能化**：关注 Databricks在自动化运维（如 Auto Analyze、Auto Scaling可观测性（如 Clinic、Performance Overview）、以及资源管控（Resource Control）方面的进展；

4. **技术、产品与商业化视角的综合洞察**：
  - **技术视角**：与同类系统（如 Doris/StarRocks、ClickHouse）做横向对比，指出 Databricks在技术路线上的独特选择与权衡；
  - **产品视角**：分析各版本迭代的重心转移（如从"功能完整性"到"性能与稳定性"、再到"HTAP 场景化落地"）；
  - **商业化视角**：结合 Databricks Cloud 产品动向，分析其 Serverless、多云策略与开源社区的协同关系。

**参考资料：**
- https://docs.databricks.com/gcp/en/release-notes/product

**输出格式要求：**
- 以**博客深度分析文章**的形式输出，面向有分布式系统与数据库内核背景的工程师读者，语言要有技术深度、不讲废话；
- 内容尽量详实，**通过直接引用原 Release Notes 中具体的条目或 GitHub PR/Issue 链接**来支撑论点，避免泛泛而谈；
- 结合相关官方博客或社区文章，对重要特性补充背景概念和技术原理；
- **专业名词及产品专属技术术语使用英文标注**，并尽可能附上英文参考链接（文档、博客或 PR）；