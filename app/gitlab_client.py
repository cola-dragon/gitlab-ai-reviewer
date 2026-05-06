from __future__ import annotations

from urllib.parse import quote

import httpx


def _diag(message: str) -> None:
    print(f'[DIAG] {message}', flush=True)

from app.diff_position import MergeRequestVersion
from app.models import FileChange


class GitLabClient:
    def __init__(self, base_url: str, token: str, timeout: float = 120.0):
        self._base_url = base_url.rstrip('/')
        self._headers = {'PRIVATE-TOKEN': token}
        self._timeout = timeout
        self._current_username: str | None = None

    async def get_current_username(self) -> str:
        if self._current_username:
            return self._current_username
        async with httpx.AsyncClient(timeout=self._timeout, headers=self._headers, verify=False) as client:
            _diag(f'gitlab get_current_username request: base_url={self._base_url}')
            response = await client.get(f'{self._base_url}/api/v4/user')
            _diag(f'gitlab get_current_username response: status={response.status_code}')
            response.raise_for_status()
            payload = response.json()
        username = payload.get('username')
        if not username:
            raise ValueError('current gitlab username not found')
        self._current_username = str(username)
        return self._current_username

    async def get_merge_request_changes(self, project_id: int, mr_iid: int) -> list[FileChange]:
        async with httpx.AsyncClient(timeout=self._timeout, headers=self._headers, verify=False) as client:
            response = await client.get(f'{self._base_url}/api/v4/projects/{project_id}/merge_requests/{mr_iid}/changes')
            response.raise_for_status()
            payload = response.json()
        return [self._to_file_change(item) for item in payload.get('changes', [])]

    async def list_merge_request_commits(self, project_id: int, mr_iid: int) -> list[dict]:
        return await self._get_paginated_json_list(f'{self._base_url}/api/v4/projects/{project_id}/merge_requests/{mr_iid}/commits')

    async def get_commit_diff(self, project_id: int, commit_id: str) -> list[FileChange]:
        payload = await self._get_paginated_json_list(f'{self._base_url}/api/v4/projects/{project_id}/repository/commits/{commit_id}/diff')
        return [self._to_file_change(item) for item in payload]

    async def _get_paginated_json_list(self, url: str) -> list[dict]:
        items: list[dict] = []
        page = 1
        async with httpx.AsyncClient(timeout=self._timeout, headers=self._headers, verify=False) as client:
            while True:
                response = await client.get(url, params={'per_page': 100, 'page': page})
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, list):
                    raise ValueError(f'expected paginated list payload from {url}')
                items.extend(payload)
                next_page = response.headers.get('X-Next-Page', '')
                if not next_page:
                    break
                page = int(next_page)
        return items

    async def get_merge_request_latest_version(self, project_id: int, mr_iid: int) -> MergeRequestVersion:
        async with httpx.AsyncClient(timeout=self._timeout, headers=self._headers, verify=False) as client:
            response = await client.get(
                f'{self._base_url}/api/v4/projects/{project_id}/merge_requests/{mr_iid}/versions',
                params={'per_page': 1},
            )
            response.raise_for_status()
            versions = response.json()
        if not versions:
            raise ValueError('merge request version not found')
        latest = versions[0]
        return MergeRequestVersion(
            base_sha=latest.get('base_commit_sha', ''),
            start_sha=latest.get('start_commit_sha', ''),
            head_sha=latest.get('head_commit_sha', ''),
        )

    async def list_merge_request_notes(self, project_id: int, mr_iid: int) -> list[dict]:
        async with httpx.AsyncClient(timeout=self._timeout, headers=self._headers, verify=False) as client:
            _diag(f'gitlab list_merge_request_notes request: project_id={project_id} mr_iid={mr_iid}')
            response = await client.get(
                f'{self._base_url}/api/v4/projects/{project_id}/merge_requests/{mr_iid}/notes',
                params={'per_page': 100, 'sort': 'desc'},
            )
            response.raise_for_status()
            data = response.json()
            count = len(data) if isinstance(data, list) else 'non-list'
            _diag(f'gitlab list_merge_request_notes response count={count}')
            return data

    async def create_review_comment(self, project_id: int, mr_iid: int, body: str) -> int:
        async with httpx.AsyncClient(timeout=self._timeout, headers=self._headers, verify=False) as client:
            _diag(
                f'gitlab create_review_comment request: project_id={project_id} '
                f'mr_iid={mr_iid} body_preview={body[:120]!r}'
            )
            response = await client.post(
                f'{self._base_url}/api/v4/projects/{project_id}/merge_requests/{mr_iid}/notes',
                data={'body': body},
            )
            _diag(f'gitlab create_review_comment response: status={response.status_code} body={response.text[:400]!r}')
            response.raise_for_status()
            payload = response.json()
            _diag(f'gitlab create_review_comment parsed_type={type(payload).__name__}')
            return int(payload['id'])

    async def update_review_comment(self, project_id: int, mr_iid: int, note_id: int, body: str) -> None:
        async with httpx.AsyncClient(timeout=self._timeout, headers=self._headers, verify=False) as client:
            _diag(
                f'gitlab update_review_comment request: project_id={project_id} '
                f'mr_iid={mr_iid} note_id={note_id}'
            )
            response = await client.put(
                f'{self._base_url}/api/v4/projects/{project_id}/merge_requests/{mr_iid}/notes/{note_id}',
                data={'body': body},
            )
            _diag(f'gitlab update_review_comment response: status={response.status_code} body={response.text[:300]!r}')
            response.raise_for_status()

    async def create_merge_request_discussion(self, project_id: int, mr_iid: int, body: str, position: dict) -> None:
        payload = {'body': body}
        for key, value in position.items():
            payload[f'position[{key}]'] = value
        async with httpx.AsyncClient(timeout=self._timeout, headers=self._headers, verify=False) as client:
            response = await client.post(
                f'{self._base_url}/api/v4/projects/{project_id}/merge_requests/{mr_iid}/discussions',
                data=payload,
            )
            response.raise_for_status()

    async def list_repository_tree(self, project_id: int, ref: str) -> list[dict]:
        # 递归列出指定 ref 下的全部仓库树条目，分页拉全
        url = f'{self._base_url}/api/v4/projects/{project_id}/repository/tree'
        items: list[dict] = []
        page = 1
        async with httpx.AsyncClient(timeout=self._timeout, headers=self._headers, verify=False) as client:
            while True:
                response = await client.get(
                    url,
                    params={'recursive': 'true', 'ref': ref, 'per_page': 100, 'page': page},
                )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, list):
                    raise ValueError(f'expected list payload from {url}')
                items.extend(payload)
                next_page = response.headers.get('X-Next-Page', '')
                if not next_page:
                    break
                page = int(next_page)
        _diag(f'gitlab list_repository_tree: project_id={project_id} ref={ref} items={len(items)}')
        return items

    async def get_repository_file_raw(self, project_id: int, file_path: str, ref: str) -> str:
        # GitLab Repository Files API 要求路径段做 URL 编码（保留 / 也要编码）
        encoded_path = quote(file_path, safe='')
        url = f'{self._base_url}/api/v4/projects/{project_id}/repository/files/{encoded_path}/raw'
        async with httpx.AsyncClient(timeout=self._timeout, headers=self._headers, verify=False) as client:
            response = await client.get(url, params={'ref': ref})
            response.raise_for_status()
            text = response.text
        _diag(f'gitlab get_repository_file_raw: path={file_path} ref={ref} bytes={len(text.encode("utf-8"))}')
        return text

    @staticmethod
    def _to_file_change(item: dict) -> FileChange:
        old_path = item.get('old_path') or item.get('new_path') or 'unknown'
        new_path = item.get('new_path') or item.get('old_path') or 'unknown'
        file_path = new_path or old_path
        return FileChange(
            file_path=file_path,
            old_path=old_path,
            new_path=new_path,
            diff_text=item.get('diff', ''),
            new_file=bool(item.get('new_file', False)),
            deleted_file=bool(item.get('deleted_file', False)),
            renamed_file=bool(item.get('renamed_file', False)),
        )
