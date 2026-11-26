"""疫苗计划：按月龄排剂次（国家免疫规划，节选）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .percentile import interpolate  # noqa: F401  （保持模块自洽）


@dataclass(frozen=True)
class Dose:
    code: str
    name: str
    dose: int
    month: int


# 月龄 -> 剂次（国家免疫规划节选；非医疗建议，以接种门诊为准）
SCHEDULE: list[Dose] = [
    Dose("hepb", "乙肝疫苗", 1, 0),
    Dose("bcg", "卡介苗", 1, 0),
    Dose("hepb", "乙肝疫苗", 2, 1),
    Dose("ipv", "脊灰疫苗", 1, 2),
    Dose("ipv", "脊灰疫苗", 2, 3),
    Dose("dtap", "百白破", 1, 3),
    Dose("ipv", "脊灰疫苗", 3, 4),
    Dose("dtap", "百白破", 2, 4),
    Dose("dtap", "百白破", 3, 5),
    Dose("hepb", "乙肝疫苗", 3, 6),
    Dose("mpsv_a", "A 群流脑", 1, 6),
    Dose("mmr", "麻腮风", 1, 8),
    Dose("je", "乙脑", 1, 8),
    Dose("mpsv_a", "A 群流脑", 2, 9),
    Dose("var", "水痘", 1, 12),
    Dose("dtap", "百白破", 4, 18),
    Dose("mmr", "麻腮风", 2, 18),
    Dose("hepa", "甲肝", 1, 18),
    Dose("je", "乙脑", 2, 24),
    Dose("mpsv_ac", "A 群 C 群流脑", 1, 36),
    Dose("ipv", "脊灰疫苗", 4, 48),
    Dose("mpsv_ac", "A 群 C 群流脑", 2, 60),
]


def age_months(birth: date, on: date) -> int:
    months = (on.year - birth.year) * 12 + (on.month - birth.month)
    if on.day < birth.day:
        months -= 1
    return max(months, 0)


def due_by(months: int) -> list[Dose]:
    return [d for d in SCHEDULE if d.month <= months]


def overdue(done_codes: set[str], months: int, grace: int = 0) -> list[Dose]:
    """已过月龄（含宽限）仍未接种的剂次。"""
    out: list[Dose] = []
    for d in SCHEDULE:
        key = f"{d.code}#{d.dose}"
        if d.month + grace <= months and key not in done_codes and d.code not in done_codes:
            out.append(d)
    return out


def upcoming(months: int, window: int = 2) -> list[Dose]:
    """未来 window 个月内要接种的。"""
    return [d for d in SCHEDULE if months < d.month <= months + window]


def due_date(birth: date, dose: Dose) -> date:
    year = birth.year + (birth.month - 1 + dose.month) // 12
    month = (birth.month - 1 + dose.month) % 12 + 1
    day = min(birth.day, 28)
    return date(year, month, day)
