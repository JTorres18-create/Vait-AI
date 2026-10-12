
import json
import os
import tempfile
import threading
from pathlib import Path

# VAIT 1.0 - Cloud Memory System
# Keep memory separate from the original local AI.

BASE_DIR = Path(__file__).resolve().parent

MEMORY_DIR = Path(
    os.getenv("VAIT_MEMORY_DIR", str(BASE_DIR))
)

MEMORY_DIR.mkdir(parents=True, exist_ok=True)

MEMORY_FILE = MEMORY_DIR / "vait_memory.json"

CATEGORIES = [
    "interests",
    "preferences",
    "projects",
    "personal",
    "important"
]

memory_lock = threading.RLock()


def load_memory():
    """Read saved memories without erasing existing data."""

    if not MEMORY_FILE.exists():
        return {category: [] for category in CATEGORIES}

    with open(MEMORY_FILE, "r", encoding="utf-8") as file:
        memory = json.load(file)

    if not isinstance(memory, dict):
        raise ValueError("Memory file must contain a JSON object.")

    for category in CATEGORIES:
        memory.setdefault(category, [])

        if not isinstance(memory[category], list):
            raise ValueError(f"Invalid memory category: {category}")

    return memory


def save_memory(memory):
    """Write memories safely using a temporary file."""

    if not isinstance(memory, dict):
        raise ValueError("Memory must be a dictionary.")

    with memory_lock:
        fd, temp_path = tempfile.mkstemp(
            dir=MEMORY_DIR,
            prefix=".vait_memory_",
            suffix=".tmp"
        )

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                json.dump(memory, file, indent=4, ensure_ascii=False)

            os.replace(temp_path, MEMORY_FILE)

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


def remember(category, fact):
    """Remember a fact without saving duplicates."""

    if category not in CATEGORIES:
        raise ValueError("Unknown memory category.")

    fact = fact.strip()

    if not fact:
        return False

    with memory_lock:
        memory = load_memory()

        existing = [
            str(item).casefold()
            for item in memory[category]
        ]

        if fact.casefold() in existing:
            return False

        memory[category].append(fact)
        save_memory(memory)

    return True


def recall():
    """Return all stored memories."""

    with memory_lock:
        return load_memory()
