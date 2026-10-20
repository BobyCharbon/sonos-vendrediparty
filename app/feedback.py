"""Retours des invités (idées, bugs, remarques) : conservés d'une soirée à l'autre, traités depuis l'admin."""
import json
import secrets
import threading
import time
from pathlib import Path

KINDS = {"idea": "💡 Idée", "bug": "🐞 Bug", "other": "💬 Autre"}
MAX_ITEMS = 500


class FeedbackBox:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.lock = threading.Lock()
        try:
            self.items: list[dict] = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.items = []

    def _save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.items, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    def add(self, guest_id: str, name: str, kind: str, text: str, context: dict) -> dict:
        item = {"id": secrets.token_hex(6), "at": time.time(), "guest_id": guest_id, "name": name, "kind": kind,
                "text": text, "context": context, "status": "new"}
        with self.lock:
            self.items = (self.items + [item])[-MAX_ITEMS:]
            self._save()
        return item

    def sent_since(self, guest_id: str, seconds: float) -> int:
        now = time.time()
        return sum(1 for i in self.items if i["guest_id"] == guest_id and now - i["at"] < seconds)

    def mine(self, guest_id: str) -> list[dict]:
        """Ce que l'invité a envoyé (sans les infos internes), du plus récent au plus ancien."""
        return [{k: i[k] for k in ("id", "at", "kind", "text", "status")} for i in reversed(self.items) if i["guest_id"] == guest_id][:20]

    def all(self) -> list[dict]:
        return list(reversed(self.items))

    def count_new(self) -> int:
        return sum(1 for i in self.items if i["status"] == "new")

    def update(self, ids: list[str], action: str):
        with self.lock:
            if action == "delete":
                self.items = [i for i in self.items if i["id"] not in ids]
            else:
                for i in self.items:
                    if i["id"] in ids:
                        i["status"] = action  # « done » (traité) ou « new » (à traiter)
            self._save()
