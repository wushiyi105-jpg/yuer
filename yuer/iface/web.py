"""FastAPI + Jinja2。"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..config import Settings
from ..domain.engine import evaluate
from ..domain.models import Child, Measurement
from ..domain.rules import vaccine as vx

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).resolve().parents[2] / "templates"))


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="yuer", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(request, "index.html", {"result": None})

    @app.post("/growth", response_class=HTMLResponse)
    def do_growth(
        request: Request,
        birth: str = Form(...),
        sex: str = Form("boy"),
        weight: str = Form(""),
        height: str = Form(""),
    ) -> HTMLResponse:
        try:
            birth_on = date.fromisoformat(birth)
        except ValueError:
            return HTMLResponse("生日格式不对，用 YYYY-MM-DD", status_code=400)
        today = date.today()
        child = Child(id=1, name="宝宝", birth_on=birth_on, sex=sex)
        m = Measurement(
            on=today,
            weight_kg=float(weight) if weight.strip() else None,
            height_cm=float(height) if height.strip() else None,
        )
        report = evaluate(child, m, set(), today)
        months = vx.age_months(birth_on, today)
        result = {
            "months": months,
            "weight": report.weight_percentile,
            "height": report.height_percentile,
            "findings": [(f.rule_id, f.message) for f in report.findings],
            "vaccines": [
                (d.name, d.dose, vx.due_date(birth_on, d).isoformat()) for d in vx.upcoming(months)
            ],
        }
        return TEMPLATES.TemplateResponse(request, "index.html", {"result": result})

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


def app_factory(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        from ..config import settings as default_settings

        settings = default_settings
    return create_app(settings)
