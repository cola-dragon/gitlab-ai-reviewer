from __future__ import annotations

import asyncio
import json


def _diag(message: str) -> None:
    print(f'[DIAG] {message}', flush=True)

from app.diff_position import MergeRequestVersion, extract_commentable_lines, resolve_issue_position
from app.models import CoverageStats, FileChange, Issue, ReviewJob, ReviewSummary
from app.summarizer import render_inline_issue_comment, render_status_comment


class ReviewWorker:
    def __init__(self, gitlab_client, llm_client, empty_changes_retries: int = 3, empty_changes_delay: float = 3.0):
        self._gitlab_client = gitlab_client
        self._llm_client = llm_client
        self._empty_changes_retries = empty_changes_retries
        self._empty_changes_delay = empty_changes_delay

    async def run(self, job: ReviewJob) -> None:
        _diag(f'review_worker.run start: job_id={job.job_id} mr_iid={job.mr_iid} sha={job.sha}')
        await self._update(job, render_status_comment(status='running', job_id=job.job_id, sha=job.sha))

        try:
            changes = await self._load_changes_with_retry(job.project_id, job.mr_iid)
            _diag(f'review_worker changes loaded: count={len(changes)}')
            commits = await self._gitlab_client.list_merge_request_commits(job.project_id, job.mr_iid)
            _diag(f'review_worker commits loaded: count={len(commits)}')
            commit_history = await self._load_commit_history(job.project_id, commits)
            payload = self._build_review_payload(changes, commits, commit_history)
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

    def _build_review_payload(self, changes: list[FileChange], commits: list[dict], commit_history: dict[str, list[dict]]) -> str:
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
