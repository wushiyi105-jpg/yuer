"""WHO 百分位：节选参考表 + 线性插值。

注意：本表为 0–60 月龄 WHO 生长标准的**节选近似值**，用于趋势判断，
不能替代儿保体检。数据来源标注在 SOURCE 中。
"""

from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[3] / "data" / "who_growth.json"
_RAW = json.loads(DATA.read_text(encoding="utf-8"))
SOURCE = str(_RAW["source"])


def _table(group: str, sex: str) -> dict[int, tuple[float, float, float]]:
    return {int(month): tuple(row) for month, row in _RAW[group][sex].items()}


# 0–60 月龄逐月表，体重 kg / 身高 cm，每项为 (P3, P50, P97)
WEIGHT = {sex: _table("weight", sex) for sex in ("boy", "girl")}
HEIGHT = {sex: _table("height", sex) for sex in ("boy", "girl")}


def interpolate(table: dict[int, tuple[float, float, float]], months: float) -> tuple[float, float, float]:
    keys = sorted(table)
    if months <= keys[0]:
        return table[keys[0]]
    if months >= keys[-1]:
        return table[keys[-1]]
    for lo, hi in zip(keys, keys[1:]):
        if lo <= months <= hi:
            ratio = (months - lo) / (hi - lo)
            a, b = table[lo], table[hi]
            return tuple(a[i] + (b[i] - a[i]) * ratio for i in range(3))  # type: ignore[return-value]
    return table[keys[-1]]


def percentile(value: float, p3: float, p50: float, p97: float) -> float:
    """把数值映射到粗略百分位：P3=3 / P50=50 / P97=97，两侧线性外推并夹到 [0.5, 99.5]。"""
    if value <= p3:
        span = max(p50 - p3, 1e-6)
        pct = 3 - (p3 - value) / span * 47
    elif value <= p50:
        pct = 3 + (value - p3) / max(p50 - p3, 1e-6) * 47
    elif value <= p97:
        pct = 50 + (value - p50) / max(p97 - p50, 1e-6) * 47
    else:
        pct = 97 + (value - p97) / max(p97 - p50, 1e-6) * 2.5
    return round(min(max(pct, 0.5), 99.5), 1)


def band(pct: float) -> str:
    if pct < 3:
        return "low"
    if pct > 97:
        return "high"
    return "normal"


def interval(pct: float) -> str:
    """给区间，不给单点：P25–P50 这种，避免家长盯一个数。"""
    edges = [3, 10, 25, 50, 75, 90, 97]
    if pct < edges[0]:
        return "<P3"
    if pct > edges[-1]:
        return ">P97"
    for lo, hi in zip(edges, edges[1:]):
        if lo <= pct < hi:
            return f"P{lo}–P{hi}"
    return f"P{edges[-2]}–P{edges[-1]}"
