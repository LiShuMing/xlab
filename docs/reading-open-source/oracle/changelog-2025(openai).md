我是一名拥有 10 年以上经验的资深研发工程师，目前是顶尖开源 OLAP 数据库（StarRocks）的核心开发者与 Committer。我的日常技术栈围绕 C++、高并发、分布式系统、向量化执行以及底层性能压榨。同时，我也在积极拥抱 AI 时代，探索 LLM、RAG 和前沿编程语言（如 Rust、Haskell）。

参考 Oracle的如下release notes, 同时结合历史资料（历史release node）、博客：
- 总结其最近这些年其database的重大feature/optimzation及新的场景支持;
- 总结其最近这些年在自动化(automatic)/执行引擎/存储引擎/优化器等方面的主要动向；
- 分析该产品的产品商业定位及市场卖点;
- 从技术、产品、商业话的视角，分析并洞察其产品在该年的定位及迭代方向的重点变化。

参考其release notes:
- https://docs.oracle.com/en-us/iaas/releasenotes/services/database/index.htm
- https://docs.oracle.com/en-us/iaas/releasenotes/services/autonomous-database-serverless/index.htm

按照博客的方式输出一篇介绍、思考的报告类文章：
输出时注意：
- 内容尽量详实，通过引用原release note中的commit/link来说明相关的功能feature；
- 语言流畅、减少空话，尽量言之有物，结合相关feature的blog或者PR文章进行补充相关的概念或者名词；
- 在专业名词或者属于该产品的技术名词，请使用英文备注，并附上英文链接。

# 从 Autonomous 到 AI Database：Oracle Database 近年的产品演进、技术主线与商业定位

过去很多人谈 Oracle Database，脑子里先出现的还是“传统企业关系数据库”。但如果你认真把 Oracle 最近几年，尤其是 Autonomous Database Serverless 和 Database 23ai/26ai 相关的 release notes、官方新特性文档和产品博客翻一遍，会发现这个标签已经不够用了。Oracle 这几年的重点，不只是把一个老牌关系数据库继续做强，而是在把数据库重写成一种更大的东西：企业级自治数据底座（autonomous data platform）+ AI-ready data plane。 ￼

这条路线并不是一夜之间出现的。2019 到 2023 年，Oracle 的主旋律还是把传统 DBA/运维/容灾/扩缩容这类复杂操作产品化、自动化、云服务化；到了 2024 年，随着 Oracle Database 23ai 正式 GA，Oracle 开始把 AI Vector Search、JSON Relational Duality、Select AI 之类的新能力推到品牌正中央；2025 年以后，发布节奏进一步指向 agentic workflow、open table/lakehouse integration、跨系统 AI 查询代理，也就是数据库边界继续外扩。 ￼

如果只看 feature list，这些变化会显得很碎。但如果从技术、产品、商业三层叠在一起看，Oracle 的方向其实很清楚：守住企业关键数据的控制面，同时把 AI、JSON/document、lakehouse/open ecosystem 这些新入口尽量收编到数据库内部。 这也是为什么 Oracle 近几年的很多能力，不是做成数据库外部旁路服务，而是强调“在数据库里”“通过 SQL/PLSQL”“与现有业务数据一起工作”。 ￼

一、先看时间线：Oracle 最近这些年到底在升级什么

1）2019：自治能力开始从概念走向可售卖能力

2019 年的一个标志性节点，是 Auto Scaling 在 Autonomous Database Serverless 上线。官方 release note 给出的描述很直接：系统会随负载波动自动调整 CPU core 数量。这个动作很重要，因为它不是单点“弹性扩容”功能，而是 Oracle 把传统容量规划、资源浪费、突发峰值处理这类 DBA/平台团队长期手工处理的事情，往“自治服务”叙事里收。 ￼

同一年，Automatic Indexing 在 Oracle Database 19c 上成为 Oracle 非常核心的技术卖点。Oracle 官方博客的说法是：系统会持续评估执行中的 SQL 与底层表，决定该建什么索引、可能要移除什么索引；它会验证索引是否真的改善性能，并通过 reinforcement learning 避免重复犯错。管理员文档则明确把它定义为：根据 workload 变化自动创建和删除索引，以提升数据库性能。对一个老牌商业数据库来说，这个 feature 的含义不只是“自动建索引”，而是 Oracle 开始系统性地把 workload-driven tuning 产品化。 ￼

从数据库工程的视角看，2019 年 Oracle 想证明的第一件事并不是“我会 AI”，而是“我可以把你过去依赖资深 DBA 经验做的那套活，逐步变成数据库自己做”。这也是 Autonomous 叙事最硬的一层：不是自然语言，不是 agent，而是运维面自动化先落地。 ￼

2）2020：自治数据库开始补齐企业可用性与场景扩展

2020 年，Autonomous Database Serverless 的 release notes 能看出第二条主线：开始明显补 网络隔离、高可用、开发测试克隆、JSON 场景。

先是 Private Endpoint。2020 年 2 月，Autonomous Database on shared Exadata infrastructure 支持 provisioning 时直接使用 private network endpoint；7 月又支持 in-place switch 到 private endpoint。这类功能本身不花哨，但它决定了 Autonomous 能不能真正进入对网络边界、访问路径、合规要求更敏感的企业环境。 ￼

再是 Autonomous Data Guard。2020 年 7 月，Autonomous Database Serverless 支持 provision standby peer database，用于 data protection 和 disaster recovery。这个点的意义在于：Oracle 把传统企业数据库里最能体现护城河的 HA/DR 能力，搬进了“自治数据库”默认产品线，而不是让用户在云上自己重新搭。 ￼

然后是 Autonomous JSON Database。2020 年 8 月，Oracle 正式把它作为 Autonomous Database 服务族的一员推出。配套官方博客进一步解释，其底层一个关键点是 OSON（optimized native binary storage format for JSON）：JSON 文档在 Autonomous JSON Database 中会自动以 OSON 形式存储，以获得更快查询、更高效更新和更低存储占用。这里很值得注意：Oracle 对 JSON 的打法不是“我再卖一个独立文档数据库”，而是把 JSON 当成 Oracle Database 本体能力的一个访问/开发模型扩展。 ￼

同样在 2020 年，Refreshable Clone 也上线了。官方描述是，可以创建 Autonomous Database 的 refreshable clone，并按设定周期从源库 refresh。这个能力看似偏运维，但它实际打到的是开发测试、报表隔离、读流量分担这类真实使用场景。2025 年 Oracle 甚至进一步把 refreshable clone 用到 elastic pool leader 的 read offload 和 live workload capture-replay 上，说明 clone 机制已经从“便利性功能”进化成平台级构件。 ￼

如果把 2020 年归纳成一句话，那就是：Oracle 开始把 Autonomous 从“更省事的托管数据库”，补成“真正可以承接企业生产需求的云数据库平台”。 Private networking、Data Guard、JSON、refreshable clone，这四个点拼起来，已经不是单纯弹性数据库实例的概念了。 ￼

3）2021–2023：少了噱头，多了平台化运维与企业级恢复

这几年如果只看传播声量，没 2024–2025 那么热闹；但如果从企业产品成熟度看，这段时间很关键。比如 2021 年，Autonomous Database Serverless 提供了 Maintenance History，允许查看 shared Exadata infrastructure 上某个 Autonomous Database 的维护历史。单看这只是一个控制台能力，但它背后反映的是 Autonomous 开始更系统地暴露可观测性、维护窗口与生命周期管理信息。 ￼

到 2023 年，数据库服务侧能看到更浓的企业恢复与大规模运维味道。例如 Oracle Database Autonomous Recovery Service 被引入为 Exadata Database Service on Dedicated Infrastructure 的 backup destination。官方将其描述为 policy-driven automatic backup and recovery system。对 Oracle 这样的产品来说，备份、恢复、保留策略、跨区域恢复能力，一直不是边角料，而是高毛利企业客户愿意继续买单的根部价值。 ￼

同一时期，Exadata Fleet Update 也被推出来，Oracle 的官方说法是它简化、标准化并增强 Oracle Database 和 Grid Infrastructure 的 patching 体验。你会发现，Oracle 这几年的“automatic”其实很少只停留在单个 SQL 优化 feature，而是往生命周期托管扩展：从索引、扩缩容，走到补丁、备份、恢复、维护、灾备。 ￼

换句话说，这几年 Oracle 在做的是一件很传统、但也最难被取代的事：把复杂企业数据库运维经验封装进服务本身。这也是 Autonomous 真正能构成商业护城河的地方。很多云数据库会先把“能跑起来”做得很轻，但 Oracle 更看重的是“出事时谁扛得住、谁恢复得快、谁能合规、谁能审计、谁能持续 patch”。 ￼

4）2024：23ai 是明显的分水岭

2024 年，Oracle Database 23ai GA，这几乎就是近年路线变化最明确的分水岭。Oracle 官方博客直接说，过去四年开发的这个 long-term support release，重点放在 AI and developer productivity；并且因为 AI 成为该版本焦点，Oracle 决定把名字从 23c 改成 23ai。这个改名不是小事，它意味着 Oracle 首次把“AI”写进数据库主版本品牌，而不是只作为周边云服务。 ￼

23ai 最有代表性的两个能力，一个是 Oracle AI Vector Search，一个是 JSON Relational Duality。

先看 Oracle AI Vector Search。Oracle 官方博客给出的定义非常明确：它提供新的 SQL operators 来生成向量嵌入，提供 first-class VECTOR data type 来存储 embeddings，提供 state-of-the-art vector indexes 做 approximate search，还支持完整的 generative AI pipeline，包括 preprocessing、vectorizing data 和 augmenting LLMs with business data。官方文档则进一步强调，这个能力是为了按语义而不是关键词查询数据。 ￼

这里最值得注意的不是“Oracle 也做了向量搜索”，而是它的组织方式。Oracle 并没有把向量检索做成数据库外的一个外挂检索层，而是把 VECTOR type、vector indexes、distance functions、SQL operators、ONNX runtime support 一起纳入数据库体系。到了 26ai 的新特性文档里，甚至已经明确写到 AI Vector Search: Optimizer，即优化器支持使用基于新 VECTOR 数据类型建立的索引，而不是做 full table scan；同时还新增 Hybrid Vector Index、HNSW/IVF 相关能力、JSON 上的 hybrid vector index、external tables 支持 vector type 等。也就是说，Oracle 的方向是把向量检索正式拉进优化器、索引、SQL、PL/SQL 和数据类型系统，而不是把它留在应用层 SDK。 ￼

再看 JSON Relational Duality。官方文档说得很直白：同一份数据可以同时拥有 document-centric 和 table-centric 两种视图；它结合了两边的优点，又尽量避免各自的局限。23c 预告博客则更明确：开发者可以以 JSON documents 作为主要持久化模型，同时继续利用 relational model；而且数据只有一个 source of truth。这个能力的战略价值其实很大，因为它试图解决关系数据库长期以来对现代应用开发模型的一个痛点：开发者想要 document/object 的开发体验，但企业又不想牺牲关系模型的一致性、规范化和事务能力。 ￼

如果把 23ai 压缩成一句话，那就是：Oracle 开始把“数据库支持 AI”升级成“数据库本身就是 AI 数据运行时的一部分”。 同时，它也在试图改善自己在开发者心中的旧形象：不再只是一套 DBA 驱动的企业数据库，而是能同时服务 relational、JSON/document、vector、graph、microservice 的统一底座。 ￼

5）2025：从 AI feature 走向 AI platform，顺手把 lakehouse 接进来

到了 2025 年，Autonomous Database Serverless 的 release notes 进一步把这个方向写实了。

首先，Oracle 在 2025 年 10 月的 release note 中直接出现了 Oracle Autonomous AI Database 这一表述，并称其“architects AI into its core, seamlessly integrating AI across all major data types and workloads”。这说明 Oracle 不只是给现有数据库加 AI 功能，而是在产品命名和包装上，把 Autonomous 的下一阶段直接定义为 Autonomous AI Database。 ￼

其次，Select AI 开始从 NL2SQL 往更完整的 AI runtime 演化。2025 年的 Serverless release notes 里，陆续出现了 Select AI Conversations、Select AI Feedback、Select AI Summarize、Select AI for Python，以及最关键的 Select AI Agent (autonomous agent framework)。Oracle 官方的说法是：这个框架允许开发者在数据库内部创建 agents、tools、tasks、teams，使其能够借助 generative AI 进行 reasoning、action 和 collaboration。这个表述已经不再是传统意义上的“数据库问答功能”，而是在把数据库推向一个 agentic workflow runtime。 ￼

再往外一步，是 Iceberg REST Catalog Integration 和 Data Lake Accelerator。前者在 2025 年 10 月的 release note 中明确说，Autonomous AI Database 可以与更广泛的 Iceberg REST catalog ecosystem 集成，包括 Databricks Unity 和 Snowflake Polaris，除了既有的 Amazon Glue 和 location-based Iceberg metadata 文件。后者则表明 Autonomous AI Database 26ai 可以通过 Data Lake Accelerator 支持 external data processing。说白了，这两条意味着 Oracle 已经非常清楚：企业数据不会只在 Oracle 体系内部，开放表格式和湖仓元数据生态已经成为事实。Oracle 的选择不是完全拥抱“数据库无中心化”，而是把开放数据生态接回 Oracle 的控制面。 ￼

同一年，Autonomous Data Guard 还继续扩展到 JSON and APEX workloads，说明 Oracle 不只是把 HA/DR 绑定在传统事务和分析 workload 上，而是要把它延伸到“现代应用开发负载”。这也与前面的 JSON/AI/Agent 路线形成闭环：你既然要数据库承接现代应用入口，那对应的企业级可用性也必须跟上。 ￼

二、如果按主题归纳，Oracle 最近几年真正押注了哪几条技术主线

1. Automatic everything：先自动化调优，再自动化运维，再自动化 AI 入口

Oracle 这些年的第一主线，始终是“automatic”。但这个词不能只按 marketing 理解。更准确地说，它分成三层。

第一层是 query/workload tuning 自动化，典型就是 Automatic Indexing。它把经验性极强、长期依赖 DBA 的索引管理变成数据库内部闭环：观测 workload、提出索引候选、验证效果、保留或回滚。这个方向本质上是把优化器相关的人工经验封进产品。 ￼

第二层是 resource / lifecycle / HA / DR 自动化。从 Auto Scaling 到 Autonomous Data Guard，再到 Maintenance History、Autonomous Recovery Service、Fleet Update，你会发现 Oracle 把真正昂贵的企业运维动作都在往服务默认能力里收。这里面最关键的产品价值不是“省几个人工”，而是降低对高水平 Oracle DBA 的组织依赖，顺便把可用性、恢复时间、合规流程标准化。 ￼

第三层则是 2024 以后出现的 AI interaction 自动化。Select AI 系列能力，本质上是在自动化“从自然语言到 SQL / summary / translation / conversation / agent action”的桥接层。也就是说，Oracle 的 automatic 已经从索引和扩缩容，走到“数据库如何理解用户意图并调动内部数据”。 ￼

这三层叠在一起，才能理解 Oracle 为什么一直强调 Autonomous。它真正想卖的不是单个自动化 feature，而是数据库从调优、运维到 AI 交互的整条托管链条。 ￼

2. 数据模型扩张：关系模型不丢，但开发入口要变

Oracle 显然没有放弃关系模型，相反，它的核心策略是：关系模型仍然是单一事实源（single source of truth），但访问与编程模型必须扩张。

2020 年的 Autonomous JSON Database 和 OSON，说明 Oracle 已经不满足于“支持 JSON 列”。它开始为 JSON workload 提供单独的服务包装和底层优化存储格式。到 23ai 的 JSON Relational Duality，这个方向进一步升级：不是仅仅把 JSON 塞进关系库，而是让同一份数据天然同时具备 relational 与 document 两种视图。 ￼

这背后其实是对现代应用开发趋势的一次回应。过去十多年，document store、ORM-heavy 开发方式、对象模型驱动 API 设计之所以流行，很大程度上是因为纯 relational schema 对应用开发者不够友好。Oracle 这套 duality 的目标，就是尽量别让开发者在“开发体验”和“关系一致性”之间二选一。它不是去做一个更像 MongoDB 的系统，而是尝试在 Oracle Database 里把这两种世界合起来。 ￼

所以，从产品路线看，Oracle 不是在削弱 relational，而是在用 JSON/document 入口保住 relational core 的统治力。这点非常 Oracle，也非常现实。 ￼

3. AI-native 化：向量、RAG、NL2SQL、Agent 尽量都放在数据库里

如果说 23ai 是分水岭，那 Oracle 后续最明确的一条技术路线，就是把数据库变成 AI 工作流里真正的参与者，而不只是数据来源。

以 Oracle AI Vector Search 为例，官方能力描述覆盖了 embeddings 生成、VECTOR 数据类型、vector indexes、similarity search、hybrid search、ONNX model support，甚至在 26ai 文档中已经出现了 optimizer、PL/SQL、JSON/OSON、external tables、HNSW/IVF index reorg 等更细的演进条目。这说明 Oracle 的向量能力不是“先做个 demo 追热点”，而是在继续往数据库内核接口里下沉。 ￼

更关键的是 Oracle 的组合方式。它强调向量与业务数据一起存储、一起查询、一起受 SQL、安全、事务和现有分析能力约束。对企业客户来说，这个卖点比“单独一个最快的向量库”更好讲。因为很多企业真正关心的不是 ANN benchmark，而是权限边界、审计、事务一致性、数据不外流、RAG 数据仍留在企业数据库里。 ￼

Select AI 则是另一层。官方文档和 release notes 显示，它已经不只是“把自然语言翻成 SQL”，而是支持 chat、conversation、feedback、summary、translation、RAG、Python 接入，乃至 agent framework。这个路径非常清晰：Oracle 不想只做一个“数据库支持 LLM”的特性，而是想做企业数据 + LLM 交互 + agent orchestration 的数据库中枢。 ￼

4. 平台边界外扩：数据库不是湖仓替代品，但要做湖仓入口

过去几年另一个很微妙但很重要的变化，是 Oracle 对开放数据生态的态度变了。

你可以看到 2025 年的 Iceberg REST Catalog Integration，明确支持 Databricks Unity、Snowflake Polaris、Amazon Glue 等生态；Data Lake Accelerator 也直接把 external data processing 拉进 Autonomous AI Database 26ai。与此同时，Autonomous Database 一直在增强 external tables、Parquet/ORC/Avro、Cloud Links、Cloud Tables 等相关能力。 ￼

这说明 Oracle 已经接受一个现实：企业数据平台不再是单一数据库封闭世界。Iceberg、对象存储、跨系统 catalog、open table formats 已经成为新的基础设施事实。Oracle 的选择并不是彻底放弃封闭体系，而是尽量确保即便数据在外部湖仓里，访问控制、查询入口、AI 接入和企业治理仍然可以回到 Oracle 的数据库/服务层里完成。  ￼

从竞争策略看，这很像一种“有限开放”：你可以接外部生态，但最好还是通过 Oracle 的数据库控制面来接。对 Oracle 来说，这比跟 Databricks/Snowflake 正面比谁更“开放原生”更符合它的商业 DNA。 ￼

三、从自动化、执行引擎、存储引擎、优化器角度，Oracle 的主要动向是什么

这部分需要说得克制一点。因为公开 release notes 不会像内核论文那样把实现细节全部展开。但从公开材料，仍然能看出一些很明确的方向。

1）自动化：Oracle 的“自治”首先发生在运维面，其次才是查询层

很多人一提 Autonomous，会先想到“数据库会自己调 SQL”。但从过去几年的发布内容看，Oracle 最稳定、最持续投入的自动化，其实是运维控制面自动化：Auto Scaling、Automatic Indexing、Autonomous Data Guard、Maintenance History、Recovery Service、Fleet Update、online restart、transportable tablespaces、wallet rotation、private endpoint 策略、弹性池管理等。 ￼

这件事的技术含义很直接：Oracle 不是先把数据库做成“会聊天的 AI 产品”，而是先把它做成“在企业生产上尽量少出事、出了事尽量快恢复、维护尽量标准化”的产品。AI 是后来加速器，不是最初地基。 ￼

2）优化器：从传统索引/统计信息世界，走向向量索引可感知

Automatic Indexing 本身就反映了 Oracle 持续把 workload-aware tuning 产品化。到了 26ai 新特性文档，Oracle 又明确公开了 AI Vector Search: Optimizer，即优化器开始支持在向量查询中选用 vector indexes，而不是 full table scan。这个信号很关键：在 Oracle 的路线里，向量检索不是旁路逻辑，而是要被正式吸纳到优化器决策空间里。 ￼

这也解释了为什么 Oracle 后面持续加入 HNSW、IVF、Hybrid Vector Index、JSON 上的 hybrid vector index、索引重组、RAC 上分布式/复制式 HNSW 等能力。它不是单纯为了补 feature matrix，而是在让向量索引逐步具备一个成熟数据库索引类型应有的管理、维护和计划选择能力。 ￼

3）执行引擎：一边继续 OLTP/分析性能深挖，一边把 vector execution 纳入核心路径

公开博客里最能体现执行层持续演进的例子之一，是 In-Memory Deep Vectorization。Oracle 官方博客提到，这个 framework 最早在 21c 引入，23ai 又扩展到 multi-level hash joins、multi join key、semi joins、outer joins 和 full group by aggregation，并利用 SIMD 指令提升性能。这里的“vectorization”不是 LLM/vector embedding 的那个 vector，而是 CPU/SIMD 执行层面的深向量化。它说明 Oracle 传统分析执行层的性能挖掘仍在继续。 ￼

另一方面，在 AI Vector Search 相关材料里，Oracle 又提到为向量距离计算实现了 SIMD-optimized vector distance kernels，并使用 state-of-the-art approximate search indexes，同时利用现代 CPU 平台的 memory bandwidth 与 multi-core parallelism；甚至在 2024 年博客中还谈到用 NVIDIA GPU 加速 embeddings 生成和 vector index 创建。综合这些信息，可以合理判断：Oracle 在执行层上采取的是双线并进——传统 SQL/分析执行路径继续深优化，同时把 vector workload 也纳入同一个高性能执行体系。  ￼

4）存储与基础设施：数据库能力与 Exadata 绑定仍然很深

Oracle 官方博客在介绍 Autonomous Database 和 23ai on Exadata 时，一再强调 Exadata 的数据库优化硬件、自动调优、高性能、低延迟与高吞吐。换句话说，Oracle 虽然在讲 Autonomous、AI、developer productivity，但它的很多核心能力——尤其是 mission-critical 的性能、可用性与恢复——仍然深度建立在 Exadata 这套纵向整合基础设施之上。 ￼

这点很关键。因为它意味着 Oracle 的路线并不是最轻、最通用、最云原生抽象的那种数据库路线，而是一条非常典型的 full-stack integrated system 路线：数据库、自治能力、恢复体系、底层基础设施、云服务接口，被打成一个整体卖。对大企业来说，这反而是价值；对偏开放生态、偏轻量成本优化的用户来说，它也构成进入门槛。 ￼

四、重大 feature / optimisation / 新场景支持，应该怎么抓重点

如果只选近几年最值得记住的几个节点，我会挑下面这些。

第一组，是 Automatic Indexing、Auto Scaling、Autonomous Data Guard、Refreshable Clone、Autonomous Recovery Service、Fleet Update。它们共同构成 Oracle 的自治底盘，也构成它与许多“普通托管数据库”的差异。别看这些 feature 不如 AI 吸睛，但在商业上，它们才是最能支撑高客单价和企业留存的部分。 ￼

第二组，是 Autonomous JSON Database + OSON + JSON Relational Duality。它们代表 Oracle 对开发模型的一个系统性回应：既不愿意放弃 relational core，又必须吸纳 document-centric application 的体验诉求。这个方向不是简单“支持 JSON”，而是在试图重新定义企业应用与数据库之间的接口形式。 ￼

第三组，是 Oracle AI Vector Search + Select AI。这是 2024 之后 Oracle 最明显的新品牌中心。向量、RAG、自然语言、总结、翻译、会话、Python 接入、agent framework，都在说明 Oracle 想做的不是外挂式 AI 集成，而是把 AI 检索和 AI 交互做成数据库能力本身。 ￼

第四组，是 Iceberg REST Catalog Integration、Data Lake Accelerator、external tables/开放格式增强。这是 Oracle 对 lakehouse/open formats 时代做出的务实回应。它不一定会成为 Oracle 最核心的品牌资产，但它能显著降低“Oracle = 封闭孤岛”的市场阻力。 ￼

五、Oracle 这几年的产品商业定位，到底在卖什么

如果把 Oracle 的近年数据库产品定位压缩成一句话，我会写成这样：

它卖的已经不只是一个数据库实例，而是一套高性能、高可用、高自动化、AI-ready 的企业数据平台。  ￼

这个定位可以拆成三层。

最底层卖的是 性能与可靠性。Exadata、Data Guard、Recovery Service、跨区域恢复、运维补丁能力，这些构成 Oracle 与很多通用云数据库的基础差异。企业最关键的账务、订单、核心主数据系统，真正看重的首先还是这些。 ￼

中间层卖的是 自动化与托管复杂度下降。Automatic Indexing、Auto Scaling、maintenance、restart、resource manager、clone、backup、fleet update，这一整套能力，解决的是“没有那么多顶尖 DBA，或者不想把 DBA 时间耗在重复性工作上”的问题。它卖的是 TCO、组织效率和可运营性。 ￼

最上层卖的是 AI-ready 与现代应用开发入口。Vector Search、Select AI、JSON Relational Duality、Python 接入、agent framework、Iceberg catalog、Data Lake Accelerator，这些能力的共同叙事是：你不需要把企业数据大规模搬离 Oracle，仍然可以接住 AI、RAG、现代 API 开发和开放数据生态。 ￼

从商业打法上看，这个定位其实很老辣。它不是去跟最轻量、最开放、最便宜的数据库正面对位，而是继续强化自己的传统强项，同时把“你以为 Oracle 做不了的新世界入口”尽量补齐。对于大量已经深度使用 Oracle 的企业客户来说，这个故事非常容易买单：不用大迁移，不用重建治理，不用把高价值数据交给一堆新的基础设施组件，也能接住 AI。 这就是 Oracle 近年最核心的市场卖点。 ￼

六、如果按年度看，产品重点变化是怎么迁移的

2019：自治能力商业化。
重点不在 AI，而在让数据库自己处理更多调优和资源弹性问题。Automatic Indexing 与 Auto Scaling，是“自治”从概念走向产品能力的代表。 ￼

2020：高可用、网络隔离、JSON 场景扩张。
Private Endpoint、Autonomous Data Guard、Autonomous JSON Database、Refreshable Clone，共同把 Autonomous 推向更完整的企业生产平台。 ￼

2021–2023：平台化运维与恢复能力体系化。
Maintenance History、Recovery Service、Fleet Update 这类能力说明 Oracle 正在把企业数据库运维经验进一步服务化、标准化。 ￼

2024：23ai 让 AI 成为数据库品牌中心。
23ai 正式 GA，Oracle 公开把 AI 写进版本名；AI Vector Search 与 JSON Relational Duality 成为最鲜明的双主角。 ￼

2025：从 AI feature 走向 AI platform。
Autonomous AI Database、Select AI Conversations/Feedback/Summarize/Translate/Python、Select AI Agent、Iceberg REST Catalog Integration、Data Lake Accelerator，这些都在表明 Oracle 正在把数据库推向一个更完整的 AI 数据与 agent 运行平台。 ￼

七、一些更直白的判断：Oracle 这条路线意味着什么

第一，Oracle 不是在变成一个“更开放的 Snowflake”或者“更现代的 Postgres 托管服务”。它的根始终还是企业级 mission-critical database，只是它在尽量把新时代入口收回来。 ￼

第二，Oracle 的“自治”含金量并不低，但它主要体现在运维控制面，不是神奇的全自动数据库魔法。 这反而更可信。因为真正难、真正贵、真正能打出差异化的，恰恰是扩缩容、补丁、备份恢复、容灾、索引管理、资源治理这些脏活累活。 ￼

第三，23ai/26ai 之后，Oracle 最重要的战略变化不是“支持向量”本身，而是它试图把 AI、JSON/document、lakehouse、agent 都统一到 Oracle Database 这个单一控制面上。 这背后有很强的产品自信，也有很强的商业防御意味。 ￼

第四，它并不是最轻、最便宜、最开放的路线，但它很可能仍然是最适合“企业核心数据不愿外流，同时又必须接住 AI”这类客户的一条路线。 这是 Oracle 的市场空间，也是它近年所有演进拼起来后最稳定的解释。 ￼

结语：作为数据库工程师，应该怎么看 Oracle 近几年的演进

如果你是做数据库内核、执行器、优化器、存储或者分布式系统的人，看 Oracle 近几年的发布，会有一种很明显的感觉：它并没有放弃传统数据库最硬的那些部分，反而还在继续打磨它们；但与此同时，它也不再满足于只做“最强企业关系数据库”这个旧角色。Oracle 正在试图把数据库重写成一个更大的东西——企业数据控制面、恢复控制面，以及 AI 交互控制面。  ￼

这条路线未必讨所有技术人喜欢。它不够轻，不够纯粹，不够“开放生态优先”。但从产品和商业上看，它非常自洽：只要 Oracle 还能牢牢控制企业最核心的数据、恢复、治理和 AI 接入边界，它就仍然能在 AI 时代保持自己极强的议价能力。过去几年 Oracle Database 的大多数迭代，无论 Automatic、JSON、Vector、Select AI 还是 Iceberg/Data Lake，本质上都在服务这件事。 ￼

你要是愿意，我下一条可以继续把这篇文章再往前推进一层，整理成更适合公开发布的版本，比如：
	1.	加一个更有博客感的标题与副标题；
	2.	把文中提到的 Oracle 专有名词单独做一个“术语索引”；
	3.	再补一版“站在 StarRocks / 新一代分析型数据库工程师视角”的对照点评。
