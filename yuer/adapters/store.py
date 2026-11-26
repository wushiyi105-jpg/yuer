"""SQLite：孩子、测量、接种、提醒任务 + Alembic 建表。"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Date, Float, Integer, String, create_engine, inspect, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from ..domain.models import Child, Measurement

MIGRATIONS_DIR = Path(__file__).resolve().parents[2]


class Base(DeclarativeBase):
    pass


class ChildRow(Base):
    __tablename__ = "children"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(60))
    birth_on: Mapped[date] = mapped_column(Date)
    sex: Mapped[str] = mapped_column(String(8), default="boy")


class MeasurementRow(Base):
    __tablename__ = "measurements"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    child_id: Mapped[int] = mapped_column(Integer, index=True)
    on: Mapped[date] = mapped_column(Date)
    weight_kg: Mapped[float | None] = mapped_column(Float, default=None)
    height_cm: Mapped[float | None] = mapped_column(Float, default=None)


class VaccinationRow(Base):
    __tablename__ = "vaccinations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    child_id: Mapped[int] = mapped_column(Integer, index=True)
    code: Mapped[str] = mapped_column(String(20))
    dose: Mapped[int] = mapped_column(Integer, default=1)
    done_on: Mapped[date] = mapped_column(Date)


class JobRow(Base):
    """提醒任务：同类提醒同一天只发一条。"""

    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(80), unique=True)
    kind: Mapped[str] = mapped_column(String(20), default="remind")
    body: Mapped[str] = mapped_column(String, default="")
    created_on: Mapped[date] = mapped_column(Date, default=date.today)


def alembic_config(db_path: Path) -> Config:
    cfg = Config(str(MIGRATIONS_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


def ensure_schema(db_path: Path, engine) -> None:
    tables = set(inspect(engine).get_table_names())
    cfg = alembic_config(db_path)
    if "alembic_version" not in tables:
        if tables:
            command.stamp(cfg, "head")
        else:
            command.upgrade(cfg, "head")
        return
    command.upgrade(cfg, "head")


class Store:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{db_path}", future=True)
        ensure_schema(db_path, self.engine)
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False)

    def add_child(self, name: str, birth_on: date, sex: str) -> int:
        with self.session_factory() as s:
            row = ChildRow(name=name, birth_on=birth_on, sex=sex)
            s.add(row)
            s.commit()
            return row.id

    def children(self) -> list[Child]:
        with self.session_factory() as s:
            rows = s.scalars(select(ChildRow)).all()
            return [Child(id=r.id, name=r.name, birth_on=r.birth_on, sex=r.sex) for r in rows]

    def add_measurement(self, child_id: int, m: Measurement) -> None:
        with self.session_factory() as s:
            s.add(MeasurementRow(child_id=child_id, on=m.on, weight_kg=m.weight_kg, height_cm=m.height_cm))
            s.commit()

    def measurements(self, child_id: int) -> list[Measurement]:
        with self.session_factory() as s:
            rows = s.scalars(
                select(MeasurementRow).where(MeasurementRow.child_id == child_id).order_by(MeasurementRow.on)
            ).all()
            return [Measurement(on=r.on, weight_kg=r.weight_kg, height_cm=r.height_cm) for r in rows]

    def add_vaccination(self, child_id: int, code: str, dose: int, done_on: date) -> None:
        with self.session_factory() as s:
            s.add(VaccinationRow(child_id=child_id, code=code, dose=dose, done_on=done_on))
            s.commit()

    def done_codes(self, child_id: int) -> set[str]:
        with self.session_factory() as s:
            rows = s.scalars(select(VaccinationRow).where(VaccinationRow.child_id == child_id)).all()
            out: set[str] = set()
            for r in rows:
                out.add(f"{r.code}#{r.dose}")
                out.add(r.code)
            return out

    def mark_job(self, key: str, body: str, kind: str = "remind") -> bool:
        with self.session_factory() as s:
            if s.scalar(select(JobRow).where(JobRow.key == key)):
                return False
            s.add(JobRow(key=key, kind=kind, body=body))
            s.commit()
            return True

    def job_keys(self) -> list[str]:
        with self.session_factory() as s:
            return list(s.scalars(select(JobRow.key)).all())
