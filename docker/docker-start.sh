#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/app"
cd "$ROOT_DIR"

required_vars=(
  GITLAB_BASE_URL
  GITLAB_TOKEN
  GITLAB_WEBHOOK_SECRET
  OPENAI_BASE_URL
  OPENAI_API_KEY
  OPENAI_MODEL
)

for name in "${required_vars[@]}"; do
  if [ -z "${!name:-}" ]; then
    echo "[ERROR] 缺少环境变量: ${name}" >&2
    exit 1
  fi
done

PROMPT_PATH="${PROMPT_DIR:-prompts}"
if [ ! -d "$PROMPT_PATH" ]; then
  echo "[ERROR] PROMPT_DIR 不存在: ${PROMPT_PATH}" >&2
  exit 1
fi

if [ ! -f "$PROMPT_PATH/system.md" ] || [ ! -f "$PROMPT_PATH/review.md" ]; then
  echo "[ERROR] PROMPT_DIR 缺少 system.md 或 review.md: ${PROMPT_PATH}" >&2
  exit 1
fi

echo "[INFO] 启动 GitLab AI Reviewer 容器..."
echo "[INFO] PROMPT_DIR=${PROMPT_PATH}"
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
