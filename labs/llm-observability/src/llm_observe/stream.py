"""Incremental SSE framing, independent of network chunk boundaries."""

import json


class SSE:
    def __init__(self) -> None:
        self.buffer = b""
        self.data: list[bytes] = []

    def feed(self, chunk: bytes) -> list[str]:
        self.buffer += chunk
        if len(self.buffer) + sum(map(len, self.data)) > 1024 * 1024:
            raise ValueError("SSE event exceeds diagnostic size limit")
        events = []
        while b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            line = line.removesuffix(b"\r")
            if not line:
                if self.data:
                    events.append(b"\n".join(self.data).decode("utf-8"))
                    self.data.clear()
            elif line.startswith(b"data:"):
                self.data.append(line[5:].removeprefix(b" "))
        return events


def event_flags(data: str) -> dict:
    if data == "[DONE]":
        return {"done": True}
    event = json.loads(data)
    choices = event.get("choices", [])
    return {
        "done": False,
        "token_ids": [token for choice in choices for token in choice.get("token_ids", []) or []],
        "visible": any((choice.get("delta") or {}).get("content") for choice in choices),
        "finish_reason": next(
            (c["finish_reason"] for c in choices if c.get("finish_reason")), None
        ),
        "usage": event.get("usage"),
        "error": event.get("error") is not None,
    }
