from __future__ import annotations

import re
from dataclasses import dataclass

from app.models import FileChange, Issue

HUNK_RE = re.compile(r'^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? \+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@')


@dataclass(slots=True)
class MergeRequestVersion:
    base_sha: str
    start_sha: str
    head_sha: str


@dataclass(slots=True)
class DiffLineSets:
    old_commentable: set[int]
    new_commentable: set[int]
    old_changed: set[int]
    new_changed: set[int]


def extract_commentable_lines(diff_text: str) -> list[dict]:
    commentable_lines: list[dict] = []
    current_old: int | None = None
    current_new: int | None = None

    for line in diff_text.splitlines():
        match = HUNK_RE.match(line)
        if match:
            current_old = int(match.group('old_start'))
            current_new = int(match.group('new_start'))
            continue
        if current_old is None or current_new is None:
            continue
        if line.startswith('\\'):
            continue
        if line.startswith('+') and not line.startswith('+++'):
            commentable_lines.append({'side': 'new', 'line': current_new, 'text': line[1:]})
            current_new += 1
            continue
        if line.startswith('-') and not line.startswith('---'):
            commentable_lines.append({'side': 'old', 'line': current_old, 'text': line[1:]})
            current_old += 1
            continue

        current_old += 1
        current_new += 1

    return commentable_lines


def resolve_issue_position(*, change: FileChange, issue: Issue, version: MergeRequestVersion) -> dict | None:
    if issue.line_start is None:
        return None

    line_sets = _collect_line_sets(change.diff_text)
    line_side = issue.line_side or _infer_line_side(issue.line_start, line_sets)
    if line_side is None:
        return None

    position = {
        'position_type': 'text',
        'base_sha': version.base_sha,
        'start_sha': version.start_sha,
        'head_sha': version.head_sha,
        'old_path': change.old_path,
        'new_path': change.new_path,
    }

    if line_side == 'new' and issue.line_start in line_sets.new_commentable:
        return position | {'new_line': issue.line_start}
    if line_side == 'old' and issue.line_start in line_sets.old_commentable:
        return position | {'old_line': issue.line_start}
    return None


def _collect_line_sets(diff_text: str) -> DiffLineSets:
    old_commentable: set[int] = set()
    new_commentable: set[int] = set()
    old_changed: set[int] = set()
    new_changed: set[int] = set()
    current_old: int | None = None
    current_new: int | None = None

    for line in diff_text.splitlines():
        match = HUNK_RE.match(line)
        if match:
            current_old = int(match.group('old_start'))
            current_new = int(match.group('new_start'))
            continue
        if current_old is None or current_new is None:
            continue
        if line.startswith('\\'):
            continue
        if line.startswith('+') and not line.startswith('+++'):
            new_commentable.add(current_new)
            new_changed.add(current_new)
            current_new += 1
            continue
        if line.startswith('-') and not line.startswith('---'):
            old_commentable.add(current_old)
            old_changed.add(current_old)
            current_old += 1
            continue

        old_commentable.add(current_old)
        new_commentable.add(current_new)
        current_old += 1
        current_new += 1

    return DiffLineSets(
        old_commentable=old_commentable,
        new_commentable=new_commentable,
        old_changed=old_changed,
        new_changed=new_changed,
    )


def _infer_line_side(line_number: int, line_sets: DiffLineSets) -> str | None:
    if line_number in line_sets.new_changed and line_number not in line_sets.old_changed:
        return 'new'
    if line_number in line_sets.old_changed and line_number not in line_sets.new_changed:
        return 'old'

    in_old = line_number in line_sets.old_commentable
    in_new = line_number in line_sets.new_commentable
    if in_new and not in_old:
        return 'new'
    if in_old and not in_new:
        return 'old'
    return None
