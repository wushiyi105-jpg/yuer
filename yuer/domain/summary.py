"""把一次评估拼成一段给家长看的话；所有输出都要过 guard。"""

from __future__ import annotations

from .models import GrowthReport


def care_note(report: GrowthReport) -> str:
    parts: list[str] = [f"{report.child.name}现在 {report.age_months} 月龄。"]
    if report.weight_percentile is not None:
        parts.append(f"体重 P{report.weight_percentile}。")
    if report.height_percentile is not None:
        parts.append(f"身高 P{report.height_percentile}。")
    if not report.findings:
        parts.append("这次测量在正常范围内，疫苗也没有漏种。")
    else:
        for f in report.findings:
            if f.rule_id.startswith("vaccine"):
                parts.append(f"{f.message}。")
            else:
                parts.append(f"{f.message}，单点不代表趋势，连着三次再看。")
        parts.append("带接种本和最近三次记录去儿保门诊，让医生判断。")
    return "".join(parts)
