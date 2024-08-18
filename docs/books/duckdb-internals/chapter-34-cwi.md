# 第34章：CWI 与 DuckDB 的学术基因

> DuckDB 不是凭空出现的——它根植于荷兰 CWI（Centrum Wiskunde & Informatica）四十年的列式数据库研究传承。理解这个传承，才能理解 DuckDB 为什么"这样设计"而非"那样设计"。

## 34.1 CWI 的研究传承：从 MonetDB（2008）到 Vectorwise 的列存储技术积淀

CWI 的数据库研究始于 1980 年代，核心人物是 Peter Boncz。他领导的 Database Architectures 研究组产出了列式数据库领域最重要的学术成果：

- **MonetDB**（2004）：第一个成熟的列式数据库系统。提出了 BAT（Binary Association Table）代数——每个列独立存储和计算
- **MonetDB/X100**（2005）：在 MonetDB 基础上提出向量化执行模型——一次处理一批数据而非逐行，减少了虚函数调用和指令缓存压力
- **Vectorwise**（2008）：MonetDB/X100 的商业化版本，由 Boncz 联合创立的 Actian 公司运营。Vectorwise 证明了向量化执行在 OLAP 场景下的性能优势

这些项目的核心洞察一脉相承：**列式存储 + 向量化执行是 OLAP 的最优解**。DuckDB 继承了这个洞察，但重新思考了"向量化执行如何嵌入"的问题。

## 34.2 Database Architectures 研究组：师承关系与技术传承

```
Peter Boncz (教授, CWI)
  ├── Hannes Mühleisen (博士生 → DuckDB Labs CEO)
  │     └── Mark Raasveldt (博士生 → DuckDB Labs CTO)
  │
  └── 其他学生/合作者:
        ├── Marcin Zukowski (Vectorwise 联合创始人)
        ├── Sandro Héritier (MonetDB 核心开发者)
        └── 多位 CWI 博士生和研究员
```

Peter Boncz 是列式数据库的先驱之一。他的 2002 年博士论文《Database Architecture Solutions for Performance and Functionality》奠定了 BAT 代数的理论基础。Hannes Mühleisen 和 Mark Raasveldt 在 Boncz 指导下，于 2018 年启动了 DuckDB 项目。

## 34.3 从 MonetDB 到 DuckDB 的技术演进

### MonetDB 的 BAT 与 DuckDB Vector 的继承关系

MonetDB 的 BAT（Binary Association Table）是列式存储的原子单元——一个 BAT 就是 `<head, tail>` 二元组的集合。DuckDB 的 Vector 本质上是 BAT 的简化版：去掉了 head（MonetDB 后来也去掉了），保留了一个紧凑的列值数组。

```cpp
// MonetDB BAT 的概念:
// BAT[head_type, tail_type] — head 通常是 oid，tail 是实际值
// 后来演变为 BAT[void, tail_type] — head 为隐式序号

// DuckDB Vector 的对应:
// Vector — 只有值数组 + ValidityMask + 类型信息
// 更简洁，更适合向量化批处理
```

### 为什么放弃全列存储内核、转向嵌入式进程内设计？

MonetDB 假设独占机器——它的内存管理、线程调度都假设它是唯一的"王者"。MonetDBLite 试图把 MonetDB 塞进 Python 进程，结果撞上了架构矛盾。

DuckDB 的选择是**从零设计嵌入式引擎**：

| 维度 | MonetDB | DuckDB |
|------|---------|--------|
| 内存管理 | 假设独占，大块 mmap | 按需分配，尊重宿主进程 |
| 线程模型 | 自行管理线程池 | 可配置线程数，可单线程运行 |
| 依赖 | 多个外部库 | 零外部依赖 |
| 内存压力 | 乐观（物化中间结果） | 保守（流式 Pipeline + 溢出到磁盘） |

### Vectorwise/Actian Vector 的向量化执行遗产

Vectorwise（后来的 Actian Vector）将 MonetDB/X100 的向量化执行商业化。它的关键贡献：

1. **Vectorized Processing**：一次处理一批数据（X100 论文称为 "block processing"），而非 Volcano 的逐行迭代
2. **Lightweight Compression**：在压缩数据上直接计算（如 RLE 数据的向量化扫描）
3. **Cache-Conscious Algorithms**：哈希表、排序等算法针对 CPU 缓存层次优化

DuckDB 继承了这三点，但做了关键改进：
- 向量化粒度从 X100 的可变批次固定为 2048 行（`STANDARD_VECTOR_SIZE`）
- 压缩算法更丰富（ALP、DictFSST、Roaring 等新品种）
- Pipeline 执行模型替代了 X100 的迭代器模型

## 34.4 学术界到工业界的转身

### 时间线

```
2018:  Mark Raasveldt 和 Hannes Mühleisen 在 CWI 启动 DuckDB 项目
2019:  SIGMOD Demo — DuckDB 首次公开展示
2020:  CIDR 论文 — "Data Management for Data Science — Towards Embedded Analytics"
       → 这篇论文正式定义了"嵌入式分析"的范式
2021:  DuckDB Labs Amsterdam B.V. 成立
       → Hannes Mühleisen (CEO) + Mark Raasveldt (CTO)
       → 商业模式：企业支持、技术咨询、定制开发
2022:  GitHub Star 数突破 10,000
2023:  MotherDuck 成立（基于 DuckDB 的云数据仓库）
2024:  DuckDB 1.0 发布，GitHub Star 数突破 20,000
2025:  DuckDB 1.3 发布，Star 数突破 30,000
2026:  DuckDB 1.5 发布，DuckLake v1.0 发布
```

### 关键论文摘要

**"Data Management for Data Science — Towards Embedded Analytics"（CIDR 2020）**

这篇论文是 DuckDB 的宣言。核心论点：
- 数据科学工作流在 Python/R 进程中完成，但 SQL 分析需要连接远程数据库——这个鸿沟是性能杀手
- 嵌入式分析引擎消除了这个鸿沟：SQL 执行在数据所在的地方
- 嵌入式不是服务器引擎的简化版，而是全新的物种——需要全新的架构决策

**"Saving Private Hash Join"（VLDB 2025）**

关于 DuckDB Hash Join 的溢出处理优化——当 Hash 表超过内存限制时，如何优雅地分区和溢出。

**运行时可扩展解析器（CIDR 2025）**

DuckDB 的 Parser Extension 机制——允许第三方扩展 SQL 语法，不需要修改 DuckDB 核心代码。

## 34.5 DuckDB Foundation：独立于商业实体的纯技术基金会

### 治理模型

```
Stichting DuckDB Foundation (荷兰非营利基金会)
  ├── 董事会：Hannes Mühleisen, Mark Raasveldt, Peter Boncz
  ├── 持有项目大部分知识产权（IP）
  ├── 资金来源：慈善捐赠
  └── 所有资金直接用于 DuckDB 开发
```

### 与商业实体的关系

DuckDB 生态中存在三个实体：

| 实体 | 角色 | 关系 |
|------|------|------|
| DuckDB Foundation | IP 持有者 + 开源守护者 | 非营利，独立于商业实体 |
| DuckDB Labs | 核心开发团队 + 商业服务 | 创始人拥有，提供企业支持 |
| MotherDuck | 云数据仓库产品 | 基于 DuckDB，独立公司 |

Foundation 持有 IP，DuckDB Labs 负责日常开发和维护，MotherDuck 是商业用户。三者利益对齐但不相互控制——这是开源项目治理的经典模式。

### 资助层级

```
Gold Supporters (€100,000+): AWS, MotherDuck, Posit
Silver Supporters (€10,000+): Mode, Hex, Watershed, Hugging Face, Crunchy Data, PostHog, ...
Technical Sponsors: Cloudflare
Open-Source Grants: Bloomberg
```

## 34.6 思考：为什么欧洲学术机构盛产优秀数据库系统

欧洲产出的重要数据库系统：MonetDB（荷兰 CWI）、DuckDB（荷兰 CWI）、ClickHouse（俄罗斯 Yandex）。

可能的解释：

1. **长期基础研究投入**：CWI 等欧洲研究机构有稳定的基础研究经费，允许研究者用 10-20 年时间深耕一个领域。Peter Boncz 从 1990 年代开始研究列式存储，到 DuckDB 已是 20 多年的积淀
2. **工程与学术的紧密结合**：CWI 的研究者既写论文也写代码——MonetDB 就是一个"论文驱动的系统"
3. **开放的文化**：欧洲学术界更倾向于开放源代码——MonetDB 是开源的，DuckDB 也是
4. **不追逐短期商业回报**：CWI 是政府资助的研究机构，不需要每季度向 VC 交差。这允许研究者做"正确而非流行"的选择

DuckDB 是这个生态的最新成果——它不是"欧洲版的 Snowflake"，而是"学术洞察的工程化"。它的价值不在于商业模式，而在于技术选择：向量化执行、零依赖、嵌入式——这些选择都有 20 年的学术积淀支撑。
