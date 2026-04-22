# GitLab Webhook 联调清单

## GitLab 侧
- URL: `http://<host>:8000/webhooks/gitlab`
- Secret Token: 与 `.env` 中 `GITLAB_WEBHOOK_SECRET` 一致
- 勾选事件：
  - Merge request events
  - Note events
- Bot 账号需要能读取 MR 并创建/编辑评论

## 服务侧必填参数
- `GITLAB_BASE_URL`
- `GITLAB_TOKEN`
- `GITLAB_WEBHOOK_SECRET`
- `OPENAI_BASE_URL`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`

## 运行开关
- `docker-compose.yml` 中 `AUTO_REVIEW_ENABLED: 'true'`：开启自动 review
- `docker-compose.yml` 中 `AUTO_REVIEW_ENABLED: 'false'`：关闭自动 review，仅保留手动触发

## 手动联调
1. 新建 MR，应自动创建 AI Review 评论（前提：`AUTO_REVIEW_ENABLED` 为 `true`）
2. 在 MR 评论区输入 `@<GITLAB_TOKEN 对应用户名> review`
3. 若当前有任务执行，应先看到 `queued`
4. 完成后评论应更新为 `completed`
5. 人工重复触发同一 sha，应收到 `skipped`

## 失败联调
- 故意填错 `OPENAI_API_KEY`，确认最终评论为 `failed`
- 故意填错 webhook token，确认接口返回 401
- 故意让 `GITLAB_TOKEN` 无法获取当前用户名，确认手动触发不生效
