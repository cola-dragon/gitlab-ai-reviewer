from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


class FakeReviewService:
    def __init__(self):
        self.calls = []

    async def submit(self, *, project_id: int, mr_iid: int, sha: str, trigger_type):
        self.calls.append((project_id, mr_iid, sha, trigger_type))
        return 'queued', 99, 'job-1'


class FakeQueueManager:
    queue_depth = 3


class FakeGitLabClient:
    def __init__(self, username: str = 'review-bot', should_fail: bool = False):
        self.username = username
        self.should_fail = should_fail

    async def get_current_username(self) -> str:
        if self.should_fail:
            raise RuntimeError('cannot resolve current user')
        return self.username


def test_healthz_returns_queue_depth():
    app = create_app(
        review_service=FakeReviewService(),
        queue_manager=FakeQueueManager(),
        gitlab_client=FakeGitLabClient(),
        webhook_secret='secret',
    )
    client = TestClient(app)

    response = client.get('/healthz')

    assert response.status_code == 200
    assert response.json() == {'ok': True, 'queue_depth': 3}


def test_merge_request_open_webhook_triggers_submit():
    service = FakeReviewService()
    app = create_app(
        review_service=service,
        queue_manager=FakeQueueManager(),
        gitlab_client=FakeGitLabClient(),
        webhook_secret='secret',
    )
    client = TestClient(app)

    payload = {
        'object_kind': 'merge_request',
        'project': {'id': 1},
        'object_attributes': {
            'iid': 2,
            'action': 'open',
            'last_commit': {'id': 'abc123'},
        },
    }

    response = client.post('/webhooks/gitlab', headers={'X-Gitlab-Token': 'secret'}, json=payload)

    assert response.status_code == 200
    assert response.json()['accepted'] is True
    assert service.calls[0][0:3] == (1, 2, 'abc123')


def test_merge_request_open_webhook_does_not_trigger_when_auto_review_disabled():
    service = FakeReviewService()
    settings = Settings(auto_review_enabled=False)
    app = create_app(
        review_service=service,
        queue_manager=FakeQueueManager(),
        gitlab_client=FakeGitLabClient(),
        webhook_secret='secret',
        settings=settings,
    )
    client = TestClient(app)

    payload = {
        'object_kind': 'merge_request',
        'project': {'id': 1},
        'object_attributes': {
            'iid': 2,
            'action': 'open',
            'last_commit': {'id': 'abc123'},
        },
    }

    response = client.post('/webhooks/gitlab', headers={'X-Gitlab-Token': 'secret'}, json=payload)

    assert response.status_code == 200
    assert response.json() == {'accepted': False}
    assert service.calls == []


def test_note_webhook_triggers_manual_review_for_current_token_username():
    service = FakeReviewService()
    app = create_app(
        review_service=service,
        queue_manager=FakeQueueManager(),
        gitlab_client=FakeGitLabClient(username='review-bot'),
        webhook_secret='secret',
    )
    client = TestClient(app)

    payload = {
        'object_kind': 'note',
        'project': {'id': 1},
        'merge_request': {'iid': 2, 'last_commit': {'id': 'abc123'}},
        'object_attributes': {
            'id': 5,
            'note': '@review-bot review',
        },
    }

    response = client.post('/webhooks/gitlab', headers={'X-Gitlab-Token': 'secret'}, json=payload)

    assert response.status_code == 200
    assert response.json()['accepted'] is True
    assert len(service.calls) == 1


def test_note_webhook_does_not_trigger_when_current_username_cannot_be_resolved():
    service = FakeReviewService()
    app = create_app(
        review_service=service,
        queue_manager=FakeQueueManager(),
        gitlab_client=FakeGitLabClient(should_fail=True),
        webhook_secret='secret',
    )
    client = TestClient(app)

    payload = {
        'object_kind': 'note',
        'project': {'id': 1},
        'merge_request': {'iid': 2, 'last_commit': {'id': 'abc123'}},
        'object_attributes': {
            'id': 5,
            'note': '@review-bot review',
        },
    }

    response = client.post('/webhooks/gitlab', headers={'X-Gitlab-Token': 'secret'}, json=payload)

    assert response.status_code == 200
    assert response.json() == {'accepted': False}
    assert service.calls == []
