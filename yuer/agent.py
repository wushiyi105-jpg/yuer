"""编排:生长百分位、矫正月龄、免疫日历、喂养区间全在本地;模型只写解释与提醒。

红线:不做诊断。模型输出里的月龄、厘米、公斤、温度数字会被剥离,避免与本地评估冲突。
"""

from __future__ import annotations

import re

from . import llm, mock, rules

JSON_ONLY = "只输出 JSON,不要输出解释或多余文字。"
NUM_RE = re.compile(r"\d+(?:\.\d+)?\s*(?:个月|月龄|岁|kg|公斤|斤|cm|厘米|℃|度)")


def _use_model(config, force_mock):
    if force_mock:
        return False
    return bool({**llm.default_config(), **(config or {})}.get("api_key"))


def _cfg(config):
    return {**llm.default_config(), **(config or {})}


def strip_measure(text):
    return NUM_RE.sub("相应数值", text)


def verdict(r):
    parts = []
    if r["months"] is None:
        return "缺月龄,生长与接种都排不了;补「8个月」或「2岁」。"
    head = "%d 月龄" % r["months"]
    if r["corrected"] is not None:
        head += "(矫正 %s 月)" % r["corrected"]
    parts.append(head)
    if r["growth"]:
        worst = [g for g in r["growth"] if g["bucket"] in ("低于 P3", "高于 P97")]
        if worst:
            parts.append("、".join("%s %s" % (g["metric"], g["bucket"]) for g in worst))
        else:
            parts.append("身高体重头围都在常见区间")
    else:
        parts.append("没给身高体重,只能排接种与喂养")
    if r["vaccines"]["next"]:
        parts.append("下一剂:%s" % r["vaccines"]["next"][0]["name"])
    if r["red_flags"]:
        parts.append("命中红线:%s,立即就医" % r["red_flags"][0]["name"])
    return ",".join(parts) + "。"


def _model_advice(r, config):
    rows = "\n".join("- %s %s:%s" % (g["metric"], g["value"], g["bucket"]) for g in r["growth"]) or "无测量值"
    raw = llm.chat([{
        "role": "system",
        "content": ("你是育儿科普助手,不做诊断、不开药。只根据给定的生长分档、接种月龄与喂养区间说话;"
                    "不要写具体月龄、厘米、公斤、温度数字;命中红线一律建议立即就医。"),
    }, {
        "role": "user",
        "content": ("月龄:%s 性别:%s 早产:%s\n生长分档:\n%s\n下一剂疫苗:%s\n喂养:%s\n红线:%s\n%s\n输出格式:"
                    '{"summary":"三句话内的评估要点","care_tips":["喂养/睡眠/发育 3-5 条"],'
                    '"risks":["必须就医或必须避免的事项"]}'
                    % (r["months"], r["sex"], "是" if r["preterm"] else "否", rows,
                       "、".join(v["name"] for v in r["vaccines"]["next"]) or "无",
                       r["feeding"]["detail"] if r["feeding"] else "无",
                       "、".join(f["name"] for f in r["red_flags"]) or "无", JSON_ONLY)),
    }], config=_cfg(config), temperature=0.3, max_tokens=1800)
    d = llm.extract_json(raw)
    return {"summary": strip_measure(str(d.get("summary") or "")),
            "care_tips": [strip_measure(str(x)) for x in d.get("care_tips", [])][:6],
            "risks": [strip_measure(str(x)) for x in d.get("risks", [])][:6]}


def check(text, config=None, db=None, force_mock=False, save=False):
    r = rules.analyze(text)
    r["text"] = text
    if _use_model(config, force_mock):
        layers = _model_advice(r, config)
        mode = "model"
    else:
        layers = mock.offline(r)
        mode = "offline"
    r.update({"verdict": verdict(r), "mode": mode, "saved_id": None, **layers})
    if db is not None and save:
        r["saved_id"] = db.save(r)
    return r
