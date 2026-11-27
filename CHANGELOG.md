# 更新记录

## Unreleased

- `0001_init` 改为显式 `op.create_table` / `op.create_index`，运行期走 `alembic upgrade`
- `app/` 只依赖 `ports`，新增内存假实现用例
- 开 ruff `E2`/`E3`；CI 增加 `docker build` 与 `/health` 探活

## 1.0.0

- 新栈重写：WHO 百分位插值（男女分开）、月龄剂次表（22 剂次，0–60 月龄）
- 体重/身高分档出 `growth.weight_band` / `growth.height_band`，单点不判趋势
- 疫苗：`vaccine.overdue` / `vaccine.upcoming`，按生日算建议日期
- 提醒任务 `jobs` 表 + `remind`，提前 7 天，同一天只发一条，`--force` 可重发
- `export` 导出 CSV（日期 / 体重 / 身高 / 疫苗 / 剂次）给医生
- 摘要守卫 `guard`：诊断、用药、可能是、疑似等整句丢弃，`note` 命令强制过守卫
- Alembic `0001_init` + `migrate`（0.x `checks` 表先备份再转换，生日按月龄反推，需人工核对）
- CLI：growth / vaccine / mark / note / remind / export / migrate / serve / doctor
- 测试 28 条，覆盖插值边界、提醒幂等、CSV、迁移、守卫、Web
