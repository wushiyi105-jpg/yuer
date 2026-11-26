from __future__ import annotations

from datetime import date

from yuer.domain.engine import evaluate
from yuer.domain.models import Child, Measurement
from yuer.domain.rules import percentile as pct
from yuer.domain.rules import vaccine as vx


def test_interpolation_between_months():
    p3, p50, p97 = pct.interpolate(pct.WEIGHT["boy"], 1.5)
    lo, hi = pct.WEIGHT["boy"][1], pct.WEIGHT["boy"][2]
    assert lo[1] < p50 < hi[1]
    assert lo[0] < p3 < hi[0]


def test_interpolation_clamps_outside_range():
    assert pct.interpolate(pct.WEIGHT["boy"], -3) == pct.WEIGHT["boy"][0]
    assert pct.interpolate(pct.WEIGHT["boy"], 999) == pct.WEIGHT["boy"][60]


def test_percentile_midpoint_is_50():
    assert pct.percentile(7.9, 6.4, 7.9, 9.8) == 50.0


def test_percentile_below_p3_is_low_band():
    assert pct.band(pct.percentile(5.0, 6.4, 7.9, 9.8)) == "low"


def test_percentile_above_p97_is_high_band():
    assert pct.band(pct.percentile(12.0, 6.4, 7.9, 9.8)) == "high"


def test_age_months_handles_day_not_reached():
    birth = date(2025, 11, 20)
    assert vx.age_months(birth, date(2026, 11, 19)) == 11
    assert vx.age_months(birth, date(2026, 11, 20)) == 12


def test_due_date_wraps_year():
    birth = date(2025, 11, 20)
    dose = vx.Dose("mmr", "麻腮风", 1, 8)
    assert vx.due_date(birth, dose) == date(2026, 7, 20)


def test_overdue_respects_done_and_grace():
    done = {"hepb#1", "hepb#2", "hepb#3", "bcg#1"}
    missing = vx.overdue(done, months=6, grace=0)
    assert all(not m.code.startswith("hepb") for m in missing)
    assert not any(m.code == "bcg" for m in missing)
    assert any(m.code == "dtap" for m in missing)


def test_upcoming_window():
    soon = vx.upcoming(6, window=2)
    assert all(6 < d.month <= 8 for d in soon)


def test_engine_flags_low_weight():
    child = Child(id=1, name="宝宝", birth_on=date(2025, 11, 27), sex="boy")
    m = Measurement(on=date(2026, 11, 27), weight_kg=6.0, height_cm=72.0)
    report = evaluate(child, m, set(), date(2026, 11, 27))
    assert any(f.rule_id == "growth.weight_band" for f in report.findings)


def test_engine_lists_overdue_vaccines():
    child = Child(id=1, name="宝宝", birth_on=date(2025, 11, 27), sex="boy")
    m = Measurement(on=date(2026, 11, 27), weight_kg=9.6)
    report = evaluate(child, m, set(), date(2026, 11, 27))
    assert report.overdue_vaccines
    assert any(f.rule_id == "vaccine.overdue" for f in report.findings)


def test_no_findings_for_normal_values():
    child = Child(id=1, name="宝宝", birth_on=date(2025, 11, 27), sex="boy")
    m = Measurement(on=date(2026, 11, 27), weight_kg=9.6, height_cm=75.7)
    report = evaluate(child, m, {"mmr#1"}, date(2026, 11, 27))
    growth = [f for f in report.findings if f.rule_id.startswith("growth.")]
    assert growth == []
