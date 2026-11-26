"""摘要守卫：育儿文案里不许出现诊断、用药、疑似之类的越界建议，整句丢弃。"""

from __future__ import annotations

import re

BANNED = (
    "诊断",
    "确诊",
    "用药",
    "吃药",
    "处方",
    "剂量",
    "可能是",
    "考虑是",
    "疑似",
    "推荐",
    "换奶粉",
    "停药",
)

_SPLIT = re.compile(r"(?<=[。！？!?\n])")


def guard(text: str) -> tuple[str, list[str]]:
    """返回（保留下来的句子，被丢掉的句子）。"""
    kept: list[str] = []
    dropped: list[str] = []
    for sentence in _SPLIT.split(text):
        s = sentence.strip()
        if not s:
            continue
        if any(word in s for word in BANNED):
            dropped.append(s)
        else:
            kept.append(s)
    return "".join(kept), dropped
