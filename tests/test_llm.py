from __future__ import annotations

from datetime import date

from yuer.app.run import growth_report, model_note
from yuer.domain.models import Child, Measurement
from yuer.ports import LLMPort


class FakeLLM:
    def write(self, system: str, facts: str) -> str:
        return "宝宝现在 2 月龄。体重在正常范围。带接种本去儿保门诊。"


def test_model_note_uses_llm_text() -> None:
    child = Child(id=1, name="宝宝", birth_on=date(2026, 9, 27), sex="girl")
    report = growth_report(child, Measurement(on=date(2026, 11, 27), weight_kg=5.2), set(), date(2026, 11, 27))
    llm: LLMPort = FakeLLM()
    text, dropped = model_note(report, llm)
    assert text.startswith("宝宝现在 2 月龄")
    assert not dropped


class BannedLLM:
    def write(self, system: str, facts: str) -> str:
        return "建议用药调整。带接种本去儿保门诊。"


def test_model_note_guards_banned_sentence() -> None:
    child = Child(id=1, name="宝宝", birth_on=date(2026, 9, 27), sex="girl")
    report = growth_report(child, Measurement(on=date(2026, 11, 27)), set(), date(2026, 11, 27))
    text, dropped = model_note(report, BannedLLM())
    assert "用药" not in text
    assert dropped
