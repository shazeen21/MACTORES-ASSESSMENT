"""The tools the agent can call, and the toy world they operate on.

The domain is deliberately boring — a handful of CRM-ish contacts. Nobody is being assessed on
contact management. What matters is the machinery around the tools: which ones are allowed to run,
whether they can be safely retried, and whether we can prove afterwards what they did.

PROVIDED: Workspace read tools, update_contact, ToolDef, build_registry.
TASK 4b:  send_message.
"""



from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.models import ToolKind


class ToolError(Exception):
    """A tool failed in a way the agent might be able to work around."""


class Workspace:
    """The in-memory world the tools act on. One per run, so runs can't interfere with each other."""

    def __init__(self, contacts: list[dict[str, Any]] | None = None):
        self.contacts: dict[str, dict[str, Any]] = {c["id"]: dict(c) for c in (contacts or [])}
        self.messages: list[dict[str, Any]] = []
        self._idem: dict[str, dict[str, Any]] = {}

    def search_contacts(self, query: str = "", **_: Any) -> list[dict[str, Any]]:
        q = (query or "").lower()
        return [
            {k: c[k] for k in ("id", "name", "email", "stage")}
            for c in self.contacts.values()
            if q in c["name"].lower() or q in c.get("email", "").lower()
        ]

    def get_contact(self, contact_id: str = "", **_: Any) -> dict[str, Any]:
        contact = self.contacts.get(contact_id)
        if contact is None:
            raise ToolError(f"contact {contact_id!r} not found")
        return dict(contact)

    def update_contact(
        self, contact_id: str = "", fields: dict | None = None, **_: Any
    ) -> dict[str, Any]:
        contact = self.contacts.get(contact_id)
        if contact is None:
            raise ToolError(f"contact {contact_id!r} not found")
        contact.update(fields or {})
        return dict(contact)

    def send_message(
        self, contact_id: str = "", body: str = "", idempotency_key: str = "", **_: Any
    ) -> dict[str, Any]:
        if not contact_id or not idempotency_key:
            raise ToolError("send_message requires both contact_id and idempotency_key")

        if contact_id not in self.contacts:
            raise ToolError(f"contact {contact_id!r} not found")

        if idempotency_key in self._idem:
            stored = dict(self._idem[idempotency_key])
            stored["deduped"] = True
            return stored

        message_id = f"m_{len(self.messages)}"
        self.messages.append({"message_id": message_id, "contact_id": contact_id, "body": body})

        result = {"message_id": message_id, "contact_id": contact_id, "deduped": False}
        self._idem[idempotency_key] = result
        return result


@dataclass(frozen=True)
class ToolDef:
    name: str
    kind: ToolKind
    func: Callable[..., Any]
    description: str = ""


def build_registry(ws: Workspace) -> dict[str, ToolDef]:
    return {
        "search_contacts": ToolDef(
            "search_contacts", "read", ws.search_contacts, "Find contacts by name or email."
        ),
        "get_contact": ToolDef("get_contact", "read", ws.get_contact, "Fetch one contact by id."),
        "update_contact": ToolDef(
            "update_contact", "write", ws.update_contact, "Update fields on a contact."
        ),
        "send_message": ToolDef(
            "send_message", "write", ws.send_message, "Send a message to a contact (idempotent)."
        ),
    }
 