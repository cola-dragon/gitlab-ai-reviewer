import pytest

from app.gitlab_client import GitLabClient


class FakeResponse:
    def __init__(self, payload, headers=None):
        self._payload = payload
        self.headers = headers or {}

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeAsyncClient:
    responses = []
    calls = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, params=None):
        FakeAsyncClient.calls.append((url, params))
        return FakeAsyncClient.responses.pop(0)


@pytest.mark.asyncio
async def test_list_merge_request_commits_fetches_all_pages(monkeypatch):
    FakeAsyncClient.calls = []
    FakeAsyncClient.responses = [
        FakeResponse([{'id': 'c1'}, {'id': 'c2'}], headers={'X-Next-Page': '2'}),
        FakeResponse([{'id': 'c3'}], headers={'X-Next-Page': ''}),
    ]
    monkeypatch.setattr('app.gitlab_client.httpx.AsyncClient', FakeAsyncClient)

    client = GitLabClient('http://gitlab.local', 'token')
    commits = await client.list_merge_request_commits(1, 2)

    assert [item['id'] for item in commits] == ['c1', 'c2', 'c3']
    assert FakeAsyncClient.calls[0][1] == {'per_page': 100, 'page': 1}
    assert FakeAsyncClient.calls[1][1] == {'per_page': 100, 'page': 2}
