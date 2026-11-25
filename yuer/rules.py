"""育儿本地规则:生长百分位带、早产矫正、免疫日历、喂养区间、红线与问诊清单。"""

import json
import os
import re

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
AGE_M_RE = re.compile(r"(\d+)\s*个?月")
AGE_Y_RE = re.compile(r"(\d+(?:\.\d+)?)\s*岁")
WEIGHT_RE = re.compile(r"体重\s*(\d+(?:\.\d+)?)\s*(kg|公斤|斤)")
HEIGHT_RE = re.compile(r"(?:身高|身长)\s*(\d+(?:\.\d+)?)\s*(cm|厘米)")
HEAD_RE = re.compile(r"头围\s*(\d+(?:\.\d+)?)\s*(cm|厘米)")
WEEK_RE = re.compile(r"(\d+)\s*周")
SIMPLE_KG_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(kg|公斤)")


def load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


def sex(text):
    low = text or ""
    for key, words in (("boys", ["男孩", "男宝", "儿子", "男"]), ("girls", ["女孩", "女宝", "女儿", "女"])):
        if any(w in low for w in words):
            return key
    return None


def age_months(text):
    m = AGE_M_RE.search(text or "")
    if m:
        return int(m.group(1))
    m = AGE_Y_RE.search(text or "")
    if m:
        return int(float(m.group(1)) * 12)
    return None


def measure(text):
    out = {}
    m = WEIGHT_RE.search(text or "") or SIMPLE_KG_RE.search(text or "")
    if m:
        v = float(m.group(1))
        out["weight"] = round(v / 2, 2) if m.group(2) == "斤" else v
    for key, regex in (("height", HEIGHT_RE), ("head", HEAD_RE)):
        m = regex.search(text or "")
        if m:
            out[key] = float(m.group(1))
    return out


def preterm(text):
    if "早产" not in (text or "") and "孕周" not in (text or ""):
        return None
    m = WEEK_RE.search(text or "")
    weeks = int(m.group(1)) if m else 36
    if weeks >= 37:
        return None
    return {"weeks": weeks, "correction": round((40 - weeks) / 4, 1)}


def corrected_age(months, pre):
    if months is None or not pre:
        return None
    return round(max(0, months - pre["correction"]), 1)


def interpolate(sex_key, metric, month):
    g = load("growth.json")
    months = g["months"]
    values = g[sex_key][metric]
    if month <= months[0]:
        return values[0]
    if month >= months[-1]:
        return values[-1]
    for i in range(len(months) - 1):
        if months[i] <= month <= months[i + 1]:
            span = months[i + 1] - months[i]
            ratio = (month - months[i]) / span
            return round(values[i] + (values[i + 1] - values[i]) * ratio, 1)
    return values[-1]


def bands(sex_key, metric, month):
    med = interpolate(sex_key, metric, month)
    factors = load("growth.json")["factors"][metric]
    return {k: round(med * f, 1) for k, f in factors.items()} | {"P50": med}


def classify(value, band):
    if value < band["P3"]:
        return "低于 P3"
    if value < band["P15"]:
        return "P3–P15"
    if value <= band["P85"]:
        return "P15–P85(常见区间)"
    if value <= band["P97"]:
        return "P85–P97"
    return "高于 P97"


def growth_assess(text, sex_key, months, pre):
    used_month = corrected_age(months, pre) or months
    got = measure(text)
    rows, alerts = [], []
    for key, label in (("weight", "体重"), ("height", "身高/身长"), ("head", "头围")):
        if key not in got or used_month is None or sex_key is None:
            continue
        band = bands(sex_key, key, used_month)
        bucket = classify(got[key], band)
        rows.append({"metric": label, "value": got[key], "band": band, "bucket": bucket})
        if bucket in ("低于 P3", "高于 P97"):
            alerts.append("%s %s 落在 %s,建议儿保面诊评估" % (label, got[key], bucket))
    return rows, alerts


def vaccines(months):
    v = load("milestones.json")["vaccines"]
    if months is None:
        return {"due": [], "next": [], "note": "缺月龄,排不出接种表"}
    due = [x for x in v if x["age_months"] <= months]
    nxt = [x for x in v if x["age_months"] > months][:3]
    return {"due": due[-4:], "next": nxt,
            "note": "已到月龄共 %d 剂,下面列最近 4 剂与接下来 3 剂" % len(due)}


def feeding(months):
    if months is None:
        return None
    for f in load("milestones.json")["feeding"]:
        lo, hi = (int(x) for x in re.findall(r"\d+", f["range"]))
        if lo <= months <= hi:
            return f
    return None


def red_flags(text, months=None):
    low = text or ""
    out = []
    for r in load("milestones.json")["red_flags"]:
        if "发热" in r["name"]:
            if months is not None and months >= 3:
                continue
            if not any(k in low for k in ("发烧", "发热", "38")):
                continue
            out.append(r)
        elif any(k in low for k in r["keywords"]):
            out.append(r)
    return out


def questions(text):
    base = [
        ("体温", "测过体温吗?多少度、用什么测的", ["度", "体温", "发热", "发烧"]),
        ("精神", "清醒时能不能逗笑、眼神是否追人", ["精神", "逗", "笑", "嗜睡"]),
        ("吃奶/吃饭", "近 24 小时吃了几次、每次大概多少", ["吃奶", "吃", "奶量", "拒食"]),
        ("尿量", "近 24 小时换了几次尿布、尿色深浅", ["尿", "尿布", "尿量"]),
        ("持续时间", "什么时候开始、有没有加重", ["小时", "天", "开始", "昨天", "今天"]),
    ]
    return [{"item": k, "question": q, "ok": any(w in (text or "") for w in words)} for k, q, words in base]


def analyze(text):
    sp = sex(text)
    months = age_months(text)
    pre = preterm(text)
    corr = corrected_age(months, pre)
    rows, alerts = growth_assess(text, sp, months, pre)
    v = vaccines(months)
    feed = feeding(months)
    notes = []
    if sp is None:
        notes.append("没写性别,百分位带按男孩估;补「男孩/女孩」")
    if months is None:
        notes.append("没写月龄,生长与接种都排不了;补「8个月」或「2岁」")
    if pre:
        notes.append("早产儿按矫正月龄评估:矫正 %s 个月(孕 %d 周)" % (corr, pre["weeks"]))
    return {"sex": sp, "months": months, "preterm": pre, "corrected": corr,
            "growth": rows, "alerts": alerts, "vaccines": v, "feeding": feed,
            "red_flags": red_flags(text, months), "questions": questions(text), "notes": notes}
