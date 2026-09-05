import pytest

from app.seed import CONTACTS
from app.tools import ToolError, Workspace


def test_send_message_appends_and_returns_result():
    ws = Workspace(CONTACTS)

    result = ws.send_message(contact_id="c_1", body="hi", idempotency_key="k1")

    assert result["contact_id"] == "c_1"
    assert "message_id" in result
    assert result["deduped"] is False
    assert len(ws.messages) == 1


def test_same_idempotency_key_twice_sends_once():
    ws = Workspace(CONTACTS)

    first = ws.send_message(contact_id="c_1", body="hi", idempotency_key="k1")
    second = ws.send_message(contact_id="c_1", body="hi again", idempotency_key="k1")

    assert len(ws.messages) == 1  # the assertion that actually matters
    assert second["deduped"] is True
    assert second["message_id"] == first["message_id"]


def test_missing_idempotency_key_raises():
    ws = Workspace(CONTACTS)
    with pytest.raises(ToolError):
        ws.send_message(contact_id="c_1", body="hi", idempotency_key="")


def test_missing_contact_id_raises():
    ws = Workspace(CONTACTS)
    with pytest.raises(ToolError):
        ws.send_message(contact_id="", body="hi", idempotency_key="k1")


def test_unknown_contact_raises():
    ws = Workspace(CONTACTS)
    with pytest.raises(ToolError):
        ws.send_message(contact_id="c_999", body="hi", idempotency_key="k1")