from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class TriggerType(StrEnum):
    AUTO = 'auto'
    MANUAL = 'manual'


@dataclass(slots=True)
class MergeRequestEvent:
    project_id: int
    merge_request_iid: int
    action: str
    sha: str


@dataclass(slots=True)
class NoteEvent:
    project_id: int
    merge_request_iid: int
    note: str
    note_id: int
    object_attributes: dict[str, Any]


@dataclass(slots=True)
class ReviewJob:
    job_id: str
    project_id: int
    mr_iid: int
    sha: str
    trigger_type: TriggerType
    note_id: int | None = None


@dataclass(slots=True)
class FileChange:
    file_path: str
    old_path: str
    new_path: str
    diff_text: str
    new_file: bool = False
    deleted_file: bool = False
    renamed_file: bool = False


@dataclass(slots=True)
class Issue:
    severity: str
    confidence: str
    title: str
    reason: str
    suggestion: str
    file_path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    line_side: str | None = None


@dataclass(slots=True)
class CoverageStats:
    files_reviewed: int
    total_files: int
    commits_reviewed: int
    total_commits: int
    inline_comments_created: int = 0
    inline_comments_failed: int = 0


@dataclass(slots=True)
class ReviewSummary:
    overall_summary: str
    high_priority_issues: list[Issue]
    medium_priority_suggestions: list[Issue]
    uncertainty_notes: list[str]
    coverage: CoverageStats
    merge_advice: str = 'fix_then_merge'
