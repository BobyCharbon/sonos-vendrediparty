"""Journal des actions sensibles côté Party (connexions admin, invités renommés, déconnectés, bannis…).

Fichier JSON Lines en ajout seul : l'app ne sait ni modifier ni effacer une ligne. Lu par Root et les admins
(GET /api/admin/audit). Jamais de code PIN ni de jeton dans une entrée.
"""
import json
import secrets
import threading
import time
from pathlib import Path

ACTOR_MAX = 80
NAME_MAX = 80
DETAIL_MAX = 200
READ_MAX = 500  # entrées renvoyées au plus par lecture


def _clip(value, size: int):
    return value[:size] if isinstance(value, str) else value


class AuditLog:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.lock = threading.Lock()

    def record(self, action: str, actor: str, target: dict | None = None, details: dict | None = None, ip: str = "") -> dict:
        entry = {
            "id": f"{time.time_ns():x}-{secrets.token_hex(3)}",
            "at": time.time(),
            "action": action,
            "actor": _clip(actor or "Inconnu", ACTOR_MAX),
            "target": {k: _clip(v, NAME_MAX) for k, v in target.items()} if target else None,
            "details": {k: _clip(v, DETAIL_MAX) for k, v in details.items()} if details else None,
            "ip": ip or None,
        }
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line)
        return entry

    def read(self, limit: int = 100, before: str | None = None) -> list[dict]:
        """Entrées les plus récentes d'abord ; « before » : la page plus ancienne que cette entrée."""
        with self.lock:
            if not self.path.exists():
                return []
            lines = self.path.read_text(encoding="utf-8").splitlines()
        entries = []
        for line in reversed(lines):
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # ligne abîmée (coupure de courant) : on garde le reste lisible
        if before:
            ids = [e.get("id") for e in entries]
            entries = entries[ids.index(before) + 1:] if before in ids else []
        return entries[:max(1, min(limit, READ_MAX))]
