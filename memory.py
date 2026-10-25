import json
import os
import threading
from datetime import datetime

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DATA_DIR = BASE_DIR  # replaced by set_profile()


def set_profile(name):
    """Each profile (personal, professional, ...) gets its own folder, so memories never mix."""
    global DATA_DIR
    safe = "".join(c for c in name.lower() if c.isalnum() or c in "-_") or "personal"
    DATA_DIR = os.path.join(BASE_DIR, safe)
    os.makedirs(DATA_DIR, exist_ok=True)
    return safe


def _path(name):
    return os.path.join(DATA_DIR, name)


def load_json(name, default):
    try:
        with open(_path(name), "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(name, obj):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = _path(name) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
    os.replace(tmp, _path(name))


class Memory:
    """Long-term facts about the user, plus short rolling chat history."""

    def __init__(self):
        self.lock = threading.Lock()
        self.facts = load_json("facts.json", [])  # [{"fact": str, "ts": iso}]

    def add(self, fact: str) -> bool:
        fact = fact.strip()
        if not fact:
            return False
        with self.lock:
            if any(fact.lower() == f["fact"].lower() for f in self.facts):
                return False
            self.facts.append({"fact": fact, "ts": datetime.now().isoformat(timespec="seconds")})
            save_json("facts.json", self.facts)
            return True

    def forget(self, needle: str) -> int:
        with self.lock:
            before = len(self.facts)
            self.facts = [f for f in self.facts if needle.lower() not in f["fact"].lower()]
            save_json("facts.json", self.facts)
            return before - len(self.facts)

    def as_text(self, limit=80) -> str:
        with self.lock:
            items = [f["fact"] for f in self.facts[-limit:]]
        return "\n".join(f"- {x}" for x in items) if items else "(nothing yet)"

    def load_history(self):
        return load_json("history.json", [])

    def save_history(self, history):
        keep = [m for m in history if m["role"] in ("user", "assistant") and m.get("content")]
        save_json("history.json", keep[-20:])
