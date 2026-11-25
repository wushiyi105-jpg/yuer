"""离线模式:评估要点、照护建议与风险,结构与模型模式一致。"""

from __future__ import annotations


def offline(r):
    tips, risks = [], []
    if r["months"] is not None:
        if r["months"] < 6:
            tips.append("6 月龄前纯奶,不加辅食不加盐;按需喂,不看钟表看饥饿信号。")
        elif r["months"] < 12:
            tips.append("辅食一次只加一种,连吃 3 天再换;先铁米粉、后菜泥肉泥。")
        else:
            tips.append("三餐与成人同步,奶量保证,少盐少糖,食物切小块防噎。")
        tips.append("每天户外活动 1–2 小时,维生素 D 按医嘱补充。")
    else:
        tips.append("先补月龄,喂养与接种都按月龄走。")
    if r["preterm"]:
        tips.append("早产儿用矫正月龄看发育,别拿足月标准比;定期随访。")
    if r["growth"]:
        tips.append("看趋势不看单点:连续两个月跨两条百分位线才需要紧张。")

    for a in r["alerts"]:
        risks.append(a)
    if r["red_flags"]:
        risks.append("红线:%s,不要在家退热观察,立即就医。" % r["red_flags"][0]["name"])
    else:
        risks.append("3 月龄以下发热、抽搐、呼吸急促、精神差,任一出现立即就医。")
    risks.append("不要自行给成人药或减量成人药;退热药按体重给药,遵医嘱。")
    if r["months"] is not None and r["months"] < 1:
        risks.append("新生儿黄疸加重、拒奶、体温不稳,尽快就诊。")

    summary = "按月龄与测量值给参考区间,重点看趋势"
    if r["growth"]:
        summary += ";本次 %s" % "、".join("%s %s" % (g["metric"], g["bucket"]) for g in r["growth"])
    summary += "。"
    return {"summary": summary, "care_tips": tips[:6], "risks": risks[:6]}
