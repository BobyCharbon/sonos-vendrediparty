"""Journal des actions sensibles côté Party (connexions admin, invités renommés, déconnectés, bannis…).

Fichier JSON Lines en ajout seul ; seules exceptions : entrées de plus de 12 mois retirées (purge), connexions d'un
compte supprimé retirées (forget). Lu par Root et les admins
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
KEEP_SECONDS = 365 * 86400  # 12 mois
# Entrées qui décrivent la personne elle-même (ses connexions) : effacées avec son compte.
OWN_ACTIONS = ("account.link", "admin.login", "admin.denied")


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

    def _rewrite(self, keep) -> int:
        """Réécrit le fichier avec les lignes que keep(entrée) garde (ou remplace) ; rend le nombre de lignes changées."""
        with self.lock:
            if not self.path.exists():
                return 0
            out, changed = [], 0
            for line in self.path.read_text(encoding="utf-8").splitlines():
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    out.append(line)
                    continue
                new = keep(entry)
                if new is entry:
                    out.append(line)
                    continue
                changed += 1
                if new:
                    out.append(json.dumps(new, ensure_ascii=False))
            if changed:
                tmp = self.path.with_suffix(".tmp")
                tmp.write_text("".join(x + "\n" for x in out), encoding="utf-8")
                tmp.replace(self.path)
            return changed

    def purge(self, now: float | None = None) -> int:
        """Entrées de plus de 12 mois retirées (politique de confidentialité : connexions et adresses IP)."""
        limit = (now or time.time()) - KEEP_SECONDS
        return self._rewrite(lambda e: e if (e.get("at") or 0) >= limit else None)

    def forget(self, gid: str) -> int:
        """Compte supprimé : ses connexions (avec leur adresse IP) partent ; les actions d'admin qui le visaient restent
        (sécurité, sanctions), sans son nom."""
        def keep(e):
            target = e.get("target") or {}
            if not gid or target.get("id") != gid:
                return e
            if e.get("action") in OWN_ACTIONS:
                return None
            return {**e, "target": {**target, "name": "Compte supprimé"}}
        return self._rewrite(keep)

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
