"""Compte progressivement obligatoire (décision de l'admin du 04.11) : un invité (code de la soirée + prénom) joue
quelques parties et propose quelques titres, puis on lui demande de créer son compte (numéro + SMS).

Deux réglages de l'admin, journalisés :
- « Parties en invité avant compte » (games) : au-delà, rejoindre ou créer une NOUVELLE partie demande un compte.
  Production (app App Store) : jamais moins de 1 (Apple 5.1.1(v) : on essaie un jeu de soirée sans compte) ; 0 (compte
  obligatoire dès l'arrivée) n'est permis que sur le site de test. Une partie où l'invité a déjà sa place n'est jamais
  coupée.
- « Titres en invité par soirée » (tracks) : titres proposés au plus par soirée ; 0 = compte requis pour proposer.

Le compteur de parties suit l'identifiant d'invité (jamais l'adresse IP : box partagée) et vit ici, côté serveur :
recharger la page ne le remet pas à zéro. Une salle de jeux n'est pas une partie : seuls les jeux qu'on y lance
comptent. Le compteur de titres, lui, se lit dans les demandes de la soirée (app/party.py).
"""
import json
import os
import threading
import time
from pathlib import Path

from .features import is_test_site

DEFAULT_GAMES = 3
DEFAULT_TRACKS = 3
SETTING_MAX = 1000          # borne haute (l'admin choisit de 0 à 50 ; les tests posent 1000 par l'environnement)
CODES_KEPT = 50             # codes de parties gardés par invité (une même partie ne compte qu'une fois)
GUESTS_KEPT = 5000          # invités suivis au plus (les plus anciens partent d'abord)
FORGET_AFTER = 180 * 86400  # s : un invité inactif depuis six mois repart de zéro

SOFT_TEXT = "Garde tes scores : crée ton compte en 30 secondes, juste ton numéro."


def _env_int(name: str, default: int) -> int:
    try:
        return max(0, min(SETTING_MAX, int(os.environ.get(name, default))))
    except ValueError:
        return default


def clamp(value: int) -> int:
    return max(0, min(SETTING_MAX, int(value)))


def games_min() -> int:
    """Plancher des parties en invité : 1 en production (jamais de compte exigé dès la 1re partie), 0 sur le site de test."""
    return 0 if is_test_site() else 1


def clamp_games(value: int) -> int:
    return max(games_min(), clamp(value))


class GuestGate:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.lock = threading.Lock()
        self.data = self._load()

    # ── Fichier ──
    def _load(self) -> dict:
        try:
            raw = json.loads(self.path.read_text())
            if isinstance(raw, dict):
                return {"settings": dict(raw.get("settings") or {}), "played": dict(raw.get("played") or {})}
        except (OSError, ValueError):
            pass
        return {"settings": {}, "played": {}}

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False))
        tmp.replace(self.path)

    # ── Réglages de l'admin ──
    def settings(self) -> dict:
        s = self.data["settings"]
        return {"games": clamp_games(s.get("games", _env_int("GUEST_GAMES_BEFORE_ACCOUNT", DEFAULT_GAMES))),
                "tracks": clamp(s.get("tracks", _env_int("GUEST_TRACKS_PER_PARTY", DEFAULT_TRACKS)))}

    def set_settings(self, games: int | None = None, tracks: int | None = None) -> tuple[dict, dict]:
        """Renvoie (avant, après) pour le journal."""
        with self.lock:
            before = self.settings()
            if games is not None:
                self.data["settings"]["games"] = clamp_games(games)
            if tracks is not None:
                self.data["settings"]["tracks"] = clamp(tracks)
            self._save()
            return before, self.settings()

    # ── Parties jouées en invité ──
    def played(self, gid: str) -> int:
        return int((self.data["played"].get(gid) or {}).get("n", 0))

    def has(self, gid: str, code: str) -> bool:
        return code in ((self.data["played"].get(gid) or {}).get("codes") or [])

    def blocked(self, gid: str, code: str = "") -> bool:
        """Une nouvelle partie demande un compte (une partie déjà comptée, elle, reste ouverte)."""
        return not (code and self.has(gid, code)) and self.played(gid) >= self.settings()["games"]

    def record(self, gid: str, code: str) -> bool:
        """L'invité entre dans une partie (créée, rejointe, ou inscrit d'office depuis la salle). Une fois par partie."""
        with self.lock:
            row = self.data["played"].get(gid) or {"n": 0, "codes": []}
            if code in row["codes"]:
                return False
            self.data["played"][gid] = {"n": row["n"] + 1, "codes": (row["codes"] + [code])[-CODES_KEPT:], "at": time.time()}
            self._prune()
            self._save()
            return True

    def forget(self, gid: str):
        """Compte créé : l'ancien identifiant d'invité n'a plus de compteur."""
        with self.lock:
            if self.data["played"].pop(gid, None) is not None:
                self._save()

    def _prune(self):
        played, now = self.data["played"], time.time()
        for gid in [g for g, row in played.items() if now - row.get("at", now) > FORGET_AFTER]:
            del played[gid]
        if len(played) > GUESTS_KEPT:
            for gid in sorted(played, key=lambda g: played[g].get("at", 0))[:len(played) - GUESTS_KEPT]:
                del played[gid]

    def status(self, gid: str, code: str = "") -> dict:
        """Ce que voit l'invité : parties jouées, limite, message doux (après la 1re), compte requis."""
        limit, n = self.settings()["games"], self.played(gid)
        blocked = self.blocked(gid, code)
        return {"account": False, "played": n, "limit": limit, "blocked": blocked, "nudge": n >= 1 and not blocked,
                "text": SOFT_TEXT}
