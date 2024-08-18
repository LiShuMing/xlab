# 可持续增长的数据架构设计

## 核心挑战
- 数据每日增量增长（可能 50-200 条/天）
- 需要支持快速查询最近数据
- 历史数据归档和压缩
- 备份和恢复效率

## 推荐架构：分层存储 + DuckDB

```
┌─────────────────────────────────────────────────────────┐
│                     查询层 (Web Server)                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │  最近7天热数据 │  │  30天温数据   │  │   历史冷数据归档    │  │
│  │  (DuckDB)   │  │  (DuckDB)    │  │  (Parquet/JSON) │  │
│  └─────────────┘  └─────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────┘
                           │
┌─────────────────────────────────────────────────────────┐
│                     存储层                               │
│  ┌─────────────────────────────────────────────────┐    │
│  │  hot.duckdb        (最近7天，内存映射，极速查询)      │    │
│  │  warm.duckdb       (30天数据，按日期分区)            │    │
│  └─────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────┐    │
│  │  archive/2026/03/   (月度Parquet，列式压缩)         │    │
│  │  archive/2026/02/                               │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

## 数据流

```
每日增量抓取
     │
     ▼
┌─────────┐    ┌─────────────┐    ┌─────────────────┐
│ 去重过滤 │ -> │ 写入 hot.db │ -> │ 每日凌晨归档任务  │
└─────────┘    └─────────────┘    └─────────────────┘
                                         │
                    ┌────────────────────┼────────────────────┐
                    ▼                    ▼                    ▼
              7天前的数据 ->      30天前的数据 ->        365天前的数据
              移到 warm.db       压缩为 Parquet          冷存储/删除
```

## 关键设计决策

### 1. 为什么用 DuckDB？

```python
# 查询最近7天的数据（毫秒级）
SELECT * FROM items
WHERE published_date >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY published_date DESC

# 聚合统计（内置优化）
SELECT DATE(published_date) as day, COUNT(*)
FROM items
GROUP BY day
ORDER BY day DESC
LIMIT 30
```

优势：
- 单文件，零配置
- 列式存储，压缩比高（预计 5-10x）
- 支持 Parquet 外部表（历史数据不导入也能查）
- Python 原生支持

### 2. 分层策略

| 层级 | 数据范围 | 存储 | 查询延迟 | 保留策略 |
|-----|---------|------|---------|---------|
| Hot | 最近7天 | DuckDB (内存映射) | < 10ms | 永久 |
| Warm | 7-30天 | DuckDB (磁盘) | < 50ms | 永久 |
| Cold | 30天-1年 | Parquet (按月份) | < 200ms | 永久 |
| Archive | > 1年 | Parquet (压缩) / 删除 | 按需加载 | 可删除 |

### 3. 归档任务（每日凌晨运行）

```python
# pseudo code
def daily_archive_job():
    # 1. 7天前的数据从 hot -> warm
    move_to_warm(cutoff_date=now() - 7days)

    # 2. 30天前的数据从 warm -> cold (Parquet)
    compress_to_parquet(cutoff_date=now() - 30days)

    # 3. 可选：365天前的数据删除或移到冷存储
    archive_or_delete(cutoff_date=now() - 365days)

    # 4. 更新索引
    refresh_index()
```

### 4. 统一查询接口

```python
class ItemStore:
    """统一存储接口，屏蔽底层实现"""

    def query(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        product: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Item]:
        """
        智能路由：
        - 最近7天 -> hot.duckdb
        - 7-30天 -> warm.duckdb
        - 历史 -> parquet (按需)
        """
        pass

    def insert(self, items: List[Item]) -> None:
        """只写入 hot.db"""
        pass

    def get_by_date(self, date: date) -> List[Item]:
        """获取某天的全部条目"""
        pass
```

## 容量估算

假设每天 100 条，每条 2KB：

| 时间段 | 条目数 | 原始大小 | DuckDB 压缩后 | Parquet 压缩后 |
|-------|-------|---------|--------------|---------------|
| 7天 | 700 | 1.4 MB | ~200 KB | - |
| 30天 | 3,000 | 6 MB | ~800 KB | - |
| 1年 | 36,500 | 73 MB | ~10 MB | ~5 MB |
| 5年 | 182,500 | 365 MB | ~50 MB | ~25 MB |

**结论**：即使 5 年数据，热数据也只有 50MB，完全可以接受。

## 迁移路径

```
Phase 1: 保持现状（JSON文件）
    │
    ▼ 数据量 > 5000 条或查询变慢
Phase 2: 引入 DuckDB（热数据），JSON保留（历史）
    │
    ▼ 数据量 > 5万条
Phase 3: 完整分层（Hot/Warm/Cold）
```

## 实施建议

**现在就可以做的**（低风险）：
1. 封装 `Storage` 抽象层
2. 保持 JSON 作为"真相源"
3. DuckDB 作为查询缓存/索引

**数据量增长后**（> 5000 条）：
1. 实现自动归档任务
2. 历史数据转 Parquet
3. 查询路由优化

需要我实现这个架构的代码吗？