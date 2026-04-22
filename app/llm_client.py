from __future__ import annotations

import json
from typing import Literal

import httpx
from pydantic import BaseModel, Field

from app.models import CoverageStats, Issue, ReviewSummary


class IssuePayload(BaseModel):
    severity: Literal['high', 'medium', 'low']
    confidence: Literal['high', 'medium', 'low']
    title: str
    reason: str
    suggestion: str
    file_path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    line_side: Literal['new', 'old'] | None = None


class MergeRequestReviewPayload(BaseModel):
    overall_summary: str
    merge_advice: Literal['can_merge', 'fix_then_merge', 'do_not_merge']
    issues: list[IssuePayload] = Field(default_factory=list)
    uncertainty_notes: list[str] = Field(default_factory=list)


class LLMClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        system_prompt: str,
        review_prompt: str,
        timeout: float = 120.0,
        api_style: str = 'chat_completions',
        structured_output_mode: str = 'json_schema',
    ):
        self._base_url = base_url.rstrip('/')
        self._api_key = api_key
        self._model = model
        self._system_prompt = system_prompt
        self._review_prompt = review_prompt
        self._timeout = timeout
        self._api_style = api_style
        self._structured_output_mode = structured_output_mode

    async def review_merge_request(self, review_payload: str) -> ReviewSummary:
        parsed = await self._call_structured(
            schema_name='merge_request_review',
            schema=MergeRequestReviewPayload.model_json_schema(),
            user_content=(
                f'{self._review_prompt}\n\n'
                '请严格按照给定 JSON Schema 返回结果。不要输出 markdown，不要输出代码块，不要输出额外解释。\n\n'
                f'{review_payload}'
            ),
        )
        issues = [Issue(**issue) for issue in parsed.get('issues', [])]
        return ReviewSummary(
            overall_summary=parsed.get('overall_summary', ''),
            high_priority_issues=[issue for issue in issues if issue.severity == 'high'],
            medium_priority_suggestions=[issue for issue in issues if issue.severity != 'high'],
            uncertainty_notes=parsed.get('uncertainty_notes', []),
            coverage=CoverageStats(files_reviewed=0, total_files=0, commits_reviewed=0, total_commits=0, inline_comments_created=0, inline_comments_failed=0),
            merge_advice=parsed.get('merge_advice', 'fix_then_merge'),
        )

    async def _call_structured(self, *, schema_name: str, schema: dict, user_content: str) -> dict:
        async with httpx.AsyncClient(
            timeout=self._timeout,
            headers={
                'Authorization': f'Bearer {self._api_key}',
                'Content-Type': 'application/json',
            },
        ) as client:
            if self._api_style != 'chat_completions':
                raise ValueError('structured outputs currently require chat_completions api_style')

            request_payload = {
                'model': self._model,
                'messages': [
                    {'role': 'system', 'content': self._system_prompt},
                    {'role': 'user', 'content': user_content},
                ],
                'temperature': 0,
            }
            if self._structured_output_mode == 'json_schema':
                request_payload['response_format'] = {
                    'type': 'json_schema',
                    'json_schema': {
                        'name': schema_name,
                        'strict': True,
                        'schema': schema,
                    },
                }
            elif self._structured_output_mode == 'json_object':
                request_payload['response_format'] = {'type': 'json_object'}

            response = await client.post(f'{self._base_url}/chat/completions', json=request_payload)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                detail = exc.response.text[:1000]
                raise httpx.HTTPStatusError(f'{exc} | response={detail}', request=exc.request, response=exc.response) from exc
            data = response.json()

        text = self._extract_text(data)
        return self._parse_json_text(text)

    @staticmethod
    def _extract_text(payload: dict) -> str:
        if 'output_text' in payload:
            return payload['output_text']
        output = payload.get('output', [])
        for item in output:
            for content in item.get('content', []):
                if content.get('type') in {'output_text', 'text'}:
                    return content.get('text', '')
        choices = payload.get('choices', [])
        if choices:
            message_content = choices[0].get('message', {}).get('content', '')
            if isinstance(message_content, str):
                return message_content
            if isinstance(message_content, list):
                return ''.join(part.get('text', '') for part in message_content if isinstance(part, dict))
        raise ValueError('LLM response did not contain output text')

    @staticmethod
    def _parse_json_text(text: str) -> dict:
        cleaned = text.strip()
        if cleaned.startswith('```'):
            lines = cleaned.splitlines()
            if len(lines) >= 3:
                cleaned = '\n'.join(lines[1:-1]).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            start = cleaned.find('{')
            end = cleaned.rfind('}')
            if start != -1 and end != -1 and end > start:
                return json.loads(cleaned[start:end + 1])
            raise
