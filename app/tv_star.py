"""Zicou en vedette à l'Apple TV (économie du 4.11.2026, scratchpad economie/usages-pieces.md, usage n° 4).

Pendant une soirée, un présent dépense 150 pièces GAGNÉES : son Zicou entre en dansant au milieu de l'écran de l'Apple
TV pendant 30 secondes, avec sa tenue. Une fois par soirée et par personne, à la suite des autres (file d'attente).
Aucun texte libre : seul le surnom du compte, s'il passe la modération (app/tv_zicou.tv_name). La musique n'est
JAMAIS touchée (ni file, ni priorité, ni saut de titre) : seule l'image change. L'accès à une partie non plus.

La file vit en mémoire du serveur Party (comme les Zicou de la soirée) ; « déjà fait ce soir » est aussi gardé dans le
Zicou du compte (owner.loop.tv_star = la soirée), pour tenir après un redémarrage. Pièces débitées d'abord ; si la
place ne peut pas être prise, elles sont rendues.
"""
import threading
import time

from . import pet, pet_collection, tv_zicou

PRICE = 150
SECONDS = 30
QUEUE_MAX = 20


class StarError(pet.PetError):
    pass


class TvStars:
    def __init__(self, clock=time.time):
        self.clock = clock
        self.lock = threading.Lock()
        self.slots: list[dict] = []   # {"uid", "soiree", "key", "name", "look", "start", "end"}

    def _prune(self, now: float) -> None:
        self.slots = [s for s in self.slots if s["end"] > now]

    def booked(self, uid: str, soiree: str) -> dict | None:
        with self.lock:
            self._prune(self.clock())
            return next((s for s in self.slots if s["uid"] == uid and s["soiree"] == soiree), None)

    def full(self) -> bool:
        with self.lock:
            self._prune(self.clock())
            return len(self.slots) >= QUEUE_MAX

    def book(self, uid: str, soiree: str, name: str | None, look: dict) -> dict:
        now = self.clock()
        with self.lock:
            self._prune(now)
            if any(s["uid"] == uid and s["soiree"] == soiree for s in self.slots):
                raise StarError("Ton Zicou est déjà dans la file de ce soir 🌟")
            if len(self.slots) >= QUEUE_MAX:
                raise StarError("La file de l'Apple TV est pleine pour l'instant. Réessaie dans quelques minutes.")
            start = max([now] + [s["end"] for s in self.slots])
            slot = {"uid": uid, "soiree": soiree, "key": tv_zicou.tv_key(uid), "name": name, "look": look,
                    "start": start, "end": start + SECONDS}
            self.slots.append(slot)
            return self._public(slot, now)

    def cancel(self, uid: str, soiree: str) -> None:
        with self.lock:
            self.slots = [s for s in self.slots if not (s["uid"] == uid and s["soiree"] == soiree)]

    def keep_only(self, soiree: str) -> None:
        """Une nouvelle soirée a commencé : la file des soirées d'avant part."""
        with self.lock:
            self.slots = [s for s in self.slots if s["soiree"] == soiree]

    @staticmethod
    def _public(slot: dict, now: float) -> dict:
        return {"starts_in": max(0, round(slot["start"] - now)), "seconds": SECONDS}

    def status(self, uid: str, soiree: str) -> dict | None:
        slot = self.booked(uid, soiree)
        return self._public(slot, self.clock()) if slot else None

    def on_air(self, soiree: str) -> tuple[dict | None, int]:
        """(la vedette à l'écran maintenant, ou None ; nombre de Zicou qui attendent). Jamais l'identifiant du compte."""
        now = self.clock()
        with self.lock:
            self._prune(now)
            mine = [s for s in self.slots if s["soiree"] == soiree]
            live = next((s for s in mine if s["start"] <= now < s["end"]), None)
            waiting = sum(1 for s in mine if s["start"] > now)
        if not live:
            return None, waiting
        return ({"key": live["key"], "name": live["name"], **live["look"],
                 "left": max(0, round(live["end"] - now)), "seconds": SECONDS}, waiting)


def book(stars: TvStars, pets, accounts, token: str, uid: str, soiree: str) -> dict:
    """Réserver le passage : pièces débitées (Zicou vivant, une fois par soirée), puis place dans la file."""
    if stars.booked(uid, soiree):
        raise StarError("Ton Zicou est déjà dans la file de ce soir 🌟")
    if stars.full():
        raise StarError("La file de l'Apple TV est pleine pour l'instant. Réessaie dans quelques minutes.")
    seen: dict = {}

    def pay(s: dict) -> dict:
        life, loop = s["life"], s["owner"].setdefault("loop", {})
        if s.get("fresh") or life["stage"] in ("egg", "dead"):
            raise StarError("Il faut un Zicou éclos pour passer à l'Apple TV 🥚")
        if loop.get("tv_star") == soiree:
            raise StarError("Ton Zicou est déjà passé en vedette ce soir. À la prochaine soirée 🌟")
        try:
            pet_collection._spend(s["owner"], PRICE)
        except pet_collection.CollectionError as e:
            raise StarError(str(e)) from None
        loop["tv_star"] = soiree
        s["journal"] += [{"kind": "tv_star", "detail": {"price": PRICE}}]
        seen["life"] = life
        return {"paid": PRICE}

    pets._retry(token, pay)
    try:
        name, _ = tv_zicou.read_member(accounts, pets, token, uid)
    except Exception:  # noqa: BLE001 — sans surnom, il passe quand même (sans nom)
        name = ""
    look = tv_zicou.look(seen["life"], pets.clock()) if seen.get("life") else None
    try:
        if look is None:
            raise StarError("Ton Zicou n'a pas pu monter sur scène. Réessaie dans un instant.")
        return stars.book(uid, soiree, tv_zicou.tv_name(name), look)
    except StarError:
        def refund(s: dict) -> dict:
            loop = s["owner"].setdefault("loop", {})
            loop["coins"] = int(loop.get("coins") or 0) + PRICE
            loop.pop("tv_star", None)
            s["journal"] += [{"kind": "tv_star_refund", "detail": {"price": PRICE}}]
            return {"refund": PRICE}
        pets._retry(token, refund)
        raise
