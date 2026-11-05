"""Zicou — le niveau (XP), permanent et sans fin (économie du 4.11.2026, scratchpad economie/design.md §2.1).

L'XP vient des soins (repas, jeu, câlin, toilette, goûter du sac), des parties (Méninges, parties de Party sans alcool)
et des gestes envers les amis (visite, cadeau). Elle est plafonnée PAR JOUR (jour de Zurich) : 20 pour les soins, 10
pour le jeu, 10 pour le social, soit 40 au plus. Jamais d'XP pour boire, noter l'app, laisser un avis ou partager.
La Pizza dorée (app/pet_feast.py) double les gains ET les plafonds pendant 24 h.

Niveau n → n+1 : 50 + 25 × n XP. Après le niveau 50, plus de nouveau niveau : chaque palier de 1 000 XP ajoute une
étoile de prestige ★. Le niveau est attaché au COMPTE (owner["xp"]) : il ne redescend jamais, même à l'envol de Zicou.
Calcul pur : l'horloge (`now`) est passée en paramètre.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Zurich")
GAINS = {"care": 4, "game": 5, "social": 5}       # XP d'un geste
CAPS = {"care": 20, "game": 10, "social": 10}      # XP par jour au plus (40 en tout)
LEVEL_MAX = 50
STAR_XP = 1000


def need(level: int) -> int:
    """XP pour passer du niveau `level` au suivant."""
    return 50 + 25 * int(level)


def _to_max() -> int:
    return sum(need(n) for n in range(1, LEVEL_MAX))


XP_TO_MAX = _to_max()   # 33 075 XP pour atteindre le niveau 50


def level_of(total: int) -> dict:
    """Niveau, XP dans le niveau, XP du niveau suivant, étoiles ★ (après le niveau 50)."""
    total = max(0, int(total or 0))
    if total >= XP_TO_MAX:
        extra = total - XP_TO_MAX
        return {"level": LEVEL_MAX, "stars": extra // STAR_XP, "xp": extra % STAR_XP, "need": STAR_XP, "total": total}
    level, left = 1, total
    while left >= need(level):
        left -= need(level)
        level += 1
    return {"level": level, "stars": 0, "xp": left, "need": need(level), "total": total}


def _state(owner: dict, now: datetime) -> dict:
    xp = owner.get("xp")
    if not isinstance(xp, dict):
        xp = owner["xp"] = {"total": 0, "day": "", "got": {}}
    today = now.astimezone(TZ).date().isoformat()
    if xp.get("day") != today:
        xp["day"], xp["got"] = today, {}
    return xp


def gain(owner: dict, kind: str, now: datetime, factor: int = 1) -> dict | None:
    """Ajoute l'XP d'un geste (plafond du jour compris). Modifie `owner` (appelé sur une copie). Renvoie l'événement
    ({"kind": "xp", "xp", "level", "level_up"}) ou None si le plafond du jour est atteint."""
    if kind not in GAINS:
        return None
    xp = _state(owner, now)
    factor = max(1, int(factor))
    cap, got = CAPS[kind] * factor, int((xp.get("got") or {}).get(kind, 0))
    amount = min(GAINS[kind] * factor, cap - got)
    if amount <= 0:
        return None
    before = level_of(xp.get("total", 0))
    xp["total"] = int(xp.get("total", 0)) + amount
    xp["got"] = {**(xp.get("got") or {}), kind: got + amount}
    after = level_of(xp["total"])
    up = (after["level"], after["stars"]) > (before["level"], before["stars"])
    return {"kind": "xp", "xp": amount, "level": after["level"], "stars": after["stars"], "level_up": up}


def view(owner: dict, now: datetime, factor: int = 1) -> dict:
    """Pour l'écran : niveau, étoiles, barre, ce qui reste à gagner aujourd'hui (plafonds affichés)."""
    xp = owner.get("xp") if isinstance(owner.get("xp"), dict) else {}
    today = now.astimezone(TZ).date().isoformat()
    got = (xp.get("got") or {}) if xp.get("day") == today else {}
    factor = max(1, int(factor))
    return level_of(xp.get("total", 0)) | {
        "today": {k: int(got.get(k, 0)) for k in CAPS}, "caps": {k: v * factor for k, v in CAPS.items()},
        "boost": factor > 1}


def badge(owner: dict) -> dict:
    """Ce que voient les amis : le niveau et les étoiles seulement."""
    lv = level_of((owner.get("xp") or {}).get("total", 0) if isinstance(owner.get("xp"), dict) else 0)
    return {"level": lv["level"], "stars": lv["stars"]}
