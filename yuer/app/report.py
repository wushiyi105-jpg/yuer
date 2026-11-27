"""体检前清单 + 疫苗日历 ICS：一次成文，家长直接带走。"""

from __future__ import annotations

from datetime import date

from ..domain.catalog import next_node, node_at
from ..domain.models import GrowthReport, Measurement
from ..domain.rules import percentile as pct
from ..domain.rules import vaccine


def _ics_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def vaccine_ics(child_name: str, birth_on: date, stamp: date | None = None) -> str:
    now = stamp or date.today()
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//yuer//vaccine-calendar//CN",
        "CALSCALE:GREGORIAN",
        "X-WR-CALNAME:疫苗接种",
    ]
    for d in vaccine.SCHEDULE:
        due = vaccine.due_date(birth_on, d)
        uid = f"yuer-{birth_on.isoformat()}-{d.code}-{d.dose}@local"
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{now.strftime('%Y%m%d')}T000000Z",
            f"DTSTART;VALUE=DATE:{due.strftime('%Y%m%d')}",
            f"SUMMARY:{_ics_escape(f'{child_name} · {d.name} 第{d.dose}剂')}",
            f"DESCRIPTION:{_ics_escape(f'{d.month} 月龄；以接种门诊安排为准')}",
            "BEGIN:VALARM",
            "TRIGGER:-P7D",
            "ACTION:DISPLAY",
            f"DESCRIPTION:{_ics_escape('提前一周预约接种')}",
            "END:VALARM",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def _trend(rows: list[Measurement], attr: str, unit: str) -> str:
    values = {m.on: getattr(m, attr) for m in rows if getattr(m, attr) is not None}
    vals = sorted(values.items())[-3:]
    if len(vals) < 3:
        return f"只有 {len(vals)} 次{unit}记录，至少 3 次再看趋势"
    seq = " → ".join(f"{v:.1f}" for _, v in vals)
    delta = vals[-1][1] - vals[0][1]
    arrow = "↑" if delta > 0 else "↓" if delta < 0 else "→"
    return f"{seq} {unit}（{arrow} {abs(delta):.1f}）"


def build_checkup(
    report: GrowthReport,
    history: list[Measurement],
    on: date,
    child_name: str = "宝宝",
) -> str:
    months = report.age_months
    node = node_at(months)
    nxt = next_node(months)

    lines = [
        f"# {child_name} 儿保体检前清单 · {on.isoformat()}",
        "",
        f"> 当前 **{months} 月龄**；对应体检节点：**{node['name']}**（{node['focus']}）。"
        f"下一个节点：{nxt['name'] if nxt else '已覆盖到 5 岁，按年度体检'}。",
        "",
        "## 一、这次量了什么",
        "",
        "| 项目 | 本次 | 所在区间 | 说明 |",
        "| --- | ---: | --- | --- |",
    ]
    if report.weight_percentile is not None:
        latest = next((m.weight_kg for m in reversed(history) if m.weight_kg is not None), None)
        lines.append(
            f"| 体重 | {latest if latest is not None else '未记录'} kg | "
            f"{pct.interval(report.weight_percentile)} | 百分位是区间，不是精确排名 |"
        )
    if report.height_percentile is not None:
        latest = next((m.height_cm for m in reversed(history) if m.height_cm is not None), None)
        lines.append(
            f"| 身高 | {latest if latest is not None else '未记录'} cm | "
            f"{pct.interval(report.height_percentile)} | 单点不说明问题，看趋势 |"
        )
    if report.weight_percentile is None and report.height_percentile is None:
        lines.append("| - | 未填 | - | 这次没有身高体重数据 |")
    lines += ["", "## 二、最近三次趋势", ""]
    lines.append(f"- 体重：{_trend(history, 'weight_kg', 'kg')}")
    lines.append(f"- 身高：{_trend(history, 'height_cm', 'cm')}")
    lines += ["", "## 三、疫苗：这次要问清楚", ""]
    if report.overdue_vaccines:
        overdue_text = "、".join(f"{v.name}第{v.dose}剂" for v in report.overdue_vaccines)
        lines.append(f"- **已过月龄未见记录**：{overdue_text}。问接种门诊怎么补、要不要重新开始。")
    if report.due_vaccines:
        soon_text = "、".join(f"{v.name}第{v.dose}剂" for v in report.due_vaccines)
        lines.append(f"- **未来 2 个月**：{soon_text}。问能否和这次体检同一天接种。")
    lines += [
        "- 问：这次补种和下一针要间隔多久？",
        "- 问：接种后出现发热，什么温度需要来医院？",
        "- 问：有没有自费疫苗建议补？为什么？",
        "",
        f"## 四、{node['name']}要问医生的问题",
        "",
    ]
    for i, q in enumerate(node["questions"], 1):
        lines.append(f"{i}. {q}")
    lines += [
        "",
        "## 五、今天带什么",
        "",
        "- 接种本（或电子接种记录）",
        "- 最近三次身高体重记录（没有就现场量）",
        "- 正在吃的药、过敏史、上次就诊记录",
        "- 想问的问题，按顺序写，别到诊室就忘",
        "",
        "---",
        "",
        "说明：百分位来自本地 WHO 0–60 月龄表，给区间不给单点；"
        "本清单不构成诊断，疫苗安排以接种门诊为准。",
        "",
    ]
    return "\n".join(lines)
