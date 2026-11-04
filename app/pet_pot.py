"""Zicou — la caisse commune du groupe (économie du 4.11.2026, scratchpad economie/usages-pieces.md, usage n° 5).

Tout le groupe verse des pièces GAGNÉES pour débloquer un décor commun (boule disco géante au Salon de Party, puis
néons, puis feu d'artifice à l'Apple TV ; 5 000 pièces chacun, migration 20261105120000). SANS classement : on montre
le total, le nombre de donateurs et les prénoms des amis qui ont donné (ordre alphabétique), jamais le montant des
autres. Les pièces ne vont à personne : elles disparaissent dans l'objectif (aucun transfert de monnaie).
Versement : pièces débitées par le serveur Party d'abord (enregistrées), puis notées par la base avec une référence
unique (un rejeu ne compte qu'une fois) ; si la base refuse, elles sont rendues.
"""
import logging
import secrets
import threading
import time

from . import pet, pet_collection
from .accounts import SUPABASE_ANON_KEY, AccountError

STEPS = (10, 50, 100, 250)      # montants proposés (10 à 250 par versement, comme la base)
DAILY_MAX = 500                 # par personne et par jour (la base le garantit aussi)
MIN_GIVE = 10
PUBLIC_TTL = 60.0               # totaux pour l'Apple TV : relus au plus une fois par minute
log = logging.getLogger("party.pet")


def shape(state: dict) -> dict:
    """Ce que voit le membre : objectif en cours, objectifs atteints, merci sans classement, ce qu'il peut encore donner."""
    goals = [g for g in state.get("goals") or [] if isinstance(g, dict)]
    rows = [{"id": str(g.get("id")), "label": str(g.get("label")), "emoji": str(g.get("emoji")),
             "target": int(g.get("target") or 0), "total": min(int(g.get("total") or 0), int(g.get("target") or 0))}
            for g in goals]
    current = next((g for g in rows if g["total"] < g["target"]), None)
    mine_today = int(state.get("mine_today") or 0)
    return {"current": current, "reached": [g for g in rows if g["total"] >= g["target"]], "goals": rows,
            "donors": int(state.get("donors") or 0), "friends": [str(n)[:40] for n in state.get("friends") or []][:30],
            "mine": int(state.get("mine") or 0), "left_today": max(0, DAILY_MAX - mine_today), "steps": list(STEPS),
            "daily_max": DAILY_MAX}


def get(store, token: str) -> dict:
    state = store._rpc(token, "pet_pot_get", {}, "La caisse commune n'a pas pu être chargée.")
    return shape(state if isinstance(state, dict) else {})


def give(store, token: str, amount: int) -> dict:
    """Verser `amount` pièces dans l'objectif en cours (jamais plus que ce qui manque, ni plus de 500 par jour)."""
    if amount not in STEPS:
        raise pet.PetError("Choisis 10, 50, 100 ou 250 pièces.")
    pot = get(store, token)
    goal = pot["current"]
    if not goal:
        raise pet.PetError("Tous les objectifs sont atteints 🎉 Le prochain arrive bientôt.")
    amount = min(amount, max(MIN_GIVE, goal["target"] - goal["total"]), pot["left_today"])
    if amount < MIN_GIVE:
        raise pet.PetError(f"{DAILY_MAX} pièces par jour au plus dans la caisse commune. Merci pour ta générosité 💜")
    ref = f"pot-{secrets.token_hex(12)}"

    def pay(s: dict) -> dict:
        if s.get("fresh"):
            raise pet.PetError("Il faut un Zicou pour participer à la caisse commune 🥚")
        try:
            pet_collection._spend(s["owner"], amount)
        except pet_collection.CollectionError as e:
            raise pet.PetError(str(e)) from None
        s["journal"] += [{"kind": "pot_give", "detail": {"goal": goal["id"], "coins": amount}}]
        return {"paid": amount}

    def refund(s: dict) -> dict:
        s["owner"].setdefault("loop", {})["coins"] = int(s["owner"]["loop"].get("coins") or 0) + amount
        s["journal"] += [{"kind": "pot_refund", "detail": {"goal": goal["id"], "coins": amount}}]
        return {"refund": amount}

    store._retry(token, pay)
    try:
        state = store._rpc(token, "pet_pot_give", {"p_goal": goal["id"], "p_coins": amount, "p_ref": ref},
                           "Le versement n'a pas pu être fait.")
    except pet.PetError:
        try:
            store._retry(token, refund)
        except pet.PetError:
            log.error("Zicou : versement à la caisse refusé ET pièces pas rendues (%s)", ref)
        raise
    out = shape(state if isinstance(state, dict) else {})
    reached = goal["id"] in {g["id"] for g in out["reached"]}
    return out | {"given": amount, "goal": goal, "just_reached": reached}


class PublicPot:
    """Totaux sans nom, pour l'Apple TV (fonction pet_pot_public, sans compte), gardés une minute."""

    def __init__(self, accounts, clock=time.monotonic):
        self.accounts, self.clock = accounts, clock
        self.lock = threading.Lock()
        self.at, self.value = -1e9, []

    def reached(self) -> list[dict]:
        with self.lock:
            if self.clock() - self.at < PUBLIC_TTL:
                return self.value
        try:
            r = self.accounts._get("POST", "/rest/v1/rpc/pet_pot_public", SUPABASE_ANON_KEY, json={})
            rows = r.json() if r.status_code == 200 and r.content else []
        except (AccountError, ValueError):
            rows = None
        value = [{"id": str(g.get("id")), "emoji": str(g.get("emoji")), "label": str(g.get("label"))}
                 for g in rows or [] if isinstance(g, dict) and int(g.get("total") or 0) >= int(g.get("target") or 1)]
        with self.lock:
            if rows is not None:
                self.at, self.value = self.clock(), value
            return self.value
