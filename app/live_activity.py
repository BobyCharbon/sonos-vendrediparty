"""Live Activity « Ton titre arrive » tenue à jour par le serveur (APNs) : la Dynamic Island avance même l'app fermée.

L'app démarre l'activité et envoie son jeton (POST /api/activity) ; le serveur, qui suit la file en continu
(watch_sonos), pousse chaque changement utile : place dans la file, pause, heure de passage recalée, titre qui passe
(« Ton titre joue actuellement »), titre retiré. Un titre ajouté pendant que l'app est fermée démarre l'activité
par push (iOS 17.2+, jeton de démarrage de l'invité).
Ce module ne fait que des calculs ; l'envoi passe par apns.Apns.send_live_activity.
Format attendu par ActivityKit : dates de content-state en secondes depuis le 1er janvier 2001 (Date Swift),
dates de « aps » (stale-date, dismissal-date, timestamp) en secondes Unix.
"""
from dataclasses import dataclass

SWIFT_EPOCH = 978307200      # 2001-01-01T00:00:00Z : origine des Date Swift
ARRIVAL_STEP = 20            # s : un écart d'heure de passage plus petit ne justifie pas une notification
START_GRACE = 8              # s : l'app ouverte démarre elle-même l'activité ; le serveur attend avant de le faire


@dataclass(frozen=True)
class Slot:
    """Un titre demandé dans la file à venir."""
    rid: str
    owner: str          # guest_id (ou HOST_ID) de la demande
    track_id: str
    title: str
    artist: str
    added_at: float
    ahead: int          # titres avant lui
    eta: float | None   # secondes avant son passage (None : inconnu, ou lecture en pause)


@dataclass(frozen=True)
class Step:
    rid: str
    event: str                    # start | update | end
    payload: dict                 # contenu de « aps » (sans timestamp, ajouté à l'envoi)
    key: tuple                    # ce qui a été montré : on ne renvoie pas la même chose
    priority: int = 10


def content_state(arrival: float, playing: bool, paused: bool, remaining: float, ahead: int) -> dict:
    return {"arrival": round(arrival - SWIFT_EPOCH, 3), "playing": playing, "paused": paused,
            "remaining": round(max(0.0, remaining), 1), "ahead": ahead}


def _waiting(slot: Slot, paused: bool, now: float, last_remaining: float) -> tuple[dict, tuple]:
    remaining = slot.eta if slot.eta is not None else last_remaining
    arrival = now + remaining
    aps = {"content-state": content_state(arrival, False, paused, remaining, slot.ahead)}
    if not paused:
        aps["stale-date"] = int(arrival)  # passé l'heure : « Ton titre joue actuellement » sans attendre de push
    key = ("wait", slot.ahead, paused, round(arrival / ARRIVAL_STEP) if not paused else round(remaining))
    return aps, key


def plan(slots: list[Slot], current_track: str | None, tracked: dict[str, dict], paused: bool, now: float) -> list[Step]:
    """tracked : activités dont l'app a donné le jeton, {rid: {"track_id", "owner", "key", "remaining"}}.
    Renvoie les envois à faire ; l'appelant note step.key dans tracked[rid] après l'envoi (pas de doublon)."""
    by_rid = {s.rid: s for s in slots}
    # Une seule activité par personne : celle de son titre qui passe, sinon de son titre le plus proche dans la file.
    first_of: dict[str, str] = {}
    for slot in slots:
        first_of.setdefault(slot.owner, slot.rid)
    playing_owners = {info.get("owner") for rid, info in tracked.items()
                      if current_track and info.get("track_id") == current_track and rid not in by_rid}
    steps = []
    for rid, info in tracked.items():
        last = info.get("key")
        slot = by_rid.get(rid)
        if slot is not None and (slot.owner in playing_owners or first_of.get(slot.owner) != rid):
            # Pas (ou plus) le prochain titre de la personne (titres échangés, autre titre en train de passer).
            if last != ("gone",):
                steps.append(Step(rid, "end", {"content-state": content_state(now, False, False, 0, 0),
                                               "dismissal-date": int(now)}, ("gone",)))
        elif slot is not None:
            aps, key = _waiting(slot, paused, now, info.get("remaining", 0.0))
            if key != last:
                # Place ou pause : important (priorité 10) ; heure recalée seulement : priorité basse.
                important = last is None or tuple(key[:3]) != tuple(last[:3])
                steps.append(Step(rid, "update", aps, key, 10 if important else 5))
        elif current_track and current_track == info.get("track_id"):
            # Le titre passe : vert « Ton titre joue actuellement », l'activité reste suivie jusqu'à la fin du titre.
            if last != ("playing",):
                steps.append(Step(rid, "update", {"content-state": content_state(now, True, False, 0, 0)}, ("playing",)))
        elif last != ("gone",):
            # Titre fini (un autre passe) ou retiré de la file : l'activité disparaît tout de suite.
            steps.append(Step(rid, "end", {"content-state": content_state(now, last == ("playing",), False, 0, 0),
                                           "dismissal-date": int(now)}, ("gone",)))
    return steps


def starts(slots: list[Slot], start_owners: set[str], tracked: dict[str, dict], started: set[str],
           paused: bool, now: float, busy_owners: frozenset[str] = frozenset()) -> list[Step]:
    """Démarrage par push : prochain titre de chaque invité qui a donné un jeton de démarrage, pas encore suivi.
    busy_owners : invités dont un titre passe en ce moment (son activité verte reste seule jusqu'à la fin)."""
    steps, seen_owner = [], set(busy_owners)
    for slot in slots:  # dans l'ordre de la file : le prochain titre de chaque invité d'abord
        if slot.owner in seen_owner or slot.owner not in start_owners:
            continue
        seen_owner.add(slot.owner)
        if slot.rid in tracked or slot.rid in started or now - slot.added_at < START_GRACE:
            continue
        aps, key = _waiting(slot, paused, now, 0.0)
        aps.update({
            "attributes-type": "TrackActivityAttributes",
            "attributes": {"requestID": slot.rid, "addedAt": round(slot.added_at - SWIFT_EPOCH, 3),
                           "trackID": slot.track_id, "title": slot.title, "artist": slot.artist},
            "alert": {"title": "⏳ Ton titre arrive", "body": f"{slot.title} · {slot.artist}"},
        })
        steps.append(Step(slot.rid, "start", aps, key))
    return steps
