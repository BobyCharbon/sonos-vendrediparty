"""Purify Test — test de pureté de soirée.

Chacun répond en privé aux 100 questions du « Purity Test », par catégorie (« oui » = déjà vécu).
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

# Catégories (ordre d'affichage) : identifiant → (libellé, emoji). Les questions sont posées catégorie par catégorie.
CATEGORIES: dict[str, tuple[str, str]] = {
    "relations": ("Relations", "💞"),
    "solo": ("Solo & écrans", "📱"),
    "sex": ("Au lit", "🛏️"),
    "places": ("Lieux insolites", "📍"),
    "group": ("À plusieurs", "👥"),
    "kink": ("Fétiches & BDSM", "⛓️"),
    "alcohol": ("Alcool & tabac", "🍺"),
    "drugs": ("Drogues", "💊"),
    "rules": ("Règles & infractions", "🚨"),
}

# Le « Purity Test » classique, en français : 100 questions, « oui » = déjà vécu au moins une fois.
# Les questions sexuelles concernent des expériences consenties entre adultes.
QUESTIONS: list[tuple[str, str]] = [
    ("relations", "As-tu déjà tenu la main de quelqu’un dans un contexte amoureux ?"),
    ("relations", "As-tu déjà eu un rendez-vous amoureux ?"),
    ("relations", "As-tu déjà été en couple ?"),
    ("relations", "As-tu déjà embrassé quelqu’un avec la langue ?"),
    ("relations", "As-tu déjà embrassé une personne le jour de votre rencontre ?"),
    ("relations", "As-tu déjà embrassé plusieurs personnes au cours de la même soirée ?"),
    ("relations", "As-tu déjà embrassé un ami ou une amie sans être en couple avec cette personne ?"),
    ("relations", "As-tu déjà donné ou reçu un suçon ?"),
    ("relations", "As-tu déjà dansé contre quelqu’un avec une intention sexuelle ?"),
    ("relations", "As-tu déjà embrassé un collègue ou une collègue ?"),
    ("relations", "As-tu déjà rencontré quelqu’un grâce à une application de rencontres ?"),
    ("relations", "As-tu déjà entretenu une relation amoureuse en la cachant à ton entourage ?"),
    ("relations", "As-tu déjà couché avec quelqu’un dont tu ne connaissais pas le prénom ?"),
    ("relations", "As-tu déjà eu une aventure sexuelle d’une seule nuit ?"),
    ("relations", "As-tu déjà eu un partenaire sexuel régulier sans relation amoureuse ?"),
    ("relations", "As-tu déjà couché avec une personne ayant au moins dix ans de différence d’âge avec toi ?"),
    ("relations", "As-tu déjà eu au moins cinq partenaires sexuels différents au total ?"),
    ("relations", "As-tu déjà eu des rapports séparés avec deux personnes différentes au cours des mêmes 24 heures ?"),
    ("relations", "As-tu déjà recommencé à coucher avec un ex après votre rupture ?"),
    ("relations", "As-tu déjà trompé un partenaire avec qui tu avais convenu d’une relation exclusive ?"),
    ("relations", "As-tu déjà couché avec une personne en sachant qu’elle trompait son partenaire ?"),
    ("relations", "As-tu déjà entretenu plusieurs relations amoureuses en parallèle avec l’accord de toutes les personnes concernées ?"),
    ("solo", "As-tu déjà regardé du contenu pornographique ?"),
    ("solo", "As-tu déjà pratiqué la masturbation ?"),
    ("solo", "As-tu déjà utilisé un sextoy en solitaire ?"),
    ("solo", "As-tu déjà pratiqué la masturbation devant un partenaire ?"),
    ("solo", "As-tu déjà participé à un jeu où les participants retiraient leurs vêtements ?"),
    ("solo", "As-tu déjà envoyé une photo de toi nu à une personne qui souhaitait la recevoir ?"),
    ("solo", "As-tu déjà demandé et reçu une photo intime de quelqu’un ?"),
    ("solo", "As-tu déjà échangé des messages décrivant explicitement ce que tu voulais faire sexuellement avec quelqu’un ?"),
    ("solo", "As-tu déjà participé à un appel vidéo à caractère sexuel ?"),
    ("solo", "As-tu déjà payé pour accéder à du contenu pornographique ou à un compte de contenu pour adultes ?"),
    ("solo", "As-tu déjà filmé ou photographié un rapport sexuel avec l’accord de toutes les personnes présentes ?"),
    ("solo", "As-tu déjà fait un striptease pour un partenaire ?"),
    ("solo", "As-tu déjà pris une douche ou un bain nu avec un partenaire ?"),
    ("sex", "As-tu déjà eu un rapport sexuel ?"),
    ("sex", "As-tu déjà masturbé un partenaire ?"),
    ("sex", "As-tu déjà fait une fellation ?"),
    ("sex", "As-tu déjà reçu une fellation ?"),
    ("sex", "As-tu déjà fait un cunnilingus ?"),
    ("sex", "As-tu déjà reçu un cunnilingus ?"),
    ("sex", "As-tu déjà donné ou reçu un anulingus ?"),
    ("sex", "As-tu déjà pratiqué la pénétration anale, comme personne pénétrante ou pénétrée ?"),
    ("sex", "As-tu déjà pratiqué le « 69 » ?"),
    ("sex", "As-tu déjà utilisé un sextoy avec un partenaire ?"),
    ("sex", "As-tu déjà utilisé un gode-ceinture avec un partenaire ?"),
    ("sex", "As-tu déjà eu un rapport sexuel pendant les règles ?"),
    ("sex", "As-tu déjà simulé un orgasme ?"),
    ("sex", "As-tu déjà eu un rapport vaginal ou anal sans préservatif ?"),
    ("sex", "As-tu déjà payé quelqu’un ou reçu de l’argent en échange d’un acte sexuel ?"),
    ("places", "As-tu déjà eu un rapport sexuel dans une voiture stationnée ?"),
    ("places", "As-tu déjà eu un rapport sexuel en plein air ?"),
    ("places", "As-tu déjà eu un rapport sexuel sous une tente ?"),
    ("places", "As-tu déjà eu un rapport sexuel dans une piscine ou un jacuzzi ?"),
    ("places", "As-tu déjà eu un rapport sexuel dans les toilettes d’un bar ou d’une boîte de nuit ?"),
    ("places", "As-tu déjà eu un rapport sexuel sur ton lieu de travail ?"),
    ("places", "As-tu déjà eu un rapport sexuel dans une cabine d’essayage ?"),
    ("places", "As-tu déjà eu un rapport sexuel dans un avion ?"),
    ("places", "As-tu déjà réservé une chambre d’hôtel uniquement pour avoir un rapport sexuel ?"),
    ("places", "As-tu déjà eu un rapport sexuel sur le site d’un festival ?"),
    ("group", "As-tu déjà fait un plan à trois ?"),
    ("group", "As-tu déjà participé à un rapport sexuel réunissant quatre personnes ou plus ?"),
    ("group", "As-tu déjà pratiqué l’échangisme, avec échange de partenaires entre couples ?"),
    ("group", "As-tu déjà fréquenté un club libertin ?"),
    ("group", "As-tu déjà participé à une soirée sexuelle privée réunissant plusieurs couples ?"),
    ("group", "As-tu déjà regardé un couple avoir un rapport sexuel en ta présence, avec son accord ?"),
    ("group", "As-tu déjà eu un rapport sexuel devant d’autres adultes qui avaient accepté de regarder ?"),
    ("kink", "As-tu déjà attaché un partenaire ou été attaché dans un contexte sexuel ?"),
    ("kink", "As-tu déjà utilisé un bandeau sur les yeux dans un contexte sexuel ?"),
    ("kink", "As-tu déjà pratiqué un jeu de domination ou de soumission avec un partenaire ?"),
    ("kink", "As-tu déjà donné ou reçu des fessées dans un contexte sexuel ?"),
    ("kink", "As-tu déjà porté une tenue en latex ou en cuir dans un but fétichiste ?"),
    ("kink", "As-tu déjà participé à un jeu de rôle sexuel avec un scénario convenu à l’avance ?"),
    ("kink", "As-tu déjà pratiqué un jeu d’humiliation verbale explicitement accepté dans un cadre BDSM ?"),
    ("kink", "As-tu déjà intégré un fétichisme des pieds à une expérience sexuelle ?"),
    ("alcohol", "As-tu déjà consommé de l’alcool ?"),
    ("alcohol", "As-tu déjà été ivre ?"),
    ("alcohol", "As-tu déjà vomi après avoir trop bu ?"),
    ("alcohol", "As-tu déjà eu un trou de mémoire concernant une partie de ta soirée à cause de l’alcool ?"),
    ("alcohol", "As-tu déjà participé à un jeu à boire ?"),
    ("alcohol", "As-tu déjà essayé de faire croire que tu étais sobre alors que tu étais ivre ?"),
    ("alcohol", "As-tu déjà fumé une cigarette ?"),
    ("alcohol", "As-tu déjà utilisé une cigarette électronique contenant de la nicotine ?"),
    ("drugs", "As-tu déjà consommé du cannabis ?"),
    ("drugs", "As-tu déjà pris de l’ecstasy ou de la MDMA ?"),
    ("drugs", "As-tu déjà consommé de la cocaïne, en poudre ou sous forme de crack ?"),
    ("drugs", "As-tu déjà pris de la kétamine à des fins récréatives ?"),
    ("drugs", "As-tu déjà pris du LSD ?"),
    ("drugs", "As-tu déjà consommé des champignons hallucinogènes ?"),
    ("drugs", "As-tu déjà pris des amphétamines, comme le speed, en dehors d’un usage médical prescrit ?"),
    ("drugs", "As-tu déjà consommé volontairement du GHB ou du GBL à des fins récréatives ?"),
    ("drugs", "As-tu déjà utilisé du poppers ?"),
    ("drugs", "As-tu déjà consommé de l’héroïne ?"),
    ("rules", "As-tu déjà triché à un examen ?"),
    ("rules", "As-tu déjà volé un article dans un magasin ?"),
    ("rules", "As-tu déjà utilisé une fausse pièce d’identité ?"),
    ("rules", "As-tu déjà dégradé volontairement un bien appartenant à quelqu’un d’autre ?"),
    ("rules", "As-tu déjà conduit en état d’ivresse ou sous l’emprise d’une drogue ?"),
    ("rules", "As-tu déjà pris la fuite pour échapper à un contrôle de police ?"),
    ("rules", "As-tu déjà été placé en garde à vue ?"),
]

TOTAL = len(QUESTIONS)


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


def leave(g: dict, gid: str):
    """Un joueur part : ses réponses privées disparaissent avec lui."""
    p = g["purity"]
    for part in ("answers", "submitted", "scores"):
        p[part].pop(gid, None)


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


def categories(g: dict, gid: str) -> list[dict]:
    """Profil de pureté par catégorie (pour son seul propriétaire : il en dit plus que le score global)."""
    done = g["purity"]["answers"].get(gid, {})
    rows = []
    for cid, (label, emoji) in CATEGORIES.items():
        idx = [i for i, (c, _) in enumerate(QUESTIONS) if c == cid]
        pure = sum(1 for i in idx if str(i) not in done)
        rows.append({"id": cid, "label": label, "emoji": emoji, "pure": pure, "total": len(idx), "pct": round(100 * pure / len(idx))})
    return rows


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
        out["categories"] = [{"id": c, "label": label, "emoji": emoji} for c, (label, emoji) in CATEGORIES.items()]
        out["questions"] = [{"i": i, "text": t, "cat": c} for i, (c, t) in enumerate(QUESTIONS)]
        if me_playing:
            out["mine"] = {int(i): True for i in p["answers"].get(gid, {})}
    if g["phase"] == "results":
        out["ranking"] = ranking(g)
        out["gorgees"] = gorgees(g)
        out["me_score"] = p["scores"].get(gid)
        if gid in p["scores"]:
            out["me_categories"] = categories(g, gid)
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
