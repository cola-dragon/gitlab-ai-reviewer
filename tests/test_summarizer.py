from app.models import CoverageStats, Issue, ReviewSummary
from app.summarizer import render_inline_issue_comment, render_status_comment


def test_render_completed_comment_contains_chinese_sections_and_coverage():
    summary = ReviewSummary(
        overall_summary='本次改动存在较高风险，不建议直接合并。最关键的问题是事务边界不完整，建议优先补齐事务与回滚后再继续合并。',
        high_priority_issues=[
            Issue(
                severity='high',
                confidence='high',
                title='必须修改｜事务一致性｜事务边界不完整',
                reason='同一业务内存在多次写库，任一步骤失败都可能产生脏数据，进而导致订单状态与库存状态不一致。',
                suggestion='将相关写操作纳入同一事务，并补充失败回滚与异常路径测试。',
                file_path='src/order/service.py',
                line_start=88,
                line_end=88,
                line_side='new',
            )
        ],
        medium_priority_suggestions=[
            Issue(
                severity='medium',
                confidence='medium',
                title='建议修改｜可观测性｜关键失败路径缺少日志',
                reason='当前异常分支只返回错误结果，没有记录关键上下文，后续线上排障成本较高。',
                suggestion='在失败分支补充结构化日志，并记录必要的业务主键与错误原因。',
            ),
            Issue(
                severity='low',
                confidence='high',
                title='可选优化｜可维护性｜重复组装返回对象',
                reason='相同的返回结构在多个分支重复拼装，后续变更时容易遗漏。',
                suggestion='可考虑抽取统一的结果构造函数，减少重复逻辑。',
            ),
        ],
        uncertainty_notes=['缺少上下游补偿逻辑信息，建议补充确认异常回滚路径。'],
        coverage=CoverageStats(files_reviewed=3, total_files=3, commits_reviewed=5, total_commits=5, inline_comments_created=1, inline_comments_failed=0),
        merge_advice='do_not_merge',
    )

    comment = render_status_comment(status='completed', job_id='job-1', sha='abc', summary=summary)

    assert '审查状态：已完成（completed）' in comment
    assert '### 结论' in comment
    assert '- 合并建议：不建议合并' in comment
    assert '- 风险等级：高' in comment
    assert '### 发现的问题' in comment
    assert '### 建议修复' in comment
    assert '### 优化建议' in comment
    assert '必须修改｜事务一致性｜事务边界不完整' in comment
    assert '`src/order/service.py:88` (new)' in comment
    assert '建议修改｜可观测性｜关键失败路径缺少日志' in comment
    assert '可选优化｜可维护性｜重复组装返回对象' in comment
    assert '### 补充说明' in comment
    assert '已审查文件：3/3' in comment
    assert '已审查提交：5/5' in comment
    assert '行级评论：1 条已创建，0 条回落到总评' in comment
    assert '审查方式：整 MR 一次审查（GitHub 风格中文 Review）' in comment
    assert '<!-- ai-review:job_id=job-1 status=completed sha=abc -->' in comment


def test_render_inline_comment_contains_action_level_and_location():
    issue = Issue(
        severity='medium',
        confidence='high',
        title='建议修改｜异常处理｜吞掉下游异常',
        reason='当前捕获异常后直接返回默认值，会掩盖真实错误并导致排障困难。',
        suggestion='保留异常上下文，至少记录日志并区分可恢复与不可恢复错误。',
        file_path='app/service.py',
        line_start=32,
        line_end=32,
        line_side='new',
    )

    comment = render_inline_issue_comment(issue)

    assert '### Review note' in comment
    assert '**建议修改｜异常处理｜吞掉下游异常**' in comment
    assert '- 为什么需要改：当前捕获异常后直接返回默认值，会掩盖真实错误并导致排障困难。' in comment
    assert '- 建议改法：保留异常上下文，至少记录日志并区分可恢复与不可恢复错误。' in comment
    assert '- 置信度：高' in comment
    assert '- 位置：`app/service.py:32`' in comment


def test_render_failed_comment_contains_error_message_and_retry_hint():
    comment = render_status_comment(status='failed', job_id='job-2', sha='def', error_message='LLM timeout')

    assert '审查状态：执行失败（failed）' in comment
    assert 'LLM timeout' in comment
    assert 'Structured Outputs 支持情况' in comment
