"""新功能：0–60 月龄表、体检节点、清单与 ICS。"""

from __future__ import annotations

from typer.testing import CliRunner

from yuer.domain.catalog import nodes
from yuer.domain.rules import percentile as pct
from yuer.domain.rules import vaccine
from yuer.iface.cli import app

runner = CliRunner()


def test_who_tables_cover_every_month() -> None:
    assert set(pct.WEIGHT["boy"]) == set(range(61))
    assert set(pct.HEIGHT["girl"]) == set(range(61))
    assert len(pct.WEIGHT["boy"]) == 61


def test_checkup_nodes_and_vaccine_doses() -> None:
    assert len(nodes()) == 11
    assert len(vaccine.SCHEDULE) == 22


def test_percentile_interval_never_single_point() -> None:
    assert pct.interval(50.0) == "P50–P75"
    assert pct.interval(2.0) == "<P3"
    assert pct.interval(99.0) == ">P97"


def test_checkup_writes_md_and_ics(tmp_path) -> None:
    out = tmp_path / "体检清单.md"
    result = runner.invoke(
        app,
        ["checkup", "--birth", "2025-11-27", "--weight", "9.2", "--height", "75", "--out", str(out)],
    )
    assert result.exit_code == 0
    body = out.read_text(encoding="utf-8")
    assert "儿保体检前清单" in body
    assert "所在区间" in body
    assert "疫苗" in body
    ics = out.with_suffix(".ics").read_text(encoding="utf-8")
    assert ics.count("BEGIN:VEVENT") == 22
    assert "VALARM" in ics
