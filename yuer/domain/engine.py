"""引擎：一次体检 / 一次接种的状态汇总。"""

from __future__ import annotations

from datetime import date

from .models import Child, Finding, GrowthReport, Measurement, Vaccination
from .rules import percentile as pct
from .rules import vaccine


def evaluate(
    child: Child,
    measurement: Measurement,
    done_codes: set[str],
    today: date | None = None,
) -> GrowthReport:
    today = today or date.today()
    months = vaccine.age_months(child.birth_on, measurement.on)
    report = GrowthReport(child=child, age_months=months)

    table_sex = "boy" if child.sex == "boy" else "girl"

    if measurement.weight_kg is not None:
        p3, p50, p97 = pct.interpolate(pct.WEIGHT[table_sex], months)
        report.weight_percentile = pct.percentile(measurement.weight_kg, p3, p50, p97)
        b = pct.band(report.weight_percentile)
        if b != "normal":
            report.findings.append(
                Finding(
                    rule_id="growth.weight_band",
                    severity="high" if report.weight_percentile < 3 else "warn",
                    message=f"体重处于 P{report.weight_percentile}，{'偏低' if b == 'low' else '偏高'}",
                    evidence=f"{measurement.weight_kg}kg，参考 P3={p3} P50={p50} P97={p97}",
                    suggestion="带上最近三次记录去儿保门诊，看趋势而不是单点",
                )
            )

    if measurement.height_cm is not None:
        p3, p50, p97 = pct.interpolate(pct.HEIGHT[table_sex], months)
        report.height_percentile = pct.percentile(measurement.height_cm, p3, p50, p97)
        if pct.band(report.height_percentile) != "normal":
            report.findings.append(
                Finding(
                    rule_id="growth.height_band",
                    severity="high",
                    message=f"身高处于 P{report.height_percentile}",
                    evidence=f"{measurement.height_cm}cm，参考 P3={p3} P50={p50} P97={p97}",
                    suggestion="同体重，先看趋势",
                )
            )

    missing = vaccine.overdue(done_codes, months)
    soon = vaccine.upcoming(months)
    report.overdue_vaccines = [
        Vaccination(d.code, d.name, d.dose, None) for d in missing
    ]
    report.due_vaccines = [Vaccination(d.code, d.name, d.dose, None) for d in soon]

    for d in missing:
        report.findings.append(
            Finding(
                rule_id="vaccine.overdue",
                severity="warn",
                message=f"{d.name} 第 {d.dose} 剂已过月龄（{d.month} 月龄）",
                evidence=f"当前 {months} 月龄，未见接种记录",
                suggestion="联系接种门诊补种",
            )
        )
    for d in soon:
        plan = vaccine.due_date(child.birth_on, d)
        report.findings.append(
            Finding(
                rule_id="vaccine.upcoming",
                severity="info",
                message=f"{d.name} 第 {d.dose} 剂将在 {plan.isoformat()} 前后接种",
                evidence=f"月龄 {d.month}",
                suggestion="提前一周预约",
            )
        )
    return report
