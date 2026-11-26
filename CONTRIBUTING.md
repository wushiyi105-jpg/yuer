# 参与

## 本地跑起来

```bash
uv sync --extra dev
uv run yuer doctor
uv run pytest -q
```

## 提 PR 之前

1. 规则改动必须落在 `yuer/domain/rules/`，并且新增一条 `rule_id`；
2. 每条 `rule_id` 至少一条断言；
3. 输出给家长的文案必须过 `domain/guard.py`，诊断 / 用药 / 疑似一律整句丢；
4. `ruff check .`、`mypy yuer`、`pytest -q` 全过；
5. 改表结构就加一条 `migrations/versions/`，写清 up/down。

## 提交信息

`type: 一句话说清改了什么`，type 用 feat / fix / docs / test / refactor。
