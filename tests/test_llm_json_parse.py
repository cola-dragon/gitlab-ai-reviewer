from app.llm_client import LLMClient


def test_parse_json_text_accepts_plain_json():
    payload = LLMClient._parse_json_text('{"summary":"ok","issues":[]}')
    assert payload['summary'] == 'ok'


def test_parse_json_text_accepts_markdown_fenced_json():
    payload = LLMClient._parse_json_text('```json\n{"summary":"ok","issues":[]}\n```')
    assert payload['summary'] == 'ok'


def test_parse_json_text_extracts_json_from_wrapped_text():
    payload = LLMClient._parse_json_text('Here is the result:\n{"summary":"ok","issues":[]}')
    assert payload['summary'] == 'ok'
