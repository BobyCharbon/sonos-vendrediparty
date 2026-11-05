"""Zicou : premier cadeau garanti à la toute première éclosion (accueil « Quelqu'un t'attend… », 4.11).

Annoncé comme tel dans l'app (aucun tirage au hasard) : le nœud papillon, déjà porté, et 50 pièces. Une seule fois
par compte (owner["welcome"]), seulement pour le tout premier œuf (gen 1). Les pièces vont dans la tirelire de la
boucle du jour (app/pet_loop.py) ; le nœud est déjà à lui depuis le premier jour (app/pet.py, new_owner)."""
from . import pet, pet_collection, pet_loop

WELCOME_ITEM = "noeud"      # « Nœud papillon » du catalogue (welcome: true)
WELCOME_COINS = 50


def apply(s: dict, events: list[dict]) -> dict | None:
    """À appeler juste après le chargement (pet_store._live). Rend le cadeau donné, ou None."""
    life, owner = s["life"], s["owner"]
    hatched = any(e.get("kind") == "hatched" for e in events)
    if not hatched or life.get("gen") != 1 or owner.get("welcome"):
        return None
    gift = {"item": WELCOME_ITEM, "coins": WELCOME_COINS, "at": pet.iso(s["now"])}
    owner["welcome"] = gift
    pet_loop.loop_of(owner)["coins"] += WELCOME_COINS
    worn = pet_collection.worn(life)
    if "neck" not in worn:
        life["acc"] = {**worn, "neck": WELCOME_ITEM}
        life["outfit"] = None
    s["news"].append({"kind": "welcome", "item": WELCOME_ITEM, "coins": WELCOME_COINS,
                      "text": f"🎁 Cadeau de bienvenue : nœud papillon et {WELCOME_COINS} pièces"})
    s["changed"] = True
    return gift


def status(s: dict, view: dict, daily: dict) -> dict:
    """Ce que l'en-tête et l'onglet Zicou montrent (sans ouvrir le panneau, sans rien enregistrer).

    need : la raison la plus forte d'y passer, ou None. « alert » (il a faim) et « gift » (un ami lui a offert
    quelque chose) allument le point rouge de la pastille ; « chest » (coffre du jour prêt) ne fait qu'une pastille
    sur l'onglet et une bulle une fois par jour : jamais de chiffre, jamais d'alarme pour un simple coffre."""
    gifts = bool(s.get("gift_ids"))
    alive = view["stage"] not in ("egg", "dead")
    need = None
    if alive and view.get("alert"):
        need = "alert"
    elif alive and gifts:
        need = "gift"
    elif alive and (daily.get("chest") or {}).get("state") == "ready":
        need = "chest"
    return {"adopted": True, "name": view["name"], "stage": view["stage"], "variant": view["variant"],
            "emotion": view["emotion"], "asleep": view["asleep"], "next_stage_in": view["next_stage_in"],
            "gen": view["gen"], "welcome": bool(s["owner"].get("welcome")),
            "acc": pet_collection.worn(s["life"]), "shiny": bool(s["life"].get("shiny")), "need": need}
