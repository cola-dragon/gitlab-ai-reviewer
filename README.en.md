# GitLab AI Reviewer

An AI reviewer service for **GitLab Merge Requests (MRs)**.

It receives GitLab webhooks, loads MR diffs and commit history, calls an OpenAI-compatible model, and writes structured review results back into the MR discussion flow as:

- one summary comment
- multiple inline review comments when positions can be resolved

![Project hero](docs/screenshots/hero-cover.png)

> Built for self-hosted GitLab teams that want practical, deployable, and customizable AI review inside their existing merge request workflow.

---

## Features

- **Automatic review** for newly opened merge requests
- **Manual trigger** with `@bot review`
- **Summary comment + inline comments**
- **Docker Compose friendly**
- **Works with OpenAI-compatible gateways**
- **Prompt files can be mounted and customized** (the main prompt lives in `prompts/review.md`)
- **Pulls the target project's README, CONTRIBUTING, `docs/` markdown** as extra LLM context before review
- **Includes tests and local debugging docs**

### What you get

- An **AI summary report** directly in the MR discussion thread
- **Inline review notes** attached to changed lines when positions can be resolved
- A lightweight reviewer service that is easy to self-host, debug, and customize

---

## Use cases

This project is a good fit if you want to:

- add an AI reviewer to a self-hosted GitLab instance
- validate LLM-assisted MR review workflows
- build an internal reviewer bot prototype
- study the end-to-end flow of webhook intake, diff analysis, LLM output, and GitLab comment write-back

---

## Visuals

### Architecture overview

![Architecture](docs/screenshots/architecture-overview.png)

### Review workflow

![Workflow](docs/screenshots/workflow-diagram.png)

### Example AI summary comment

![Summary demo](docs/screenshots/ai-review-summary-demo.png)

### Example inline comment

![Inline demo](docs/screenshots/ai-inline-comment-demo.png)

> The repository currently uses AI-generated visuals as illustrative assets. You can replace them later with real screenshots if you prefer.

---

## Quick Start (Docker recommended)

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd gitlab-ai-reviewer
```

### 2. Copy the env template

```bash
cp .env.example .env
```

### 3. Fill in `.env`

Minimum example:

```env
GITLAB_BASE_URL=https://gitlab.example.com
GITLAB_TOKEN=glpat-xxxxxxxxxx
GITLAB_WEBHOOK_SECRET=your_webhook_secret
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=sk-xxxxxxxxxx
OPENAI_MODEL=gpt-5.4
```

### 4. Start the service

```bash
./run-docker.sh
```

### 5. Run a health check

```bash
curl http://127.0.0.1:8000/healthz
```

Expected response:

```json
{"ok":true,"queue_depth":0}
```

---

## Configuration

The following 6 variables are the main ones you need:

| Variable | Required | Description | Example |
| --- | --- | --- | --- |
| `GITLAB_BASE_URL` | Yes | GitLab base URL, without `/api/v4` | `https://gitlab.example.com` |
| `GITLAB_TOKEN` | Yes | GitLab API token, preferably from a dedicated bot user | `glpat-xxx` |
| `GITLAB_WEBHOOK_SECRET` | Yes | Webhook validation secret | `your_secret` |
| `OPENAI_BASE_URL` | Yes | OpenAI or compatible gateway base URL | `https://api.openai.com/v1` |
| `OPENAI_API_KEY` | Yes | Model API key | `sk-xxx` |
| `OPENAI_MODEL` | Yes | Model name | `gpt-5.4` |

Most other runtime knobs already have defaults and usually do not need to be set.

---

## GitLab setup

### 1. Create a bot user

It is strongly recommended to use a dedicated reviewer bot instead of an admin or personal account token.

The bot should have permission to:

- view the project and merge requests
- create comments on merge requests

### 2. Create a Personal Access Token

Recommended scope:

- `api`

Then put it into:

```env
GITLAB_TOKEN=...
```

### 3. Configure the webhook

In the GitLab project, add a webhook with:

- URL: `http://<your-reviewer-host>/webhooks/gitlab`
- Secret Token: exactly the same as `GITLAB_WEBHOOK_SECRET`
- Events:
  - `Merge request events`
  - `Note events`

---

## Trigger rules

### Automatic review

Automatic review runs when:

- webhook `object_kind == merge_request`
- `action == open`
- `AUTO_REVIEW_ENABLED == true`

So the current behavior is focused on **newly opened merge requests**.

### Manual review

Manual review is triggered by:

```text
@<username-resolved-from-GITLAB_TOKEN> review
```

For example, if the token belongs to `review-bot`, the trigger command is:

```text
@review-bot review
```

---

## How it works

High-level flow:

1. GitLab sends an MR or note webhook
2. The service validates `X-Gitlab-Token`
3. The webhook handler decides whether a review should start
4. The service loads MR changes, commits, commit diffs, and the latest MR version
5. The service pulls the target project's README, CONTRIBUTING, and `docs/` markdown as extra context (enabled by default; disable with `PROJECT_DOCS_ENABLED=false`)
6. A review payload is built for the LLM
7. The LLM returns structured review output
8. The service updates the summary comment and attempts inline discussions

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for module-level details.

---

## Stability

This repository is currently best suited for:

- local deployment
- proof of concept usage
- small-team internal adoption
- customization and secondary development

It does **not** currently promise:

- enterprise-grade high availability
- best performance for extremely large MRs
- universal compatibility across every GitLab version
- perfect inline-comment resolution for all complex diffs

### Verified scope

- Deployment: Docker Compose
- Trigger styles: automatic MR review + note-triggered manual review
- Output styles: summary comment + inline comments
- Model integration: OpenAI-compatible APIs
- Runtime environments: local Docker and self-hosted GitLab testing

---

## Known limitations

- The current implementation reviews the **whole MR in one pass** instead of chunking
- Very large diffs increase prompt size and context cost
- Inline comments depend on diff-position resolution and may fall back to summary-only output
- Manual trigger depends on successfully resolving the current GitLab username from `GITLAB_TOKEN`
- Prompt quality directly affects review quality

---

## Common Docker commands

### Check status

```bash
docker compose ps
```

### Stream logs

```bash
docker compose logs -f reviewer
```

### Restart

```bash
docker compose restart reviewer
```

### Stop

```bash
docker compose down
```

### Rebuild after `.env` changes

```bash
docker compose up -d --build
```

### Reload prompt files

```bash
docker compose restart reviewer
```

> The main prompt lives in `prompts/review.md` — that is usually the only file you need to customize. The system prompt and reserved templates (`system.md`, `chunk_review.md`, `final_summary.md`) live under `prompts/extras/`.

---

## FAQ

### 1. Why does the webhook return 401?

Usually because the Secret Token configured in GitLab does not exactly match `GITLAB_WEBHOOK_SECRET` in `.env`.

### 2. Why does manual trigger not work?

Check both:

1. the exact comment format:

   ```text
   @<resolved-username> review
   ```

2. whether `GITLAB_TOKEN` can successfully resolve the current GitLab username

### 3. Why does automatic review not run?

Check whether `docker-compose.yml` has:

```yaml
AUTO_REVIEW_ENABLED: 'true'
```

### 4. Why do I only get the summary comment without inline comments?

GitLab inline comments can only be attached to lines that still exist in the final diff and can be positioned reliably.

### 5. The model call succeeded, but GitLab got no comment. Why?

Check:

- whether `GITLAB_TOKEN` has API permission
- whether the bot user can comment on the project
- whether GitLab API calls failed in logs

---

## Related docs

- Local debugging: [`docs/LOCAL_DEBUG.md`](docs/LOCAL_DEBUG.md)
- Local GitLab setup: [`docs/LOCAL_GITLAB_SETUP.md`](docs/LOCAL_GITLAB_SETUP.md)
- Webhook checklist: [`docs/WEBHOOK_CHECKLIST.md`](docs/WEBHOOK_CHECKLIST.md)
- Architecture: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- Contributing: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Security: [`SECURITY.md`](SECURITY.md)

---

## Roadmap

- [ ] Support chunk-based review for large MRs
- [ ] Support more manual trigger commands
- [ ] Support path/file ignore rules
- [ ] Support richer review strategies and configuration
- [ ] Improve operational visibility and task observability

---

## License

Apache-2.0. See [`LICENSE`](LICENSE).
