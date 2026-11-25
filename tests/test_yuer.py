import unittest

from yuer import agent, rules


def baby():
    return "男孩,8个月,体重9kg,身高70cm,头围45cm,最近有点发烧"


class TestParse(unittest.TestCase):
    def test_sex_boy(self):
        self.assertEqual(rules.sex("男孩 8个月"), "boys")

    def test_sex_girl(self):
        self.assertEqual(rules.sex("女孩 1岁"), "girls")

    def test_sex_none(self):
        self.assertIsNone(rules.sex("8个月 9kg"))

    def test_age_months(self):
        self.assertEqual(rules.age_months("8个月"), 8)

    def test_age_years(self):
        self.assertEqual(rules.age_months("2岁"), 24)

    def test_measure_all(self):
        got = rules.measure(baby())
        self.assertEqual(got["weight"], 9.0)
        self.assertEqual(got["height"], 70.0)
        self.assertEqual(got["head"], 45.0)

    def test_weight_jin(self):
        self.assertEqual(rules.measure("体重18斤")["weight"], 9.0)


class TestPreterm(unittest.TestCase):
    def test_32_weeks(self):
        p = rules.preterm("早产 32周")
        self.assertEqual(p["weeks"], 32)
        self.assertEqual(p["correction"], 2.0)

    def test_term(self):
        self.assertIsNone(rules.preterm("39周出生"))

    def test_no_mention(self):
        self.assertIsNone(rules.preterm("8个月"))

    def test_corrected(self):
        self.assertEqual(rules.corrected_age(8, {"correction": 2.0}), 6.0)


class TestGrowth(unittest.TestCase):
    def test_interpolate_mid(self):
        self.assertAlmostEqual(rules.interpolate("boys", "weight", 8), 8.6, places=1)

    def test_interpolate_anchor(self):
        self.assertEqual(rules.interpolate("girls", "height", 12), 74.0)

    def test_interpolate_edges(self):
        self.assertEqual(rules.interpolate("boys", "weight", 0), 3.3)
        self.assertEqual(rules.interpolate("boys", "weight", 30), 12.2)

    def test_bands_order(self):
        b = rules.bands("boys", "weight", 8)
        self.assertLess(b["P3"], b["P15"])
        self.assertLess(b["P15"], b["P50"])
        self.assertLess(b["P50"], b["P85"])
        self.assertLess(b["P85"], b["P97"])

    def test_classify_common(self):
        b = rules.bands("boys", "weight", 8)
        self.assertEqual(rules.classify(9.0, b), "P15–P85(常见区间)")

    def test_classify_low(self):
        b = rules.bands("boys", "weight", 8)
        self.assertEqual(rules.classify(6.0, b), "低于 P3")

    def test_classify_high(self):
        b = rules.bands("boys", "weight", 8)
        self.assertEqual(rules.classify(12.0, b), "高于 P97")

    def test_growth_rows(self):
        rows, alerts = rules.growth_assess(baby(), "boys", 8, None)
        self.assertEqual(len(rows), 3)
        self.assertEqual(alerts, [])

    def test_growth_alert(self):
        rows, alerts = rules.growth_assess("男孩 8个月 体重6kg", "boys", 8, None)
        self.assertTrue(alerts)


class TestVaccineFeeding(unittest.TestCase):
    def test_due_contains_8(self):
        v = rules.vaccines(8)
        self.assertTrue(any("麻腮风" in x["name"] for x in v["due"]))

    def test_next_is_9(self):
        self.assertEqual(rules.vaccines(8)["next"][0]["age_months"], 9)

    def test_no_age(self):
        self.assertEqual(rules.vaccines(None)["due"], [])

    def test_feeding_8(self):
        self.assertEqual(rules.feeding(8)["range"], "6–8 月")

    def test_feeding_9(self):
        self.assertEqual(rules.feeding(9)["range"], "9–11 月")

    def test_feeding_24(self):
        self.assertEqual(rules.feeding(24)["range"], "18–24 月")


class TestFlagsAndAgent(unittest.TestCase):
    def test_fever_under_3(self):
        flags = rules.red_flags("2个月 发烧38度", 2)
        self.assertTrue(any("发热" in f["name"] for f in flags))

    def test_fever_over_3_ignored(self):
        flags = rules.red_flags("8个月 发烧", 8)
        self.assertFalse(any("发热" in f["name"] for f in flags))

    def test_seizure(self):
        self.assertTrue(rules.red_flags("抽了一次", 8))

    def test_offline_structure(self):
        r = agent.check(baby(), force_mock=True)
        self.assertEqual(r["mode"], "offline")
        for k in ("summary", "care_tips", "risks", "vaccines", "feeding"):
            self.assertTrue(r[k])

    def test_verdict_bucket(self):
        r = agent.check(baby(), force_mock=True)
        self.assertIn("常见区间", r["verdict"])

    def test_strip_measure(self):
        self.assertNotIn("9kg", agent.strip_measure("体重 9kg"))
        self.assertNotIn("8个月", agent.strip_measure("8个月"))

    def test_preterm_note(self):
        r = agent.check("早产32周 男孩 实际8个月 体重7kg", force_mock=True)
        self.assertTrue(any("矫正" in n for n in r["notes"]))

    def test_no_age(self):
        r = agent.check("宝宝有点发烧", force_mock=True)
        self.assertIn("缺月龄", r["verdict"])


if __name__ == "__main__":
    unittest.main()
