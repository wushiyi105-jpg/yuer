# 贡献指南

感谢你有兴趣参与 smartcook 的开发。

## 本地运行

```bash
git clone https://github.com/wushiyi105-jpg/smartcook.git
cd smartcook
cp .env.example .env        # 填入你自己的 LLM_API_KEY(项目不自带 key)
python -m smartcook --help
```

## 运行测试

```bash
python -m unittest discover tests -v
```

## 提交 PR

1. fork 本仓库
2. 从 main 拉一个功能分支
3. 改动并本地跑通测试(必须全绿)
4. 提交 PR,写清楚改了什么、为什么

## 约定

- 零第三方依赖,只用 Python 标准库
- 保持「硬事实本地算、软判断交给模型」的现有分工
