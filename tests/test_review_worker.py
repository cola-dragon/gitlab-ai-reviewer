import pytest

from app.models import CoverageStats, FileChange, Issue, ReviewJob, ReviewSummary, TriggerType
from app.review_worker import ReviewWorker


class FakeGitLabClient:
    def __init__(self):
        self.updates = []
        self.discussions = []

    async def get_merge_request_changes(self, project_id: int, mr_iid: int):
        return [
            FileChange(
                file_path='src/a.py',
                old_path='src/a.py',
                new_path='src/a.py',
                diff_text='@@ -10,2 +10,3 @@\n old\n+danger\n keep\n',
                new_file=False,
                deleted_file=False,
                renamed_file=False,
            ),
            FileChange(
                file_path='docs/guide.md',
                old_path='docs/guide.md',
                new_path='docs/guide.md',
                diff_text='@@ -1 +1 @@\n-old\n+new\n',
                new_file=False,
                deleted_file=False,
                renamed_file=False,
            ),
        ]

    async def list_merge_request_commits(self, project_id: int, mr_iid: int):
        return [{'id': 'c1', 'title': 'update a'}, {'id': 'c2', 'title': 'update docs'}]

    async def get_commit_diff(self, project_id: int, commit_id: str):
        if commit_id == 'c1':
            return [
                FileChange(
                    file_path='src/a.py',
                    old_path='src/a.py',
                    new_path='src/a.py',
                    diff_text='@@ -10,1 +10,2 @@\n old\n+danger\n',
                    new_file=False,
                    deleted_file=False,
                    renamed_file=False,
                )
            ]
        return []

    async def get_merge_request_latest_version(self, project_id: int, mr_iid: int):
        return {'base_sha': 'base', 'start_sha': 'start', 'head_sha': 'head'}

    async def create_merge_request_discussion(self, project_id: int, mr_iid: int, body: str, position: dict):
        self.discussions.append((body, position))

    async def update_review_comment(self, project_id: int, mr_iid: int, note_id: int, body: str):
        self.updates.append(body)


class FakeLLMClient:
    async def review_merge_request(self, review_payload: str):
        assert 'commit_history' in review_payload
        assert 'src/a.py' in review_payload
        assert 'commentable_lines' in review_payload
        assert '"side": "new"' in review_payload
        assert '"line": 11' in review_payload
        assert 'danger' in review_payload
        return ReviewSummary(
            overall_summary='存在高危风险，不建议合并。',
            high_priority_issues=[
                Issue(
                    severity='high',
                    confidence='high',
                    title='安全风险｜危险代码',
                    reason='reason',
                    suggestion='fix',
                    file_path='src/a.py',
                    line_start=11,
                    line_end=11,
                    line_side=None,
                )
            ],
            medium_priority_suggestions=[],
            uncertainty_notes=[],
            coverage=CoverageStats(files_reviewed=0, total_files=0, commits_reviewed=0, total_commits=0, inline_comments_created=0, inline_comments_failed=0),
            merge_advice='do_not_merge',
        )


@pytest.mark.asyncio
async def test_review_worker_updates_summary_and_creates_inline_discussion():
    gitlab = FakeGitLabClient()
    worker = ReviewWorker(gitlab_client=gitlab, llm_client=FakeLLMClient())
    job = ReviewJob(job_id='job-1', project_id=1, mr_iid=2, sha='abc', trigger_type=TriggerType.AUTO, note_id=99)

    await worker.run(job)

    assert any('审查状态：审查中（running）' in update for update in gitlab.updates)
    assert any('审查状态：已完成（completed）' in update for update in gitlab.updates)
    completed = gitlab.updates[-1]
    assert '已审查文件：2/2' in completed
    assert '已审查提交：2/2' in completed
    assert '行级评论：1 条已创建' in completed
    assert len(gitlab.discussions) == 1
    assert gitlab.discussions[0][1]['new_line'] == 11


def test_build_review_payload_compacts_commit_history():
    worker = ReviewWorker(gitlab_client=FakeGitLabClient(), llm_client=FakeLLMClient())
    changes = [
        FileChange(
            file_path='src/a.py',
            old_path='src/a.py',
            new_path='src/a.py',
            diff_text='@@ -1 +1 @@\n-old\n+new\n',
            new_file=False,
            deleted_file=False,
            renamed_file=False,
        )
    ]
    commits = [
        {'id': 'c1abcdef', 'title': 'first'},
        {'id': 'c2abcdef', 'title': 'second'},
    ]
    history = {
        'src/a.py': [
            {'commit_id': 'c1abcdef', 'title': 'first', 'file_path': 'src/a.py', 'change_type': 'modified', 'diff': '+ one\n- two'},
            {'commit_id': 'c2abcdef', 'title': 'second', 'file_path': 'src/a.py', 'change_type': 'modified', 'diff': '+ three'},
        ]
    }

    payload = worker._build_review_payload(changes, commits, history)

    assert 'touch_count' in payload
    assert 'recent_commits' in payload
    assert 'c1abcdef' in payload
    assert '+ one' not in payload
    assert '+ three' not in payload


def test_build_review_payload_includes_commentable_changed_lines():
    worker = ReviewWorker(gitlab_client=FakeGitLabClient(), llm_client=FakeLLMClient())
    changes = [
        FileChange(
            file_path='src/a.py',
            old_path='src/a.py',
            new_path='src/a.py',
            diff_text='@@ -10,2 +10,3 @@\n old\n+danger\n keep\n',
            new_file=False,
            deleted_file=False,
            renamed_file=False,
        )
    ]

    payload = worker._build_review_payload(changes, commits=[], commit_history={})

    assert 'commentable_lines' in payload
    assert '"side": "new"' in payload
    assert '"line": 11' in payload
    assert 'danger' in payload
    assert '"text": "keep"' not in payload
