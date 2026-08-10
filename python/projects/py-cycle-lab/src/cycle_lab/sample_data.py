"""Deterministic sample data for the first LongCycle UI implementation."""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any


def _series(length: int, base: float, amp: float, drift: float = 0.0) -> list[float]:
    values = []
    for i in range(length):
        values.append(round(base + amp * math.sin(i / 4.3) + 0.35 * math.cos(i / 8.1) + drift * i, 3))
    return values


def dashboard_payload() -> dict[str, Any]:
    today = date.today()
    months = 180
    dates = [
        (today - timedelta(days=30 * (months - i))).replace(day=1).isoformat()
        for i in range(months)
    ]
    spread = _series(months, 0.7, 1.15, drift=-0.004)
    stress = [round(max(0.04, min(0.92, 0.42 - value / 3.4 + 0.1 * math.sin(i / 12))), 3) for i, value in enumerate(spread)]
    expansion = [round(max(0.05, min(0.88, 1.0 - s - 0.16)), 3) for s in stress]
    slowdown = [round(max(0.04, 1.0 - stress[i] - expansion[i]), 3) for i in range(months)]

    assets = [
        {
            "name": "沪深300",
            "pe": 31,
            "pb": 26,
            "erp": 67,
            "sentiment": 42,
            "trend": 48,
            "action": "分批关注",
        },
        {
            "name": "中证500",
            "pe": 46,
            "pb": 39,
            "erp": 55,
            "sentiment": 51,
            "trend": 44,
            "action": "观察",
        },
        {
            "name": "纳指100",
            "pe": 78,
            "pb": 81,
            "erp": 28,
            "sentiment": 83,
            "trend": 72,
            "action": "暂停追买",
        },
        {
            "name": "标普500",
            "pe": 64,
            "pb": 69,
            "erp": 41,
            "sentiment": 66,
            "trend": 61,
            "action": "谨慎",
        },
        {
            "name": "黄金",
            "pe": None,
            "pb": None,
            "erp": 52,
            "sentiment": 58,
            "trend": 67,
            "action": "观察",
        },
        {
            "name": "美债",
            "pe": None,
            "pb": None,
            "erp": 72,
            "sentiment": 35,
            "trend": 40,
            "action": "再平衡检查",
        },
        {
            "name": "现金",
            "pe": None,
            "pb": None,
            "erp": 68,
            "sentiment": 22,
            "trend": 34,
            "action": "防守储备",
        },
    ]

    return {
        "as_of": today.isoformat(),
        "state": "中性偏谨慎",
        "kpis": [
            {"label": "周期温度", "value": 64, "state": "中性偏热", "delta": "+4", "tone": "caution"},
            {"label": "估值吸引力", "value": 47, "state": "中性", "delta": "-2", "tone": "neutral"},
            {"label": "情绪拥挤度", "value": 72, "state": "偏拥挤", "delta": "+7", "tone": "risk"},
            {"label": "现金吸引力", "value": 68, "state": "有吸引力", "delta": "+1", "tone": "opportunity"},
        ],
        "yield_curve": {"dates": dates, "spread": spread},
        "regime": {
            "dates": dates,
            "expansion": expansion,
            "slowdown": slowdown,
            "stress": stress,
            "current": "Stress rising",
        },
        "risk_signals": [
            {"level": "high", "title": "10Y-2Y 利差处于历史低分位", "detail": "期限结构提示宏观风险溢价应上调"},
            {"level": "medium", "title": "情绪拥挤度高于 70", "detail": "高拥挤状态下不宜追涨扩仓"},
            {"level": "medium", "title": "美股成长估值高于长期中位", "detail": "纳指100 估值与情绪均偏热"},
            {"level": "low", "title": "A股宽基估值仍处观察区", "detail": "估值较低，但盈利下修风险仍需跟踪"},
        ],
        "assets": assets,
        "watchlist": [
            {
                "asset": "纳指100ETF",
                "thesis": "AI 与软件生产率提升驱动长期盈利增长",
                "action": "暂停追买",
                "conditions": [
                    {"label": "PE 分位 < 60%", "met": False},
                    {"label": "情绪分位 < 60%", "met": False},
                    {"label": "美债实际利率不再快速上行", "met": True},
                ],
                "risks": ["利率重新上行", "盈利预期下修", "估值继续压缩"],
            },
            {
                "asset": "沪深300ETF",
                "thesis": "估值均值回归与长期权益风险溢价修复",
                "action": "分批关注",
                "conditions": [
                    {"label": "PE 分位 < 35%", "met": True},
                    {"label": "PB 分位 < 30%", "met": True},
                    {"label": "情绪未进入极端拥挤", "met": True},
                ],
                "risks": ["盈利继续下修", "风险偏好恢复缓慢"],
            },
        ],
        "lab": {
            "sample_in": {"cagr": "18.2%", "sharpe": "2.05", "drawdown": "-9%", "win_rate": "64%"},
            "sample_out": {"cagr": "3.1%", "sharpe": "0.28", "drawdown": "-24%", "win_rate": "49%"},
            "diagnosis": "高过拟合风险：样本外 Sharpe 衰减明显，参数排序跨折不稳定。",
        },
    }
