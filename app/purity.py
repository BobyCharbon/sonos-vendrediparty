"""Purify Test — test de pureté de soirée.

Chacun répond en privé à une centaine d'affirmations (« fait » / « pas fait »).
Le score = pourcentage de « pas fait » (100 % = tout pur). À la fin, l'animateur
révèle les scores et un classement du plus pur au plus sulfureux. Les réponses
individuelles ne sont jamais montrées, seul le score compte.

Participation réservée aux comptes Party connectés (num. de tél. vérifié) :
cette règle est appliquée côté main.py au moment de rejoindre (le siège est lié
au compte), ce module travaille ensuite sur des identifiants de joueur.

Module autonome et testable (mêmes conventions que quiz.py).
"""
import json
import time
from pathlib import Path

STATS_PATH: Path | None = None  # réglé par main.py (DATA_DIR / purity_stats.json)

# Affirmations adaptées du « test de pureté » classique, en français, ordonnées
# du plus innocent au plus osé. Niveau indicatif : "soft" | "awkward" | "hot".
# (texte complété après « Est-ce que tu as déjà… »)
QUESTIONS: list[tuple[str, str]] = [
    ("tenu la main de quelqu'un par amour", "soft"),
    ("eu un coup de cœur pour quelqu'un", "soft"),
    ("envoyé un message que tu as regretté", "soft"),
    ("séché un cours ou une journée de travail", "soft"),
    ("menti à tes parents sur où tu étais", "soft"),
    ("fait semblant d'être malade pour éviter quelque chose", "soft"),
    ("triché à un examen ou un test", "soft"),
    ("été collé ou convoqué à l'école", "soft"),
    ("eu une retenue ou une sanction", "soft"),
    ("raté un rendez-vous important en dormant trop", "soft"),
    ("pleuré devant un film", "soft"),
    ("eu le cœur brisé", "soft"),
    ("brisé le cœur de quelqu'un", "soft"),
    ("stalké quelqu'un sur les réseaux", "soft"),
    ("liké une vieille photo par accident en stalkant", "awkward"),
    ("eu un crush sur un·e prof", "awkward"),
    ("eu un crush sur l'ami·e de ton ami·e", "awkward"),
    ("embrassé quelqu'un", "soft"),
    ("embrassé quelqu'un le premier soir", "awkward"),
    ("embrassé deux personnes différentes le même jour", "hot"),
    ("eu un rendez-vous amoureux", "soft"),
    ("été en couple", "soft"),
    ("dit « je t'aime » sans le penser", "awkward"),
    ("menti sur tes sentiments", "awkward"),
    ("rompu avec quelqu'un par message", "awkward"),
    ("été largué par message", "awkward"),
    ("repris une relation que tu savais finie", "awkward"),
    ("eu une relation secrète", "hot"),
    ("dragué quelqu'un en couple", "hot"),
    ("été dragué par quelqu'un en couple", "awkward"),
    ("flirté pour obtenir quelque chose", "awkward"),
    ("menti sur ton âge pour impressionner", "awkward"),
    ("créé un faux profil", "awkward"),
    ("espionné le téléphone de ton/ta partenaire", "hot"),
    ("lu des messages qui ne t'étaient pas destinés", "awkward"),
    ("bu de l'alcool", "soft"),
    ("été ivre", "awkward"),
    ("eu une gueule de bois mémorable", "awkward"),
    ("vomi à cause de l'alcool", "awkward"),
    ("oublié une partie de ta soirée", "hot"),
    ("fini une soirée dans un endroit inconnu", "hot"),
    ("dansé sur une table", "awkward"),
    ("chanté en karaoké complètement faux", "soft"),
    ("fait un jeu à boire", "soft"),
    ("fumé une cigarette", "awkward"),
    ("fumé du cannabis", "hot"),
    ("participé à une soirée qui a dégénéré", "hot"),
    ("été à une fête sans y être invité", "awkward"),
    ("menti pour entrer quelque part", "awkward"),
    ("passé une nuit blanche à faire la fête", "awkward"),
    ("envoyé un message en étant ivre", "awkward"),
    ("appelé ton ex en étant ivre", "hot"),
    ("regretté un texto le lendemain d'une soirée", "awkward"),
    ("posté quelque chose que tu as supprimé de honte", "awkward"),
    ("menti sur un CV ou en entretien", "awkward"),
    ("volé quelque chose, même un bonbon", "awkward"),
    ("conduit sans permis ou trop vite", "hot"),
    ("fait un pari stupide en public", "awkward"),
    ("parié de l'argent", "awkward"),
    ("fait une bêtise filmée qui a circulé", "hot"),
    ("eu un fou rire au pire moment", "soft"),
    ("fait semblant de connaître quelqu'un", "soft"),
    ("oublié le prénom de quelqu'un juste après l'avoir rencontré", "soft"),
    ("fait un compliment juste par politesse", "soft"),
    ("jugé quelqu'un sur son physique", "awkward"),
    ("parlé dans le dos d'un·e ami·e", "awkward"),
    ("trahi un secret", "awkward"),
    ("gardé un secret lourd pour un·e ami·e", "soft"),
    ("menti à ton/ta meilleur·e ami·e", "awkward"),
    ("été jaloux·se au point de faire une scène", "hot"),
    ("tenu quelqu'un dans tes bras toute une nuit", "awkward"),
    ("dormi dans le même lit que ton crush", "hot"),
    ("eu un flirt qui n'a mené nulle part", "awkward"),
    ("eu une aventure d'un soir", "hot"),
    ("embrassé quelqu'un dont tu ne connaissais pas le prénom", "hot"),
    ("fait un date à l'aveugle", "awkward"),
    ("rencontré quelqu'un via une appli", "awkward"),
    ("eu plusieurs conversations de drague en même temps", "hot"),
    ("envoyé une photo osée", "hot"),
    ("reçu une photo osée", "hot"),
    ("eu un fantasme sur quelqu'un dans la pièce ce soir", "hot"),
    ("eu le béguin pour deux personnes en même temps", "awkward"),
    ("menti sur le nombre de tes relations", "hot"),
    ("fait semblant d'aimer un cadeau", "soft"),
    ("ghosté quelqu'un", "awkward"),
    ("été ghosté", "awkward"),
    ("recontacté quelqu'un uniquement par ennui", "awkward"),
    ("fait le premier pas", "soft"),
    ("déclaré ta flamme et pris un râteau", "awkward"),
    ("gardé les affaires d'un·e ex", "soft"),
    ("pleuré à cause de quelqu'un dans cette pièce", "hot"),
    ("eu un secret que personne ici ne connaît", "hot"),
    ("menti en répondant à une question de ce test", "hot"),
    ("fait quelque chose ce soir que tu ne raconteras à personne", "hot"),
    ("eu le coup de foudre", "soft"),
    ("changé d'avis sur quelqu'un après une soirée", "awkward"),
    ("regretté une relation", "awkward"),
    ("pardonné une trahison", "awkward"),
    ("refait ta vie après une rupture difficile", "soft"),
    ("promis de ne plus jamais refaire une bêtise… puis recommencé", "soft"),
]

TOTAL = len(QUESTIONS)
LEVELS = {"soft": "😇", "awkward": "😬", "hot": "🔥"}


class PurityError(Exception):
    pass


def defaults() -> dict:
    # sips : gorgées pour le·la plus sulfureux·se à la révélation (0 = sans alcool).
    return {"alcohol": False, "sips": 2}


def init(g: dict):
    g["purity"] = {
        "answers": {},   # gid -> {index(str): True si « fait »}
        "submitted": {}, # gid -> True quand la personne a validé ses réponses
        "scores": {},    # gid -> score % (rempli à la révélation)
    }
    g.setdefault("options", {}).setdefault("alcohol", False)
    g["options"].setdefault("sips", 2)


def configure(g: dict, s: dict):
    """Réglages en salon (avant le lancement) : alcool et nombre de gorgées."""
    if g["phase"] != "lobby":
        raise PurityError("La partie est déjà lancée")
    if "alcohol" in s:
        g["options"]["alcohol"] = bool(s["alcohol"])
    if "sips" in s:
        try:
            g["options"]["sips"] = max(0, min(10, int(s["sips"])))
        except (TypeError, ValueError):
            pass


def start(g: dict):
    """L'animateur ouvre les réponses : chacun remplit son test en privé."""
    if g["phase"] not in ("lobby", "results"):
        raise PurityError("La partie est déjà en cours")
    p = g["purity"]
    p["answers"], p["submitted"], p["scores"] = {}, {}, {}
    g["phase"] = "answering"
    g["updated_at"] = time.time()


def _participant(g: dict, gid: str) -> bool:
    from . import games
    return bool(gid) and games.player(g, gid) is not None


def answer(g: dict, gid: str, index: int, done: bool):
    """Enregistre une réponse privée à une affirmation."""
    if g["phase"] != "answering":
        raise PurityError("Ce n'est pas le moment de répondre")
    if not _participant(g, gid):
        raise PurityError("Tu ne participes pas à cette partie")
    if g["purity"]["submitted"].get(gid):
        raise PurityError("Tu as déjà validé tes réponses")
    if not isinstance(index, int) or not 0 <= index < TOTAL:
        raise PurityError("Affirmation inconnue")
    answers = g["purity"]["answers"].setdefault(gid, {})
    if done:
        answers[str(index)] = True
    else:
        answers.pop(str(index), None)


def submit(g: dict, gid: str):
    """La personne valide son test (ses réponses sont figées)."""
    if g["phase"] != "answering":
        raise PurityError("Ce n'est pas le moment de valider")
    if not _participant(g, gid):
        raise PurityError("Tu ne participes pas à cette partie")
    g["purity"]["submitted"][gid] = True
    g["updated_at"] = time.time()


def unsubmit(g: dict, gid: str):
    """Revenir sur sa validation tant que l'animateur n'a pas révélé."""
    if g["phase"] != "answering":
        raise PurityError("Trop tard pour revenir en arrière")
    g["purity"]["submitted"].pop(gid, None)


def _score_of(g: dict, gid: str) -> int:
    done = len(g["purity"]["answers"].get(gid, {}))
    return round(100 * (TOTAL - done) / TOTAL)


def everyone_done(g: dict) -> bool:
    players = [p["id"] for p in g["players"]]
    return bool(players) and all(g["purity"]["submitted"].get(pid) for pid in players)


def reveal(g: dict):
    """L'animateur révèle : on fige les scores de ceux qui ont validé."""
    if g["phase"] != "answering":
        raise PurityError("Rien à révéler")
    p = g["purity"]
    scored = [pl["id"] for pl in g["players"] if p["submitted"].get(pl["id"])]
    if not scored:
        raise PurityError("Personne n'a encore validé ses réponses")
    p["scores"] = {gid: _score_of(g, gid) for gid in scored}
    g["phase"] = "results"
    g["updated_at"] = time.time()
    record(g)


def ranking(g: dict) -> list[dict]:
    """Classement du plus pur (score haut) au plus sulfureux (score bas)."""
    scores = g["purity"].get("scores", {})
    rows = []
    for pl in g["players"]:
        if pl["id"] in scores:
            rows.append({"pid": pl["pid"], "name": pl["name"], "score": scores[pl["id"]]})
    rows.sort(key=lambda r: (-r["score"], r["name"].casefold()))
    return rows


def gorgees(g: dict) -> list[dict]:
    """Option alcool : le·la plus sulfureux·se (score le plus bas) boit `sips` gorgées."""
    if not g["options"].get("alcohol") or g["phase"] != "results":
        return []
    sips = int(g["options"].get("sips", 0))
    rows = ranking(g)
    if not sips or not rows:
        return []
    low = min(r["score"] for r in rows)
    return [{"pid": r["pid"], "name": r["name"], "sips": sips} for r in rows if r["score"] == low]


# --- Classement général (persisté entre les parties, par compte) ---

def _load_stats() -> dict:
    if STATS_PATH and STATS_PATH.exists():
        try:
            return json.loads(STATS_PATH.read_text())
        except (ValueError, OSError):
            return {}
    return {}


def _save_stats(data: dict):
    if not STATS_PATH:
        return
    STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    tmp.replace(STATS_PATH)


def record(g: dict):
    """Ajoute chaque score révélé au classement général (meilleur = plus pur gardé)."""
    if not STATS_PATH:
        return
    scores = g["purity"].get("scores", {})
    if not scores:
        return
    data = _load_stats()
    for pl in g["players"]:
        gid = pl["id"]
        # Participation réservée aux comptes : le guest_id « acct-… » est l'identité stable.
        if gid not in scores or not gid.startswith("acct-"):
            continue
        row = data.get(gid) or {"name": pl["name"], "plays": 0, "best": 0, "last": 0}
        row["name"] = pl["name"]
        row["plays"] += 1
        row["last"] = scores[gid]
        row["best"] = max(row["best"], scores[gid])
        data[gid] = row
    _save_stats(data)


def leaderboard(limit: int = 20) -> dict:
    data = _load_stats()
    rows = sorted(data.values(), key=lambda r: (-r.get("best", 0), r.get("name", "").casefold()))
    return {"rows": rows[:limit], "total": len(data)}


def view(g: dict, gid: str) -> dict:
    """Vue envoyée au téléphone : questions + progression perso ; classement à la fin."""
    p = g["purity"]
    me_playing = _participant(g, gid)
    out = {
        "phase": g["phase"],
        "total": TOTAL,
        "alcohol": bool(g["options"].get("alcohol")),
        "sips": int(g["options"].get("sips", 0)),
        "playing": me_playing,
        "submitted": bool(p["submitted"].get(gid)),
        "answered": len(p["answers"].get(gid, {})) if me_playing else 0,
        "count_submitted": sum(1 for pl in g["players"] if p["submitted"].get(pl["id"])),
        "count_players": len(g["players"]),
    }
    if g["phase"] in ("lobby", "answering"):
        out["questions"] = [{"i": i, "text": t, "level": lv, "emoji": LEVELS[lv]} for i, (t, lv) in enumerate(QUESTIONS)]
        if me_playing:
            out["mine"] = {int(i): True for i in p["answers"].get(gid, {})}
    if g["phase"] == "results":
        out["ranking"] = ranking(g)
        out["gorgees"] = gorgees(g)
        out["me_score"] = p["scores"].get(gid)
    return out


def summary_facts(g: dict) -> list[str]:
    """Résumé pour le tableau de la soirée (room_merge)."""
    rows = ranking(g)
    if not rows:
        return []
    purest = rows[0]
    naughtiest = rows[-1]
    facts = [f"Le plus pur : {purest['name']} ({purest['score']} %)"]
    if len(rows) > 1:
        facts.append(f"Le plus sulfureux : {naughtiest['name']} ({naughtiest['score']} %)")
    return facts
