"""集成测试:HTTP 层、CLI 端到端、四份示例的结论是否站得住。

单测只测函数,这里测的是「真发请求、真起进程、真读文件」之后用户看到的东西。
"""

import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from yuer import agent, llm, rules, web
from yuer import db as dbmod

ROOT = Path(__file__).resolve().parents[1]
CASES = ["case-01", "case-02", "case-03", "case-04"]


def case_text(cid):
    return (ROOT / "examples" / (cid + ".txt")).read_text(encoding="utf-8")


class TestHttp(unittest.TestCase):
    """真起一个 http.server,用 socket 发原始请求。"""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.db = dbmod.Database(os.path.join(cls.tmp, "y.db"))
        cls.srv = ThreadingHTTPServer(
            ("127.0.0.1", 0), web._handler(cls.db, llm.default_config(), True))
        cls.port = cls.srv.server_address[1]
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def conn(self):
        return socket.create_connection(("127.0.0.1", self.port), timeout=8)

    def read_response(self, sock):
        """读完整响应:先头,再按 Content-Length 补 body。"""
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = sock.recv(4096)
            if not chunk:
                break
            buf += chunk
        head, body = buf.split(b"\r\n\r\n", 1)
        text = head.decode("latin-1")
        m = re.search(r"Content-Length: (\d+)", text)
        n = int(m.group(1)) if m else 0
        while len(body) < n:
            chunk = sock.recv(4096)
            if not chunk:
                break
            body += chunk
        return text.split("\r\n")[0], body[:n]

    def send(self, sock, path, body=None):
        if body is None:
            head = "GET %s HTTP/1.1\r\nHost: x\r\n\r\n" % path
        else:
            head = ("POST %s HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\n"
                    "Content-Length: %d\r\n\r\n%s" % (path, len(body), body.decode("utf-8")))
        sock.sendall(head.encode("utf-8"))
        return self.read_response(sock)

    def test_page_is_html(self):
        s = self.conn()
        status, body = self.send(s, "/")
        s.close()
        self.assertIn("200", status)
        self.assertIn("育儿".encode("utf-8"), body)

    def test_status_says_mock(self):
        s = self.conn()
        status, body = self.send(s, "/api/status")
        s.close()
        self.assertIn("200", status)
        self.assertTrue(json.loads(body)["mock"])

    def test_check_returns_verdict(self):
        s = self.conn()
        status, body = self.send(s, "/api/check",
                                 json.dumps({"text": case_text("case-01")}).encode("utf-8"))
        s.close()
        self.assertIn("200", status)
        r = json.loads(body)
        self.assertEqual(r["months"], 8)
        self.assertIn("月龄", r["verdict"])

    def test_unknown_path_still_reads_body(self):
        # 服务端是 HTTP/1.0,每个响应后关连接;未知路径先回 404,body 不会留在缓冲里
        s = self.conn()
        status, _ = self.send(s, "/api/nope", '{"text":"男孩 8个月"}'.encode("utf-8"))
        self.assertIn("404", status)
        s.close()
        s = self.conn()
        status2, body2 = self.send(s, "/api/check",
                                   json.dumps({"text": "男孩,8个月,体重9kg"}).encode("utf-8"))
        s.close()
        self.assertIn("200", status2)
        self.assertIn("月龄".encode("utf-8"), body2)

    def test_truncated_json_is_400(self):
        # issue #4:截断的 body 原来回 500,还带 json 解析器原文
        s = self.conn()
        status, body = self.send(s, "/api/check", '{"text": "男孩,8个月,体重9kg'.encode("utf-8"))
        s.close()
        self.assertIn("400", status)
        self.assertIn("不是合法 JSON".encode("utf-8"), body)
        self.assertNotIn(b"Unterminated string", body)

    def test_empty_body_is_not_500(self):
        s = self.conn()
        status, _ = self.send(s, "/api/check", b"")
        s.close()
        self.assertIn("200", status)

    def test_get_unknown_is_404(self):
        s = self.conn()
        status, _ = self.send(s, "/nope")
        s.close()
        self.assertIn("404", status)


class TestCases(unittest.TestCase):
    """四份真实描述 → 结论必须站得住。"""

    def test_case01_all_in_common_band(self):
        r = rules.analyze(case_text("case-01"))
        self.assertEqual(r["months"], 8)
        self.assertEqual(len(r["growth"]), 3)
        for g in r["growth"]:
            self.assertEqual(g["bucket"], "P15–P85(常见区间)")

    def test_case02_growth_uses_corrected_age(self):
        r = rules.analyze(case_text("case-02"))
        self.assertEqual(r["months"], 6)
        self.assertEqual(r["corrected"], 4.0)
        # 4 个月女孩体重 P15 是 5.4;用 6 个月会变成 5.9
        self.assertEqual(r["growth"][0]["band"]["P15"], 5.4)

    def test_case02_vaccines_follow_chronological_age(self):
        r = rules.analyze(case_text("case-02"))
        self.assertEqual(r["vaccines"]["next"][0]["age_months"], 8)

    def test_case03_hits_red_flag(self):
        r = rules.analyze(case_text("case-03"))
        self.assertTrue(any("精神差" in f["name"] for f in r["red_flags"]))
        self.assertIn("立即就医", agent.verdict(r))

    def test_case04_hits_red_flag_and_asks_urine(self):
        r = rules.analyze(case_text("case-04"))
        self.assertTrue(r["red_flags"])
        urine = [q for q in r["questions"] if q["item"] == "尿量"][0]
        self.assertFalse(urine["ok"])

    def test_feeding_boundary_at_6_months(self):
        self.assertEqual(rules.feeding(6)["range"], "0–6 月")
        self.assertEqual(rules.feeding(7)["range"], "6–8 月")


class TestCli(unittest.TestCase):
    """真起进程跑 python -m yuer。"""

    def run_cli(self, *args, stdin=""):
        return subprocess.run([sys.executable, "-m", "yuer", *args],
                              cwd=str(ROOT), capture_output=True, text=True,
                              encoding="utf-8", timeout=60, input=stdin)

    def test_check_file(self):
        p = self.run_cli("--mock", "check", "--file", "examples/case-01.txt")
        self.assertEqual(p.returncode, 0)
        self.assertIn("育儿生长评估", p.stdout)
        self.assertIn("P15–P85", p.stdout)

    def test_check_json(self):
        p = self.run_cli("--mock", "--json", "check", "--file", "examples/case-03.txt")
        self.assertEqual(p.returncode, 0)
        body = json.loads(p.stdout)
        self.assertEqual(body["months"], 24)
        self.assertTrue(body["red_flags"])

    def test_check_without_text_exits_2(self):
        p = self.run_cli("--mock", "check")
        self.assertEqual(p.returncode, 2)
        self.assertIn("没有描述", p.stderr)

    def test_growth_prints_five_bands(self):
        p = self.run_cli("growth", "--month", "8", "--sex", "boys")
        self.assertEqual(p.returncode, 0)
        for k in ("P3", "P15", "P50", "P85", "P97"):
            self.assertIn(k, p.stdout)

    def test_vaccines_lists_24_months(self):
        p = self.run_cli("vaccines")
        self.assertEqual(p.returncode, 0)
        self.assertIn("麻腮风", p.stdout)

    def test_history_on_empty_db(self):
        tmp = tempfile.mkdtemp()
        db = os.path.join(tmp, "empty.db")
        p = self.run_cli("--db", db, "history")
        self.assertEqual(p.returncode, 0)
        self.assertIn("还没有记录", p.stdout)


class TestDocs(unittest.TestCase):
    """示例输出要留在仓库里,且和现在的 CLI 大致对得上。"""

    def test_out_files_exist(self):
        for cid in CASES:
            self.assertTrue((ROOT / "examples" / "out" / (cid + ".md")).exists(), cid)

    def test_case01_out_mentions_common_band(self):
        text = (ROOT / "examples" / "out" / "case-01.md").read_text(encoding="utf-8")
        self.assertIn("P15–P85", text)
        self.assertIn("8 月龄", text)

    def test_cases_json_has_four_rows(self):
        rows = json.loads((ROOT / "examples" / "cases.json").read_text(encoding="utf-8"))
        self.assertEqual([r["id"] for r in rows], CASES)
        for r in rows:
            self.assertTrue(r["source"])


if __name__ == "__main__":
    unittest.main()
