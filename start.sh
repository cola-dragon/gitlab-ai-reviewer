#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

if [ ! -f .env ]; then
  echo "[ERROR] .env 不存在，请先复制 .env.example 并填写配置"
  exit 1
fi

if [ ! -d .venv ]; then
  echo "[ERROR] .venv 不存在，请先创建虚拟环境并安装依赖"
  exit 1
fi

if ! grep -q '^GITLAB_TOKEN=' .env; then
  echo "[ERROR] .env 中缺少 GITLAB_TOKEN"
  exit 1
fi

if grep -q '^GITLAB_TOKEN=REPLACE_ME_GITLAB_TOKEN$' .env; then
  echo "[ERROR] 请先把 .env 里的 GITLAB_TOKEN 替换成 ai_bot 的真实 token"
  exit 1
fi

echo "[INFO] 使用项目目录: $ROOT_DIR"
echo "[INFO] 启动 GitLab AI Reviewer..."
exec ./.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
