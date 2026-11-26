# 回归测试映射

这一轮改的两个 issue 与测试的对应关系。写下来是为了下次动 `web.py` 时知道哪条测试会挡住。

## #3 未知 POST 路径不读请求体 → 结论:不是 bug

**当时怎么判的**:在同一个 socket 上先 `POST /api/nope`(带 body),再发 `POST /api/check`,第二发报 `WinError 10053`,于是怀疑「body 没读干净、被当成下一个请求行」。

**实测结论**:`web.py` 的 handler 没有设 `protocol_version`,默认就是 **HTTP/1.0**——每个响应发完服务端主动关连接。第二发报 10053 是客户端在**已关闭的连接**上继续写,不是残留 body 造成的。同一个请求换个新连接就是正常的 200。

**留下什么**:`do_POST` 改成先 `_raw()` 把 body 读完再判路径。这不是为了修 10053,而是让「未知路径」和「非法 JSON」走同一条读体路径,少一处漏读的机会;真正的回归保护是下面这条测试。

- 测试:`TestHttp.test_unknown_path_still_reads_body` —— 未知路径回 404,随后新连接上的 `/api/check` 必须回 200。
- 想真的把连接复用起来,得先给 handler 设 `protocol_version = "HTTP/1.1"` 并处理 `Connection: close`;那是另一个改动,不在这轮。

## #4 截断/非法 JSON 回 500 且带解析器原文

**原来**:`json.loads` 抛 `JSONDecodeError`,落到兜底 `except Exception`,回 500,`str(e)` 原样给前端,用户看到「请求失败:Unterminated string starting at: line 1 column 10」。

**改法**:`do_POST` 里解析单独 `try`,失败回 **400** + `{"error": "请求体不是合法 JSON"}`;兜底 500 只回 `{"error": "服务器内部错误"}`,不再透内部文本。

- 测试:`TestHttp.test_truncated_json_is_400` —— 断言 400、断言响应里有「不是合法 JSON」、断言**没有** `Unterminated string`。
- 连带:`TestHttp.test_empty_body_is_not_500` —— 空 body 仍按 `{}` 处理,不能因为这次改动变成 400/500。

## 示例侧的护栏

`examples/case-02.txt` 是早产儿那条,最容易改坏:生长分档要走矫正月龄(4.0 月,P15 = 5.4),接种仍按实足月龄(6 月,下一剂 8 月龄)。两条测试分别钉住这两个方向:

- `TestCases.test_case02_growth_uses_corrected_age`
- `TestCases.test_case02_vaccines_follow_chronological_age`
