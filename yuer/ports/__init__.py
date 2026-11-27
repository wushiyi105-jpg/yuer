"""端口：成长记录 / 接种记录 / 提醒任务。"""

from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

from ..domain.models import Child, Measurement


@runtime_checkable
class StorePort(Protocol):
    def add_child(self, name: str, birth_on: date, sex: str) -> int: ...

    def children(self) -> list[Child]: ...

    def add_measurement(self, child_id: int, m: Measurement) -> None: ...

    def measurements(self, child_id: int) -> list[Measurement]: ...

    def add_vaccination(self, child_id: int, code: str, dose: int, done_on: date) -> None: ...

    def done_codes(self, child_id: int) -> set[str]: ...

    def mark_job(self, key: str, body: str, kind: str = "remind") -> bool: ...

    def job_keys(self) -> list[str]: ...
