"""命令行入口:python -m yuer <命令>。"""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__, agent, llm, rules
from . import db as dbmod
from .llm import LLMError

BANNER = ("⚠️  当前为离线模式(未配置 LLM_API_KEY):生长分档、矫正月龄、接种表与喂养区间由本地给出。\n"
          "   填入 LLM_API_KEY 后,评估解释与照护建议由模型撰写(数值仍以本地为准)。\n"
          "   ⚠️  本工具不做诊断,只做参考与分流;异常请面诊儿保医生。\n")


def render(r):
    mode = "模型" if r["mode"] == "model" else "离线模式"
    lines = ["👶 育儿生长评估  [%s]" % mode, "", "📌 " + r["verdict"], ""]
    for n in r["notes"]:
        lines.append("注:" + n)
    if r["notes"]:
        lines.append("")

    lines.append("🔎 基本信息")
    lines.append("  性别:%s  月龄:%s  矫正:%s"
                 % ({"boys": "男", "girls": "女"}.get(r["sex"], "未写"),
                    r["months"] if r["months"] is not None else "—",
                    r["corrected"] if r["corrected"] is not None else "—"))
    lines.append("")

    if r["growth"]:
        lines.append("📏 生长分档(按月龄插值)")
        for g in r["growth"]:
            b = g["band"]
            lines.append("  · %s %s:参考 %s–%s,本次落 %s"
                         % (g["metric"], g["value"], b["P15"], b["P85"], g["bucket"]))
            lines.append("      P3 %s / P15 %s / P50 %s / P85 %s / P97 %s"
                         % (b["P3"], b["P15"], b["P50"], b["P85"], b["P97"]))
        lines.append("")

    lines.append("💉 接种")
    v = r["vaccines"]
    for x in v["due"]:
        lines.append("  ✅ 已到月龄:%s" % x["name"])
    for x in v["next"]:
        lines.append("  ⏭ %d 月龄:%s" % (x["age_months"], x["name"]))
    lines.append("  注:" + v["note"])
    for n in rules.load("milestones.json")["notes"]:
        lines.append("  ⚠ " + n)
    lines.append("")

    if r["feeding"]:
        lines.append("🍼 喂养(%s)" % r["feeding"]["range"])
        lines.append("  " + r["feeding"]["detail"])
        lines.append("")

    if r["red_flags"]:
        lines.append("🚨 红线")
        for f in r["red_flags"]:
            lines.append("  · %s —— %s" % (f["name"], f["why"]))
        lines.append("")
        lines.append("  ⚠️  命中红线,先就医,不要在家观察或自行用药。")
        lines.append("")
    else:
        lines.append("🚨 红线(出现任一条立即就医)")
        for f in rules.load("milestones.json")["red_flags"]:
            lines.append("  · " + f["name"])
        lines.append("")

    if r["summary"]:
        lines.append("🧭 评估")
        lines.append("  " + r["summary"])
        lines.append("")
    if r["care_tips"]:
        lines.append("💡 照护建议")
        for t in r["care_tips"]:
            lines.append("  · " + t)
        lines.append("")
    if r["risks"]:
        lines.append("🚩 注意")
        for t in r["risks"]:
            lines.append("  · " + t)
        lines.append("")

    lines.append("🩺 问诊前准备")
    for q in r["questions"]:
        lines.append("  %s %s —— %s" % ("✅" if q["ok"] else "❌", q["item"], q["question"]))
    return "\n".join(lines)


def _text(args):
    if args.file:
        with open(args.file, encoding="utf-8") as f:
            return f.read()
    if args.text:
        return args.text
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return ""


def cmd_check(args):
    text = _text(args)
    if not text.strip():
        print("❌ 没有描述:用 --text、--file 或管道输入。", file=sys.stderr)
        sys.exit(2)
    db = dbmod.Database(args.db) if args.db else dbmod.Database()
    r = agent.check(text, config=llm.config_from_args(args), db=db, force_mock=args.mock, save=args.save)
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return
    print(render(r))
    if r.get("saved_id"):
        print("\n已入库(#%d),`python -m yuer history` 可回看。" % r["saved_id"])


def cmd_vaccines(args):
    rows = rules.load("milestones.json")["vaccines"]
    print("💉 国家免疫规划(0–24 月)")
    for x in rows:
        print("  %2d 月  %s%s" % (x["age_months"], x["name"], "" if x["free"] else "(自费/部分省)"))
    for n in rules.load("milestones.json")["notes"]:
        print("  ⚠ " + n)


def cmd_feeding(args):
    rows = rules.load("milestones.json")["feeding"]
    print("🍼 按月龄喂养")
    for f in rows:
        print("\n【%s】%s" % (f["range"], f["mode"]))
        print("  " + f["detail"])


def cmd_growth(args):
    if not args.month or not args.sex:
        print("用法:python -m yuer growth --month 8 --sex boys")
        return
    for key, label in (("weight", "体重 kg"), ("height", "身高 cm"), ("head", "头围 cm")):
        b = rules.bands(args.sex, key, args.month)
        print("%s: P3 %s / P15 %s / P50 %s / P85 %s / P97 %s"
              % (label, b["P3"], b["P15"], b["P50"], b["P85"], b["P97"]))


def cmd_history(args):
    rows = dbmod.Database(args.db).latest(args.limit)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    if not rows:
        print("还没有记录。`python -m yuer check --text \"男孩 8个月 体重9kg\" --save` 存一条。")
        return
    print("👶 评估记录")
    for r in rows:
        print("  #%d  %s 月  %s  体重 %s  身高 %s  异常 %s 项  %s"
              % (r["id"], r["months"], r["sex"] or "—", r["weight"] or "—",
                 r["height"] or "—", r["alerts"], r["created_at"]))


def cmd_web(args):
    from . import web
    web.serve(host=args.host, port=args.port, db_path=args.db, force_mock=args.mock)


def build_parser():
    p = argparse.ArgumentParser(prog="yuer", description="育儿 · 生长与喂养参考:百分位、接种、喂养区间,不做诊断。")
    p.add_argument("--version", action="version", version="yuer %s" % __version__)
    p.add_argument("--mock", action="store_true", help="强制离线模式")
    p.add_argument("--json", action="store_true", help="输出原始 JSON")
    p.add_argument("--model", help="覆盖 LLM_MODEL")
    p.add_argument("--base-url", help="覆盖 LLM_BASE_URL")
    p.add_argument("--api-key", help="覆盖 LLM_API_KEY")
    p.add_argument("--db", help="SQLite 路径")
    sub = p.add_subparsers(dest="command", required=True)

    cp = sub.add_parser("check", help="评估一次")
    cp.add_argument("--text", help="描述:性别、月龄、身高体重头围、症状")
    cp.add_argument("--file", help="从文件读")
    cp.add_argument("--save", action="store_true")
    cp.set_defaults(func=cmd_check)

    vp = sub.add_parser("vaccines", help="接种表")
    vp.set_defaults(func=cmd_vaccines)

    fp = sub.add_parser("feeding", help="喂养区间")
    fp.set_defaults(func=cmd_feeding)

    gp = sub.add_parser("growth", help="查某月龄百分位带")
    gp.add_argument("--month", type=int)
    gp.add_argument("--sex", choices=["boys", "girls"])
    gp.set_defaults(func=cmd_growth)

    hp = sub.add_parser("history", help="历史记录")
    hp.add_argument("--limit", type=int, default=10)
    hp.set_defaults(func=cmd_history)

    wp = sub.add_parser("web", help="启动 Web 界面")
    wp.add_argument("--host", default="127.0.0.1")
    wp.add_argument("--port", type=int, default=8000)
    wp.add_argument("--mock", action="store_true", default=argparse.SUPPRESS)
    wp.set_defaults(func=cmd_web)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    if not args.mock and args.command == "check" and not llm.config_from_args(args).get("api_key"):
        print(BANNER, file=sys.stderr)
    try:
        args.func(args)
    except LLMError as e:
        print("❌ %s" % e, file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
