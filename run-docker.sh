#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "[ERROR] 未检测到 docker，请先安装 Docker。" >&2
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD=(docker-compose)
else
  echo "[ERROR] 未检测到 docker compose，请先安装 Docker Compose。" >&2
  exit 1
fi

if [ ! -f .env ]; then
  echo "[ERROR] .env 不存在，请先执行: cp .env.example .env" >&2
  exit 1
fi

if ! grep -q '^GITLAB_TOKEN=' .env; then
  echo "[ERROR] .env 中缺少 GITLAB_TOKEN" >&2
  exit 1
fi

if ! grep -q '^OPENAI_API_KEY=' .env; then
  echo "[ERROR] .env 中缺少 OPENAI_API_KEY" >&2
  exit 1
fi

echo "[INFO] 使用目录: $ROOT_DIR"
echo "[INFO] 即将执行: ${COMPOSE_CMD[*]} up -d --build"
"${COMPOSE_CMD[@]}" up -d --build

echo
echo "[OK] 服务已启动。常用命令："
echo "  查看状态: ${COMPOSE_CMD[*]} ps"
echo "  查看日志: ${COMPOSE_CMD[*]} logs -f reviewer"
echo "  健康检查: curl http://127.0.0.1:8000/healthz"
echo "  停止服务: ${COMPOSE_CMD[*]} down"
