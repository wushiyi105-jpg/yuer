"""迁移是真的：空库 upgrade 显式建四表，downgrade base 可往返。"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from sqlalchemy import create_engine, inspect

from yuer.adapters.store import alembic_config


def test_upgrade_creates_tables(tmp_path: Path) -> None:
    db = tmp_path / "schema.db"
    command.upgrade(alembic_config(db), "head")
    engine = create_engine(f"sqlite:///{db}")
    names = set(inspect(engine).get_table_names())
    assert {"children", "measurements", "vaccinations", "jobs", "alembic_version"} <= names
    assert {c["name"] for c in inspect(engine).get_columns("measurements")} == {
        "id",
        "child_id",
        "on",
        "weight_kg",
        "height_cm",
    }


def test_downgrade_then_upgrade(tmp_path: Path) -> None:
    cfg = alembic_config(tmp_path / "round.db")
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    engine = create_engine(f"sqlite:///{tmp_path / 'round.db'}")
    assert "children" not in set(inspect(engine).get_table_names())
    command.upgrade(cfg, "head")
    assert "children" in set(inspect(engine).get_table_names())
