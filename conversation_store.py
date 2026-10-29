"""VAIT's private, bounded recent conversation history.

Keeps a small number of recent user/assistant turns on the same storage
as VAIT's existing long-term memories. Does not edit vait_memory.json.
"""

import json
import os
import tempfile
import threading

from memory_store import MEMORY_DIR

HISTORY_FILE = MEMORY_DIR / "vait_recent_history.json"
MAX_MESSAGES = 16  # Most recent eight exchanges.
_LOCK = threading.RLock()


def get_recent_messages():
    """Read a sanitized recent message list for the OpenAI Responses API."""
    with _LOCK:
        if not HISTORY_FILE.exists():
            return []
        with open(HISTORY_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, list):
            raise ValueError("Conversation history must be a list.")
        recent = []
        for item in data[-MAX_MESSAGES:]:
            if (
                isinstance(item, dict)
                and item.get("role") in ("user", "assistant")
                and isinstance(item.get("content"), str)
            ):
                recent.append({"role": item["role"], "content": item["content"]})
        return recent


def save_exchange(user_text, assistant_text):
    """Atomically append a successful exchange without changing long-term memory."""
    if not isinstance(user_text, str) or not isinstance(assistant_text, str):
        raise TypeError("Conversation messages must be strings.")
    with _LOCK:
        messages = get_recent_messages()
        messages.extend((
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": assistant_text},
        ))
        messages = messages[-MAX_MESSAGES:]
        fd, temporary_path = tempfile.mkstemp(
            prefix=".vait_conversation_", suffix=".tmp", dir=MEMORY_DIR
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                json.dump(messages, file, ensure_ascii=False, indent=2)
            os.replace(temporary_path, HISTORY_FILE)
        finally:
            if os.path.exists(temporary_path):
                os.remove(temporary_path)
