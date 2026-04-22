from __future__ import annotations

import hashlib


def _diag(message: str) -> None:
    print(f'[DIAG] {message}', flush=True)

from app.models import ReviewJob, TriggerType
from app.queue_manager import ReviewQueueManager
from app.summarizer import parse_ai_review_marker, render_status_comment


class ReviewService:
    def __init__(self, gitlab_client, queue_manager: ReviewQueueManager):
        self._gitlab_client = gitlab_client
        self._queue_manager = queue_manager

    async def submit(self, *, project_id: int, mr_iid: int, sha: str, trigger_type: TriggerType) -> tuple[str, int, str]:
        _diag(
            f'review_service.submit start: project_id={project_id} '
            f'mr_iid={mr_iid} sha={sha} trigger_type={trigger_type.value}'
        )
        if await self._has_duplicate_review(project_id=project_id, mr_iid=mr_iid, sha=sha):
            _diag('review_service duplicate detected')
            _diag('review_service creating skipped comment')
            note_id = await self._gitlab_client.create_review_comment(
                project_id,
                mr_iid,
                render_status_comment(
                    status='skipped',
                    job_id='duplicate',
                    sha=sha,
                    error_message='已有相同 sha 的 review 结果或任务正在执行，跳过重复触发。',
                ),
            )
            _diag(f'review_service duplicate comment created: note_id={note_id}')
            return 'duplicate', note_id, 'duplicate'

        job_id = self._build_job_id(project_id=project_id, mr_iid=mr_iid, sha=sha, trigger_type=trigger_type)
        _diag(f'review_service job created: job_id={job_id}')
        _diag('review_service creating queued comment')
        note_id = await self._gitlab_client.create_review_comment(
            project_id,
            mr_iid,
            render_status_comment(status='queued', job_id=job_id, sha=sha),
        )
        _diag(f'review_service queued comment created: note_id={note_id}')
        job = ReviewJob(job_id=job_id, project_id=project_id, mr_iid=mr_iid, sha=sha, trigger_type=trigger_type, note_id=note_id)
        state = await self._queue_manager.enqueue(job)
        _diag(f'review_service enqueue result: state={state}')
        if state == 'running':
            await self._gitlab_client.update_review_comment(
                project_id,
                mr_iid,
                note_id,
                render_status_comment(status='running', job_id=job_id, sha=sha),
            )
        return state, note_id, job_id

    async def _has_duplicate_review(self, *, project_id: int, mr_iid: int, sha: str) -> bool:
        notes = await self._gitlab_client.list_merge_request_notes(project_id, mr_iid)
        for note in notes:
            marker = parse_ai_review_marker(note.get('body', ''))
            if marker and marker.get('sha') == sha and marker.get('status') in {'queued', 'running', 'completed'}:
                return True
        return False

    @staticmethod
    def _build_job_id(*, project_id: int, mr_iid: int, sha: str, trigger_type: TriggerType) -> str:
        raw = f'{project_id}:{mr_iid}:{sha}:{trigger_type.value}'.encode('utf-8')
        return hashlib.sha1(raw).hexdigest()[:16]
