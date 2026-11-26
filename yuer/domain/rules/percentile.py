"""WHO 百分位：节选参考表 + 线性插值。

注意：本表为 0–60 月龄 WHO 生长标准的**节选近似值**，用于趋势判断，
不能替代儿保体检。数据来源标注在 SOURCE 中。
"""

from __future__ import annotations

SOURCE = "WHO Child Growth Standards (2006)，0–60 月龄节选，近似值"

# 月龄 -> (P3, P50, P97)，体重 kg
WEIGHT = {
    "boy": {
        0: (2.5, 3.3, 4.4), 1: (3.4, 4.5, 5.8), 2: (4.3, 5.6, 7.1),
        3: (5.0, 6.4, 8.0), 6: (6.4, 7.9, 9.8), 9: (7.1, 8.9, 10.9),
        12: (7.8, 9.6, 11.8), 18: (8.8, 10.9, 13.5), 24: (9.7, 12.2, 15.3),
        36: (11.3, 14.3, 18.3), 48: (12.7, 16.3, 21.2), 60: (14.1, 18.3, 24.2),
    },
    "girl": {
        0: (2.4, 3.2, 4.2), 1: (3.2, 4.2, 5.5), 2: (3.9, 5.1, 6.6),
        3: (4.5, 5.8, 7.5), 6: (5.7, 7.3, 9.2), 9: (6.5, 8.2, 10.5),
        12: (7.1, 8.9, 11.3), 18: (8.1, 10.2, 13.0), 24: (9.0, 11.5, 14.8),
        36: (10.8, 13.9, 18.1), 48: (12.3, 16.1, 21.5), 60: (13.7, 18.2, 25.0),
    },
}

# 月龄 -> (P3, P50, P97)，身高 cm
HEIGHT = {
    "boy": {
        0: (46.1, 49.9, 53.7), 1: (51.1, 54.7, 58.4), 2: (54.7, 58.4, 62.2),
        3: (57.6, 61.4, 65.3), 6: (63.6, 67.6, 71.6), 9: (67.7, 72.0, 76.2),
        12: (71.3, 75.7, 80.2), 18: (76.9, 82.3, 87.7), 24: (81.7, 87.8, 93.9),
        36: (88.7, 96.1, 103.5), 48: (94.9, 103.3, 111.7), 60: (100.7, 110.0, 119.2),
    },
    "girl": {
        0: (45.4, 49.1, 52.9), 1: (50.0, 53.7, 57.4), 2: (53.2, 57.1, 61.0),
        3: (55.8, 59.8, 63.8), 6: (61.2, 65.7, 70.3), 9: (65.3, 70.1, 75.0),
        12: (68.9, 74.0, 79.2), 18: (74.9, 80.7, 86.5), 24: (80.0, 86.4, 92.9),
        36: (87.4, 95.1, 102.7), 48: (94.1, 102.7, 111.3), 60: (99.9, 109.4, 118.9),
    },
}


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
