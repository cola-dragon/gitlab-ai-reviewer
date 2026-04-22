# 本地 GitLab Docker 联调说明

> 本文档提供的是 **本地自建 GitLab 用于联调本项目** 的建议方式。  
> 当前仓库**不再内置** `./local/start-gitlab.sh` / `./local/stop-gitlab.sh` 这类辅助脚本，请使用你自己的 GitLab Docker / Docker Compose 启动方式。

## 推荐目标环境

- GitLab：自建 Docker / Docker Compose 实例
- reviewer：当前仓库中的服务
- 用途：验证 webhook、自动触发、手动触发、评论回写

## 常见本地地址示例

- Web：`http://localhost:8929`
- SSH：`ssh://git@localhost:2224/<group>/<repo>.git`

这些地址只是常见示例，请以你本地实际 GitLab 配置为准。

## 本地 root 初始登录信息

- 用户名：`root`
- 密码：通常可在 GitLab 容器内查看 `/etc/gitlab/initial_root_password`

例如：

```bash
docker exec -it <your-gitlab-container> cat /etc/gitlab/initial_root_password
```

## 启停方式

请使用你自己的 GitLab 启动命令，例如：

```bash
docker compose up -d
docker compose down
```

或：

```bash
docker run ...
docker stop <your-gitlab-container>
```

## reviewer 服务启动

推荐在宿主机直接运行当前仓库自带的一键脚本：

```bash
./run-docker.sh
```

默认地址：`http://127.0.0.1:8000`

如果你想本机直接跑 Python，也可以继续使用：
```bash
./start.sh
```

## 自动 review 开关
直接改仓库根目录 `docker-compose.yml`：

```yaml
environment:
  AUTO_REVIEW_ENABLED: 'true'
```

- `true`：新建 MR 自动触发
- `false`：关闭自动触发，只能手动评论触发

改完后重新执行：

```bash
docker compose up -d --build
```

## GitLab webhook 如何回调到宿主机服务

如果 GitLab 容器需要访问宿主机上的 reviewer 服务，Webhook URL 建议填：

```text
http://host.docker.internal:8000/webhooks/gitlab
```

> 在 Docker Desktop for Mac 上，`host.docker.internal` 通常可直接访问宿主机。

如果你使用的是 Linux Docker 环境，可能需要改成：

- 宿主机局域网地址
- `172.17.0.1`
- 或者通过反向代理 / tunnel 暴露 reviewer 服务

## 本地联调推荐流程
1. 启动本地 GitLab
2. 登录 `root` 并完成初始化
3. 创建测试 group / project
4. 创建 reviewer bot 用户并生成 token
5. 在项目根目录 `.env` 中填好 `GITLAB_TOKEN`
6. 按需要在 `docker-compose.yml` 中决定是否开启自动 review
7. 启动 reviewer 服务
8. 新建 MR 测自动触发
9. 评论 `@<GITLAB_TOKEN 对应用户名> review` 测手动触发
