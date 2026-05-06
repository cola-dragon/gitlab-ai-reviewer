"""测试 GitLab 仓库树与文件 raw 接口的两个新方法。"""
from urllib.parse import quote

import pytest

from app.gitlab_client import GitLabClient


class FakeResponse:
    def __init__(self, payload=None, text=None, headers=None):
        self._payload = payload
        self._text = text
        self.headers = headers or {}

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload

    @property
    def text(self):
        return self._text


class FakeAsyncClient:
    """模拟 httpx.AsyncClient，按队列顺序返回响应，并记录每次调用。"""

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
async def test_list_repository_tree_fetches_all_pages(monkeypatch):
    # 构造两页响应：第一页 X-Next-Page=2，第二页为最后一页
    FakeAsyncClient.calls = []
    FakeAsyncClient.responses = [
        FakeResponse(
            payload=[{'path': 'README.md', 'type': 'blob'}, {'path': 'docs/a.md', 'type': 'blob'}],
            headers={'X-Next-Page': '2'},
        ),
        FakeResponse(
            payload=[{'path': 'src/main.py', 'type': 'blob'}],
            headers={'X-Next-Page': ''},
        ),
    ]
    monkeypatch.setattr('app.gitlab_client.httpx.AsyncClient', FakeAsyncClient)

    client = GitLabClient('http://gitlab.local', 'token')
    tree = await client.list_repository_tree(42, 'sha-abc')

    assert [item['path'] for item in tree] == ['README.md', 'docs/a.md', 'src/main.py']
    assert FakeAsyncClient.calls[0][0] == 'http://gitlab.local/api/v4/projects/42/repository/tree'
    assert FakeAsyncClient.calls[0][1] == {'recursive': 'true', 'ref': 'sha-abc', 'per_page': 100, 'page': 1}
    assert FakeAsyncClient.calls[1][1] == {'recursive': 'true', 'ref': 'sha-abc', 'per_page': 100, 'page': 2}


@pytest.mark.asyncio
async def test_get_repository_file_raw_encodes_simple_path(monkeypatch):
    FakeAsyncClient.calls = []
    FakeAsyncClient.responses = [FakeResponse(text='# Hello')]
    monkeypatch.setattr('app.gitlab_client.httpx.AsyncClient', FakeAsyncClient)

    client = GitLabClient('http://gitlab.local', 'token')
    text = await client.get_repository_file_raw(7, 'docs/guide.md', 'main')

    assert text == '# Hello'
    expected_path = quote('docs/guide.md', safe='')
    assert FakeAsyncClient.calls[0][0] == f'http://gitlab.local/api/v4/projects/7/repository/files/{expected_path}/raw'
    assert FakeAsyncClient.calls[0][1] == {'ref': 'main'}


@pytest.mark.asyncio
async def test_get_repository_file_raw_encodes_chinese_and_spaces(monkeypatch):
    FakeAsyncClient.calls = []
    FakeAsyncClient.responses = [
        FakeResponse(text='zh'),
        FakeResponse(text='spaces'),
    ]
    monkeypatch.setattr('app.gitlab_client.httpx.AsyncClient', FakeAsyncClient)

    client = GitLabClient('http://gitlab.local', 'token')
    await client.get_repository_file_raw(1, 'docs/中文文档.md', 'sha1')
    await client.get_repository_file_raw(1, 'path/with spaces.md', 'sha1')

    chinese_path = quote('docs/中文文档.md', safe='')
    spaces_path = quote('path/with spaces.md', safe='')
    assert chinese_path in FakeAsyncClient.calls[0][0]
    assert spaces_path in FakeAsyncClient.calls[1][0]
    # 两次调用都不应包含未编码的斜杠（Repository Files API 强制要求编码）
    assert '/docs/' not in FakeAsyncClient.calls[0][0].split('/repository/files/', 1)[1]
    assert '/path/' not in FakeAsyncClient.calls[1][0].split('/repository/files/', 1)[1]
