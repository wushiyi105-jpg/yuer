"""自检：配置 / 数据库 / 疫苗表 / 模型 / webhook。"""

from __future__ import annotations

import sqlite3

import httpx

from .config import Settings


def _db(settings: Settings) -> tuple[bool, str]:
    try:
        settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(settings.db_path)
        tables = {
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            if r[0] != "alembic_version"
        }
        conn.close()
    except Exception as exc:  # noqa: BLE001
        return False, f"{settings.db_path} 不可写：{exc}"
    return (True, f"{settings.db_path}（{len(tables)} 张表）") if tables else (False, "还没有表，先跑一次 growth --save")


def _schedule() -> tuple[bool, str]:
    from .domain.rules.vaccine import SCHEDULE

    months = sorted({d.month for d in SCHEDULE})
    return True, f"{len(SCHEDULE)} 剂次，覆盖 {months[0]}–{months[-1]} 月龄（国家免疫规划节选）"


def _llm(settings: Settings) -> tuple[bool, str]:
    if not settings.llm_enabled:
        return True, "未配置 API key，走离线模式"
    try:
        with httpx.Client(timeout=8) as client:
            resp = client.get(
                f"{settings.llm_base_url.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            )
        return resp.status_code < 400, f"{settings.llm_model} · HTTP {resp.status_code}"
    except httpx.HTTPError as exc:
        return False, f"连不上：{exc}"


def _webhook(settings: Settings) -> tuple[bool, str]:
    if not settings.webhook_url:
        return True, "未配置 webhook，跳过推送"
    try:
        with httpx.Client(timeout=8) as client:
            resp = client.post(
                settings.webhook_url, json={"msg_type": "text", "content": {"text": "yuer doctor 探活"}}
            )
        return 200 <= resp.status_code < 300, f"HTTP {resp.status_code}"
    except httpx.HTTPError as exc:
        return False, f"连不上：{exc}"


def run_doctor(settings: Settings) -> list[tuple[str, bool, str]]:
    return [
        ("config", True, f"db={settings.db_path} 提醒提前 {settings.remind_ahead_days} 天"),
        ("database", *_db(settings)),
        ("vaccine", *_schedule()),
        ("llm", *_llm(settings)),
        ("webhook", *_webhook(settings)),
    ]
