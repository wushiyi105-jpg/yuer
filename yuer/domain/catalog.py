"""本地育儿知识：体检节点与问题清单。"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA = Path(__file__).resolve().parents[2] / "data"


@lru_cache(maxsize=1)
def nodes() -> list[dict[str, Any]]:
    return list(json.loads((DATA / "checkup_nodes.json").read_text(encoding="utf-8"))["nodes"])


def node_at(months: int) -> dict[str, Any]:
    """取当前月龄对应的体检节点；超过 60 月龄用最后一个。"""
    chosen = nodes()[0]
    for node in nodes():
        if int(node["month"]) <= months:
            chosen = node
        else:
            break
    return chosen


def next_node(months: int) -> dict[str, Any] | None:
    for node in nodes():
        if int(node["month"]) > months:
            return node
    return None
