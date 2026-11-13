"""Message pour tout le monde (avis eb710b132330, 13.11.2026) : maintenance, information ou annonce.

- L'admin le pose lui-même (Réglages › « Annonce et maintenance ») : il s'affiche sur tous les onglets de l'app,
  web et iPhone, jusqu'à ce qu'il l'arrête.
- Chaque mise à jour du serveur le pose toute seule juste avant de redémarrer
  (``python -m app.notice deploy``, voir deploy/update.sh) : les joueurs lisent « Mise à jour en cours » au lieu
  d'une erreur. Le serveur qui redémarre l'efface ; s'il ne revient pas, elle s'éteint seule après AUTO_TTL.

Les messages vivent dans de petits fichiers JSON (DATA_DIR/notice.json pour l'admin, notice-deploy.json pour une
mise à jour), relus quand ils changent : la commande du déploiement les écrit depuis un autre processus.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import sys
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path

KINDS = ("maintenance", "info", "announce")
TITLES = {"maintenance": "Mise à jour en cours", "info": "Information", "announce": "Annonce"}
DEPLOY_MESSAGE = "Party revient tout seul dans une minute. Ta partie est gardée."
TITLE_MAX = 60
MESSAGE_MAX = 280
AUTO_TTL = 10 * 60   # une maintenance de déploiement oubliée (serveur pas revenu) ne reste jamais affichée
DEPLOY_ACTOR = "Mise à jour automatique"


class NoticeError(ValueError):
    """Message refusé : la phrase est montrée telle quelle à l'admin."""


@dataclass(frozen=True)
class Notice:
    id: str
    kind: str
    title: str
    message: str
    auto: bool
    at: float
    by: str

    def public(self) -> dict:
        """Ce que tout le monde reçoit (jamais qui l'a posé)."""
        return {"id": self.id, "kind": self.kind, "title": self.title, "message": self.message, "auto": self.auto}


def _clean(text: object, limit: int, multiline: bool) -> str:
    if text is None:
        return ""
    if not isinstance(text, str):
        raise NoticeError("Texte invalide.")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(c for c in text if c == "\n" or c >= " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    if multiline:
        text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    else:
        text = " ".join(line for line in lines if line)
    if len(text) > limit:
        raise NoticeError(f"{limit} caractères au plus.")
    return text


def make(kind: str, title: object = None, message: object = None, by: str = "", auto: bool = False,
         now: float | None = None) -> Notice:
    """Message validé : type connu, titre et texte courts ; une information ou une annonce a toujours un texte."""
    if kind not in KINDS:
        raise NoticeError("Choisis Maintenance, Information ou Annonce.")
    title = _clean(title, TITLE_MAX, multiline=False) or TITLES[kind]
    message = _clean(message, MESSAGE_MAX, multiline=True)
    if not message and kind != "maintenance":
        raise NoticeError("Écris le message à afficher.")
    return Notice(id=secrets.token_hex(6), kind=kind, title=title, message=message, auto=auto,
                  at=time.time() if now is None else now, by=(by or "")[:60])


def _from_dict(d: object) -> Notice | None:
    if not isinstance(d, dict):
        return None
    try:
        n = Notice(id=str(d["id"]), kind=str(d["kind"]), title=str(d["title"]), message=str(d.get("message") or ""),
                   auto=bool(d.get("auto")), at=float(d["at"]), by=str(d.get("by") or ""))
    except (KeyError, TypeError, ValueError):
        return None
    return n if n.kind in KINDS else None


class _Slot:
    """Un message gardé dans un fichier, relu seulement quand il change (la commande du déploiement l'écrit)."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.lock = threading.Lock()
        self._stamp: tuple[int, int] | None = None
        self._notice: Notice | None = None

    def read(self) -> Notice | None:
        with self.lock:
            try:
                st = self.path.stat()
            except FileNotFoundError:
                self._stamp, self._notice = None, None
                return None
            stamp = (st.st_mtime_ns, st.st_size)
            if stamp != self._stamp:
                try:
                    self._notice = _from_dict(json.loads(self.path.read_text("utf-8")))
                except (OSError, ValueError):
                    self._notice = None
                self._stamp = stamp
            return self._notice

    def write(self, notice: Notice) -> Notice:
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(asdict(notice), ensure_ascii=False), "utf-8")
            os.replace(tmp, self.path)
            self._stamp = None
        return notice

    def erase(self) -> bool:
        with self.lock:
            existed = self.path.exists()
            self.path.unlink(missing_ok=True)
            self._stamp, self._notice = None, None
            return existed


class NoticeStore:
    """Le message de l'admin (notice.json) et celui d'une mise à jour en cours (notice-deploy.json), à part :
    la fin d'une mise à jour ne fait jamais disparaître l'annonce de l'admin."""

    def __init__(self, path: Path):
        path = Path(path)
        self.admin = _Slot(path)
        self.deploy = _Slot(path.with_name(path.stem + "-deploy" + path.suffix))

    def current(self, now: float | None = None) -> Notice | None:
        mine = self.admin.read()
        if mine and mine.kind == "maintenance":
            return mine
        auto = self.deploy.read()
        if auto and (time.time() if now is None else now) - auto.at <= AUTO_TTL:
            return auto
        return mine

    def admin_notice(self) -> Notice | None:
        return self.admin.read()

    def set(self, notice: Notice) -> Notice:
        return (self.deploy if notice.auto else self.admin).write(notice)

    def clear(self) -> None:
        self.admin.erase()

    def clear_auto(self) -> bool:
        """Au démarrage du serveur : la mise à jour est finie."""
        return self.deploy.erase()


def deploy(store: NoticeStore) -> Notice:
    """Juste avant de redémarrer : « Mise à jour en cours » pour tout le monde (l'annonce de l'admin est gardée)."""
    return store.set(make("maintenance", message=DEPLOY_MESSAGE, by=DEPLOY_ACTOR, auto=True))


def main(argv: list[str]) -> int:
    store = NoticeStore(Path(os.environ.get("DATA_DIR", "data")) / "notice.json")
    if argv[1:] == ["deploy"]:
        deploy(store)
        print("« Mise à jour en cours » affiché pour tout le monde.")
        return 0
    if argv[1:] == ["done"]:
        store.clear_auto()
        print("Mise à jour terminée : message effacé.")
        return 0
    print("Usage : python -m app.notice deploy|done", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
