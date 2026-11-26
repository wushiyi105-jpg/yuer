"""疫苗提醒：逾期未种 + 临期（默认提前 7 天）。纯函数。"""

from __future__ import annotations

from datetime import date

from .models import Child
from .rules import vaccine as vx


def vaccine_reminder(
    children: list[Child],
    done_by_child: dict[int, set[str]],
    today: date,
    ahead_days: int = 7,
) -> str | None:
    lines: list[str] = []
    for child in children:
        months = vx.age_months(child.birth_on, today)
        done = done_by_child.get(child.id, set())
        missing = vx.overdue(done, months)
        soon = [
            d
            for d in vx.upcoming(months, window=2)
            if 0 <= (vx.due_date(child.birth_on, d) - today).days <= ahead_days
        ]
        if not missing and not soon:
            continue
        lines.append(f"{child.name}（{months} 月龄）")
        for d in missing:
            lines.append(f"- 逾期：{d.name} 第 {d.dose} 剂（{d.month} 月龄）")
        for d in soon:
            lines.append(f"- {ahead_days} 天内：{d.name} 第 {d.dose} 剂，{vx.due_date(child.birth_on, d)}")
    if not lines:
        return None
    return f"{today.isoformat()} 疫苗提醒\n" + "\n".join(lines)
