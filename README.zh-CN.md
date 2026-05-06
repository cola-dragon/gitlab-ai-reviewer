# GitLab AI Reviewer

一个面向 **GitLab Merge Request（MR）** 的 AI 代码评审服务。

它接收 GitLab Webhook，拉取 MR 改动和提交历史，调用兼容 OpenAI 协议的大模型生成结构化评审结果，并直接在 MR 讨论流中回写：

- 一条总评评论
- 多条可定位的行级评论

![项目封面](docs/screenshots/hero-cover.png)

> 面向自建 GitLab 团队，目标是在现有 Merge Request 工作流中提供实用、可部署、可定制的 AI 代码审查体验。

---

## 功能特性

- 支持 **新建 MR 自动触发 review**
- 支持在评论区使用 **`@bot review` 手动触发**
- 支持 **总评评论 + 行级评论**
- 支持 **Docker Compose 一键部署**
- 支持 **OpenAI 兼容接口**
- 支持 **外挂 prompts**，无需重建镜像即可调整评审提示词（主提示词集中在 `prompts/review.md`）
- 支持 **review 前自动拉取被审项目的 README、CONTRIBUTING、`docs/` 等 markdown 文档**作为 LLM 上下文
- 内置测试与本地联调文档，便于二次开发

### 你会得到什么

- 一个直接出现在 MR 讨论区里的 **AI 总评报告**
- 在可定位场景下挂到具体代码行上的 **AI 行级评论**
- 一个便于自部署、联调、排障和二次定制的轻量 reviewer 服务

---

## 使用场景

这个项目适合以下场景：

- 给自建 GitLab 实例增加一个 AI reviewer
- 验证 LLM 在 MR 代码评审中的可用性
- 作为公司内部 reviewer bot 的 PoC 或参考实现
- 研究 GitLab Webhook、MR diff 分析、LLM 结构化输出、评论回写的完整链路

---

## 效果示意

### 1. 架构图

![架构图](docs/screenshots/architecture-overview.png)

### 2. 触发与处理流程

![流程图](docs/screenshots/workflow-diagram.png)

### 3. AI 总评示意

![总评示意](docs/screenshots/ai-review-summary-demo.png)

### 4. 行级评论示意

![行级评论示意](docs/screenshots/ai-inline-comment-demo.png)

> 当前仓库中的示意图以 AI 生成图为主，用于帮助理解产品结构和使用方式。后续你可以按需替换成真实运行截图。

---

## 快速开始（Docker 推荐）

### 第 1 步：克隆仓库

```bash
git clone <your-repo-url>
cd gitlab-ai-reviewer
```

### 第 2 步：复制环境变量模板

```bash
cp .env.example .env
```

### 第 3 步：填写 `.env`

最小配置如下：

```env
GITLAB_BASE_URL=https://gitlab.example.com
GITLAB_TOKEN=glpat-xxxxxxxxxx
GITLAB_WEBHOOK_SECRET=your_webhook_secret
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=sk-xxxxxxxxxx
OPENAI_MODEL=gpt-5.4
```

### 第 4 步：启动服务

```bash
./run-docker.sh
```

### 第 5 步：健康检查

```bash
curl http://127.0.0.1:8000/healthz
```

正常会返回：

```json
{"ok":true,"queue_depth":0}
```

---

## 配置说明

普通部署场景下，重点配置这 6 个参数：

| 变量名 | 必填 | 说明 | 示例 |
| --- | --- | --- | --- |
| `GITLAB_BASE_URL` | 是 | GitLab 地址，不要带 `/api/v4` | `https://gitlab.example.com` |
| `GITLAB_TOKEN` | 是 | 用于调用 GitLab API 的 token，建议使用 bot 用户 | `glpat-xxx` |
| `GITLAB_WEBHOOK_SECRET` | 是 | Webhook 校验密钥 | `your_secret` |
| `OPENAI_BASE_URL` | 是 | OpenAI 或兼容网关地址 | `https://api.openai.com/v1` |
| `OPENAI_API_KEY` | 是 | 模型服务 API Key | `sk-xxx` |
| `OPENAI_MODEL` | 是 | 模型名 | `gpt-5.4` |

其余运行参数已内置默认值，常见场景下无需额外配置。

---

## GitLab 如何配置

### 1. 创建一个 bot 用户

强烈建议不要直接使用管理员账号或日常开发账号的 token。  
推荐创建专用 reviewer bot，并赋予其：

- 查看项目和 MR 的权限
- 在 MR 中发表评论的权限

### 2. 创建 Personal Access Token

推荐 scope：

- `api`

然后写入：

```env
GITLAB_TOKEN=...
```

### 3. 配置 Webhook

在 GitLab 项目中新增 Webhook：

- URL：`http://<your-reviewer-host>/webhooks/gitlab`
- Secret Token：与 `.env` 中 `GITLAB_WEBHOOK_SECRET` 完全一致
- 事件：
  - `Merge request events`
  - `Note events`

---

## 触发规则

### 自动触发

满足以下条件时会自动审查：

- webhook `object_kind == merge_request`
- `action == open`
- `AUTO_REVIEW_ENABLED == true`

也就是说，当前版本默认是在 **新建 MR** 时自动触发。

### 手动触发

当前手动触发格式为：

```text
@<当前 GITLAB_TOKEN 对应用户名> review
```

例如 token 对应用户名是 `review-bot`，则命令为：

```text
@review-bot review
```

---

## 工作原理

整体流程如下：

1. GitLab 发送 MR 或 Note webhook
2. 服务校验 `X-Gitlab-Token`
3. 根据事件判断是否需要触发 review
4. 拉取 MR changes、commits、commit diff、MR version
5. 拉取被审项目仓库中的 README、CONTRIBUTING、`docs/` 等 markdown 文档（默认开启，可通过 `PROJECT_DOCS_ENABLED=false` 关闭）
6. 构建 review payload
7. 调用大模型生成结构化评审结果
8. 先更新总评评论，再尝试创建行级评论

详细技术说明见：[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

---

## 稳定性说明

当前版本适合作为：

- 本地部署
- 小团队内部试用
- 功能验证 / PoC
- 二次开发基础工程

当前不承诺：

- 企业级高可用
- 超大 MR 的最佳性能
- 所有 GitLab 版本的完全兼容
- 复杂改动下 100% 稳定的行级评论定位

### 已验证范围

- 部署方式：Docker Compose
- 触发方式：MR 自动触发、评论手动触发
- 输出方式：总评 + 行级评论
- 模型接口：OpenAI 兼容协议
- 运行方式：本地 Docker / 自建 GitLab 联调

---

## 已知限制

- 当前采用 **整 MR 一次审查** 模式，不做 chunk 分片
- 超大 diff 场景下，提示词长度和上下文成本会增加
- 行级评论依赖 diff 定位，复杂改动下可能只能保留在总评里
- 手动触发依赖通过 `GITLAB_TOKEN` 成功解析当前用户名
- 提示词质量会直接影响 review 效果

---

## 常用 Docker 命令

### 查看状态

```bash
docker compose ps
```

### 查看日志

```bash
docker compose logs -f reviewer
```

### 重启服务

```bash
docker compose restart reviewer
```

### 停止服务

```bash
docker compose down
```

### 改了 `.env` 后怎么办

```bash
docker compose up -d --build
```

### 改了 `prompts/` 后怎么办

```bash
docker compose restart reviewer
```

> 主提示词集中在 `prompts/review.md`，使用者通常只需修改这一个文件。系统提示与未启用的预留模板（`system.md`、`chunk_review.md`、`final_summary.md`）位于 `prompts/extras/`。

---

## FAQ / 常见问题

### 1）Webhook 返回 401

优先检查：

- GitLab Webhook 页面里的 Secret Token
- `.env` 中的 `GITLAB_WEBHOOK_SECRET`

这两个必须完全一致。

### 2）手动触发没反应

重点检查：

1. 评论格式是否严格匹配：

   ```text
   @<token 对应用户名> review
   ```

2. 当前 `GITLAB_TOKEN` 是否真的能通过 GitLab API 解析出用户名

### 3）自动触发没反应

检查 `docker-compose.yml` 中是否设置了：

```yaml
AUTO_REVIEW_ENABLED: 'true'
```

### 4）为什么只有总评，没有行级评论

GitLab 行级评论只能挂到最终 diff 中仍然存在且可定位的行。  
如果代码行已经变化、删除或定位失败，该问题会保留在总评中。

### 5）模型调用成功，但 GitLab 没有评论

优先排查：

- `GITLAB_TOKEN` 是否有 API 权限
- bot 是否具备项目评论权限
- GitLab API 调用日志是否报错

---

## 相关文档

- 本地联调：[`docs/LOCAL_DEBUG.md`](docs/LOCAL_DEBUG.md)
- 本地 GitLab 搭建：[`docs/LOCAL_GITLAB_SETUP.md`](docs/LOCAL_GITLAB_SETUP.md)
- Webhook 联调清单：[`docs/WEBHOOK_CHECKLIST.md`](docs/WEBHOOK_CHECKLIST.md)
- 架构说明：[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- 贡献指南：[`CONTRIBUTING.md`](CONTRIBUTING.md)
- 安全策略：[`SECURITY.md`](SECURITY.md)

---

## Roadmap

- [ ] 支持大 MR chunk review / 分片审查
- [ ] 支持更多手动触发命令
- [ ] 支持忽略特定路径或文件
- [ ] 支持更丰富的 review 策略配置
- [ ] 支持更清晰的运行状态与任务可观测性

---

## License

Apache-2.0，详见 [`LICENSE`](LICENSE)。
