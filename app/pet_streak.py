"""Compagnon — série 🔥 protégée (lot 1 « revenir tous les jours », 4 novembre 2026). Calcul pur, horloge en paramètre.

Un jour compte dès qu'on s'occupe vraiment de lui (repas, jeu, câlin, toilette, goûter) ou qu'on fait un cadeau à un
ami ; le coffre seul, la simple visite et le coucher ne suffisent pas (playtest « Marc » : le paresseux gardait sa
série sans un soin). Un gel est offert dès le départ (playtest « Léa »). Les jours manqués
ne cassent pas forcément la série :
  · samedi en répit : être passé le vendredi protège le samedi (le lendemain de soirée) ;
  · gels ❄️ : au plus 2, +1 tous les 7 jours de série ; un gel protège un jour manqué (la série tient, sans grandir) ;
  · rattrapage : si elle casse quand même, on peut la récupérer sous 48 h (1 partie de Méninges + 1 soin), 1×/mois.
Paliers 3/7/14/30/50/100/365 : récompense connue d'avance (app/pet_loop.py). Jamais de ton culpabilisant.
"""
import copy
from datetime import date, timedelta

MAX_FREEZES = 2
FREEZE_EVERY = 7          # +1 gel tous les 7 jours de série
REPAIR_DAYS = 2           # rattrapage possible le jour du retour et le lendemain (48 h)
REPAIR_MAX_GAP = 2        # … si l'absence non protégée n'a pas dépassé 2 jours
MILESTONES = (3, 7, 14, 30, 50, 100, 365)
SATURDAY, FRIDAY = 5, 4


START_FREEZES = 1         # un gel offert dès le départ (playtest « Léa » : 🔥 0 dès le premier week-end)


def new() -> dict:
    return {"count": 0, "last": "", "best": 0, "freezes": START_FREEZES, "lost": None, "repair_month": ""}


def _d(value: str) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def normalized(streak: dict | None) -> dict:
    """Série d'avant le lot 1 (count, last, best) complétée des nouveaux champs."""
    out = {**new(), "freezes": 0} if streak else new()   # une ancienne série n'a pas de gel ; une neuve en a un
    out.update(copy.deepcopy(streak or {}))
    return out


def _protection(missed: list[date], last: date, freezes: int) -> tuple[list[dict], int, bool]:
    """Pour chaque jour manqué (dans l'ordre) : répit du samedi, gel, ou rien. Renvoie (protections, gels restants,
    série cassée ?)."""
    out, broken = [], False
    for m in missed:
        if m.weekday() == SATURDAY and m - timedelta(days=1) == last:
            out.append({"day": m.isoformat(), "by": "saturday"})
        elif freezes > 0:
            freezes -= 1
            out.append({"day": m.isoformat(), "by": "freeze"})
        else:
            broken = True
            break
    return out, freezes, broken


def _missed(last: date, today: date) -> list[date]:
    return [last + timedelta(days=i) for i in range(1, (today - last).days)]


def note_day(streak: dict, today: date, brain_today: bool = False) -> tuple[dict, list[dict]]:
    """Le jour `today` compte. Renvoie (nouvelle série, événements) ; l'entrée ne change pas. Événements : protected
    (répit ou gel), broken (avec ou sans rattrapage possible), freeze_earned, milestone, repaired."""
    s, events = normalized(streak), []
    last = _d(s["last"])
    if last == today:
        return s, events
    if last and today < last:
        return s, events   # horloge revenue en arrière : rien
    _expire_repair(s, today)
    if not last:
        s["count"] = 1
    else:
        protected, left, broken = _protection(_missed(last, today), last, s["freezes"])
        if not broken:   # série cassée quand même : les gels ne sont pas dépensés pour rien
            s["freezes"] = left
            events += [{"kind": "protected", **p} for p in protected]
        if broken:
            unprotected = len([m for m in _missed(last, today)
                               if not (m.weekday() == SATURDAY and m - timedelta(days=1) == last)])
            can_repair = (s["count"] >= 2 and unprotected <= REPAIR_MAX_GAP
                          and s.get("repair_month") != today.strftime("%Y-%m"))
            if can_repair:
                s["lost"] = {"count": s["count"], "until": (today + timedelta(days=REPAIR_DAYS - 1)).isoformat(),
                             "brain": bool(brain_today), "care": False}
            events.append({"kind": "broken", "was": s["count"], "repair": can_repair})
            s["count"] = 1
        else:
            s["count"] += 1
    s["last"] = today.isoformat()
    events += _grow(s)
    return s, events


def _grow(s: dict) -> list[dict]:
    events = []
    if s["count"] > 0 and s["count"] % FREEZE_EVERY == 0 and s["freezes"] < MAX_FREEZES:
        s["freezes"] += 1
        events.append({"kind": "freeze_earned", "freezes": s["freezes"]})
    if s["count"] in MILESTONES:
        events.append({"kind": "milestone", "days": s["count"]})
    s["best"] = max(s.get("best", 0), s["count"])
    return events


def _expire_repair(s: dict, today: date) -> None:
    lost = s.get("lost")
    if lost and (_d(lost.get("until")) or today) < today:
        s["lost"] = None


def repair_progress(streak: dict, what: str, today: date) -> tuple[dict, list[dict]]:
    """Une partie de Méninges (what="brain") ou un soin (what="care") pendant le rattrapage. Les deux faits : la série
    perdue revient (augmentée des jours depuis le retour)."""
    s = normalized(streak)
    _expire_repair(s, today)
    lost = s.get("lost")
    if not lost or what not in ("brain", "care"):
        return s, []
    lost[what] = True
    if not (lost["brain"] and lost["care"]):
        return s, []
    restored = lost["count"] + s["count"]
    s.update(count=restored, lost=None, repair_month=today.strftime("%Y-%m"))
    events = [{"kind": "repaired", "count": restored}]
    for m in MILESTONES:   # un palier franchi grâce au rattrapage compte aussi
        if lost["count"] < m <= restored:
            events.append({"kind": "milestone", "days": m})
    s["best"] = max(s.get("best", 0), restored)
    return s, events


def current(streak: dict | None, today: date) -> int:
    """Série affichée aujourd'hui : elle tient si on est passé aujourd'hui, ou si les jours manqués depuis sont tous
    protégés (répit, gels) — sinon 0 (le record reste)."""
    s = normalized(streak)
    last = _d(s["last"])
    if not last or today < last:
        return 0 if not last else s["count"]
    missed = _missed(last, today)
    if not missed:
        return s["count"]
    # Aujourd'hui n'est pas encore manqué : seuls les jours passés comptent.
    _, _, broken = _protection(missed, last, s["freezes"])
    return 0 if broken else s["count"]


def next_milestone(count: int) -> int | None:
    return next((m for m in MILESTONES if m > count), None)
