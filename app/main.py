from __future__ import annotations

from fastapi import FastAPI, Header, HTTPException, Request


def _diag(message: str) -> None:
    print(f'[DIAG] {message}', flush=True)

from app.config import Settings, get_settings
from app.gitlab_client import GitLabClient
from app.llm_client import LLMClient
from app.models import MergeRequestEvent, NoteEvent, TriggerType
from app.prompt_loader import PromptLoader
from app.queue_manager import ReviewQueueManager
from app.review_service import ReviewService
from app.review_worker import ReviewWorker
from app.webhook_handler import should_trigger_auto_review, should_trigger_manual_review


def build_dependencies(settings: Settings):
    prompt_loader = PromptLoader(settings.prompt_dir)
    gitlab_client = GitLabClient(settings.gitlab_base_url, settings.gitlab_token, settings.request_timeout_seconds)
    llm_client = LLMClient(
        base_url=settings.openai_base_url,
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        system_prompt=prompt_loader.load('system.md'),
        review_prompt=prompt_loader.load('review.md'),
        timeout=settings.request_timeout_seconds,
        api_style=settings.openai_api_style,
        structured_output_mode=settings.openai_structured_output_mode,
    )
    review_worker = ReviewWorker(gitlab_client=gitlab_client, llm_client=llm_client)
    queue_manager = ReviewQueueManager(worker=review_worker.run)
    review_service = ReviewService(gitlab_client=gitlab_client, queue_manager=queue_manager)
    return review_service, queue_manager, gitlab_client


def _extract_sha_from_merge_request_payload(payload: dict, attributes: dict) -> str:
    last_commit = attributes.get('last_commit') or payload.get('merge_request', {}).get('last_commit', {})
    return last_commit.get('id', '') or last_commit.get('sha', '') or attributes.get('last_commit_id', '')


def _extract_mr_iid_from_note_payload(payload: dict, attributes: dict) -> int:
    if payload.get('merge_request', {}).get('iid'):
        return int(payload['merge_request']['iid'])
    return int(attributes.get('noteable_iid', 0))


def create_app(
    *,
    review_service: ReviewService | None = None,
    queue_manager: ReviewQueueManager | None = None,
    gitlab_client: GitLabClient | None = None,
    webhook_secret: str | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    app = FastAPI(title='GitLab AI Reviewer')
    active_settings = settings or get_settings()
    if review_service is None or queue_manager is None or gitlab_client is None:
        built_review_service, built_queue_manager, built_gitlab_client = build_dependencies(active_settings)
        review_service = review_service or built_review_service
        queue_manager = queue_manager or built_queue_manager
        gitlab_client = gitlab_client or built_gitlab_client
    active_webhook_secret = webhook_secret or active_settings.gitlab_webhook_secret

    @app.get('/healthz')
    async def healthz():
        return {'ok': True, 'queue_depth': queue_manager.queue_depth}

    @app.post('/webhooks/gitlab')
    async def gitlab_webhook(request: Request, x_gitlab_token: str | None = Header(default=None)):
        _diag(f'webhook arrived: token_present={x_gitlab_token is not None}')
        if x_gitlab_token != active_webhook_secret:
            _diag('webhook rejected: invalid token')
            raise HTTPException(status_code=401, detail='invalid webhook token')

        payload = await request.json()
        object_kind = payload.get('object_kind')
        _diag(f'webhook payload parsed: object_kind={object_kind}')

        if object_kind == 'merge_request' and active_settings.auto_review_enabled:
            attributes = payload.get('object_attributes', {})
            event = MergeRequestEvent(
                project_id=payload['project']['id'],
                merge_request_iid=int(attributes['iid']),
                action=attributes.get('action', ''),
                sha=_extract_sha_from_merge_request_payload(payload, attributes),
            )
            _diag(
                f'merge_request event: project_id={event.project_id} '
                f'mr_iid={event.merge_request_iid} action={event.action} sha={event.sha}'
            )
            if should_trigger_auto_review(event):
                _diag(f'auto review accepted: mr_iid={event.merge_request_iid}')
                state, note_id, job_id = await review_service.submit(
                    project_id=event.project_id,
                    mr_iid=event.merge_request_iid,
                    sha=event.sha,
                    trigger_type=TriggerType.AUTO,
                )
                _diag(f'auto review submitted: state={state} note_id={note_id} job_id={job_id}')
                return {'accepted': True, 'state': state, 'note_id': note_id, 'job_id': job_id}
            _diag(f'auto review skipped: mr_iid={event.merge_request_iid} action={event.action}')

        if object_kind == 'note':
            attributes = payload.get('object_attributes', {})
            is_mr_note = bool(payload.get('merge_request')) or attributes.get('noteable_type') == 'MergeRequest'
            _diag(
                f'note event: project_id={payload.get("project", {}).get("id")} '
                f'note_id={attributes.get("id", 0)} '
                f'noteable_type={attributes.get("noteable_type")} '
                f'is_mr_note={is_mr_note} note={attributes.get("note", "")!r}'
            )
            if is_mr_note:
                event = NoteEvent(
                    project_id=payload['project']['id'],
                    merge_request_iid=_extract_mr_iid_from_note_payload(payload, attributes),
                    note=attributes.get('note', ''),
                    note_id=attributes.get('id', 0),
                    object_attributes=attributes,
                )
                try:
                    trigger_username = await gitlab_client.get_current_username()
                    _diag(f'current username resolved: {trigger_username}')
                except Exception as exc:
                    _diag(f'current username resolve failed: {type(exc).__name__}: {exc}')
                    raise
                matched = should_trigger_manual_review(event, ai_username=trigger_username)
                _diag(
                    f'manual review match: mr_iid={event.merge_request_iid} '
                    f'note_id={event.note_id} ai_username={trigger_username} matched={matched}'
                )
                if matched:
                    sha = payload.get('merge_request', {}).get('last_commit', {}).get('id', '') or attributes.get('commit_id', '')
                    _diag(f'manual review accepted: mr_iid={event.merge_request_iid} sha={sha}')
                    state, note_id, job_id = await review_service.submit(
                        project_id=event.project_id,
                        mr_iid=event.merge_request_iid,
                        sha=sha,
                        trigger_type=TriggerType.MANUAL,
                    )
                    _diag(f'manual review submitted: state={state} note_id={note_id} job_id={job_id}')
                    return {'accepted': True, 'state': state, 'note_id': note_id, 'job_id': job_id}
                _diag('manual review skipped: pattern_not_matched')
            else:
                _diag('note skipped: not MR note')

        _diag(f'webhook accepted=false: object_kind={object_kind}')
        return {'accepted': False}

    return app


app = create_app()
