"""CLI：Typer + rich。"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from ..adapters.store import Store
from ..config import settings as base_settings
from ..domain.engine import evaluate
from ..domain.models import Child, Measurement
from ..domain.rules import vaccine as vx

app = typer.Typer(add_completion=False, help="yuer —— 育儿成长与疫苗")
console = Console()


def _settings(db: Path | None):
    return base_settings.model_copy(update={"db_path": db}) if db else base_settings


@app.command()
def growth(
    birth: str = typer.Option(..., help="出生日期 YYYY-MM-DD"),
    sex: str = typer.Option("boy", help="boy / girl"),
    weight: float = typer.Option(None, help="体重 kg"),
    height: float = typer.Option(None, help="身高 cm"),
    on: str = typer.Option(None, help="测量日期，默认今天"),
    save: bool = typer.Option(False, "--save"),
    as_json: bool = typer.Option(False, "--json"),
    db: Path = typer.Option(None),
) -> None:
    """算百分位并列出接种状态。"""
    birth_on = date.fromisoformat(birth)
    measured_on = date.fromisoformat(on) if on else date.today()
    child = Child(id=1, name="宝宝", birth_on=birth_on, sex=sex)
    m = Measurement(on=measured_on, weight_kg=weight, height_cm=height)

    store = Store(_settings(db).db_path)
    report = evaluate(child, m, store.done_codes(1), measured_on)
    if save:
        store.add_child(child.name, birth_on, sex)
        store.add_measurement(1, m)

    if as_json:
        console.print_json(json.dumps({
            "age_months": report.age_months,
            "weight_percentile": report.weight_percentile,
            "height_percentile": report.height_percentile,
            "overdue": [f"{v.name} 第{v.dose}剂" for v in report.overdue_vaccines],
            "upcoming": [f"{v.name} 第{v.dose}剂" for v in report.due_vaccines],
        }, ensure_ascii=False))
        return

    console.print(f"[bold]{report.age_months} 月龄[/]")
    if report.weight_percentile is not None:
        console.print(f"体重 P{report.weight_percentile}")
    if report.height_percentile is not None:
        console.print(f"身高 P{report.height_percentile}")
    for f in report.findings:
        color = "red" if f.severity == "high" else "yellow" if f.severity == "warn" else "cyan"
        console.print(f"  · [{color}]{f.rule_id}[/] {f.message}")


@app.command()
def vaccine(
    birth: str = typer.Option(..., help="出生日期"),
    on: str = typer.Option(None, help="查询日期，默认今天"),
    as_json: bool = typer.Option(False, "--json"),
    db: Path = typer.Option(None),
) -> None:
    """按月龄列出待种与逾期。"""
    birth_on = date.fromisoformat(birth)
    today = date.fromisoformat(on) if on else date.today()
    months = vx.age_months(birth_on, today)
    store = Store(_settings(db).db_path)
    done = store.done_codes(1)

    missing = vx.overdue(done, months)
    soon = vx.upcoming(months)
    if as_json:
        console.print_json(json.dumps({
            "age_months": months,
            "overdue": [{"name": d.name, "dose": d.dose, "month": d.month} for d in missing],
            "upcoming": [{"name": d.name, "dose": d.dose, "month": d.month,
                          "plan": vx.due_date(birth_on, d).isoformat()} for d in soon],
        }, ensure_ascii=False))
        return

    table = Table(title=f"{months} 月龄 · 接种计划")
    for col in ("疫苗", "剂次", "月龄", "建议日期"):
        table.add_column(col)
    for d in missing:
        table.add_row(d.name, str(d.dose), str(d.month), "已过")
    for d in soon:
        table.add_row(d.name, str(d.dose), str(d.month), vx.due_date(birth_on, d).isoformat())
    console.print(table)


@app.command()
def mark(
    code: str = typer.Option(..., help="疫苗代码，如 mmr"),
    dose: int = typer.Option(1),
    on: str = typer.Option(None, help="接种日期"),
    db: Path = typer.Option(None),
) -> None:
    """记录一次接种。"""
    store = Store(_settings(db).db_path)
    store.add_vaccination(1, code, dose, date.fromisoformat(on) if on else date.today())
    console.print(f"[green]已记录[/] {code} 第 {dose} 剂")


@app.command()
def note(
    birth: str = typer.Option(..., help="出生日期"),
    sex: str = typer.Option("boy"),
    weight: float = typer.Option(None, help="体重 kg"),
    height: float = typer.Option(None, help="身高 cm"),
    on: str = typer.Option(None, help="测量日期"),
    db: Path = typer.Option(None),
) -> None:
    """给家长看的一段话（过摘要守卫，不出现诊断/用药）。"""
    from ..domain.guard import guard
    from ..domain.summary import care_note

    birth_on = date.fromisoformat(birth)
    measured_on = date.fromisoformat(on) if on else date.today()
    child = Child(id=1, name="宝宝", birth_on=birth_on, sex=sex)
    report = evaluate(child, Measurement(on=measured_on, weight_kg=weight, height_cm=height), set(), measured_on)
    text, dropped = guard(care_note(report))
    console.print(text or "[yellow]整段都被守卫拦下，只保留结论：请带记录去儿保门诊[/]")
    if dropped:
        console.print(f"[yellow]已丢弃 {len(dropped)} 句越界表述[/]")


@app.command()
def remind(db: Path = typer.Option(None), force: bool = typer.Option(False, "--force")) -> None:
    """疫苗提醒：逾期与 7 天内到期，同一天只发一条。"""
    from ..domain.remind import vaccine_reminder

    settings = _settings(db)
    store = Store(settings.db_path)
    children = store.children()
    if not children:
        console.print("[yellow]还没有孩子记录，先跑一次 growth --save[/]")
        return
    done = {c.id: store.done_codes(c.id) for c in children}
    text = vaccine_reminder(children, done, date.today(), settings.remind_ahead_days)
    if not text:
        console.print("[green]今天没有疫苗要提醒[/]")
        return
    key = f"vaccine:{date.today().isoformat()}"
    if not store.mark_job(key, text) and not force:
        console.print(f"[yellow]{key} 已提醒过[/]，加 --force 可重发")
        return
    console.print(text)
    if settings.webhook_url:
        import httpx

        resp = httpx.post(
            settings.webhook_url, json={"msg_type": "text", "content": {"text": text}}, timeout=10
        )
        console.print(f"[dim]webhook HTTP {resp.status_code}[/]")


@app.command()
def export(
    child_id: int = typer.Option(1, help="孩子 id"),
    out: Path = typer.Option(None, "--out", help="CSV 路径，默认打印"),
    db: Path = typer.Option(None),
) -> None:
    """导出测量与接种记录 CSV，给医生看。"""
    import csv
    import io

    store = Store(_settings(db).db_path)
    rows: list[list[str]] = [["日期", "体重kg", "身高cm", "疫苗", "剂次"]]
    for m in store.measurements(child_id):
        rows.append([m.on.isoformat(), str(m.weight_kg or ""), str(m.height_cm or ""), "", ""])
    for code in sorted(store.done_codes(child_id)):
        if "#" not in code:
            continue
        base, dose = code.split("#", 1)
        rows.append(["", "", "", base, dose])
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    if out:
        out.write_text(buf.getvalue(), encoding="utf-8")
        console.print(f"[green]已写出[/] {out}（{len(rows) - 1} 行）")
    else:
        console.print(buf.getvalue())


@app.command()
def migrate(db: Path = typer.Option(None)) -> None:
    """0.x 旧库（checks 表）迁到 1.0，先备份。"""
    from ..adapters.migrate import migrate as run_migrate

    path = _settings(db).db_path
    if not path.exists():
        console.print(f"[red]没有这个库：{path}[/]")
        raise typer.Exit(code=2)
    try:
        result = run_migrate(path)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]迁移失败，原文件未改动[/] {exc}")
        raise typer.Exit(code=2) from exc
    if result["status"] == "current":
        console.print("[green]已是最新 schema[/]")
        return
    console.print(f"[green]{result['status']}[/] 转换 {result['rows']} 行，备份 {result['backup']}")


@app.command()
def doctor(db: Path = typer.Option(None)) -> None:
    """环境自检：配置 / 数据库 / 疫苗表 / 模型 / webhook。"""
    from ..doctor import run_doctor

    bad = 0
    for name, ok, detail in run_doctor(_settings(db)):
        console.print(f"{'[green]ok[/]' if ok else '[red]fail[/]'}  {name:10} {detail}")
        bad += 0 if ok else 1
    raise typer.Exit(code=1 if bad else 0)


@app.command()
def serve(port: int = typer.Option(8000), db: Path = typer.Option(None)) -> None:
    """Web 界面。"""
    import uvicorn

    from .web import app_factory

    uvicorn.run(app_factory(_settings(db)), host="127.0.0.1", port=port)


if __name__ == "__main__":  # pragma: no cover
    app()
