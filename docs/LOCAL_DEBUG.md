# 本地联调步骤

## 方式一：推荐，走 Docker 一键启动

```bash
cp .env.example .env
./run-docker.sh
```

健康检查：

```bash
curl http://127.0.0.1:8000/healthz
```

查看日志：

```bash
docker compose logs -f reviewer
```

## 方式二：本机直接跑 Python

```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./start.sh
```

健康检查：

```bash
curl http://127.0.0.1:8000/healthz
```

如果使用 ngrok / 内网穿透，将回调地址填入 GitLab Webhook。
