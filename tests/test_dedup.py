import pytest

from app.models import TriggerType
from app.review_service import ReviewService


class FakeGitLabClient:
    def __init__(self, notes=None):
        self.notes = notes or []
        self.created = []
        self.updated = []
        self.next_note_id = 77

    async def list_merge_request_notes(self, project_id: int, mr_iid: int):
        return self.notes

    async def create_review_comment(self, project_id: int, mr_iid: int, body: str) -> int:
        self.created.append(body)
        return self.next_note_id

    async def update_review_comment(self, project_id: int, mr_iid: int, note_id: int, body: str) -> None:
        self.updated.append(body)


class FakeQueueManager:
    async def enqueue(self, job):
        return 'queued'


@pytest.mark.asyncio
async def test_submit_skips_duplicate_for_same_sha_and_replies_comment():
    gitlab = FakeGitLabClient(
        notes=[
            {
                'body': '## AI Review\n状态：completed\n\n<!-- ai-review:job_id=old status=completed sha=abc123 -->'
            }
        ]
    )
    service = ReviewService(gitlab_client=gitlab, queue_manager=FakeQueueManager())

    state, note_id, job_id = await service.submit(
        project_id=1,
        mr_iid=2,
        sha='abc123',
        trigger_type=TriggerType.AUTO,
    )

    assert state == 'duplicate'
    assert note_id == 77
    assert job_id == 'duplicate'
    assert '审查状态：已跳过（skipped）' in gitlab.created[0]
