from app.diff_position import MergeRequestVersion, resolve_issue_position
from app.models import FileChange, Issue


def test_resolve_issue_position_for_added_line():
    change = FileChange(
        file_path='src/a.py',
        old_path='src/a.py',
        new_path='src/a.py',
        diff_text='@@ -10,2 +10,3 @@\n old\n+new line\n keep\n',
        new_file=False,
        deleted_file=False,
        renamed_file=False,
    )
    issue = Issue(
        severity='high',
        confidence='high',
        title='added line issue',
        reason='reason',
        suggestion='fix',
        file_path='src/a.py',
        line_start=11,
        line_end=11,
        line_side='new',
    )
    version = MergeRequestVersion(base_sha='base', start_sha='start', head_sha='head')

    position = resolve_issue_position(change=change, issue=issue, version=version)

    assert position == {
        'position_type': 'text',
        'base_sha': 'base',
        'start_sha': 'start',
        'head_sha': 'head',
        'old_path': 'src/a.py',
        'new_path': 'src/a.py',
        'new_line': 11,
    }


def test_resolve_issue_position_returns_none_for_missing_line():
    change = FileChange(
        file_path='src/a.py',
        old_path='src/a.py',
        new_path='src/a.py',
        diff_text='@@ -1 +1 @@\n-old\n+new\n',
        new_file=False,
        deleted_file=False,
        renamed_file=False,
    )
    issue = Issue(
        severity='high',
        confidence='high',
        title='missing line',
        reason='reason',
        suggestion='fix',
        file_path='src/a.py',
        line_start=9,
        line_end=9,
        line_side='new',
    )
    version = MergeRequestVersion(base_sha='base', start_sha='start', head_sha='head')

    assert resolve_issue_position(change=change, issue=issue, version=version) is None


def test_resolve_issue_position_infers_new_side_when_missing():
    change = FileChange(
        file_path='src/a.py',
        old_path='src/a.py',
        new_path='src/a.py',
        diff_text='@@ -10,1 +10,2 @@\n old\n+danger\n',
        new_file=False,
        deleted_file=False,
        renamed_file=False,
    )
    issue = Issue(
        severity='high',
        confidence='high',
        title='missing side',
        reason='reason',
        suggestion='fix',
        file_path='src/a.py',
        line_start=11,
        line_end=11,
        line_side=None,
    )
    version = MergeRequestVersion(base_sha='base', start_sha='start', head_sha='head')

    position = resolve_issue_position(change=change, issue=issue, version=version)

    assert position == {
        'position_type': 'text',
        'base_sha': 'base',
        'start_sha': 'start',
        'head_sha': 'head',
        'old_path': 'src/a.py',
        'new_path': 'src/a.py',
        'new_line': 11,
    }


def test_resolve_issue_position_returns_none_when_side_is_ambiguous():
    change = FileChange(
        file_path='src/a.py',
        old_path='src/a.py',
        new_path='src/a.py',
        diff_text='@@ -10,1 +10,1 @@\n keep\n',
        new_file=False,
        deleted_file=False,
        renamed_file=False,
    )
    issue = Issue(
        severity='high',
        confidence='high',
        title='ambiguous side',
        reason='reason',
        suggestion='fix',
        file_path='src/a.py',
        line_start=10,
        line_end=10,
        line_side=None,
    )
    version = MergeRequestVersion(base_sha='base', start_sha='start', head_sha='head')

    assert resolve_issue_position(change=change, issue=issue, version=version) is None
