import json
import logging

from app.core.logging import JsonFormatter


def test_json_formatter_includes_extra_fields_and_no_traceback_by_default() -> None:
    record = logging.LogRecord("x", logging.INFO, __file__, 1, "hello %s", ("world",), None)
    record.request_id = "abc"
    payload = json.loads(JsonFormatter().format(record))
    assert payload["message"] == "hello world"
    assert payload["request_id"] == "abc"
    assert "exception" not in payload
