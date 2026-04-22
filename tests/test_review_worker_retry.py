import pytest

from app.models import CoverageStats, FileChange, Issue, ReviewJob, ReviewSummary, TriggerType
from app.review_worker import ReviewWorker


class FlakyGitLabClient:
    def __init__(self):
        self.calls = 0
        self.updates = []
        self.discussions = []

    async def get_merge_request_changes(self, project_id: int, mr_iid: int):
        self.calls += 1
        if self.calls == 1:
            return []
        return [
            FileChange(
                file_path='src/a.py',
                old_path='src/a.py',
                new_path='src/a.py',
                diff_text='@@ -1 +1 @@\n-old\n+danger\n',
                new_file=False,
                deleted_file=False,
                renamed_file=False,
            )
        ]

    async def list_merge_request_commits(self, project_id: int, mr_iid: int):
        return [{'id': 'c1', 'title': 'danger'}]

    async def get_commit_diff(self, project_id: int, commit_id: str):
        return []

    async def get_merge_request_latest_version(self, project_id: int, mr_iid: int):
        return {'base_sha': 'base', 'start_sha': 'start', 'head_sha': 'head'}

    async def create_merge_request_discussion(self, project_id: int, mr_iid: int, body: str, position: dict):
        self.discussions.append((body, position))

    async def update_review_comment(self, project_id: int, mr_iid: int, note_id: int, body: str):
        self.updates.append(body)


class FakeLLMClient:
    async def review_merge_request(self, review_payload: str):
        return ReviewSummary(
            overall_summary='不建议合并，检测到高危 TLS 风险',
            high_priority_issues=[
                Issue(
                    severity='high',
                    confidence='high',
                    title='关闭 TLS 校验',
                    reason='会导致中间人攻击风险',
                    suggestion='恢复证书校验',
                    file_path='src/a.py',
                    line_start=1,
                    line_end=1,
                    line_side='new',
                )
            ],
            medium_priority_suggestions=[],
            uncertainty_notes=[],
            coverage=CoverageStats(files_reviewed=0, total_files=0, commits_reviewed=0, total_commits=0, inline_comments_created=0, inline_comments_failed=0),
            merge_advice='do_not_merge',
        )


@pytest.mark.asyncio
async def test_review_worker_retries_when_changes_temporarily_empty():
    gitlab = FlakyGitLabClient()
    worker = ReviewWorker(gitlab_client=gitlab, llm_client=FakeLLMClient(), empty_changes_retries=2, empty_changes_delay=0)
    job = ReviewJob(job_id='job-retry', project_id=1, mr_iid=1, sha='abc', trigger_type=TriggerType.MANUAL, note_id=99)

    await worker.run(job)

    assert gitlab.calls == 2
    assert any('已审查文件：1/1' in update for update in gitlab.updates)
    assert any('行级评论：1 条已创建' in update for update in gitlab.updates)
