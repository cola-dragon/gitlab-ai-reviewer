from __future__ import annotations

import re

from app.models import Issue, ReviewSummary

MARKER_RE = re.compile(r'<!-- ai-review:job_id=(?P<job_id>[^\s]+) status=(?P<status>[^\s]+) sha=(?P<sha>[^\s]+) -->')

STATUS_LABELS = {
    'queued': '排队中',
    'running': '审查中',
    'completed': '已完成',
    'failed': '执行失败',
    'skipped': '已跳过',
}

SEVERITY_LABELS = {
    'high': '高风险',
    'medium': '中风险',
    'low': '低风险',
}

ACTION_LEVEL_LABELS = {
    'high': '必须修改',
    'medium': '建议修改',
    'low': '可选优化',
}

CONFIDENCE_LABELS = {
    'high': '高',
    'medium': '中',
    'low': '低',
}

MERGE_ADVICE_LABELS = {
    'can_merge': '可以合并',
    'fix_then_merge': '建议修复后合并',
    'do_not_merge': '不建议合并',
}


def parse_ai_review_marker(body: str) -> dict[str, str] | None:
    match = MARKER_RE.search(body)
    if not match:
        return None
    return match.groupdict()


def _label(mapping: dict[str, str], key: str, default: str) -> str:
    return mapping.get(key.lower(), default) if key else default


def _issue_location(issue: Issue) -> str | None:
    if not issue.file_path or issue.line_start is None:
        return None
    if issue.line_end and issue.line_end != issue.line_start:
        return f'{issue.file_path}:{issue.line_start}-{issue.line_end}'
    return f'{issue.file_path}:{issue.line_start}'


def _split_non_blocking_issues(issues: list[Issue]) -> tuple[list[Issue], list[Issue]]:
    suggestions = [issue for issue in issues if issue.severity == 'medium']
    optimizations = [issue for issue in issues if issue.severity == 'low']
    return suggestions, optimizations


def _render_issue_list(issues: list[Issue], *, empty_text: str) -> str:
    if not issues:
        return f'- {empty_text}'

    lines = []
    for index, issue in enumerate(issues, start=1):
        action_level = _label(ACTION_LEVEL_LABELS, issue.severity, issue.severity)
        severity = _label(SEVERITY_LABELS, issue.severity, issue.severity)
        confidence = _label(CONFIDENCE_LABELS, issue.confidence, issue.confidence)
        lines.append(f'{index}. **[{action_level}][{severity}][置信度：{confidence}] {issue.title}**')
        location = _issue_location(issue)
        if location:
            lines.append(f'   - 位置：`{location}` ({issue.line_side or "unknown"})')
        lines.append(f'   - 影响：{issue.reason}')
        lines.append(f'   - 建议：{issue.suggestion}')
    return '\n'.join(lines)


def _derive_risk_level(summary: ReviewSummary) -> str:
    if summary.high_priority_issues or summary.merge_advice == 'do_not_merge':
        return '高'
    if summary.medium_priority_suggestions or summary.merge_advice == 'fix_then_merge':
        return '中'
    return '低'


def render_inline_issue_comment(issue: Issue) -> str:
    action_level = _label(ACTION_LEVEL_LABELS, issue.severity, issue.severity)
    confidence = _label(CONFIDENCE_LABELS, issue.confidence, issue.confidence)
    location = _issue_location(issue)
    title = issue.title if issue.title.startswith(f'{action_level}｜') else f'{action_level}｜{issue.title}'
    lines = [
        '### Review note',
        f'**{title}**',
        f'- 为什么需要改：{issue.reason}',
        f'- 建议改法：{issue.suggestion}',
        f'- 置信度：{confidence}',
    ]
    if location:
        lines.append(f'- 位置：`{location}`')
    return '\n'.join(lines)


def render_status_comment(
    *,
    status: str,
    job_id: str,
    sha: str,
    summary: ReviewSummary | None = None,
    error_message: str | None = None,
) -> str:
    status_label = STATUS_LABELS.get(status, status)
    lines = ['## AI 代码审查报告', f'审查状态：{status_label}（{status}）', '']

    if status == 'completed' and summary is not None:
        merge_advice = MERGE_ADVICE_LABELS.get(summary.merge_advice, summary.merge_advice)
        suggestions, optimizations = _split_non_blocking_issues(summary.medium_priority_suggestions)
        lines.extend(
            [
                '### 结论',
                f'- 合并建议：{merge_advice}',
                f'- 风险等级：{_derive_risk_level(summary)}',
                f'- 一句话判断：{summary.overall_summary}',
                '',
                '### 发现的问题',
                _render_issue_list(summary.high_priority_issues, empty_text='当前未发现阻塞合并的关键问题'),
                '',
                '### 建议修复',
                _render_issue_list(suggestions, empty_text='当前未发现需要优先处理的工程性问题'),
                '',
                '### 优化建议',
                _render_issue_list(optimizations, empty_text='当前未发现具有明确收益的可选优化项'),
            ]
        )
        if summary.uncertainty_notes:
            lines.extend(['', '### 补充说明', *[f'- {note}' for note in summary.uncertainty_notes]])
        lines.extend(
            [
                '',
                '### 本次审查范围',
                f'- 已审查文件：{summary.coverage.files_reviewed}/{summary.coverage.total_files}',
                f'- 已审查提交：{summary.coverage.commits_reviewed}/{summary.coverage.total_commits}',
                f'- 行级评论：{summary.coverage.inline_comments_created} 条已创建，{summary.coverage.inline_comments_failed} 条回落到总评',
                '- 审查依据：MR 最终 diff + MR 内提交历史摘要',
                '- 审查方式：整 MR 一次审查（GitHub 风格中文 Review）',
            ]
        )
    elif status == 'failed':
        lines.extend(
            [
                '### 审查结果',
                '- 本次 AI 审查执行失败，未能生成有效审查结论。',
                f'- 失败原因：{error_message or "unknown error"}',
                '- 处理建议：检查 LLM 配置、GitLab API 权限、Structured Outputs 支持情况或网络连通性后重新触发。',
            ]
        )
    elif status == 'queued':
        lines.extend(
            [
                '### 审查结果',
                '- 当前已有审查任务执行中，本次请求已进入队列。',
                '- 后续将自动开始，无需重复 @AI。',
            ]
        )
    elif status == 'running':
        lines.extend(
            [
                '### 审查结果',
                '- 已受理本次审查请求，正在后台拉取 MR 最终 diff 与提交历史。',
                '- 当前使用整 MR 一次审查模式，并输出更适合人工阅读的中文 Review。',
            ]
        )
    elif status == 'skipped':
        lines.extend(
            [
                '### 审查结果',
                '- 本次请求未进入执行队列。',
                f'- 原因：{error_message or "检测到重复触发"}',
            ]
        )

    lines.extend(['', f'<!-- ai-review:job_id={job_id} status={status} sha={sha} -->'])
    return '\n'.join(lines)
