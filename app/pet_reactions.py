"""Zicou — « Zicou réagit à ce que tu fais » (décision F de l'admin, 4.11.2026).

Quand un membre connecté (identifiant acct-…) ajoute un titre accepté dans la file, termine une partie d'un jeu de
soirée ou une partie de Méninges, son Zicou gagne un petit bonus (pièces 🪙 + humeur, app/pet.py REWARDS), plafonné
par jour et par source. Le bonus lui-même est appliqué à la prochaine ouverture de Zicou (pet.rewards, d'après les
dates notées ici ou dans la base) : une même chose n'est jamais comptée deux fois. Ici, on note ce qui s'est passé et on
prépare un petit bandeau éphémère (« +5 🪙 pour Zicou ») que la page récupère (app/static/pet/reactions.js) : jamais de
notification push, coupable dans Réglages › Zicou.

Conformité des stores (App Store 1.4.3, Google Play) : JAMAIS de récompense pour un jeu à boire (catégorie « 🍻 Alcool »
de app/static/games.js, Pyramide) ni pour une partie jouée avec l'option alcool (gorgées), jamais pour noter, partager
ou inviter. Sans Zicou : aucun effet ; on propose une seule fois d'en adopter un, à la place du bonus.
"""
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from . import pet

KEEP_SECONDS = 3 * 24 * 3600     # au-delà, une note ne rapporte plus rien (pet.REWARD_WINDOW_HOURS = 48 h)
KEEP_PER_PLAYER = 40
PENDING_MAX = 5                  # bandeaux en attente par compte (les plus récents)
PENDING_SECONDS = 600            # un bandeau non affiché dans les 10 min est oublié (il n'a plus de sens)

# Jeux à boire : jamais récompensés (même liste que la catégorie « 🍻 Alcool » de games.js, plus la Pyramide, qui se
# joue toujours avec des gorgées). Les autres jeux qui ont une option gorgées (Blackjack, Quiz, Qui de nous ?…) ne
# sont récompensés que joués SANS alcool (options.sips = 0 et options.alcohol faux).
DRINKING_GAMES = frozenset({"beerpong", "whoof", "never", "roulette", "biskit", "casino", "purity", "pyramid"})
NOT_A_GAME = frozenset({"room"})   # la salle de jeux n'est pas une partie

SOURCES = ("music", "party", "brain")   # notées par le serveur Party. Présence et réponse à un événement : plus rien
#                                         (décision du 04.11.2026) ; les pièces d'un événement : droit zicou.event_coins.
TEXTS = {
    "music": "🪩 {n} danse sur ton son ! +{c} 🪙",
    "party": "🎉 Bien joué ! +{c} 🪙 pour {n}",
    "brain": "🧠 {n} est fier de toi : +{c} 🪙",
}
NO_COIN_TEXTS = {   # plafond commun de pièces atteint : la joie reste, sans pièce
    "music": "🪩 {n} danse sur ton son !",
    "party": "🎉 Bien joué ! {n} est ravi",
    "brain": "🧠 {n} est fier de toi",
}
ADOPT_TEXT = "🥚 Adopte ton Zicou : il gagnera des pièces à chaque titre et chaque partie"


def rewardable_game(g: dict) -> bool:
    """Une partie terminée peut-elle rapporter quelque chose au Zicou ? Jamais un jeu à boire, jamais avec gorgées."""
    kind = str(g.get("type") or "")
    if not kind or kind in DRINKING_GAMES or kind in NOT_A_GAME:
        return False
    options = g.get("options") or {}
    try:
        sips = int(options.get("sips") or 0)
    except (TypeError, ValueError):
        return False   # option illisible : prudence, pas de récompense
    return sips <= 0 and not options.get("alcohol")


def _day(ts: float) -> str:
    return pet.day_of(datetime.fromtimestamp(ts, timezone.utc))


class ActivityLog:
    """Ce que les membres ont fait dans Party (parties terminées, titres ajoutés, Méninges) : 3 jours au plus, dans un
    fichier (les parties et la file vivent dans la mémoire du serveur, pas dans Supabase). Garde aussi, par compte,
    l'état connu de son Zicou (nom, vivant), la proposition d'adoption déjà faite et le choix « réactions coupées »."""

    def __init__(self, path: Path | None):
        self.path = path
        self.lock = threading.Lock()
        self.rows: dict[str, list[list]] = {}       # gid → [[id, ts, source], …]
        self.pets: dict[str, dict] = {}             # gid → {"name", "alive"} ou {"none": True}
        self.offered: dict[str, float] = {}         # gid → date de la proposition d'adoption (une seule fois)
        self.quiet: set[str] = set()                # gid : réactions coupées (Réglages › Zicou)
        self.pending: dict[str, list[dict]] = {}    # gid → bandeaux à montrer (mémoire seulement)
        self._load()

    # ── Fichier ──

    def _load(self) -> None:
        if not self.path or not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text())
        except (OSError, ValueError):
            return
        if not isinstance(raw, dict):
            return
        if raw.get("v") != 2:   # ancien format (PartyLog) : {gid: [[id, ts], …]}, que des parties de Party
            self.rows = {k: [[r[0], r[1], "party"] for r in v if isinstance(r, list) and len(r) >= 2]
                         for k, v in raw.items() if isinstance(v, list)}
            return
        rows, pets_, offered, quiet = raw.get("rows"), raw.get("pets"), raw.get("offered"), raw.get("quiet")
        self.rows = {k: [r for r in v if isinstance(r, list) and len(r) == 3] for k, v in (rows or {}).items()
                     if isinstance(v, list)} if isinstance(rows, dict) else {}
        self.pets = {k: v for k, v in pets_.items() if isinstance(v, dict)} if isinstance(pets_, dict) else {}
        self.offered = {k: float(v) for k, v in offered.items() if isinstance(v, (int, float))} \
            if isinstance(offered, dict) else {}
        self.quiet = {g for g in quiet if isinstance(g, str)} if isinstance(quiet, list) else set()

    def _write(self) -> None:
        if not self.path:
            return
        data = {"v": 2, "rows": self.rows, "pets": self.pets, "offered": self.offered, "quiet": sorted(self.quiet)}
        try:
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data))
            tmp.replace(self.path)
        except OSError:
            pass   # disque plein : le bonus est perdu, rien d'autre

    # ── Notes (compatibles avec l'ancien PartyLog) ──

    def note(self, gid: str, item_id: str, now: float | None = None, source: str = "party") -> bool:
        """Une chose faite (une fois par identifiant, par source et par joueur). True si c'est nouveau."""
        return self._note(gid, item_id, now or time.time(), source) is not None

    def _note(self, gid: str, item_id: str, now: float, source: str) -> int | None:
        """Note sous le verrou ; renvoie le rang de cette note dans la journée pour sa source, None si déjà notée."""
        if not gid.startswith("acct-") or not item_id or source not in SOURCES:
            return None
        with self.lock:
            rows = [r for r in self.rows.get(gid, []) if now - r[1] < KEEP_SECONDS]
            if any(r[0] == item_id and r[2] == source for r in rows):
                return None
            today = _day(now)
            rank = 1 + sum(1 for r in rows if r[2] == source and _day(r[1]) == today)
            self.rows[gid] = (rows + [[item_id, now, source]])[-KEEP_PER_PLAYER:]
            self._write()
        return rank

    def times(self, gid: str, source: str = "party") -> list[str]:
        with self.lock:
            rows = [r for r in self.rows.get(gid, []) if r[2] == source]
        return [pet.iso(datetime.fromtimestamp(r[1], timezone.utc)) for r in rows]

    # ── Réactions ──

    def react(self, gid: str, source: str, item_id: str, now: float | None = None) -> bool:
        """Note l'action et, si elle rapporte encore quelque chose aujourd'hui, prépare un bandeau. True si notée."""
        now = now or time.time()
        rank = self._note(gid, item_id, now, source)
        if rank is None:
            return False
        if rank <= pet.REWARDS[source][1]:   # plafond du jour atteint : rien à montrer (le bonus non plus)
            coins = self._coins_left(gid, now, source)
            with self.lock:
                if gid not in self.quiet:
                    queue = [p for p in self.pending.get(gid, []) if now - p["at"] < PENDING_SECONDS]
                    self.pending[gid] = (queue + [{"source": source, "at": now, "coins": coins}])[-PENDING_MAX:]
        return True

    def _coins_left(self, gid: str, now: float, source: str) -> int:
        """Pièces que rapporte cette action (estimation pour le bandeau) : plafond par source ET plafond commun du jour
        (pet.ACTIVITY_COINS_PER_DAY, Méninges + parties + titres réunis). Le vrai calcul reste pet.rewards()."""
        today = _day(now)
        with self.lock:
            rows = sorted((r for r in self.rows.get(gid, []) if _day(r[1]) == today and r[2] in pet.REWARDS),
                          key=lambda r: r[1])
        used, ranks = 0, {}
        for r in rows[:-1]:
            ranks[r[2]] = ranks.get(r[2], 0) + 1
            if ranks[r[2]] <= pet.REWARDS[r[2]][1]:
                used += min(pet.REWARDS[r[2]][2], max(0, pet.ACTIVITY_COINS_PER_DAY - used))
        return max(0, min(pet.REWARDS[source][2], pet.ACTIVITY_COINS_PER_DAY - used))

    def has_pending(self, gid: str) -> bool:
        with self.lock:
            return bool(self.pending.get(gid))

    def mark_pet(self, gid: str, name: str | None, alive: bool) -> None:
        """État du Zicou de ce compte, vu à la dernière ouverture de Zicou (name None : pas de Zicou)."""
        if not gid.startswith("acct-"):
            return
        state = {"none": True} if name is None else {"name": str(name)[:pet.NAME_MAX], "alive": bool(alive)}
        with self.lock:
            if self.pets.get(gid) == state:
                return
            self.pets[gid] = state
            self._write()

    def known(self, gid: str) -> bool:
        with self.lock:
            return gid in self.pets

    def set_enabled(self, gid: str, on: bool) -> bool:
        with self.lock:
            if on:
                self.quiet.discard(gid)
            else:
                self.quiet.add(gid)
                self.pending.pop(gid, None)
            self._write()
        return on

    def enabled(self, gid: str) -> bool:
        with self.lock:
            return gid not in self.quiet

    def take(self, gid: str, now: float | None = None) -> list[dict]:
        """Bandeaux à montrer maintenant (retirés de la file). État du Zicou inconnu : ils attendent (voir resolve)."""
        now = now or time.time()
        with self.lock:
            state = self.pets.get(gid)
            queue = [p for p in self.pending.get(gid, []) if now - p["at"] < PENDING_SECONDS]
            if state is None:
                self.pending[gid] = queue
                return []
            self.pending.pop(gid, None)
            if not queue or gid in self.quiet:
                return []
            if state.get("none"):
                if gid in self.offered:
                    return []
                self.offered[gid] = now
                self._write()
                return [{"kind": "adopt", "text": ADOPT_TEXT}]
            if not state.get("alive"):
                return []   # œuf ou envolé : il ne reçoit rien, on ne montre rien
            name = state.get("name") or pet.DEFAULT_NAME
            out = []
            for p in queue:
                c = int(p.get("coins", pet.REWARDS[p["source"]][2]))
                text = TEXTS[p["source"]].format(n=name, c=c) if c > 0 else NO_COIN_TEXTS[p["source"]].format(n=name)
                out.append({"kind": "reward", "source": p["source"], "coins": c, "text": text})
            return out
