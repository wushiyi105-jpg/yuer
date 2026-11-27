"""用例：成长评估、接种计划、家长说明、提醒、导出。只认 domain + ports。"""

from __future__ import annotations

from datetime import date

from ..domain.engine import evaluate
from ..domain.guard import guard
from ..domain.models import Child, GrowthReport, Measurement
from ..domain.remind import vaccine_reminder
from ..domain.rules import vaccine as vx
from ..domain.summary import care_note
from ..ports import LLMPort, StorePort

NOTE_PROMPT = (
    "你是育儿记录助手。只根据给定评估事实写 2-3 句给家长看的中文说明，"
    "不给诊断、不推荐用药、不编造数字，最后提醒带记录去儿保门诊。"
)


def growth_report(child: Child, m: Measurement, done: set[str], on: date) -> GrowthReport:
    return evaluate(child, m, done, on)


def save_growth(store: StorePort, child: Child, m: Measurement) -> int:
    child_id = store.add_child(child.name, child.birth_on, child.sex)
    store.add_measurement(child_id, m)
    return child_id


def vaccine_plan(birth_on: date, today: date, done: set[str]) -> tuple[int, list, list]:
    months = vx.age_months(birth_on, today)
    return months, vx.overdue(done, months), vx.upcoming(months)


def mark_vaccine(store: StorePort, child_id: int, code: str, dose: int, done_on: date) -> None:
    store.add_vaccination(child_id, code, dose, done_on)


def guarded_note(report: GrowthReport) -> tuple[str, list[str]]:
    text, dropped = guard(care_note(report))
    return text or "", dropped


def model_note(report: GrowthReport, llm: LLMPort | None = None) -> tuple[str, list[str]]:
    if llm is None:
        return "", []
    try:
        raw = llm.write(NOTE_PROMPT, care_note(report))
    except Exception:  # noqa: BLE001 模型失败回本地说明
        return "", []
    return guard(raw)


def reminder(store: StorePort, today: date, ahead_days: int = 7) -> str:
    children = store.children()
    done = {c.id: store.done_codes(c.id) for c in children}
    return vaccine_reminder(children, done, today, ahead_days) or ""


def export_rows(store: StorePort, child_id: int) -> list[list[str]]:
    rows: list[list[str]] = [["日期", "体重kg", "身高cm", "疫苗", "剂次"]]
    for m in store.measurements(child_id):
        rows.append([m.on.isoformat(), str(m.weight_kg or ""), str(m.height_cm or ""), "", ""])
    for code in sorted(store.done_codes(child_id)):
        if "#" not in code:
            continue
        base, dose = code.split("#", 1)
        rows.append(["", "", "", base, dose])
    return rows
