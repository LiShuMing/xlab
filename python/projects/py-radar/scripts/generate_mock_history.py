#!/usr/bin/env python3
"""Generate mock historical data for 7 days to demonstrate pagination."""

import json
from datetime import datetime, timedelta
from pathlib import Path

# Sample mock news items for different days
mock_items = [
    {
        "title": "PostgreSQL 17 发布新特性",
        "original_title": "PostgreSQL 17 Beta 1 Released",
        "product": "PostgreSQL",
        "sources": ["https://postgresql.org/about/news/"],
        "published_date": "2026-03-23T10:00:00+00:00",
        "content_type": "release",
        "what_changed": ["新增 JSON 性能优化", "改进 vacuum 效率"],
        "why_it_matters": ["大幅提升复杂查询性能", "减少维护窗口时间"],
        "evidence": ["测试显示 30% 性能提升"],
    },
    {
        "title": "MongoDB 8.0 性能基准测试",
        "original_title": "MongoDB 8.0 Benchmark Results",
        "product": "MongoDB",
        "sources": ["https://mongodb.com/blog/"],
        "published_date": "2026-03-22T14:00:00+00:00",
        "content_type": "benchmark",
        "what_changed": ["新的存储引擎架构", "改进索引压缩"],
        "why_it_matters": ["降低存储成本", "提高查询吞吐量"],
        "evidence": ["YCSB 测试显示 2x 提升"],
    },
    {
        "title": "Redis 集群最佳实践",
        "original_title": "Redis Cluster Best Practices 2026",
        "product": "Redis",
        "sources": ["https://redis.io/blog/"],
        "published_date": "2026-03-21T09:00:00+00:00",
        "content_type": "tutorial",
        "what_changed": ["新的分片策略", "故障转移优化"],
        "why_it_matters": ["提高可用性", "简化运维"],
        "evidence": ["生产环境验证"],
    },
    {
        "title": "ClickHouse 实时分析优化",
        "original_title": "ClickHouse Real-time Analytics",
        "product": "ClickHouse",
        "sources": ["https://clickhouse.com/blog/"],
        "published_date": "2026-03-20T16:00:00+00:00",
        "content_type": "blog",
        "what_changed": ["新增流式插入", "物化视图增强"],
        "why_it_matters": ["支持实时仪表板", "降低延迟"],
        "evidence": ["延迟从秒级降至毫秒级"],
    },
    {
        "title": "TiDB 7.5 LTS 发布",
        "original_title": "TiDB 7.5 LTS Release Notes",
        "product": "TiDB",
        "sources": ["https://pingcap.com/blog/"],
        "published_date": "2026-03-19T11:00:00+00:00",
        "content_type": "release",
        "what_changed": ["全局索引支持", "TiFlash 升级"],
        "why_it_matters": ["简化跨分片查询", "增强分析能力"],
        "evidence": ["TPC-H 测试通过"],
    },
    {
        "title": "CockroachDB 多区域部署指南",
        "original_title": "Multi-Region Deployment Guide",
        "product": "CockroachDB",
        "sources": ["https://cockroachlabs.com/blog/"],
        "published_date": "2026-03-18T13:00:00+00:00",
        "content_type": "tutorial",
        "what_changed": ["新的区域配置语法", " follower reads 优化"],
        "why_it_matters": ["降低跨区域延迟", "提高一致性"],
        "evidence": ["延迟降低 60%"],
    },
    {
        "title": "DuckDB 1.0 正式版发布",
        "original_title": "DuckDB 1.0 GA Release",
        "product": "DuckDB",
        "sources": ["https://duckdb.org/news/"],
        "published_date": "2026-03-17T08:00:00+00:00",
        "content_type": "release",
        "what_changed": ["稳定 API 保证", "性能优化"],
        "why_it_matters": ["生产环境就绪", "嵌入式分析首选"],
        "evidence": ["100% 向后兼容承诺"],
    },
]


def generate_report(date: datetime, items: list) -> dict:
    """Generate a report for a specific date."""
    date_str = date.strftime("%Y-%m-%d")

    return {
        "date": date_str,
        "executive_summary": [
            f"{item['product']}: {item['title']}" for item in items[:3]
        ],
        "top_updates": items,
        "themes": [],
        "action_items": [],
        "metadata": {
            "total_items_collected": len(items) * 10,
            "top_items_count": len(items),
            "language": "zh",
        },
    }


def main():
    output_dir = Path("out")
    output_dir.mkdir(exist_ok=True)

    today = datetime.now()

    # Generate 7 days of reports
    for i in range(7):
        date = today - timedelta(days=i)

        # Get items for this day (cycle through mock_items)
        start_idx = i % len(mock_items)
        items = []
        for j in range(3):  # 3 items per day
            item_idx = (start_idx + j) % len(mock_items)
            item = mock_items[item_idx].copy()
            # Adjust date
            item_date = date - timedelta(hours=j * 4)
            item["published_date"] = item_date.isoformat()
            items.append(item)

        report = generate_report(date, items)

        # Write JSON
        json_path = output_dir / f"{date.strftime('%Y-%m-%d')}.json"
        json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(f"Generated: {json_path}")

    print("\nDone! 7 days of mock data generated.")


if __name__ == "__main__":
    main()
