"""领域模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class Child:
    id: int
    name: str
    birth_on: date
    sex: str  # boy / girl


@dataclass(frozen=True)
class Measurement:
    on: date
    weight_kg: float | None = None
    height_cm: float | None = None


@dataclass(frozen=True)
class Vaccination:
    code: str
    name: str
    dose: int
    done_on: date | None = None


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str
    message: str
    evidence: str
    suggestion: str = ""


@dataclass
class GrowthReport:
    child: Child
    age_months: int
    weight_percentile: float | None = None
    height_percentile: float | None = None
    findings: list[Finding] = field(default_factory=list)
    due_vaccines: list[Vaccination] = field(default_factory=list)
    overdue_vaccines: list[Vaccination] = field(default_factory=list)
