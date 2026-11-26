from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from yuer.adapters.migrate import migrate
from yuer.adapters.store import Store
from yuer.config import Settings
from yuer.doctor import run_doctor
from yuer.domain.engine import evaluate
from yuer.domain.guard import guard
from yuer.domain.models import Child, Measurement
from yuer.domain.remind import vaccine_reminder
from yuer.domain.summary import care_note
from yuer.iface.cli import app
from yuer.iface.web import create_app

runner = CliRunner()
TODAY = date(2026, 11, 27)


def test_guard_drops_medical_advice():
    text, dropped = guard("体重偏轻。可能是吸收问题，建议用药。记得预约门诊。")
    assert "可能是" not in text and "用药" not in text
    assert len(dropped) == 1
    assert "记得预约门诊" in text


def test_care_note_has_no_banned_words():
    report = evaluate(Child(1, "宝宝", date(2025, 11, 1), "boy"), Measurement(TODAY, 8.2, 72.0), set(), TODAY)
    text, dropped = guard(care_note(report))
    assert text
    assert not dropped


def test_vaccine_reminder_lists_overdue_and_upcoming():
    child = Child(1, "宝宝", date(2026, 9, 1), "boy")  # 2 月龄
    text = vaccine_reminder([child], {1: {"hepb#1", "bcg", "hepb#2"}}, TODAY, ahead_days=7)
    assert text and "逾期" in text
    assert vaccine_reminder([child], {1: set()}, TODAY, ahead_days=0) is not None


def test_remind_once_and_force(tmp_path):
    db = str(tmp_path / "r.db")
    runner.invoke(app, ["growth", "--birth", "2026-09-01", "--weight", "5.6", "--height", "58", "--save", "--db", db])
    first = runner.invoke(app, ["remind", "--db", db])
    second = runner.invoke(app, ["remind", "--db", db])
    assert first.exit_code == 0
    assert "已提醒过" in second.stdout
    forced = runner.invoke(app, ["remind", "--force", "--db", db])
    assert forced.exit_code == 0


def test_export_csv(tmp_path):
    db = str(tmp_path / "e.db")
    runner.invoke(app, ["growth", "--birth", "2026-01-01", "--weight", "9.5", "--save", "--db", db])
    runner.invoke(app, ["mark", "--code", "mmr", "--dose", "1", "--db", db])
    out = tmp_path / "records.csv"
    result = runner.invoke(app, ["export", "--out", str(out), "--db", db])
    assert result.exit_code == 0
    body = out.read_text(encoding="utf-8")
    assert body.startswith("日期")
    assert "mmr" in body


def test_export_prints_when_no_out(tmp_path):
    db = str(tmp_path / "p.db")
    runner.invoke(app, ["growth", "--birth", "2026-01-01", "--weight", "9.5", "--save", "--db", db])
    result = runner.invoke(app, ["export", "--db", db])
    assert "体重kg" in result.stdout


def test_migrate_legacy_checks(tmp_path):
    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE checks (id INTEGER PRIMARY KEY, months INTEGER, sex TEXT, weight REAL,"
        " height REAL, alerts INTEGER, detail TEXT, created_at TEXT)"
    )
    conn.execute(
        "INSERT INTO checks (months, sex, weight, height, alerts, detail, created_at)"
        " VALUES (6, 'girl', 7.2, 66, 1, ?, '2026-11-20 10:00:00')",
        (json.dumps({"rule": "x"}),),
    )
    conn.commit()
    conn.close()
    result = migrate(db)
    assert result["status"] == "converted"
    assert result["rows"] == 1
    store = Store(db)
    child = store.children()[0]
    assert child.sex == "girl"
    assert store.measurements(child.id)[0].weight_kg == 7.2


def test_migrate_unknown_schema(tmp_path):
    db = tmp_path / "odd.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE nope (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()
    with pytest.raises(ValueError):
        migrate(db)


def test_migrate_current_and_missing(tmp_path):
    db = tmp_path / "new.db"
    Store(db).children()
    assert migrate(db)["status"] == "current"
    assert migrate(tmp_path / "absent.db")["status"] == "created"


def test_migrate_missing_exit_2(tmp_path):
    result = runner.invoke(app, ["migrate", "--db", str(tmp_path / "none.db")])
    assert result.exit_code == 2


def test_doctor_offline(tmp_path):
    settings = Settings(db_path=Path(tmp_path) / "doc.db", llm_api_key="", webhook_url="")
    checks = {n: (ok, d) for n, ok, d in run_doctor(settings)}
    assert checks["vaccine"][0] is True
    assert "剂次" in checks["vaccine"][1]
    assert "离线模式" in checks["llm"][1]
    assert "跳过" in checks["webhook"][1]


def test_doctor_cli_ok_after_save(tmp_path):
    db = str(tmp_path / "ok.db")
    runner.invoke(app, ["growth", "--birth", "2026-09-01", "--weight", "6", "--save", "--db", db])
    result = runner.invoke(app, ["doctor", "--db", db])
    assert result.exit_code == 0


def test_note_cli_prints_safe_text(tmp_path):
    result = runner.invoke(
        app, ["note", "--birth", "2026-09-01", "--weight", "5.2", "--db", str(tmp_path / "n.db")]
    )
    assert result.exit_code == 0
    assert "月龄" in result.stdout


def test_web_growth_and_health(tmp_path):
    settings = Settings(db_path=Path(tmp_path) / "web.db", llm_api_key="")
    client = TestClient(create_app(settings))
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/").status_code == 200
    resp = client.post("/growth", data={"birth": "2026-09-01", "sex": "boy", "weight": "5.6", "height": "58"})
    assert resp.status_code == 200


def test_web_bad_birth_is_400(tmp_path):
    settings = Settings(db_path=Path(tmp_path) / "bad.db", llm_api_key="")
    client = TestClient(create_app(settings))
    resp = client.post("/growth", data={"birth": "2025/11/27", "sex": "boy", "weight": "9.6"})
    assert resp.status_code == 400


def test_store_jobs_idempotent(tmp_path):
    store = Store(tmp_path / "j.db")
    assert store.mark_job("vaccine:2026-11-27", "a") is True
    assert store.mark_job("vaccine:2026-11-27", "b") is False
    assert store.job_keys() == ["vaccine:2026-11-27"]
