"""Compagnon — la collection côté serveur Party (lot A, 4.11.2026) : branchée sur PetStore (app/pet_store.py).

· au chargement : conversion des anciennes tenues, Zicou shiny tiré à l'éclosion (1 sur 64, hasard HMAC du serveur),
  cadeaux d'événement rangés (tirés par la base, voir la migration 20261104210000), certificats signés pour les
  exemplaires pas encore signés, bonus de série ;
· coffres : un Légendaire ou un Mythique tiré est FRAPPÉ en base (numéro unique, tirage limité) puis signé ;
· actions de collection (/api/pet/coll) : porter, boutique (pièces gagnées seulement), atelier (poussière), vitrine
  (titre filtré par app/moderation.py, et par la base) ;
· vérification publique d'un certificat (code ZC-…) avec la clé publique publiée.
Jamais d'argent réel ni de lot réel ; aucune récompense liée à l'alcool.
"""
import copy
import random

from . import moderation, pet, pet_catalog, pet_cert, pet_chest, pet_collection, pet_feast
from .accounts import SUPABASE_ANON_KEY, AccountError

AWARDS_KEPT = 100
COLL_ACTIONS = ("equip", "buy", "craft", "showcase", "feast", "dye", "dye_wear", "room")


def _rng(store, uid: str, purpose: str):
    return random.Random(store.seed(uid, "", purpose)) if store.rng is None else store.rng


def owned(s: dict) -> set[str]:
    return pet_collection.owned(s["owner"], s.get("items"))


def ctx(s: dict) -> dict:
    return {"owned": owned(s), "mythic_left": s.get("mythic_left") or {}, "today": pet.day_of(s["now"])}


# ── Chargement ──

def enrich(store, token: str, s: dict, data: dict, events: list[dict]) -> None:
    """Après le chargement (app/pet_store._live) : collection à jour, shiny, cadeaux d'événement, certificats."""
    s["items"] = [x for x in data.get("items") or [] if isinstance(x, dict) and pet_catalog.item(x.get("item"))]
    s["mythic_left"] = {k: int(v) for k, v in (data.get("mythic_left") or {}).items() if isinstance(v, (int, float))}
    s.setdefault("reveals", [])
    s.setdefault("awards_applied", [])
    owner, life = s["owner"], s["life"]
    had = copy.deepcopy(owner.get("coll"))
    changed = had != pet_collection.coll_of(owner)   # première fois : anciennes tenues converties
    if any(e["kind"] == "hatched" for e in events) and "shiny" not in life:
        life["shiny"] = pet_collection.roll_shiny(_rng(store, s["seed"], f"shiny:{life['gen']}"))
        changed = True
        if life["shiny"]:
            s["news"].append({"kind": "shiny", "text": f"✨ {life['name']} est un Zicou SHINY ! (1 chance sur {pet_collection.SHINY_ONE_IN})"})
            s["reveals"].append({"kind": "shiny"})
    s["items"] = sign_pending(store, token, s["items"])   # avant les révélations : le code du certificat y figure
    changed |= _apply_awards(s, data.get("awards") or [])
    changed |= finish(s)
    if changed:
        s["changed"] = True


def _apply_awards(s: dict, awards: list) -> bool:
    coll, have, done = pet_collection.coll_of(s["owner"]), owned(s), False
    for a in awards:
        if not isinstance(a, dict) or not pet_catalog.item(a.get("item")):
            continue
        aid = str(a.get("id"))
        if aid in coll["awards"]:
            s["awards_applied"].append(aid)   # déjà rangé (enregistrement réussi, marque pas encore posée)
            continue
        iid, inst = a["item"], a.get("instance")
        dust = 0
        if not inst:
            if iid in have:
                dust = pet_catalog.dust_value(iid)
                coll["dust"] += dust
            else:
                coll["inv"] = {**coll["inv"], iid: 1}
                have.add(iid)
        coll["awards"] = (coll["awards"] + [aid])[-AWARDS_KEPT:]
        s["awards_applied"].append(aid)
        serial = next((x for x in s["items"] if x.get("id") == inst), {}) if inst else {}
        s["reveals"].append({"kind": "award", "event": str(a.get("event") or "un événement Party")[:80],
                             "item": pet_catalog.public_item(iid), "dup": bool(dust), "dust": dust,
                             "serial": serial.get("serial"), "of": serial.get("edition"), "code": serial.get("code")})
        s["news"].append({"kind": "award", "text": f"🎁 Cadeau de « {str(a.get('event') or 'ta soirée')[:60]} » !"})
        done = True
    return done


def finish(s: dict) -> bool:
    """Après tout changement : bonus de série (une fois), rien de porté qui ne soit plus à lui."""
    have = owned(s)
    got = pet_collection.series_bonus(s["owner"], have)
    for g in got:
        s["news"].append({"kind": "series_done", "text": f"{g['emoji']} Série {g['label']} complète ! +{g['coins']} pièces, +{g['dust']} poussière ✨"})
    worn = pet_collection.worn(s["life"])
    pet_collection.strip_lost(s["life"], have)
    return bool(got) or worn != pet_collection.worn(s["life"])


# ── Frappe et certificats ──

def sign_pending(store, token: str, items: list[dict]) -> list[dict]:
    """Signe (Ed25519) les exemplaires pas encore signés ; un échec n'empêche rien (réessayé au prochain passage)."""
    out = []
    for x in items:
        if not x.get("sig") and store.secret:
            cert = pet_cert.sign(store.secret, x)
            try:
                x = store._rpc(token, "pet_cert_set", {"p_id": x["id"], "p_sig": cert["sig"], "p_code": cert["code"],
                                                        "p_payload": cert["payload"]}, "Certificat pas encore prêt.") or x
            except pet.PetError:
                pass
        out.append(x)
    return out


def mint(store, token: str, s: dict, iid: str, source: str, ref: str) -> dict | None:
    """Frappe un exemplaire (numéro unique, tirage limité) puis le signe ; None si tous les exemplaires sont partis."""
    try:
        inst = store._rpc(token, "pet_mint", {"p_item": iid, "p_source": source, "p_ref": ref}, "La frappe a échoué.")
    except pet.PetError as e:
        if "partis" in str(e):
            return None
        raise
    inst = sign_pending(store, token, [inst])[0]
    s["items"] = [x for x in s.get("items", []) if x.get("id") != inst.get("id")] + [inst]
    if inst.get("edition"):
        s.setdefault("mythic_left", {})[iid] = max(0, int(s["mythic_left"].get(iid, 1)) - 1)
    return inst


def settle_found(store, token: str, s: dict, action: str, found: dict | None) -> dict | None:
    """Coffre : un Légendaire ou un Mythique neuf est frappé ; plus aucun exemplaire → sa poussière à la place."""
    if not found or not found.get("mint"):
        return found
    day = pet.day_of(s["now"])
    inst = mint(store, token, s, found["item"], action, f"{action}:{day}")
    coll = pet_collection.coll_of(s["owner"])
    if inst is None:
        dust = pet_catalog.rarities()["legendary"]["dust"]
        coll["dust"] += dust
        found = found | {"mint": False, "dup": True, "dust": dust, "label": f"Tous les exemplaires sont partis : +{dust} poussière ✨"}
    else:
        found = found | {"serial": inst["serial"], "of": inst.get("edition"), "code": inst.get("code"), "instance": inst["id"],
                         "item_info": pet_catalog.public_item(found["item"])}
        if found["rarity"] == "mythic":
            s["news"].append({"kind": "mythic", "text": f"🌈 Mythique n° {inst['serial']}/{inst.get('edition')} !"})
    loop = s["owner"]["loop"]
    key = "chest" if action == "chest" else "missions"
    if isinstance(loop.get(key), dict):
        loop[key] = {**loop[key], "found": found}
    return found


# ── Ce qu'on montre ──

def friend_extras(life: dict) -> dict:
    """Chez un ami : ce qu'il porte, shiny, sa vitrine (titre déjà filtré, signalable)."""
    lvl = life.get("lvl") if isinstance(life.get("lvl"), dict) else {}
    return {"acc": pet_collection.worn(life), "shiny": bool(life.get("shiny")),
            "showcase": pet_collection.showcase_view(life), "dye": pet_collection.dyes_worn(life),
            "room": int(life.get("room") or 0),
            "lvl": {"level": int(lvl.get("level") or 1), "stars": int(lvl.get("stars") or 0)}}


def summary(s: dict) -> dict:
    """Pour l'écran d'accueil : ce qu'il porte, shiny, poussière, garantie, cadeaux à révéler."""
    coll = s["owner"].get("coll") or {}
    return {"acc": pet_collection.worn(s["life"]), "shiny": bool(s["life"].get("shiny")), "dust": int(coll.get("dust", 0)),
            "pity_left": pet_chest.pity_left(int(coll.get("pity", 0))), "reveals": s.get("reveals", []),
            "showcase": pet_collection.showcase_view(s["life"]), "dex": _dex_count(s),
            "dye": pet_collection.dyes_worn(s["life"]), "room": int(coll.get("room") or 0)}


def _dex_count(s: dict) -> dict:
    have = owned(s)
    regular = [i for i in pet_catalog.items() if pet_catalog.item(i)["rarity"] != "mythic"]
    return {"have": sum(1 for i in regular if i in have), "total": len(regular),
            "mythics": sum(1 for i in pet_catalog.mythics() if i in have)}


def full(store, s: dict) -> dict:
    """Écran Collection : Zicoudex, boutique du jour, atelier, décor, coffre (chances), vitrine, certificats."""
    have, coll, loop = owned(s), pet_collection.coll_of(s["owner"]), s["owner"].get("loop") or {}
    today = pet.day_of(s["now"])
    shop = pet_collection.shop_today(_shop_rng(store, today), today)
    bought = coll["shop"].get("bought", []) if coll["shop"].get("day") == today else []
    snacks = coll["snacks"]["n"] if coll["snacks"].get("day") == today else 0
    craftable = [i for i in pet_catalog.items() if pet_catalog.craft_cost(i, today) is not None]
    room = int(coll.get("room") or 0)
    return {
        "coins": int(loop.get("coins", 0)), "dust": coll["dust"], "acc": pet_collection.worn(s["life"]),
        "shiny": bool(s["life"].get("shiny")), "shiny_odds": f"1 chance sur {pet_collection.SHINY_ONE_IN} à l'éclosion",
        "dex": pet_collection.dex(have, s.get("items"), today),
        "shop": [pet_catalog.public_item(i) | {"price": pet_catalog.shop_price(i), "owned": i in have, "bought": i in bought}
                 for i in shop],
        "decor": [pet_catalog.public_item(i) | {"price": pet_catalog.shop_price(i), "owned": i in have}
                  for i in pet_catalog.decor_items(today)],
        "shop_rule": {"commons": pet_collection.SHOP_COMMONS, "rare_today": pet_collection.rare_day(today),
                      "rare_every": pet_collection.SHOP_RARE_EVERY},
        "room": {"level": room, "price": pet_collection.room_price(room), "max": pet_collection.ROOM_MAX},
        "dyes": {"colors": [{"id": d, "label": label, "hex": hx} for d, label, hx in pet_collection.DYES],
                 "prices": pet_collection.DYE_PRICES, "owned": coll.get("dyes") or {},
                 "worn": pet_collection.dyes_worn(s["life"])},
        "feast": pet_feast.view(s["life"], s["owner"], s["now"], today),
        "snacks": [{"id": k, "label": pet_chest.SNACKS[k][0], "emoji": pet_chest.SNACKS[k][1], "price": p}
                   for k, p in pet_collection.SNACK_PRICES.items()],
        "snacks_left": max(0, pet_collection.SNACKS_PER_DAY - snacks),
        "craft": [pet_catalog.public_item(i) | {"cost": pet_catalog.craft_cost(i, today), "owned": i in have} for i in craftable],
        "rates": [{"rarity": r["id"], "label": r["label"], "dust": r["dust"], "craft": r["craft"]}
                  for r in pet_catalog.data()["rarities"] if r["id"] != "mythic"],
        "odds": pet_chest.odds(coll["pity"], s.get("mythic_left")),
        "bonus_odds": pet_chest.odds(coll["pity"], s.get("mythic_left"), bonus=True),
        "pity_left": pet_chest.pity_left(coll["pity"]), "pity": pet_chest.PITY,
        "showcase": pet_collection.showcase_view(s["life"]),
        "items": [_instance_view(x) for x in s.get("items", [])],
        "slots": [{"id": x["id"], "label": x["label"]} for x in pet_catalog.data()["slots"]],
        "series_done": coll["series"],
    }


def _instance_view(x: dict) -> dict:
    return pet_catalog.public_item(x["item"]) | {"instance": x["id"], "serial": x["serial"], "of": x.get("edition"),
                                                 "code": x.get("code"), "minted_at": x.get("minted_at"), "source": x.get("source")}


def _shop_rng(store, day: str):
    """Même boutique pour tout le monde ce jour-là (graine HMAC du serveur, imprévisible à l'avance)."""
    return random.Random(store.seed("shop", day, "shop"))


# ── Actions de collection ──

def act(store, token: str, action: str, item: str = "", slot: str = "", items: list[str] | None = None,
        title: str = "") -> dict:
    if action not in COLL_ACTIONS:
        raise pet.PetError("Action inconnue")
    if action == "showcase":
        title = " ".join(str(title or "").split())[:pet_collection.SHOWCASE_TITLE_MAX]
        if title:
            try:
                title = moderation.require_clean(title, "showcase")
            except moderation.ContentRefused as e:
                raise pet.PetError(str(e)) from None

    def work(s: dict) -> dict:
        have = owned(s)
        today = pet.day_of(s["now"])
        try:
            out = _do(store, token, s, action, have, today, item, slot, items or [], title)
        except (pet_collection.CollectionError, pet_feast.FeastError) as e:
            raise pet.PetError(str(e)) from None
        finish(s)
        s["journal"] += [{"kind": f"coll_{action}", "detail": {"item": item or slot}}]
        s["want_full"] = True
        return out
    return store._retry(token, work)


def _do(store, token, s, action, have, today, item, slot, items, title) -> dict:
    if action == "equip":
        target = slot or (pet_catalog.item(item) or {}).get("slot", "")
        if not target and not item:   # « Sans tenue » : il retire tout
            s["life"]["acc"], s["life"]["outfit"] = {}, None
            return {"action": action, "slot": "", "item": ""}
        if not target:
            raise pet_collection.CollectionError("Pas encore débloquée : cet objet n'est pas encore à toi.")
        pet_collection.equip(s["life"], have, target, item)
        return {"action": action, "slot": target, "item": item}
    if action == "feast":
        done = pet_feast.buy(s["life"], s["owner"], item, s["now"], today, lambda price: pet_collection._spend(s["owner"], price))
        info = pet_feast.FEASTS[item]
        s["news"].append({"kind": "feast", "text": f"{info['emoji']} {info['label']} servie : {info['effect'].lower()} (−{done['price']} 🪙)"})
        return {"action": action, **done}
    if action == "room":
        done = pet_collection.grow_room(s["owner"], s["life"])
        s["news"].append({"kind": "room", "text": f"🏠 Chambre agrandie : niveau {done['level']} (−{done['price']} 🪙)"})
        return {"action": action, **done}
    if action in ("dye", "dye_wear"):
        color = slot   # la couleur voyage dans « slot » (même modèle de requête)
        if action == "dye":
            done = pet_collection.buy_dye(s["owner"], have, item, color)
            pet_collection.wear_dye(s["owner"], s["life"], item, color)
            s["news"].append({"kind": "dye", "text": f"🎨 Teinture « {_dye_label(color)} » : {_label(item)} (−{done['price']} 🪙)"})
            return {"action": action, **done}
        pet_collection.wear_dye(s["owner"], s["life"], item, color)
        return {"action": action, "item": item, "color": color}
    if action == "buy":
        shop = pet_collection.shop_today(_shop_rng(store, today), today)
        done = pet_collection.buy(s["owner"], have, item, today, shop)
        s["news"].append({"kind": "bought", "text": f"🛍️ {_label(item)} : à toi ! (−{done['price']} 🪙)"})
        return {"action": action, **done}
    if action == "craft":
        done = pet_collection.craft(s["owner"], have, item, today)
        inst = mint(store, token, s, item, "atelier", f"atelier:{item}") if done["mint"] else None
        s["news"].append({"kind": "crafted", "text": f"🔨 Fabriqué à l'atelier : {_label(item)} (−{done['cost']} ✨)"})
        return {"action": action, **done, **({"serial": inst["serial"], "code": inst.get("code")} if inst else {})}
    pet_collection.set_showcase(s["life"], have, items, title, s.get("items"))
    return {"action": action}


def _dye_label(color: str) -> str:
    return next((label for d, label, _ in pet_collection.DYES if d == color), color)


def _label(iid: str) -> str:
    if iid.startswith("snack:"):
        return pet_chest.SNACKS.get(iid.split(":", 1)[1], ("Goûter",))[0]
    return (pet_catalog.item(iid) or {}).get("label", iid)


# ── Vérification publique ──

def verify(store, code: str) -> dict:
    """Certificat d'un objet (code ZC-…) : authentique si la signature tient avec la clé publique publiée."""
    norm = pet_cert.normalize_code(code)
    if not norm:
        raise pet.PetError("Ce code ne ressemble pas à un code d'authenticité (ZC-XXXX-XXXX-XXXX).")
    try:
        r = store.accounts._get("POST", "/rest/v1/rpc/pet_verify", SUPABASE_ANON_KEY, json={"p_code": norm})
    except AccountError as e:
        raise pet.PetError(str(e)) from e
    row = r.json() if r.status_code == 200 and r.content else None
    if not isinstance(row, dict) or not row.get("sig"):
        return {"code": norm, "found": False}
    key = pet_cert.public_key_b64(store.secret)
    good = bool(row.get("payload")) and pet_cert.verify(key, row["payload"], row["sig"]) and pet_cert.code_of(row["sig"]) == norm
    return {"code": norm, "found": True, "authentic": good, "key_fingerprint": pet_cert.fingerprint(key),
            "item": pet_catalog.public_item(row["item"]) if pet_catalog.item(row.get("item")) else None,
            "serial": row.get("serial"), "of": row.get("edition"), "minted_at": row.get("minted_at"),
            "source": row.get("source"), "event": row.get("event"), "retired": bool(row.get("retired")),
            "owners": [{"since": o.get("since"), "how": o.get("how")} for o in row.get("owners") or []],
            "payload": row.get("payload"), "sig": row.get("sig")}


def public_key(store) -> dict:
    key = pet_cert.public_key_b64(store.secret)
    return {"alg": "Ed25519", "key": key, "fingerprint": pet_cert.fingerprint(key), "format": pet_cert.FORMAT,
            "payload": "ZC1|exemplaire|objet|numéro|tirage (0 = sans limite)|date de frappe UTC|origine"}
