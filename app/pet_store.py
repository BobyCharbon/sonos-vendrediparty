"""Compagnon : lecture / écriture du personnage dans Supabase (au nom du compte connecté, fonctions pet_* de la
migration 20261104130000_compagnon.sql) et parties de Party terminées (récompenses). Le calcul de vie est dans
app/pet.py ; ici, on charge, on fait vivre jusqu'à maintenant, on applique, on enregistre."""
import copy
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from . import pet
from .accounts import AccountError

PARTY_KEEP_SECONDS = 3 * 24 * 3600
PARTY_KEEP_PER_PLAYER = 20
SAVE_ATTEMPTS = 2   # un conflit (autre appareil) : on relit et on rejoue une fois


class PetUnavailable(pet.PetError):
    """Base injoignable ou en panne : passager (HTTP 503)."""


class PetConflict(pet.PetError):
    pass


class PartyLog:
    """Parties de Party terminées par un joueur relié à un compte (identifiant acct-…) : petit bonus pour son compagnon.
    Gardé dans un fichier (les parties vivent dans la mémoire du serveur, pas dans Supabase), 3 jours au plus."""

    def __init__(self, path: Path | None):
        self.path = path
        self.lock = threading.Lock()
        self.data: dict[str, list[list]] = {}
        if path and path.exists():
            try:
                raw = json.loads(path.read_text())
                self.data = {k: v for k, v in raw.items() if isinstance(v, list)} if isinstance(raw, dict) else {}
            except (OSError, ValueError):
                self.data = {}

    def note(self, gid: str, game_id: str, now: float | None = None) -> bool:
        """Une partie terminée (une fois par partie et par joueur). True si c'est nouveau."""
        if not gid.startswith("acct-") or not game_id:
            return False
        now = now or time.time()
        with self.lock:
            rows = [r for r in self.data.get(gid, []) if now - r[1] < PARTY_KEEP_SECONDS]
            if any(r[0] == game_id for r in rows):
                return False
            self.data[gid] = (rows + [[game_id, now]])[-PARTY_KEEP_PER_PLAYER:]
            self._write()
        return True

    def times(self, gid: str) -> list[str]:
        with self.lock:
            rows = list(self.data.get(gid, []))
        return [pet.iso(datetime.fromtimestamp(r[1], timezone.utc)) for r in rows]

    def _write(self) -> None:
        if not self.path:
            return
        try:
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data))
            tmp.replace(self.path)
        except OSError:
            pass  # disque plein : le bonus de la partie est perdu, rien d'autre


def _now() -> datetime:
    return datetime.now(timezone.utc)


REWARD_TEXT = {"brain": "🧠 Bonus Méninges : il est tout fier de toi", "party": "🎮 Bonus partie de Party : quelle ambiance !",
               "soiree": "🪩 Bonus soirée : il a dansé toute la nuit"}
EVENT_TEXT = {"hatched": "🐣 L'œuf a éclos !", "died": "🕊️ Il s'est envolé…", "egg": "🥚 Un nouvel œuf est arrivé"}
STAGE_TEXT = {"teen": "ado", "adult": "adulte"}
VARIANT_TEXT = {"star": " étoile ✨", "classic": "", "wild": " rebelle 😜"}


def news_lines(name: str, events: list[dict], got: list[dict], applied: list[dict], unlocked: list[str]) -> list[dict]:
    lines = []
    for e in events:
        if e["kind"] == "evolved":
            lines.append({"kind": "evolved", "text": f"🎉 {name} est devenu {STAGE_TEXT[e['stage']]}{VARIANT_TEXT[e['variant']]} !"})
        elif e["kind"] in EVENT_TEXT:
            lines.append({"kind": e["kind"], "text": EVENT_TEXT[e["kind"]]})
    lines += [{"kind": "reward", "text": REWARD_TEXT[g["source"]]} for g in got]
    for a in applied:
        _, what, emoji = pet.GIFTS[a["kind"]]
        lines.append({"kind": "gift", "text": f"{emoji} {a['from']} lui a offert {what}"})
    labels = {o[0]: (o[1], o[2]) for o in pet.OUTFITS}
    lines += [{"kind": "unlocked", "text": f"{labels[u][1]} Nouvelle tenue : {labels[u][0]}"} for u in unlocked]
    return lines


class PetStore:
    def __init__(self, accounts, party_log: PartyLog, clock=_now):
        self.accounts = accounts      # app.accounts.Accounts
        self.party = party_log
        self.clock = clock

    def _rpc(self, token: str, name: str, args: dict, fallback: str):
        """Jeton vérifié d'abord (AccountError → 401) ; refus de la base → PetError (400) ; conflit → PetConflict ;
        panne → PetUnavailable (503)."""
        self.accounts._uid(token)
        try:
            r = self.accounts._get("POST", f"/rest/v1/rpc/{name}", token, json=args)
        except AccountError as e:
            raise PetUnavailable(str(e)) from e
        if r.status_code >= 500:
            raise PetUnavailable("Ton compagnon ne répond pas. Réessaie dans un instant.")
        if r.status_code == 401:
            raise AccountError("Ta connexion a expiré. Reconnecte-toi.")
        if r.status_code not in (200, 204):
            try:
                message = str(r.json().get("message", ""))
            except ValueError:
                message = ""
            kind, _, text = message.partition(": ")
            if kind == "conflict":
                raise PetConflict(text or fallback)
            raise pet.PetError(text if text else fallback)
        try:
            return r.json() if r.content else None
        except ValueError as e:
            raise PetUnavailable(fallback) from e

    # ── Mon compagnon ──

    def _live(self, token: str) -> dict:
        """Charge et fait vivre jusqu'à maintenant (récompenses et cadeaux compris), sans encore enregistrer."""
        data = self._rpc(token, "pet_load", {}, "Ton compagnon n'a pas pu être chargé.")
        data = data if isinstance(data, dict) else {}
        now = self.clock()
        saved = data.get("pet") if isinstance(data.get("pet"), dict) else None
        if saved:
            life, owner, version, journal = saved["life"], saved["owner"], int(saved.get("version") or 0), []
        else:
            life, owner = pet.new_pet(now)
            version, journal = 0, [{"kind": "egg", "detail": {"gen": 1}}]
        life, owner = copy.deepcopy(life), copy.deepcopy(owner)
        events = pet.advance(life, now, owner)
        gid = self.accounts.gid(self.accounts._uid(token))
        life, owner, got = pet.rewards(life, owner, now, data.get("brain") or [], self.party.times(gid), data.get("events") or [])
        received = [g for g in data.get("gifts") or [] if isinstance(g, dict)]
        life, owner, applied = pet.gifts(life, owner, now, received)
        unlocked = pet.unlock(owner)
        journal += [{"kind": e["kind"], "detail": {k: v for k, v in e.items() if k != "kind"}} for e in events]
        journal += [{"kind": "reward", "detail": {"source": g["source"]}} for g in got]
        journal += [{"kind": "gift_received", "detail": {"kind": a["kind"]}} for a in applied]
        return {"now": now, "life": life, "owner": owner, "version": version, "journal": journal,
                "gift_ids": [str(g.get("id")) for g in received if g.get("id")],
                "changed": not saved or bool(events or got or applied or unlocked),
                "news": news_lines(life["name"], events, got, applied, unlocked)}

    def _save(self, token: str, s: dict, cared: bool) -> None:
        proj = pet.projections(s["life"], s["now"])
        self._rpc(token, "pet_save", {
            "p_life": s["life"], "p_owner": s["owner"], "p_version": s["version"], "p_hungry_at": proj["hungry_at"],
            "p_dies_at": proj["dies_at"], "p_cared": cared, "p_gifts": s["gift_ids"], "p_journal": s["journal"][-12:],
        }, "Ton compagnon n'a pas pu être enregistré. Réessaie dans un instant.")

    def _answer(self, s: dict, effect: dict | None = None) -> dict:
        return {"pet": pet.view(s["life"], s["owner"], s["now"]), "news": s["news"], "effect": effect}

    def me(self, token: str) -> dict:
        for attempt in range(SAVE_ATTEMPTS):
            s = self._live(token)
            if not s["changed"]:
                return self._answer(s)
            try:
                self._save(token, s, cared=False)
                return self._answer(s)
            except PetConflict:
                if attempt == SAVE_ATTEMPTS - 1:
                    raise
        raise PetConflict("Ton compagnon a changé sur un autre appareil.")

    def act(self, token: str, action: str, score: int = 0, name: str = "", outfit: str = "") -> dict:
        for attempt in range(SAVE_ATTEMPTS):
            s = self._live(token)
            life, owner, effect = pet.act(s["life"], s["owner"], action, s["now"], score=score, name=name, outfit=outfit)
            s["news"] += news_lines(life["name"], effect["events"], [], [], effect["unlocked"])
            s["life"], s["owner"] = life, owner
            detail = {"score": int(score)} if action == "play" else {}
            s["journal"] += [{"kind": action, "detail": detail}]
            s["journal"] += [{"kind": e["kind"], "detail": {k: v for k, v in e.items() if k != "kind"}} for e in effect["events"]]
            try:
                self._save(token, s, cared=action in ("feed", "play", "cuddle", "heal", "sleep", "wake"))
                return self._answer(s, {"action": action, "unlocked": effect["unlocked"]})
            except PetConflict:
                if attempt == SAVE_ATTEMPTS - 1:
                    raise
        raise PetConflict("Ton compagnon a changé sur un autre appareil.")

    # ── Amis ──

    def _card(self, row: dict, now: datetime) -> dict | None:
        life = row.get("life")
        if not isinstance(life, dict):
            return None
        try:
            shown = pet.friend_view(life, now)
        except (KeyError, TypeError, ValueError):
            return None   # état illisible : cet ami n'apparaît pas plutôt que de tout casser
        return {"id": str(row.get("id")), "member": " ".join(str(row.get("name") or "?").split())[:40],
                "avatar_url": row.get("avatar_url") or None, "gifted": bool(row.get("gifted")), "pet": shown}

    def friends(self, token: str) -> dict:
        rows = self._rpc(token, "pet_friends", {}, "Les compagnons de tes amis n'ont pas pu être chargés.")
        now = self.clock()
        cards = [c for c in (self._card(r, now) for r in rows or [] if isinstance(r, dict)) if c]
        return {"friends": cards}

    def friend(self, token: str, friend_id: str) -> dict:
        row = self._rpc(token, "pet_friend", {"p_friend": friend_id}, "Ce compagnon n'a pas pu être chargé.")
        card = self._card(row, self.clock()) if isinstance(row, dict) else None
        if not card:
            raise pet.PetError("Ce compagnon n'a pas pu être chargé.")
        return card

    def gift(self, token: str, friend_id: str, kind: str) -> dict:
        if kind not in pet.GIFTS:
            raise pet.PetError("Cadeau inconnu.")
        self._rpc(token, "pet_gift", {"p_friend": friend_id, "p_kind": kind}, "Le cadeau n'a pas pu être offert.")
        return self.friend(token, friend_id)
