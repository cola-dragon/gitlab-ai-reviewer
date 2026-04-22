import re

from app.models import MergeRequestEvent, NoteEvent


def should_trigger_manual_review(event: NoteEvent, *, ai_username: str) -> bool:
    pattern = rf'^\s*@{re.escape(ai_username)}\s+review\s*$'
    return re.match(pattern, event.note, flags=re.IGNORECASE) is not None


def should_trigger_auto_review(event: MergeRequestEvent) -> bool:
    return event.action == 'open'
