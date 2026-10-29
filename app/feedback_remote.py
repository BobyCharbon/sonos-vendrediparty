"""Avis partagés entre le site de test et la production : une seule liste, gardée par la production.

Le site de test (FEEDBACK_REMOTE_URL = adresse de la production) ne garde plus ses avis : il lit et écrit ceux de la
production par POST /api/feedback-sync, protégé par un secret partagé (FEEDBACK_SYNC_SECRET, même valeur des deux
côtés). Même interface que FeedbackBox : le reste du serveur ne voit pas la différence."""
import threading
import time

import httpx

SYNC_PATH = "/api/feedback-sync"
SYNC_HEADER = "X-Feedback-Sync"
READ_TTL = 3  # s : la pastille de l'admin relit souvent ; une liste de 3 s suffit
# Opérations que la production accepte (lecture et écriture des avis, rien d'autre).
OPS = ("add", "mine", "mark_seen", "all", "count_new", "get", "set_note", "mark_sent", "set_claude_state", "update", "absorb")
UNAVAILABLE = "Les avis sont momentanément indisponibles. Réessaie dans un instant."


class FeedbackUnavailable(RuntimeError):
    """La production ne répond pas : l'avis n'est ni perdu ni enregistré, on le dit à la personne."""


class FeedbackRemote:
    def __init__(self, url: str, secret: str, client: httpx.Client | None = None):
        self.url = url.rstrip("/")
        self.secret = secret
        self.client = client or httpx.Client(timeout=8)
        self.lock = threading.Lock()
        self.cache: dict[str, tuple[float, object]] = {}

    def _call(self, op: str, **args):
        try:
            r = self.client.post(self.url + SYNC_PATH, json={"op": op, "args": args}, headers={SYNC_HEADER: self.secret})
        except httpx.HTTPError as e:
            raise FeedbackUnavailable(UNAVAILABLE) from e
        if r.status_code != 200:
            raise FeedbackUnavailable(UNAVAILABLE)
        return r.json().get("result")

    def _read(self, op: str):
        now = time.time()
        with self.lock:
            hit = self.cache.get(op)
        if hit and now - hit[0] < READ_TTL:
            return hit[1]
        value = self._call(op)
        with self.lock:
            self.cache[op] = (now, value)
        return value

    def _write(self, op: str, **args):
        with self.lock:
            self.cache.clear()  # la prochaine lecture voit le changement
        return self._call(op, **args)

    # Même interface que FeedbackBox.
    def add(self, guest_id: str, name: str, kind: str, text: str, context: dict) -> dict:
        return self._write("add", guest_id=guest_id, name=name, kind=kind, text=text, context=context)

    def mine(self, guest_id: str) -> list[dict]:
        return self._call("mine", guest_id=guest_id)

    def mark_seen(self, guest_id: str):
        self._write("mark_seen", guest_id=guest_id)

    def all(self) -> list[dict]:
        return self._read("all")

    def count_new(self) -> int:
        try:
            return self._read("count_new")
        except FeedbackUnavailable:
            return 0  # la pastille ne bloque jamais l'admin

    def get(self, fid: str) -> dict | None:
        return self._call("get", fid=fid)

    def set_note(self, fid: str, note: str) -> dict | None:
        return self._write("set_note", fid=fid, note=note)

    def mark_sent(self, fid: str, number: int, url: str) -> dict | None:
        return self._write("mark_sent", fid=fid, number=number, url=url)

    def set_claude_state(self, fid: str, state: str, error: str = "", sha: str = "", migrations: list[str] | None = None) -> dict | None:
        return self._write("set_claude_state", fid=fid, state=state, error=error, sha=sha, migrations=migrations)

    def update(self, ids: list[str], action: str, reply: str = "") -> list[dict]:
        return self._write("update", ids=ids, action=action, reply=reply)

    def absorb(self, items: list[dict]) -> int:
        """Verse dans la liste commune des avis gardés jusqu'ici en local (une seule fois, sans doublon)."""
        return self._write("absorb", items=items)
