"""« Le Masque » — tout le monde répond en secret à la même question profonde, puis devine qui a écrit quoi.

Un tour : une question s'affiche ; chacun écrit sa réponse sur son téléphone (une phrase). Quand tout le monde a écrit,
les réponses apparaissent mélangées, sans prénom (chacun voit celles des autres, jamais la sienne : un voisin ne doit
pas pouvoir la repérer). Chacun relie les réponses aux prénoms.

Le masque se règle UNE fois pour toute la table, par l'organisateur avant la partie (avis du 04.11) :
- « open » (masques levés, par défaut) : à la révélation, l'auteur de chaque réponse, qui a voté quoi (juste ou faux) ;
- « closed » (masques gardés) : personne ne saura jamais qui a écrit quoi ; on voit seulement à qui on a pensé, en
  nombre, sans le prénom des votants (sinon l'absence de l'auteur parmi les votants le trahirait). Pas de points.

Points (masques levés) : 1 par auteur trouvé. Pas de point pour une réponse drôle : on joue la sincérité. L'animateur
peut retirer une réponse (elle sort du jeu, sans son auteur).

Module autonome et testable (mêmes conventions que debate.py) : il ne connaît que la partie `g` ; les droits
d'animateur restent dans main.py, et tout passe par le verrou unique des jeux.
"""
import random

from .masque_cards import MASQUE_CARDS
from .moderation import ContentRefused, require_clean

CATS = {
    "souvenirs": "📼 Souvenirs", "toi": "🪞 Toi en vrai", "liens": "🤝 Les liens",
    "valeurs": "🧭 Valeurs", "reves": "🌠 Rêves & peurs", "imaginaire": "🔮 Et si…",
}
LEVELS = {"leger": "🌤 Léger", "profond": "🌊 Profond", "intime": "🕯 Intime"}
DEFAULT_LEVELS = ["leger", "profond"]  # l'intime se choisit : jamais proposé d'office
COUNTS = (5, 8, 12)
MASKS = {"open": "🙋 Masques levés", "closed": "🎭 Masques gardés"}
DEFAULT_MASK = "open"
MIN_PLAYERS = 3  # deviner parmi deux réponses n'est pas un jeu
MIN_ANSWER, MAX_ANSWER = 2, 140
POINT_FOUND = 1


class MasqueError(ValueError):
    """Message affiché tel quel au joueur."""


def state(g: dict) -> dict:
    S = g.setdefault("masque", {
        "cats": list(CATS), "levels": list(DEFAULT_LEVELS), "count": COUNTS[1], "mask": DEFAULT_MASK, "used": [],
        "n": 0, "q": None, "answers": {}, "slots": [], "hidden": [], "guesses": {}, "sent": {}, "scores": {},
        "history": [], "result": None,
    })
    S.setdefault("mask", DEFAULT_MASK)  # partie créée avant le réglage commun
    return S


def is_open(S: dict) -> bool:
    return S.get("mask", DEFAULT_MASK) == "open"


def init(g: dict):
    state(g)


def _player(g: dict, gid: str) -> dict | None:
    return next((p for p in g["players"] if p["id"] == gid), None)


def _name(g: dict, gid: str) -> str:
    p = _player(g, gid)
    return p["name"] if p else "?"


def deck(S: dict) -> list[int]:
    return [i for i, (cat, level, _) in enumerate(MASQUE_CARDS) if cat in S["cats"] and level in S["levels"]]


def configure(g: dict, settings: dict):
    """Catégories, niveaux, nombre de questions et masque (levé ou gardé pour toute la table) : avant la partie, ou
    entre deux parties."""
    S = state(g)
    if g["phase"] not in ("lobby", "end"):
        raise MasqueError("Les réglages se changent avant la partie")
    cats = settings.get("cats", S["cats"])
    levels = settings.get("levels", S["levels"])
    if not isinstance(cats, list) or not cats or any(not isinstance(c, str) or c not in CATS for c in cats):
        raise MasqueError("Garde au moins une catégorie")
    if not isinstance(levels, list) or not levels or any(not isinstance(lv, str) or lv not in LEVELS for lv in levels):
        raise MasqueError("Garde au moins un niveau")
    count = settings.get("count", S["count"])
    if isinstance(count, bool) or not isinstance(count, int) or count not in COUNTS:
        raise MasqueError("Nombre de questions inconnu")
    mask = settings.get("mask", S["mask"])
    if not isinstance(mask, str) or mask not in MASKS:
        raise MasqueError("Choix du masque inconnu")
    chosen = {"cats": list(dict.fromkeys(cats)), "levels": list(dict.fromkeys(levels))}
    if not deck(chosen):
        raise MasqueError("Aucune question pour ce choix")
    S.update(chosen, count=count, mask=mask)


def start(g: dict, rng=random):
    if len(g["players"]) < MIN_PLAYERS:
        raise MasqueError(f"Il faut au moins {MIN_PLAYERS} joueurs")
    S = state(g)
    S.update(n=0, scores={}, history=[], result=None)
    _deal(g, rng)


def _deal(g: dict, rng=random):
    """Nouvelle question, jamais deux fois la même dans la soirée (tant que le paquet n'est pas épuisé)."""
    S = state(g)
    cards = deck(S)
    if not cards:
        raise MasqueError("Aucune question pour ce choix")
    fresh = [i for i in cards if i not in S["used"]]
    if not fresh:  # paquet épuisé : on le remélange, sans retomber sur la question qu'on vient de voir
        last = S["used"][-1] if S["used"] else None
        S["used"] = [i for i in S["used"] if i not in cards]
        fresh = [i for i in cards if i != last] or cards
    pick = rng.choice(fresh)
    S["used"].append(pick)
    cat, level, text = MASQUE_CARDS[pick]
    S.update(q={"text": text, "cat": cat, "level": level}, answers={}, slots=[], hidden=[], guesses={},
             sent={}, result=None, n=S["n"] + 1)
    g["phase"] = "write"
    g["round"] = g.get("round", 0) + 1


INVISIBLE = {0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x2060, 0xFEFF, *range(0x202A, 0x202F), *range(0x2066, 0x206A)}


def _clean(text) -> str:
    """Une phrase lisible : sans caractères de contrôle ni invisibles (une réponse « vide » ne passe pas)."""
    text = "".join(c for c in str(text or "") if ord(c) >= 32 and ord(c) not in INVISIBLE)
    return " ".join(text.split())[:MAX_ANSWER]


def write(g: dict, gid: str, text, rng=random):
    """Sa réponse (modifiable tant que tout le monde n'a pas écrit). La dernière réponse lance la devinette."""
    S = state(g)
    if g["phase"] != "write" or not _player(g, gid):
        raise MasqueError("Pas maintenant")
    text = _clean(text)
    if len(text) < MIN_ANSWER:
        raise MasqueError("Écris au moins quelques mots")
    try:  # filtre commun (Apple 1.2) : la réponse s'affiche à toute la table et sur la TV
        text = require_clean(text, "answer")
    except ContentRefused as e:
        raise MasqueError(str(e)) from None
    S["answers"][gid] = text
    if all(p["id"] in S["answers"] for p in g["players"]):
        show(g, rng)


def swap(g: dict, rng=random):
    """L'animateur change de question tant que personne n'a répondu (la question ne compte qu'une fois)."""
    S = state(g)
    if g["phase"] != "write":
        raise MasqueError("Pas maintenant")
    if S["answers"]:
        raise MasqueError("Quelqu'un a déjà répondu")
    S["n"] -= 1
    _deal(g, rng)


def show(g: dict, rng=random):
    """Fin de l'écriture (tous ont écrit, ou l'animateur n'attend plus) : réponses mélangées, sans prénom."""
    S = state(g)
    if g["phase"] != "write":
        raise MasqueError("Pas maintenant")
    authors = [p["id"] for p in g["players"] if p["id"] in S["answers"]]
    if len(authors) < MIN_PLAYERS:
        raise MasqueError(f"Il faut au moins {MIN_PLAYERS} réponses")
    rng.shuffle(authors)
    S["slots"] = [{"gid": a, "text": S["answers"][a]} for a in authors]
    # Prénoms proposés figés à cet instant : un départ ou un retrait ne doit rien trahir par élimination.
    S["authors"] = [{"gid": p["id"], "pid": p["pid"], "name": p["name"]} for p in g["players"] if p["id"] in S["answers"]]
    S["guessers"] = [p["id"] for p in g["players"]]  # un retardataire peut deviner, mais on ne l'attend pas
    g["phase"] = "guess"


def _mine(S: dict, gid: str) -> int | None:
    return next((i for i, s in enumerate(S["slots"]) if s["gid"] == gid), None)


def _everyone_sent(g: dict) -> bool:
    """Tous ceux qui étaient là quand les réponses sont apparues (et encore là) ont envoyé leurs choix."""
    S = state(g)
    here = {p["id"] for p in g["players"]}
    expected = [x for x in S.get("guessers") or here if x in here]
    return bool(expected) and all(S["sent"].get(x) for x in expected)


def guess(g: dict, gid: str, picks, unmask=None):
    """Ses devinettes (réponse → prénom). Envoi définitif. `unmask` (ancien choix individuel du masque, encore envoyé
    par une page restée ouverte) est ignoré : le masque se règle pour toute la table avant la partie."""
    S = state(g)
    if g["phase"] != "guess" or not _player(g, gid):
        raise MasqueError("Pas maintenant")
    if S["sent"].get(gid):
        raise MasqueError("Tes choix sont déjà envoyés")
    if not isinstance(picks, dict):
        raise MasqueError("Choix inconnus")
    mine = _mine(S, gid)
    pids = {a["pid"]: a["gid"] for a in S.get("authors") or []}
    clean: dict[str, str] = {}
    for slot, pid in picks.items():
        try:
            index = int(slot)
        except (TypeError, ValueError):
            raise MasqueError("Choix inconnus") from None
        if not isinstance(pid, str) or not 0 <= index < len(S["slots"]) or index == mine:
            raise MasqueError("Choix inconnus")
        who = pids.get(pid)
        if who == gid:
            raise MasqueError("Ce joueur n'a pas répondu")
        if who is None or index in S["hidden"]:
            continue  # réponse retirée ou prénom inconnu entre-temps : ce choix ne compte pas, l'envoi passe
        if who in clean.values():
            raise MasqueError("Un prénom ne va qu'avec une réponse")
        clean[str(index)] = who
    S["guesses"][gid] = clean
    S["sent"][gid] = True
    if _everyone_sent(g):
        reveal(g)


def hide(g: dict, index):
    """L'animateur retire une réponse (déplacée, blessante) : elle sort du jeu et son auteur reste inconnu."""
    S = state(g)
    if g["phase"] != "guess":
        raise MasqueError("Pas maintenant")
    try:
        index = int(index)
    except (TypeError, ValueError):
        raise MasqueError("Réponse inconnue") from None
    if not 0 <= index < len(S["slots"]):
        raise MasqueError("Réponse inconnue")
    if index not in S["hidden"]:
        S["hidden"].append(index)
        for picks in S["guesses"].values():
            picks.pop(str(index), None)


REPORTED = "Réponse retirée après un signalement."


def report(g: dict, gid: str, index) -> dict | None:
    """« Signaler » (tout joueur, Apple 1.2) : la réponse disparaît aussitôt pour toute la table (et la TV), sans dire
    qui l'a signalée ; renvoie {text, author} pour le journal de l'admin (None si déjà retirée)."""
    S = state(g)
    if g["phase"] not in ("guess", "reveal") or not _player(g, gid):
        raise MasqueError("Pas maintenant")
    try:
        index = int(index)
    except (TypeError, ValueError):
        raise MasqueError("Réponse inconnue") from None
    if not 0 <= index < len(S["slots"]):
        raise MasqueError("Réponse inconnue")
    if index == _mine(S, gid):
        raise MasqueError("C'est ta réponse")
    slot = S["slots"][index]
    if g["phase"] == "guess":
        if index in S["hidden"]:
            return None
        hide(g, index)
    else:
        row = (S["result"] or [None] * (index + 1))[index]
        if not row or row.get("hidden"):
            return None
        # Même liste que la dernière entrée de l'historique : la réponse sort aussi du bilan de fin.
        S["result"][index] = {"text": None, "hidden": True, "reported": True}
    return {"text": slot["text"], "author": slot["gid"]}


def _frozen_name(g: dict, gid: str) -> str:
    """Le prénom figé à l'apparition des réponses (un auteur parti reste nommé, masques levés), sinon l'actuel."""
    frozen = next((a["name"] for a in state(g).get("authors") or [] if a["gid"] == gid), None)
    return frozen or _name(g, gid)


def _tally(names: list[str]) -> list[dict]:
    """Masques gardés : à qui on a pensé, en nombre, triés par nombre puis par prénom (jamais dans l'ordre des votants,
    qui dirait qui a voté et donc, par absence, qui a écrit)."""
    counts: dict[str, int] = {}
    for n in names:
        counts[n] = counts.get(n, 0) + 1
    return [{"guess": n, "n": k} for n, k in sorted(counts.items(), key=lambda x: (-x[1], x[0].casefold()))]


def reveal(g: dict):
    S = state(g)
    if g["phase"] != "guess":
        raise MasqueError("Pas maintenant")
    if not any(S["sent"].values()):
        raise MasqueError("Personne n'a encore envoyé ses choix")
    open_ = is_open(S)
    rows = []
    for i, slot in enumerate(S["slots"]):
        if i in S["hidden"]:
            rows.append({"text": None, "hidden": True})
            continue
        author = slot["gid"]
        # Votes dans l'ordre de la table : qui a pensé à qui (les justes d'abord).
        voters = [p["id"] for p in g["players"] if str(i) in S["guesses"].get(p["id"], {})]
        picked = {x: S["guesses"][x][str(i)] for x in voters}
        found = [x for x in voters if picked[x] == author]
        if open_:
            for x in found:
                S["scores"][x] = S["scores"].get(x, 0) + POINT_FOUND
            votes = [{"voter": _frozen_name(g, x), "guess": _frozen_name(g, picked[x]), "right": picked[x] == author}
                     for x in sorted(voters, key=lambda x: picked[x] != author)]
        else:
            votes = _tally([_frozen_name(g, picked[x]) for x in voters])
        rows.append({"text": slot["text"], "hidden": False, "open": open_,
                     "author": _frozen_name(g, author) if open_ else None,
                     "found": [_frozen_name(g, x) for x in found] if open_ else None,
                     "votes": votes, "_author": author, "_found": found})
    S["result"] = rows
    S["history"].append({"q": S["q"]["text"], "rows": rows})
    g["phase"] = "reveal"


def next_step(g: dict, rng=random):
    S = state(g)
    if g["phase"] != "reveal":
        raise MasqueError("Pas maintenant")
    if S["n"] >= S["count"]:
        g["phase"] = "end"
        return
    _deal(g, rng)


def leave(g: dict, gid: str, rng=random):
    """Un joueur s'en va : ce qu'il a écrit ou deviné disparaît, et la partie n'attend plus après lui."""
    S = state(g)
    S["answers"].pop(gid, None)
    S["guesses"].pop(gid, None)
    S["sent"].pop(gid, None)
    if g["phase"] in ("write", "guess", "reveal") and len(g["players"]) < MIN_PLAYERS:
        g["phase"] = "end"  # deviner parmi deux réponses n'est plus un jeu
        return
    if g["phase"] == "write":
        if len(S["answers"]) >= MIN_PLAYERS and all(p["id"] in S["answers"] for p in g["players"]):
            show(g, rng)
    elif g["phase"] == "guess":
        # Sa réponse reste en jeu (la retirer à son départ dirait à tous qu'elle était la sienne) ; elle suit le
        # masque de la table, choisi par l'organisateur avant la partie.
        if _everyone_sent(g):
            reveal(g)


def summary(g: dict) -> dict:
    """Bilan : classement et prix, masques levés seulement (masques gardés : ni points ni prix, rien ne se confirme)."""
    S = state(g)
    found: dict[str, int] = {}
    guessed_about: dict[str, list[int]] = {}
    for h in S["history"]:
        for r in h["rows"]:
            if r.get("hidden") or not r.get("open"):
                continue
            guessed_about.setdefault(r["_author"], []).append(len(r["_found"]))
            for x in r["_found"]:
                found[x] = found.get(x, 0) + 1

    def best(counts: dict) -> list[str]:
        here = {x: n for x, n in counts.items() if _player(g, x)}
        top = max(here.values(), default=0)
        return [_name(g, x) for x, n in here.items() if n == top and top > 0]

    mystery = {a: sum(v) / len(v) for a, v in guessed_about.items() if _player(g, a)}
    least = min(mystery.values(), default=None)
    if least is not None and len(mystery) > 1 and all(v == least for v in mystery.values()):
        least = None  # tout le monde à égalité : ce n'est un prix pour personne
    ranking = sorted(({"name": p["name"], "pid": p["pid"], "score": S["scores"].get(p["id"], 0)} for p in g["players"]),
                     key=lambda x: -x["score"])
    return {"ranking": ranking, "sharp": best(found),
            "mystery": [_name(g, a) for a, v in mystery.items() if v == least] if least is not None else [],
            "questions": len(S["history"])}


def _public(rows: list[dict] | None) -> list[dict] | None:
    """Sans les identifiants secrets des joueurs (gid) : seuls les prénoms des masques levés sortent."""
    return [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows] if rows is not None else None


def view(g: dict, gid: str, lead: bool) -> dict:
    S = state(g)
    me = _player(g, gid)
    q = S["q"]
    out = {"cats": S["cats"], "levels": S["levels"], "count": S["count"], "n": S["n"], "playing": bool(me),
           "cat_list": [{"id": k, "label": v, "size": sum(1 for c in MASQUE_CARDS if c[0] == k)} for k, v in CATS.items()],
           "level_list": [{"id": k, "label": v} for k, v in LEVELS.items()], "counts": list(COUNTS),
           "min_players": MIN_PLAYERS, "max_answer": MAX_ANSWER, "mask": S["mask"],
           "mask_list": [{"id": k, "label": v} for k, v in MASKS.items()],
           "q": q and {**q, "cat_label": CATS[q["cat"]], "level_label": LEVELS[q["level"]]},
           "scores": [{"pid": p["pid"], "name": p["name"], "score": S["scores"].get(p["id"], 0)} for p in g["players"]]}
    if g["phase"] == "write":
        out["wrote"] = [{"pid": p["pid"], "name": p["name"], "done": p["id"] in S["answers"]} for p in g["players"]]
        out["mine"] = S["answers"].get(gid)
        out["can_show"] = lead and len(S["answers"]) >= MIN_PLAYERS
    if g["phase"] == "guess":
        mine = _mine(S, gid)
        # Les réponses sans leur auteur, et sans la sienne : rien sur l'écran ne la désigne à un voisin (avis du 04.11).
        # Tout joueur voit donc la même chose : les réponses des autres, autant de cartes que de prénoms à placer.
        out["slots"] = [{"i": i, "text": None if i in S["hidden"] else s["text"], "hidden": i in S["hidden"]}
                        for i, s in enumerate(S["slots"]) if i != mine]
        out["authors"] = [{"pid": a["pid"], "name": a["name"]} for a in S.get("authors") or [] if a["gid"] != gid]
        out["sent"] = bool(S["sent"].get(gid))
        expected = set(S.get("guessers") or [])
        out["progress"] = [{"pid": p["pid"], "name": p["name"], "done": bool(S["sent"].get(p["id"]))} for p in g["players"]
                           if not expected or p["id"] in expected]
        out["late"] = bool(me) and bool(expected) and gid not in expected
        out["can_reveal"] = lead and any(S["sent"].values())
    if g["phase"] == "reveal":
        out["result"] = _public(S["result"])
        # Ses devinettes, juste ou faux, sur chaque réponse (masques levés seulement : un masque gardé ne confirme rien,
        # pas même à qui a vu juste ou faux, sinon on trouverait l'auteur par élimination).
        picks = S["guesses"].get(gid, {})
        out["my_marks"] = [None if r.get("hidden") or not r.get("open") or str(i) not in picks
                           else "right" if picks[str(i)] == r["_author"] else "wrong"
                           for i, r in enumerate(S["result"] or [])]
    if g["phase"] == "end":
        out["summary"] = summary(g)
        out["history"] = [{"q": h["q"], "rows": _public(h["rows"])} for h in S["history"]]
    return out


def summary_facts(g: dict) -> list[str]:
    S = state(g)
    if not S["history"]:
        return []
    s = summary(g)
    facts = [f"{s['questions']} question(s) posée(s)"]
    if s["sharp"]:
        facts.append("Le plus perspicace : " + ", ".join(s["sharp"]))
    if s["mystery"]:
        facts.append("Le plus mystérieux : " + ", ".join(s["mystery"]))
    return facts
