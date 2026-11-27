"""内存假实现跑 save_growth + 导出，全程不建 SQLite 文件。"""

from __future__ import annotations

from datetime import date

from yuer.app.run import export_rows, save_growth
from yuer.domain.models import Child, Measurement
from yuer.ports import StorePort


class FakeStore:
    def __init__(self) -> None:
        self.child_list: list[Child] = []
        self.measures: list[Measurement] = []

    def add_child(self, name: str, birth_on: date, sex: str) -> int:
        self.child_list.append(Child(id=len(self.child_list) + 1, name=name, birth_on=birth_on, sex=sex))
        return len(self.child_list)

    def children(self) -> list[Child]:
        return self.child_list

    def add_measurement(self, child_id: int, m: Measurement) -> None:
        self.measures.append(m)

    def measurements(self, child_id: int) -> list[Measurement]:
        return self.measures

    def add_vaccination(self, child_id: int, code: str, dose: int, done_on: date) -> None:
        return None

    def done_codes(self, child_id: int) -> set[str]:
        return {"mmr#1"}

    def mark_job(self, key: str, body: str, kind: str = "remind") -> bool:
        return True

    def job_keys(self) -> list[str]:
        return []


def test_save_growth_and_export_with_fake_store() -> None:
    store: StorePort = FakeStore()
    child = Child(id=1, name="宝宝", birth_on=date(2025, 1, 1), sex="girl")
    m = Measurement(on=date(2026, 11, 27), weight_kg=12.3, height_cm=88.0)
    cid = save_growth(store, child, m)
    assert cid == 1
    rows = export_rows(store, cid)
    assert rows[1][1] == "12.3"
    assert rows[-1][3] == "mmr"
