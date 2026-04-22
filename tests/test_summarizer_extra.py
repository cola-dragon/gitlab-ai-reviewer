from app.summarizer import parse_ai_review_marker, render_status_comment


def test_parse_ai_review_marker_reads_hidden_comment():
    body = 'abc\n<!-- ai-review:job_id=job1 status=completed sha=abc123 -->'
    marker = parse_ai_review_marker(body)

    assert marker == {'job_id': 'job1', 'status': 'completed', 'sha': 'abc123'}


def test_render_skipped_comment_contains_reason():
    comment = render_status_comment(status='skipped', job_id='dup', sha='abc', error_message='已有相同 sha 的 review 结果')
    assert '审查状态：已跳过（skipped）' in comment
    assert '已有相同 sha 的 review 结果' in comment
