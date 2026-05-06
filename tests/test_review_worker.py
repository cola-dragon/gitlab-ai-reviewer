import pytest

from app.models import CoverageStats, FileChange, Issue, ReviewJob, ReviewSummary, TriggerType
from app.review_worker import ReviewWorker


def _make_change(path='src/x.py'):
    return FileChange(
        file_path=path, old_path=path, new_path=path,
        diff_text='@@ -1 +1 @@\n-old\n+new\n',
        new_file=False, deleted_file=False, renamed_file=False,
    )


class FakeGitLabClient:
    def __init__(self, tree=None, file_contents=None, file_errors=None):
        self.updates = []
        self.discussions = []
        # 项目文档相关 stub：tree 为 list[dict]，file_contents 为 path->str，file_errors 为 path->Exception
        self.tree = tree if tree is not None else []
        self.file_contents = file_contents or {}
        self.file_errors = file_errors or {}
        self.tree_calls = 0
        self.file_calls: list[str] = []

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

    async def list_repository_tree(self, project_id: int, ref: str):
        self.tree_calls += 1
        return self.tree

    async def get_repository_file_raw(self, project_id: int, file_path: str, ref: str):
        self.file_calls.append(file_path)
        if file_path in self.file_errors:
            raise self.file_errors[file_path]
        return self.file_contents.get(file_path, '')


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


# ----------------------------- 项目文档拉取相关测试 -----------------------------

@pytest.mark.asyncio
async def test_load_project_docs_returns_empty_when_disabled():
    gitlab = FakeGitLabClient(tree=[{'path': 'README.md', 'type': 'blob'}],
                              file_contents={'README.md': 'hello'})
    worker = ReviewWorker(gitlab_client=gitlab, llm_client=FakeLLMClient(),
                          project_docs_enabled=False)

    docs = await worker._load_project_docs(1, 'sha-x')

    assert docs == []
    assert gitlab.tree_calls == 0
    assert gitlab.file_calls == []


@pytest.mark.asyncio
async def test_load_project_docs_priority_root_then_docs_then_others():
    tree = [
        {'path': 'src/inner/note.md', 'type': 'blob'},
        {'path': 'docs/guide.md', 'type': 'blob'},
        {'path': 'README.md', 'type': 'blob'},
        {'path': 'docs/sub/deep.md', 'type': 'blob'},  # 非 docs 顶层 → 第三优先级
        {'path': 'CONTRIBUTING.md', 'type': 'blob'},
    ]
    gitlab = FakeGitLabClient(
        tree=tree,
        file_contents={p['path']: f'content of {p["path"]}' for p in tree},
    )
    worker = ReviewWorker(gitlab_client=gitlab, llm_client=FakeLLMClient())

    docs = await worker._load_project_docs(1, 'sha')

    paths = [d['path'] for d in docs]
    # 根目录两个按字典序：CONTRIBUTING.md, README.md；之后 docs/guide.md；之后其他
    assert paths == ['CONTRIBUTING.md', 'README.md', 'docs/guide.md', 'docs/sub/deep.md', 'src/inner/note.md']


@pytest.mark.asyncio
async def test_load_project_docs_filters_blocked_paths_and_non_md():
    tree = [
        {'path': 'README.md', 'type': 'blob'},
        {'path': 'node_modules/lib/x.md', 'type': 'blob'},   # 黑名单
        {'path': '.venv/foo.md', 'type': 'blob'},            # 前缀黑名单
        {'path': '.venv313/bar.md', 'type': 'blob'},         # 前缀黑名单变体
        {'path': '.spec-workflow/templates/x.md', 'type': 'blob'},  # 黑名单
        {'path': 'src/main.py', 'type': 'blob'},             # 非 md
        {'path': 'docs/', 'type': 'tree'},                   # 非 blob
        {'path': 'README.txt', 'type': 'blob'},              # 非 md
    ]
    contents = {p['path']: 'x' for p in tree}
    gitlab = FakeGitLabClient(tree=tree, file_contents=contents)
    worker = ReviewWorker(gitlab_client=gitlab, llm_client=FakeLLMClient())

    docs = await worker._load_project_docs(1, 'sha')

    assert [d['path'] for d in docs] == ['README.md']


@pytest.mark.asyncio
async def test_load_project_docs_respects_max_files():
    tree = [{'path': f'doc_{i:02d}.md', 'type': 'blob'} for i in range(30)]
    contents = {p['path']: 'x' for p in tree}
    gitlab = FakeGitLabClient(tree=tree, file_contents=contents)
    worker = ReviewWorker(gitlab_client=gitlab, llm_client=FakeLLMClient(),
                          project_docs_max_files=20)

    docs = await worker._load_project_docs(1, 'sha')

    assert len(docs) == 20
    # 字典序前 20 个
    assert docs[0]['path'] == 'doc_00.md'
    assert docs[-1]['path'] == 'doc_19.md'


@pytest.mark.asyncio
async def test_load_project_docs_truncates_oversize_file():
    big_content = 'A' * 5000
    tree = [{'path': 'README.md', 'type': 'blob'}]
    gitlab = FakeGitLabClient(tree=tree, file_contents={'README.md': big_content})
    worker = ReviewWorker(gitlab_client=gitlab, llm_client=FakeLLMClient(),
                          project_docs_max_bytes_per_file=1024)

    docs = await worker._load_project_docs(1, 'sha')

    assert len(docs) == 1
    entry = docs[0]
    assert entry['truncated'] is True
    assert '[...truncated...]' in entry['content']
    assert len(entry['content'].encode('utf-8')) <= 1024


@pytest.mark.asyncio
async def test_load_project_docs_stops_at_total_bytes_limit():
    # 每个文件 600 字节，total 上限 1500 → 最多接入 3 个就停止（第 3 个之后跳出循环）
    tree = [{'path': f'd_{i}.md', 'type': 'blob'} for i in range(10)]
    contents = {p['path']: 'X' * 600 for p in tree}
    gitlab = FakeGitLabClient(tree=tree, file_contents=contents)
    worker = ReviewWorker(gitlab_client=gitlab, llm_client=FakeLLMClient(),
                          project_docs_max_bytes_per_file=1024,
                          project_docs_max_total_bytes=1500)

    docs = await worker._load_project_docs(1, 'sha')

    # 每次进循环前检查 total_bytes >= max_total_bytes，所以第 3 个加入后累计 1800 才会跳出，
    # 因此应当拉到 3 个文件
    assert len(docs) == 3


@pytest.mark.asyncio
async def test_load_project_docs_tolerates_individual_fetch_failure():
    tree = [
        {'path': 'README.md', 'type': 'blob'},
        {'path': 'broken.md', 'type': 'blob'},
        {'path': 'CONTRIBUTING.md', 'type': 'blob'},
    ]
    gitlab = FakeGitLabClient(
        tree=tree,
        file_contents={'README.md': 'r', 'CONTRIBUTING.md': 'c'},
        file_errors={'broken.md': RuntimeError('boom')},
    )
    worker = ReviewWorker(gitlab_client=gitlab, llm_client=FakeLLMClient())

    docs = await worker._load_project_docs(1, 'sha')

    paths = [d['path'] for d in docs]
    assert paths == ['CONTRIBUTING.md', 'README.md']  # broken.md 被跳过


@pytest.mark.asyncio
async def test_load_project_docs_tolerates_tree_failure():
    class _Boom:
        async def list_repository_tree(self, project_id, ref):
            raise RuntimeError('tree gone')

        async def get_repository_file_raw(self, *a, **kw):  # pragma: no cover - 不应被调用
            raise AssertionError('should not be called')

    worker = ReviewWorker(gitlab_client=_Boom(), llm_client=FakeLLMClient())
    docs = await worker._load_project_docs(1, 'sha')
    assert docs == []


def test_build_review_payload_includes_project_docs_field():
    worker = ReviewWorker(gitlab_client=FakeGitLabClient(), llm_client=FakeLLMClient())
    project_docs = [{'path': 'README.md', 'content': '# Hi', 'truncated': False}]

    payload = worker._build_review_payload(
        changes=[_make_change()], commits=[], commit_history={}, project_docs=project_docs,
    )

    assert '"project_docs"' in payload
    assert '"path": "README.md"' in payload
    assert '"truncated": false' in payload
