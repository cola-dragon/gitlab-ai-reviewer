# Architecture / 架构说明

## Overview / 总览

GitLab AI Reviewer is a webhook-driven review service built around a small set of focused modules:

GitLab AI Reviewer 是一个由 webhook 驱动的评审服务，由一组职责清晰的小模块组成：

1. **Webhook intake** — accept GitLab MR and note events
2. **Trigger decision** — decide whether to start auto or manual review
3. **Queueing** — deduplicate and serialize review jobs
4. **Data loading** — fetch MR changes, commits, diffs, and version metadata
5. **LLM review** — request structured output from an OpenAI-compatible model
6. **Write-back** — update summary comments and create inline discussions

---

## Runtime flow / 运行流程

### Step 1: Webhook entry

File: `app/main.py`

- Exposes `POST /webhooks/gitlab`
- Validates `X-Gitlab-Token`
- Parses webhook payload
- Handles both `merge_request` and `note` events

### Step 2: Trigger routing

Files:

- `app/main.py`
- `app/webhook_handler.py`

Behavior:

- Auto review only runs for new MR open events
- Manual review only runs when the note matches `@<resolved-bot-username> review`

### Step 3: Review submission and deduplication

File: `app/review_service.py`

- Checks existing MR notes for duplicate review markers
- Creates an initial queued/running/skipped status comment
- Builds a review job ID
- Enqueues the job through the queue manager

### Step 4: Data collection

Files:

- `app/review_worker.py`
- `app/gitlab_client.py`

The worker fetches:

- MR file changes
- MR commit list
- per-commit diffs
- latest MR version metadata

These inputs are combined into a structured review payload for the model.

### Step 5: LLM structured review

File: `app/llm_client.py`

The service sends:

- a system prompt
- a review prompt
- a JSON schema response format
- the assembled MR payload

The model returns structured data containing:

- overall summary
- merge advice
- issues with severity and confidence
- optional file and line hints

### Step 6: Comment write-back

Files:

- `app/review_worker.py`
- `app/gitlab_client.py`
- `app/summarizer.py`
- `app/diff_position.py`

The worker:

- updates the top-level status / summary comment
- resolves line positions for issues when possible
- creates inline MR discussions for resolvable issues

If a line cannot be positioned reliably, the issue remains in the summary output.

---

## Module map / 模块映射

### `app/main.py`

Application entrypoint.

- Creates the FastAPI app
- Wires settings, prompt loader, GitLab client, LLM client, queue manager, review service, and worker
- Provides `/healthz`
- Accepts GitLab webhooks

### `app/webhook_handler.py`

Minimal trigger rules.

- `should_trigger_auto_review`
- `should_trigger_manual_review`

### `app/review_service.py`

Submission orchestration layer.

- deduplication
- initial note creation
- queue submission
- running/queued state transitions

### `app/review_worker.py`

Main execution pipeline.

- load MR data
- build review payload
- call model
- update summary comment
- create inline comments

### `app/gitlab_client.py`

Thin async wrapper over GitLab REST APIs.

- current user lookup
- MR changes
- commits
- notes
- versions
- discussions

### `app/llm_client.py`

OpenAI-compatible structured output client.

- sends chat completion requests
- requests JSON schema output
- extracts and parses model output

### `app/prompt_loader.py`

Loads prompt files from the configured prompt directory.

主 prompt 位于 `prompts/review.md`（使用者主要在这里定制审查口径）；系统提示与暂未启用的预留模板（`system.md`、`chunk_review.md`、`final_summary.md`）位于 `prompts/extras/`。

### `app/queue_manager.py`

Serializes review execution and exposes queue depth to health checks.

### `app/diff_position.py`

Maps model issues to GitLab inline comment positions.

### `app/summarizer.py`

Renders summary status comments and inline issue comments.

---

## Data flow / 数据流

```text
GitLab Webhook
  -> FastAPI /webhooks/gitlab
  -> trigger decision
  -> ReviewService.submit()
  -> queue manager
  -> ReviewWorker.run()
  -> GitLab API + LLM API
  -> summary comment update
  -> inline discussions
```

---

## Key design choices / 关键设计取舍

### 1. Whole-MR review instead of chunk review

Current behavior reviews the MR as a single unit.

当前版本按“整 MR 一次审查”处理，而不是做 chunk 分片。

Benefits:

- simpler execution model
- easier to reason about
- easier to deploy and debug

Trade-off:

- large diffs cost more tokens
- very large MRs may need chunking in the future

### 2. Structured output over free-form text

The LLM is asked to return JSON that matches a schema.

模型使用结构化 JSON 输出而不是纯自然语言输出。

Benefits:

- easier downstream parsing
- more stable automation
- cleaner separation between generation and rendering

### 3. Summary-first, inline-when-possible

The service always tries to leave a summary result.

服务会优先确保总评可见，再尽量创建行级评论。

This makes the system resilient when diff positioning is incomplete or unstable.

---

## Stability boundaries / 稳定性边界

The current implementation is intentionally lightweight and best suited for:

- local deployments
- internal tooling
- proof-of-concept usage
- customization by engineering teams

当前实现有意保持轻量，更适合：

- 本地部署
- 内部工具
- PoC 验证
- 工程团队二次开发

It is not yet a fully hardened platform for:

- large-scale multi-tenant operation
- strict permission partitioning
- advanced observability and audit requirements
- very large merge requests at scale

---

## Suggested future evolution / 后续可演进方向

- chunk-based review for large MRs
- ignore rules for files and paths
- richer reviewer configuration
- better observability and execution tracing
- retry and backoff controls for external services
- UI or dashboard for job status
