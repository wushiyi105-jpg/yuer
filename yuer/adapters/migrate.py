"""0.x → 1.0：旧库 checks 表转成 children + measurements，先备份。"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from .store import ChildRow, MeasurementRow, Store


def _backup(db_path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = db_path.with_name(f"{db_path.stem}.bak-{stamp}.db")
    backup.write_bytes(db_path.read_bytes())
    return backup


def _parse_day(value: Any) -> date | None:
    if not value:
        return None
    text = str(value).strip()[:10]
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def migrate(db_path: Path) -> dict[str, Any]:
    if not db_path.exists():
        Store(db_path)
        return {"status": "created", "backup": None, "rows": 0}

    backup = _backup(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "alembic_version" in tables and "children" in tables:
            return {"status": "current", "backup": str(backup), "rows": 0}
        if "checks" not in tables:
            raise ValueError("库里有未知表结构，未改动原文件")
        checks = conn.execute("SELECT * FROM checks ORDER BY id").fetchall()
    finally:
        conn.close()

    tmp = db_path.with_name(db_path.stem + ".migrating.db")
    if tmp.exists():
        tmp.unlink()
    try:
        store = Store(tmp)
        with store.session_factory() as s:
            sex = (checks[0]["sex"] if checks else "boy") or "boy"
            first_on = _parse_day(checks[0]["created_at"]) if checks else date.today()
            months = int(checks[0]["months"] or 0) if checks else 0
            birth = (first_on or date.today()) - timedelta(days=int(months * 30.44))
            child = ChildRow(name="宝宝", birth_on=birth, sex=sex)
            s.add(child)
            s.flush()
            for c in checks:
                on = _parse_day(c["created_at"])
                if not on:
                    continue
                s.add(
                    MeasurementRow(
                        child_id=child.id,
                        on=on,
                        weight_kg=float(c["weight"]) if c["weight"] is not None else None,
                        height_cm=float(c["height"]) if c["height"] is not None else None,
                    )
                )
            s.commit()
        store.engine.dispose()
        tmp.replace(db_path)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise
    detail_note = json.dumps({"source": "checks"}, ensure_ascii=False)
    return {
        "status": "converted",
        "backup": str(backup),
        "rows": len(checks),
        "note": detail_note,
    }
