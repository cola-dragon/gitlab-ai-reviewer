from app.models import NoteEvent, MergeRequestEvent
from app.webhook_handler import should_trigger_auto_review, should_trigger_manual_review


def test_manual_trigger_matches_ai_username_review_case_insensitive():
    event = NoteEvent(
        project_id=1,
        merge_request_iid=2,
        note='  @AI_TEST review  ',
        note_id=101,
        object_attributes={},
    )

    assert should_trigger_manual_review(event, ai_username='ai_test') is True


def test_manual_trigger_rejects_wrong_username():
    event = NoteEvent(
        project_id=1,
        merge_request_iid=2,
        note='@ai review',
        note_id=102,
        object_attributes={},
    )

    assert should_trigger_manual_review(event, ai_username='ai_test') is False


def test_manual_trigger_rejects_other_commands():
    event = NoteEvent(
        project_id=1,
        merge_request_iid=2,
        note='@ai_test why',
        note_id=103,
        object_attributes={},
    )

    assert should_trigger_manual_review(event, ai_username='ai_test') is False


def test_auto_trigger_only_for_open_action():
    open_event = MergeRequestEvent(project_id=1, merge_request_iid=2, action='open', sha='abc')
    update_event = MergeRequestEvent(project_id=1, merge_request_iid=2, action='update', sha='abc')

    assert should_trigger_auto_review(open_event) is True
    assert should_trigger_auto_review(update_event) is False
