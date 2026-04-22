import pytest

from app.llm_client import LLMClient
from app.models import CoverageStats


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeAsyncClient:
    last_request = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json):
        FakeAsyncClient.last_request = (url, json)
        return FakeResponse(
            {
                'choices': [
                    {
                        'message': {
                            'content': '{"overall_summary":"存在高危风险，不建议合并。","merge_advice":"do_not_merge","issues":[{"severity":"high","confidence":"high","title":"安全风险｜默认关闭 TLS 校验","reason":"verify=False 会关闭证书校验","suggestion":"恢复 verify=True","file_path":"src/a.py","line_start":12,"line_end":12,"line_side":"new"}],"uncertainty_notes":[]}'
                        }
                    }
                ]
            }
        )


@pytest.mark.asyncio
async def test_review_merge_request_uses_strict_json_schema(monkeypatch):
    monkeypatch.setattr('app.llm_client.httpx.AsyncClient', FakeAsyncClient)

    client = LLMClient(
        base_url='https://api.openai.com/v1',
        api_key='sk-test',
        model='gpt-5.4',
        system_prompt='system prompt',
        review_prompt='review prompt',
        timeout=30,
        api_style='chat_completions',
        structured_output_mode='json_schema',
    )

    summary = await client.review_merge_request('{"files":[]}')

    url, payload = FakeAsyncClient.last_request
    assert url == 'https://api.openai.com/v1/chat/completions'
    assert payload['response_format']['type'] == 'json_schema'
    assert payload['response_format']['json_schema']['strict'] is True
    assert payload['response_format']['json_schema']['name'] == 'merge_request_review'
    assert summary.overall_summary.startswith('存在高危风险')
    assert summary.high_priority_issues[0].file_path == 'src/a.py'
    assert summary.high_priority_issues[0].line_start == 12
    assert summary.coverage == CoverageStats(files_reviewed=0, total_files=0, commits_reviewed=0, total_commits=0, inline_comments_created=0, inline_comments_failed=0)
