from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import project_sessions_dir


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def estimate_tokens(text: str) -> int:
    """A deliberately rough, dependency-free token estimate (not an exact tokenizer)."""
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def _estimate_content_tokens(content: Any) -> int:
    if isinstance(content, str):
        return estimate_tokens(content)
    if isinstance(content, list):
        total = 0
        for part in content:
            if not isinstance(part, dict):
                total += estimate_tokens(str(part))
                continue
            if part.get("type") == "text":
                total += estimate_tokens(str(part.get("text", "")))
            elif part.get("type") == "zeqou_image_ref":
                # Vision token costs vary by model; estimate from the image area
                # rather than counting only its local filename as the old code did.
                width = max(1, int(part.get("width", 1024) or 1024))
                height = max(1, int(part.get("height", 1024) or 1024))
                total += max(256, min(8_000, (width * height + 767) // 768))
            elif part.get("type") == "image_url":
                # Never count base64 image bytes as text tokens when provider
                # usage is unavailable; use a deliberately rough vision budget.
                total += 1_024
            else:
                total += estimate_tokens(json.dumps(part, ensure_ascii=False))
        return total
    if content is None:
        return 0
    return estimate_tokens(json.dumps(content, ensure_ascii=False))


def estimate_messages_tokens(messages: list[dict[str, Any]]) -> int:
    total = 0
    for message in messages:
        total += estimate_tokens(str(message.get("role", ""))) + 3
        total += _estimate_content_tokens(message.get("content", ""))
        if message.get("tool_calls"):
            total += estimate_tokens(json.dumps(message["tool_calls"], ensure_ascii=False))
        if message.get("tool_call_id"):
            total += estimate_tokens(str(message["tool_call_id"]))
    return total + 2


class SessionStore:
    def __init__(self, cwd: Path) -> None:
        self.cwd = cwd.resolve()
        self.directory = project_sessions_dir(self.cwd)

    def _path(self, session_id: str) -> Path:
        if not session_id.replace("-", "").isalnum() or len(session_id) > 64:
            raise ValueError("Invalid session ID")
        return self.directory / f"{session_id}.json"

    def save(self, session: dict[str, Any]) -> None:
        session["updated_at"] = now_iso()
        path = self._path(str(session["id"]))
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(path)

    def load(self, session_id: str) -> dict[str, Any]:
        path = self._path(session_id)
        session = json.loads(path.read_text(encoding="utf-8"))
        if Path(session.get("cwd", "")).resolve() != self.cwd:
            raise ValueError("This session belongs to a different project directory")
        return session

    def new(self, system_prompt: str, title: str = "New session") -> dict[str, Any]:
        session_id = datetime.now().strftime("%y%m%d-%H%M%S") + "-" + secrets.token_hex(3)
        session = {
            "id": session_id,
            "title": title,
            "cwd": str(self.cwd),
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "messages": [{"role": "system", "content": system_prompt}],
            "usage": {"input_tokens": 0, "output_tokens": 0, "estimated_input_tokens": 0, "calls": 0},
            "last_turn": {"input_tokens": 0, "output_tokens": 0, "exact": False, "calls": 0},
            "last_context": {"tokens": 0, "exact": False},
        }
        self.save(session)
        return session

    def list(self) -> list[dict[str, Any]]:
        sessions: list[dict[str, Any]] = []
        for path in self.directory.glob("*.json"):
            try:
                item = json.loads(path.read_text(encoding="utf-8"))
                if item.get("cwd") and Path(item["cwd"]).resolve() == self.cwd:
                    sessions.append(item)
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                continue
        return sorted(sessions, key=lambda x: x.get("updated_at", ""), reverse=True)

    def latest(self) -> dict[str, Any] | None:
        items = self.list()
        return items[0] if items else None

    def delete(self, session_id: str) -> None:
        self._path(session_id).unlink(missing_ok=True)

    def snapshot(self, session: dict[str, Any], suffix: str = "backup") -> Path:
        folder = self.directory / "backups"
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = folder / f"{session['id']}-{stamp}-{suffix}.json"
        target.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")
        return target
