import pytest

from app.models import ReviewJob, TriggerType
from app.review_service import ReviewService


class FakeGitLabClient:
    def __init__(self):
        self.created = []
        self.updated = []
        self.next_note_id = 42
        self.notes = []

    async def list_merge_request_notes(self, project_id: int, mr_iid: int):
        return self.notes

    async def create_review_comment(self, project_id: int, mr_iid: int, body: str) -> int:
        self.created.append((project_id, mr_iid, body))
        return self.next_note_id

    async def update_review_comment(self, project_id: int, mr_iid: int, note_id: int, body: str) -> None:
        self.updated.append((project_id, mr_iid, note_id, body))


class FakeQueueManager:
    def __init__(self, state: str):
        self.state = state
        self.enqueued: list[ReviewJob] = []

    async def enqueue(self, job: ReviewJob) -> str:
        self.enqueued.append(job)
        return self.state


@pytest.mark.asyncio
async def test_submit_creates_queued_comment_and_updates_to_running_when_worker_immediate():
    gitlab = FakeGitLabClient()
    queue = FakeQueueManager(state='running')
    service = ReviewService(gitlab_client=gitlab, queue_manager=queue)

    state, note_id, job_id = await service.submit(
        project_id=1,
        mr_iid=2,
        sha='abc',
        trigger_type=TriggerType.AUTO,
    )

    assert state == 'running'
    assert note_id == 42
    assert job_id
    assert '审查状态：排队中（queued）' in gitlab.created[0][2]
    assert '审查状态：审查中（running）' in gitlab.updated[0][3]
    assert queue.enqueued[0].note_id == 42


@pytest.mark.asyncio
async def test_submit_keeps_queued_comment_when_worker_busy():
    gitlab = FakeGitLabClient()
    queue = FakeQueueManager(state='queued')
    service = ReviewService(gitlab_client=gitlab, queue_manager=queue)

    state, note_id, _ = await service.submit(
        project_id=1,
        mr_iid=2,
        sha='abc',
        trigger_type=TriggerType.MANUAL,
    )

    assert state == 'queued'
    assert note_id == 42
    assert len(gitlab.updated) == 0
