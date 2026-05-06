from __future__ import annotations

import asyncio
import json


def _diag(message: str) -> None:
    print(f'[DIAG] {message}', flush=True)

from app.diff_position import MergeRequestVersion, extract_commentable_lines, resolve_issue_position
from app.models import CoverageStats, FileChange, Issue, ReviewJob, ReviewSummary
from app.summarizer import render_inline_issue_comment, render_status_comment


class ReviewWorker:
    # 项目文档路径黑名单：路径中任一段命中下列名称即跳过（避免拉取无关 markdown）
    _DOCS_BLOCKED_SEGMENTS = frozenset({
        'node_modules',
        'vendor',
        'dist',
        'build',
        'target',
        '.git',
        '.spec-workflow',
    })
    # `.venv` 这类前缀放宽匹配（如 `.venv313`、`.venv-prod` 等也跳过）
    _DOCS_BLOCKED_PREFIXES = ('.venv',)
    # 允许的 markdown 后缀
    _DOCS_MD_SUFFIXES = ('.md', '.MD', '.markdown')

    def __init__(
        self,
        gitlab_client,
        llm_client,
        empty_changes_retries: int = 3,
        empty_changes_delay: float = 3.0,
        project_docs_enabled: bool = True,
        project_docs_max_files: int = 20,
        project_docs_max_bytes_per_file: int = 8192,
        project_docs_max_total_bytes: int = 60000,
    ):
        self._gitlab_client = gitlab_client
        self._llm_client = llm_client
        self._empty_changes_retries = empty_changes_retries
        self._empty_changes_delay = empty_changes_delay
        self._project_docs_enabled = project_docs_enabled
        self._project_docs_max_files = project_docs_max_files
        self._project_docs_max_bytes_per_file = project_docs_max_bytes_per_file
        self._project_docs_max_total_bytes = project_docs_max_total_bytes

    async def run(self, job: ReviewJob) -> None:
        _diag(f'review_worker.run start: job_id={job.job_id} mr_iid={job.mr_iid} sha={job.sha}')
        await self._update(job, render_status_comment(status='running', job_id=job.job_id, sha=job.sha))

        try:
            changes = await self._load_changes_with_retry(job.project_id, job.mr_iid)
            _diag(f'review_worker changes loaded: count={len(changes)}')
            commits = await self._gitlab_client.list_merge_request_commits(job.project_id, job.mr_iid)
            _diag(f'review_worker commits loaded: count={len(commits)}')
            commit_history = await self._load_commit_history(job.project_id, commits)
            project_docs = await self._load_project_docs(job.project_id, job.sha)
            _diag(f'review_worker project_docs loaded: count={len(project_docs)}')
            payload = self._build_review_payload(changes, commits, commit_history, project_docs)
            _diag(f'review_worker payload built: chars={len(payload)}')
            summary = await self._llm_client.review_merge_request(payload)
            _diag('review_worker llm completed')
            version = await self._load_version(job.project_id, job.mr_iid)
            _diag(f'review_worker version loaded: base={version.base_sha[:8]} head={version.head_sha[:8]}')
            inline_created, inline_failed = await self._create_inline_comments(job, summary, changes, version)
            _diag(f'review_worker inline comments result: created={inline_created} failed={inline_failed}')
            summary.coverage = CoverageStats(
                files_reviewed=len(changes),
                total_files=len(changes),
                commits_reviewed=len(commits),
                total_commits=len(commits),
                inline_comments_created=inline_created,
                inline_comments_failed=inline_failed,
            )
            await self._update(job, render_status_comment(status='completed', job_id=job.job_id, sha=job.sha, summary=summary))
            _diag('review_worker completed status updated')
        except Exception as exc:  # pragma: no cover
            _diag(f'review_worker failed: {type(exc).__name__}: {exc}')
            await self._update(job, render_status_comment(status='failed', job_id=job.job_id, sha=job.sha, error_message=str(exc)))

    async def _load_changes_with_retry(self, project_id: int, mr_iid: int):
        changes = []
        for attempt in range(self._empty_changes_retries + 1):
            changes = await self._gitlab_client.get_merge_request_changes(project_id, mr_iid)
            if changes:
                return changes
            if attempt < self._empty_changes_retries:
                await asyncio.sleep(self._empty_changes_delay)
        return changes

    async def _load_commit_history(self, project_id: int, commits: list[dict]) -> dict[str, list[dict]]:
        history: dict[str, list[dict]] = {}
        for commit in commits:
            commit_id = commit.get('id', '')
            commit_changes = await self._gitlab_client.get_commit_diff(project_id, commit_id)
            for change in commit_changes:
                keys = {change.file_path, change.old_path, change.new_path}
                item = {
                    'commit_id': commit_id,
                    'title': commit.get('title', ''),
                    'file_path': change.file_path,
                    'change_type': self._change_type(change),
                    'diff': change.diff_text,
                }
                for key in keys:
                    if key:
                        history.setdefault(key, []).append(item)
        return history

    async def _load_project_docs(self, project_id: int, sha: str) -> list[dict]:
        # 在 review 之前拉取被审项目仓库中的 markdown 文档作为 LLM 上下文。
        # 任何异常都不能阻塞 review，因此整体用 try/except 包裹，失败返回空列表。
        if not self._project_docs_enabled:
            return []
        try:
            tree = await self._gitlab_client.list_repository_tree(project_id, sha)
        except Exception as exc:
            _diag(f'project_docs list_tree failed: err={type(exc).__name__}: {exc}')
            return []

        candidates = []
        for item in tree:
            if item.get('type') != 'blob':
                continue
            path = item.get('path') or ''
            if not path or not path.endswith(self._DOCS_MD_SUFFIXES):
                continue
            if self._is_path_blocked(path):
                continue
            candidates.append(path)

        # 优先级排序：根目录 > docs/ 顶层 > 其他；同优先级按字典序
        candidates.sort(key=self._docs_priority_key)
        candidates = candidates[: self._project_docs_max_files]

        results: list[dict] = []
        total_bytes = 0
        for path in candidates:
            if total_bytes >= self._project_docs_max_total_bytes:
                _diag(f'project_docs total_bytes limit reached: {total_bytes}>={self._project_docs_max_total_bytes}')
                break
            try:
                content = await self._gitlab_client.get_repository_file_raw(project_id, path, sha)
            except Exception as exc:
                _diag(f'project_docs fetch failed: path={path} err={type(exc).__name__}: {exc}')
                continue
            content, truncated = self._truncate_doc_content(content, self._project_docs_max_bytes_per_file)
            entry_bytes = len(content.encode('utf-8'))
            results.append({'path': path, 'content': content, 'truncated': truncated})
            total_bytes += entry_bytes
        return results

    @classmethod
    def _is_path_blocked(cls, path: str) -> bool:
        # 路径段精确命中黑名单则跳过；`.venv` 这类前缀放宽匹配
        segments = path.split('/')
        for seg in segments:
            if seg in cls._DOCS_BLOCKED_SEGMENTS:
                return True
            if any(seg.startswith(prefix) for prefix in cls._DOCS_BLOCKED_PREFIXES):
                return True
        return False

    @staticmethod
    def _docs_priority_key(path: str) -> tuple[int, str]:
        segments = path.split('/')
        if len(segments) == 1:
            return (0, path)
        if len(segments) == 2 and segments[0] == 'docs':
            return (1, path)
        return (2, path)

    @staticmethod
    def _truncate_doc_content(content: str, max_bytes: int) -> tuple[str, bool]:
        # 单文件 utf-8 字节超限时，按字符级切前 80% / 后 20%，中间塞 [...truncated...]，
        # 并用字节级二次裁剪兜底，确保最终字节数不超过 max_bytes
        encoded = content.encode('utf-8')
        if len(encoded) <= max_bytes:
            return content, False
        marker = '\n\n[...truncated...]\n\n'
        marker_bytes = len(marker.encode('utf-8'))
        budget = max(max_bytes - marker_bytes, 0)
        head_chars = max(int(len(content) * 0.8), 1)
        tail_chars = max(len(content) - head_chars, 0)
        # 按字符切片
        head = content[:head_chars]
        tail = content[-tail_chars:] if tail_chars > 0 else ''
        # 字节级裁剪：保证 head_bytes + tail_bytes <= budget
        head_budget = int(budget * 0.8)
        tail_budget = budget - head_budget
        head_safe = head.encode('utf-8')[:head_budget].decode('utf-8', errors='ignore')
        tail_safe = tail.encode('utf-8')[-tail_budget:].decode('utf-8', errors='ignore') if tail_budget > 0 else ''
        truncated_content = f'{head_safe}{marker}{tail_safe}'
        return truncated_content, True

    async def _load_version(self, project_id: int, mr_iid: int) -> MergeRequestVersion:
        version = await self._gitlab_client.get_merge_request_latest_version(project_id, mr_iid)
        if isinstance(version, MergeRequestVersion):
            return version
        return MergeRequestVersion(
            base_sha=version['base_sha'],
            start_sha=version['start_sha'],
            head_sha=version['head_sha'],
        )

    async def _create_inline_comments(
        self,
        job: ReviewJob,
        summary: ReviewSummary,
        changes: list[FileChange],
        version: MergeRequestVersion,
    ) -> tuple[int, int]:
        created = 0
        failed = 0
        change_map = self._build_change_map(changes)
        issues = [*summary.high_priority_issues, *summary.medium_priority_suggestions]

        for issue in issues:
            if not issue.file_path:
                failed += 1
                continue
            change = change_map.get(issue.file_path)
            if change is None:
                failed += 1
                continue
            position = resolve_issue_position(change=change, issue=issue, version=version)
            if position is None:
                failed += 1
                continue
            if issue.line_side is None:
                issue.line_side = 'new' if 'new_line' in position else 'old'
            await self._gitlab_client.create_merge_request_discussion(
                job.project_id,
                job.mr_iid,
                render_inline_issue_comment(issue),
                position,
            )
            created += 1

        return created, failed

    @staticmethod
    def _build_change_map(changes: list[FileChange]) -> dict[str, FileChange]:
        change_map: dict[str, FileChange] = {}
        for change in changes:
            for key in {change.file_path, change.old_path, change.new_path}:
                if key:
                    change_map[key] = change
        return change_map

    def _build_review_payload(
        self,
        changes: list[FileChange],
        commits: list[dict],
        commit_history: dict[str, list[dict]],
        project_docs: list[dict] | None = None,
    ) -> str:
        files = []
        for change in changes:
            history = commit_history.get(change.file_path) or commit_history.get(change.new_path) or commit_history.get(change.old_path) or []
            files.append(
                {
                    'file_path': change.file_path,
                    'old_path': change.old_path,
                    'new_path': change.new_path,
                    'change_type': self._change_type(change),
                    'final_diff': change.diff_text,
                    'commentable_lines': extract_commentable_lines(change.diff_text),
                    'commit_history': self._compact_commit_history(history),
                }
            )
        return json.dumps(
            {
                'meta': {
                    'total_files': len(changes),
                    'total_commits': len(commits),
                },
                'files': files,
                'project_docs': project_docs or [],
            },
            ensure_ascii=False,
        )

    @staticmethod
    def _compact_commit_history(history: list[dict]) -> dict:
        if not history:
            return {
                'touch_count': 0,
                'change_type_path': [],
                'recent_commits': [],
            }
        compact_commits = []
        for item in history[-5:]:
            compact_commits.append(
                {
                    'commit_id': item.get('commit_id', '')[:12],
                    'title': item.get('title', ''),
                    'change_type': item.get('change_type', ''),
                }
            )
        return {
            'touch_count': len(history),
            'change_type_path': [item.get('change_type', '') for item in history[:8]],
            'recent_commits': compact_commits,
            'first_commit': {
                'commit_id': history[0].get('commit_id', '')[:12],
                'title': history[0].get('title', ''),
                'change_type': history[0].get('change_type', ''),
            },
            'last_commit': {
                'commit_id': history[-1].get('commit_id', '')[:12],
                'title': history[-1].get('title', ''),
                'change_type': history[-1].get('change_type', ''),
            },
        }

    @staticmethod
    def _change_type(change: FileChange) -> str:
        if change.deleted_file:
            return 'deleted'
        if change.new_file:
            return 'new'
        if change.renamed_file:
            return 'renamed'
        return 'modified'

    async def _update(self, job: ReviewJob, body: str) -> None:
        if job.note_id is None:
            raise ValueError('note_id is required for status updates')
        await self._gitlab_client.update_review_comment(job.project_id, job.mr_iid, job.note_id, body)
