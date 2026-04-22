# Contributing / 贡献指南

Thanks for your interest in contributing to GitLab AI Reviewer.

感谢你关注并愿意参与 GitLab AI Reviewer。

---

## Ways to contribute / 参与方式

You can contribute in several ways:

- report bugs
- improve documentation
- suggest features
- improve prompts
- submit code changes with tests

你可以通过以下方式参与：

- 提交 bug 报告
- 改进文档
- 提出功能建议
- 优化 prompts
- 提交带测试的代码修改

---

## Before you start / 开始前建议

Please:

1. read the existing README and docs first
2. search existing issues or discussions
3. keep changes focused and minimal
4. avoid mixing unrelated refactors with a feature or fix

建议你先：

1. 阅读现有 README 和 `docs/`
2. 搜索是否已有同类 issue / 讨论
3. 保持改动聚焦、最小化
4. 不要把无关重构和当前功能 / 修复混在一起

---

## Development setup / 开发环境

### Docker

```bash
cp .env.example .env
./run-docker.sh
```

### Local Python

```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./start.sh
```

---

## Recommended workflow / 推荐工作流

1. Fork the repository
2. Create a focused branch
3. Make your changes
4. Add or update tests when behavior changes
5. Run relevant validation locally
6. Open a pull request with a clear description

推荐流程：

1. Fork 仓库
2. 创建聚焦的分支
3. 完成修改
4. 如果行为有变化，请补充或更新测试
5. 本地跑相关验证
6. 提交清晰描述的 PR

---

## Coding expectations / 代码要求

- Keep changes small and reviewable
- Follow existing project patterns
- Prefer explicit behavior over hidden magic
- Do not hardcode secrets, tokens, or environment-specific values
- Update docs when user-facing behavior changes

代码要求：

- 保持改动小而可审阅
- 遵循现有项目风格
- 优先清晰显式的行为
- 不要硬编码密钥、token、环境专属信息
- 如果用户可见行为变化，请同步更新文档

---

## Testing / 测试

If your change affects behavior, please run the relevant tests.

如果你的改动会影响行为，请至少运行相关测试。

Typical commands:

```bash
pytest -q
```

Or run a focused subset:

```bash
pytest tests/test_main.py -q
```

---

## Pull request notes / PR 说明

A good PR should include:

- what changed
- why it changed
- how it was tested
- any limitations or follow-up work

一个好的 PR 建议说明：

- 改了什么
- 为什么改
- 如何验证
- 是否还有限制或后续工作

---

## Security issues / 安全问题

Please do **not** open public issues for suspected security vulnerabilities.  
Use the process in [`SECURITY.md`](SECURITY.md) instead.

如果你发现疑似安全问题，请**不要**直接公开提 issue。  
请按 [`SECURITY.md`](SECURITY.md) 中的方式反馈。
