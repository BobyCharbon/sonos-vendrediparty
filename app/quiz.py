"""Quiz : 14 thèmes, 5 modes, jouable seul ou à plusieurs, avec un classement général entre les parties.

Modes
- classic  : Classique. Tout le monde répond à la même question ; points selon la rapidité, bonus de série.
- speed    : Rapidité. Le premier qui trouve gagne la question ; une erreur bloque pour cette question.
- survival : Survie. Une erreur ou un temps écoulé coûte une vie ; questions de plus en plus dures.
- chrono   : Contre-la-montre. Chacun à son rythme, le plus de bonnes réponses avant la fin du temps.
- ladder   : Paliers. 15 questions de plus en plus dures, 2 paliers assurés, jokers 50/50 et « changer ».

Le serveur garde l'heure : il fait avancer la partie (fin du temps, révélation, question suivante) à chaque
requête (tick), et la bonne réponse n'est jamais envoyée avant la révélation.
"""

import json
import random
import threading
import time
from pathlib import Path

from . import quizbank as qb

MODES = {
    "classic": ("Classique", "🏆"),
    "speed": ("Rapidité", "⚡"),
    "survival": ("Survie", "❤️"),
    "chrono": ("Contre-la-montre", "⏱️"),
    "ladder": ("Paliers", "🪜"),
}
DIFFS = {"mix": "Toutes", "1": "Facile", "2": "Moyen", "3": "Difficile", "prog": "Progressive"}
REVEAL = 5  # secondes d'affichage de la bonne réponse avant la question suivante
LADDER = [100, 200, 300, 500, 1000, 2000, 4000, 8000, 16000, 32000, 64000, 125000, 250000, 500000, 1000000]
LADDER_SAFE = (4, 9)  # paliers assurés (index) : 1 000 et 32 000
LADDER_TIME = 30
STATS_PATH: Path | None = None  # réglé par main.py (DATA_DIR / quiz_stats.json)
_stats_lock = threading.Lock()


class QuizError(Exception):
    pass


def defaults() -> dict:
    return {"mode": "classic", "themes": [], "diff": "mix", "count": 15, "time": 20, "lives": 3, "chrono": 60}


def init(g: dict):
    g.setdefault("quiz", {"settings": defaults(), "used": [], "scores": {}, "cur": None, "personal": {}, "deadline": None,
                          "n": 0, "recorded": False, "last": None})


def configure(g: dict, s: dict):
    """L'animateur règle la partie (avant de lancer)."""
    init(g)
    if g["phase"] not in ("lobby", "end"):
        raise QuizError("La partie est en cours")
    cur = g["quiz"]["settings"]
    if s.get("mode") in MODES:
        if s["mode"] == "speed" and len(g["players"]) < 2:
            raise QuizError("La Rapidité se joue à 2 joueurs au moins")
        cur["mode"] = s["mode"]
    if isinstance(s.get("themes"), list):
        cur["themes"] = [t for t in s["themes"] if qb.BANK.get(t)]
    if str(s.get("diff")) in DIFFS:
        cur["diff"] = str(s["diff"])
    for key, lo, hi in (("count", 5, 50), ("time", 8, 60), ("lives", 1, 5), ("chrono", 30, 300)):
        if key in s:
            try:
                cur[key] = max(lo, min(hi, int(s[key])))
            except (TypeError, ValueError):
                pass


# --- Tirage des questions ---

def _pool(g: dict, diff: str | int) -> list[dict]:
    themes = g["quiz"]["settings"]["themes"] or [t for t in qb.THEMES if qb.BANK[t]]
    qs = [q for t in themes for q in qb.BANK.get(t, [])]
    if str(diff) in ("1", "2", "3"):
        qs = [q for q in qs if q["d"] == int(diff)] or qs
    return qs


def _draw(g: dict, rng, diff=None, exclude=()) -> dict:
    Q = g["quiz"]
    diff = diff or Q["settings"]["diff"]
    pool = _pool(g, diff)
    used = set(Q["used"]) | set(exclude)
    fresh = [q for q in pool if q["id"] not in used]
    if not fresh:  # tout a été posé : on recommence (rare, il y a des milliers de questions)
        Q["used"] = []
        fresh = pool
    if not fresh:
        raise QuizError("Aucune question pour ces thèmes")
    q = rng.choice(fresh)
    Q["used"].append(q["id"])
    if len(Q["used"]) > 3000:
        del Q["used"][:1000]
    choices = [q["a"], *q["w"]]
    rng.shuffle(choices)
    return {"qid": q["id"], "choices": choices, "ans": choices.index(q["a"])}


def _prog_diff(n: int) -> str:
    """Difficulté progressive : facile, puis moyen, puis difficile."""
    return "1" if n < 5 else "2" if n < 12 else "3"


# --- Scores ---

def _sc(g: dict, gid: str) -> dict:
    return g["quiz"]["scores"].setdefault(gid, {"pts": 0, "ok": 0, "n": 0, "streak": 0, "best": 0, "lives": g["quiz"]["settings"]["lives"],
                                                "out": False, "themes": {}})


def _count(g: dict, gid: str, qid: str, ok: bool):
    s = _sc(g, gid)
    s["n"] += 1
    t = qid.split(":")[0]
    th = s["themes"].setdefault(t, [0, 0])
    th[1] += 1
    if ok:
        s["ok"] += 1
        th[0] += 1
        s["streak"] += 1
        s["best"] = max(s["best"], s["streak"])
    else:
        s["streak"] = 0
    if not ok and g["options"].get("sips"):
        from .games import add_sips
        add_sips(g, gid, drink=g["options"]["sips"])


def _active(g: dict) -> list[str]:
    """Joueurs qui jouent la question en cours (pas les éliminés de la Survie, ni ceux qui attendent)."""
    return [p["id"] for p in g["players"] if not p.get("waiting") and not _sc(g, p["id"])["out"]]


# --- Déroulement ---

def start(g: dict, rng=random):
    init(g)
    Q = g["quiz"]
    if not g["players"]:
        raise QuizError("Il faut au moins 1 joueur")
    if Q["settings"]["mode"] == "speed" and len(g["players"]) < 2:
        raise QuizError("La Rapidité se joue à 2 joueurs au moins : choisis un autre mode ou attends un deuxième joueur")
    for p in g["players"]:
        p["waiting"] = False
    lives = Q["settings"]["lives"]
    Q.update(used=Q["used"][-500:], scores={}, cur=None, personal={}, deadline=None, n=0, recorded=False, last=None, paused=False)
    for p in g["players"]:
        _sc(g, p["id"])["lives"] = lives
    mode = Q["settings"]["mode"]
    if mode in ("chrono", "ladder"):
        g["phase"] = "run"
        now = time.time()
        if mode == "chrono":
            Q["deadline"] = now + Q["settings"]["chrono"]
        for p in g["players"]:
            _personal_next(g, p["id"], rng)
    else:
        _next_question(g, rng)


def _next_question(g: dict, rng):
    Q = g["quiz"]
    s = Q["settings"]
    diff = _prog_diff(Q["n"]) if s["diff"] == "prog" or (s["mode"] == "survival" and s["diff"] == "mix") else s["diff"]
    now = time.time()
    Q["cur"] = {**_draw(g, rng, diff), "start": now, "end": now + s["time"], "answers": {}, "locked": [], "winner": None}
    Q["n"] += 1
    g["round"] = Q["n"]
    g["phase"] = "q"


def token(g: dict, gid: str) -> str:
    """Identifie la question affichée : une réponse ou un « Suivante » arrivé en retard est ignoré."""
    Q = g["quiz"]
    if g["phase"] == "run":
        P = Q["personal"].get(gid) or {}
        return f"p{P.get('i', 0)}{'b' if P.get('between') else ''}"
    return f"{g['phase']}{Q['n']}"


def answer(g: dict, gid: str, choice: int, rng=random, tok: str = ""):
    init(g)
    Q = g["quiz"]
    tick(g, rng)
    if tok and tok != token(g, gid):
        raise QuizError("Trop tard : la question a changé")
    if not any(p["id"] == gid for p in g["players"]):
        raise QuizError("Rejoins la partie pour répondre")
    if g["phase"] == "run":
        return _personal_answer(g, gid, choice, rng)
    if g["phase"] != "q":
        raise QuizError("Pas de question en cours")
    c = Q["cur"]
    if gid not in _active(g):
        raise QuizError("Tu es éliminé·e : regarde les autres jouer")
    if gid in c["answers"] or gid in c["locked"]:
        raise QuizError("Tu as déjà répondu")
    if not 0 <= choice < 4:
        raise QuizError("Réponse invalide")
    now = time.time()
    ok = choice == c["ans"]
    t = max(0.0, now - c["start"])
    mode = Q["settings"]["mode"]
    pts = 0
    if mode == "speed":
        if ok and not c["winner"]:
            c["winner"] = gid
            pts = 1000
        elif not ok:
            c["locked"].append(gid)
    elif ok:
        streak = _sc(g, gid)["streak"]
        pts = 500 + round(500 * max(0.0, 1 - t / Q["settings"]["time"])) + min(streak, 5) * 50
    c["answers"][gid] = {"c": choice, "t": round(t, 2), "ok": ok, "pts": pts}
    tick(g, rng)


def _reveal(g: dict):
    Q = g["quiz"]
    c = Q["cur"]
    mode = Q["settings"]["mode"]
    for gid in _active(g):
        a = c["answers"].get(gid)
        ok = bool(a and a["ok"]) and (mode != "speed" or c["winner"] == gid)
        if mode == "speed" and a and a["ok"] and c["winner"] != gid:
            continue  # bonne réponse, mais trop tard : ni point, ni erreur
        if mode == "speed" and not a:
            continue  # pas répondu en rapidité : pas de pénalité
        _count(g, gid, c["qid"], ok)
        s = _sc(g, gid)
        s["pts"] += a["pts"] if a else 0
        if mode == "survival" and not ok:
            s["lives"] -= 1
            if s["lives"] <= 0:
                s["out"] = True
                s["out_at"] = Q["n"]
    g["phase"] = "rev"
    c["next_at"] = time.time() + REVEAL


def _over(g: dict) -> bool:
    Q = g["quiz"]
    s = Q["settings"]
    if s["mode"] == "survival":
        alive = [p for p in g["players"] if not _sc(g, p["id"])["out"]]
        return len(alive) == 0 or (len(g["players"]) > 1 and len(alive) <= 1)
    return Q["n"] >= s["count"]


def next_step(g: dict, rng=random, tok: str = ""):
    """L'animateur passe à la suite (sans attendre la fin du temps ou de la révélation)."""
    init(g)
    tick(g, rng)
    if tok and tok != token(g, ""):
        return  # double clic (ou deux animateurs) : on ne saute pas une question
    g["quiz"]["paused"] = False
    if g["phase"] == "q":
        _reveal(g)
    elif g["phase"] == "rev":
        _advance(g, rng)
    elif g["phase"] == "run":
        _finish(g)


def _advance(g: dict, rng):
    if _over(g):
        _finish(g)
    else:
        _next_question(g, rng)


def tick(g: dict, rng=random) -> bool:
    """Fait avancer la partie selon l'heure ; True si quelque chose a changé (à enregistrer)."""
    if g.get("type") != "quiz" or "quiz" not in g:
        return False
    Q = g["quiz"]
    now = time.time()
    changed = False
    if g["phase"] == "q":
        c = Q["cur"]
        act = _active(g)
        done = all(x in c["answers"] or x in c["locked"] for x in act)
        if now >= c["end"] or done or (Q["settings"]["mode"] == "speed" and c["winner"]):
            _reveal(g)
            changed = True
    if g["phase"] == "rev" and not Q.get("paused") and now >= Q["cur"].get("next_at", 0):
        _advance(g, rng)
        changed = True
    if g["phase"] == "run":
        changed |= _personal_tick(g, rng)
    return changed


# --- Modes à son rythme (Contre-la-montre, Paliers) ---

def _personal_next(g: dict, gid: str, rng):
    Q = g["quiz"]
    P = Q["personal"].setdefault(gid, {"i": 0, "done": False, "level": 0, "jokers": ["5050", "swap"], "cut": [], "last": None})
    mode = Q["settings"]["mode"]
    diff = (["1"] * 5 + ["2"] * 5 + ["3"] * 5)[min(P["i"], 14)] if mode == "ladder" else Q["settings"]["diff"]
    now = time.time()
    P["q"] = {**_draw(g, rng, diff), "start": now,
              "end": now + LADDER_TIME if mode == "ladder" else Q["deadline"]}
    P["cut"] = []


def _personal_answer(g: dict, gid: str, choice: int, rng):
    Q = g["quiz"]
    if gid not in Q["personal"]:
        _personal_next(g, gid, rng)  # arrivé en cours de route
        raise QuizError("C'est parti : à toi de jouer !")
    P = Q["personal"][gid]
    if P["done"]:
        raise QuizError("Tu as fini : attends les autres")
    if P.get("between"):
        raise QuizError("Question suivante dans un instant")
    q = P["q"]
    now = time.time()
    if now > q["end"] + 0.5:
        raise QuizError("Temps écoulé")
    ok = choice == q["ans"]
    mode = Q["settings"]["mode"]
    s = _sc(g, gid)
    _count(g, gid, q["qid"], ok)
    P["last"] = {"qid": q["qid"], "choices": q["choices"], "c": choice, "ans": q["ans"], "ok": ok, "at": now}
    if mode == "chrono":
        if ok:
            s["pts"] += 100 + min(s["streak"] - 1, 5) * 20
        P["i"] += 1
        _personal_next(g, gid, rng)
    else:
        if ok:
            P["level"] = P["i"] + 1
            P["i"] += 1
            s["pts"] = P["level"] * 100
            if P["level"] >= len(LADDER):
                P["done"] = True
                s["pts"] += 1000
            else:
                # La bonne réponse reste affichée un moment (ou jusqu'à la fin de la pause).
                P.update(between=now + REVEAL, paused=False)
        else:
            safe = max([i + 1 for i in LADDER_SAFE if i + 1 <= P["level"]], default=0)
            P.update(done=True, fell=True, level=safe)  # le gain retombe au palier assuré ; les points gagnés restent
    if all(x["done"] for x in Q["personal"].values()) and mode == "ladder":
        _finish(g)


def joker(g: dict, gid: str, kind: str, rng=random):
    init(g)
    Q = g["quiz"]
    P = Q["personal"].get(gid)
    if g["phase"] != "run" or Q["settings"]["mode"] != "ladder" or not P or P["done"]:
        raise QuizError("Pas de joker ici")
    if P.get("between"):
        raise QuizError("Attends la question suivante")
    if kind not in P["jokers"]:
        raise QuizError("Joker déjà utilisé")
    P["jokers"].remove(kind)
    q = P["q"]
    if kind == "5050":
        wrong = [i for i in range(4) if i != q["ans"]]
        P["cut"] = rng.sample(wrong, 2)
    else:
        lvl = (["1"] * 5 + ["2"] * 5 + ["3"] * 5)[min(P["i"], 14)]
        now = time.time()
        P["q"] = {**_draw(g, rng, lvl), "start": now, "end": now + LADDER_TIME}
        P["cut"] = []


def pause(g: dict, gid: str, lead: bool, rng=random):
    """⏸ / ▶ après avoir répondu. Paliers : chacun pour soi ; autres modes : l'animateur (ou l'admin, ou le joueur seul)."""
    init(g)
    Q = g["quiz"]
    tick(g, rng)
    if g["phase"] == "run":
        P = Q["personal"].get(gid)
        if Q["settings"]["mode"] != "ladder" or not P or not P.get("between"):
            raise QuizError("Pas de pause possible maintenant")
        if P.get("paused"):  # reprise : question suivante tout de suite
            P.update(between=None, paused=False)
            _personal_next(g, gid, rng)
        else:
            P["paused"] = True
        return
    if not lead:
        raise QuizError("Seul l'animateur peut mettre en pause")
    if g["phase"] not in ("q", "rev"):
        raise QuizError("Pas de pause possible maintenant")
    if Q.get("paused"):
        Q["paused"] = False
        if g["phase"] == "rev":
            _advance(g, rng)
    else:
        Q["paused"] = True


def stop(g: dict, gid: str):
    """Paliers : s'arrêter et garder ce qu'on a gagné."""
    init(g)
    Q = g["quiz"]
    P = Q["personal"].get(gid)
    if g["phase"] != "run" or Q["settings"]["mode"] != "ladder" or not P or P["done"]:
        raise QuizError("Rien à arrêter")
    P.update(done=True, stopped=True)
    if all(x["done"] for x in Q["personal"].values()):
        _finish(g)


def _personal_tick(g: dict, rng) -> bool:
    Q = g["quiz"]
    now = time.time()
    changed = False
    # Arrivés pendant la partie : ils commencent tout de suite.
    for p in g["players"]:
        if p["id"] not in Q["personal"] and not p.get("waiting"):
            _personal_next(g, p["id"], rng)
            changed = True
    if Q["settings"]["mode"] == "chrono":
        if now >= Q["deadline"]:
            _finish(g)
            return True
        return changed
    for gid, P in Q["personal"].items():
        if P.get("between"):
            if not P.get("paused") and now >= P["between"]:
                P.update(between=None, paused=False)
                _personal_next(g, gid, rng)
                changed = True
            continue
        if not P["done"] and now > P["q"]["end"] + 0.5:
            # Temps écoulé aux Paliers : comme une mauvaise réponse.
            _count(g, gid, P["q"]["qid"], False)
            safe = max([i + 1 for i in LADDER_SAFE if i + 1 <= P["level"]], default=0)
            P["last"] = {"qid": P["q"]["qid"], "choices": P["q"]["choices"], "c": None, "ans": P["q"]["ans"], "ok": False, "at": now}
            P.update(done=True, fell=True, level=safe)  # le gain retombe au palier assuré ; les points gagnés restent
            changed = True
    if Q["personal"] and all(x["done"] for x in Q["personal"].values()):
        _finish(g)
        changed = True
    return changed


def _finish(g: dict):
    g["phase"] = "end"
    record(g)


# --- Classement général (toutes les parties) ---

def _load_stats() -> dict:
    if STATS_PATH and STATS_PATH.exists():
        try:
            return json.loads(STATS_PATH.read_text())
        except (OSError, ValueError):
            pass
    return {"players": {}}


def _save_stats(data: dict):
    if not STATS_PATH:
        return
    STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False))
    tmp.replace(STATS_PATH)


def _stat_key(p: dict) -> str:
    """Un participant sans téléphone est compté par son prénom ; les autres par leur appareil."""
    from .games import normalize
    return "m:" + normalize(p["name"]) if p.get("manual") else p["id"]


def board(g: dict) -> list[tuple[dict, dict]]:
    """Joueurs triés : points, puis bonnes réponses, puis (Survie) qui a tenu le plus longtemps."""
    Q = g["quiz"]
    rows = [(p, _sc(g, p["id"])) for p in g["players"] if p["id"] in Q["scores"]]
    return sorted(rows, key=lambda r: (-r[1]["pts"], -r[1]["ok"], -(r[1].get("out_at") or 10**6)))


def record(g: dict):
    Q = g["quiz"]
    if Q.get("recorded"):
        return
    Q["recorded"] = True
    rows = board(g)
    if not rows:
        return
    mode = Q["settings"]["mode"]
    with _stats_lock:
        data = _load_stats()
        P = data.setdefault("players", {})
        for rank, (p, s) in enumerate(rows):
            if not s["n"]:
                continue
            st = P.setdefault(_stat_key(p), {"name": p["name"], "pts": 0, "games": 0, "wins": 0, "ok": 0, "n": 0, "best_streak": 0,
                                                "records": {}, "themes": {}})
            st["name"] = p["name"]
            st["pts"] += s["pts"]
            st["games"] += 1
            st["wins"] += 1 if rank == 0 and len(rows) > 1 else 0
            st["ok"] += s["ok"]
            st["n"] += s["n"]
            st["best_streak"] = max(st["best_streak"], s["best"])
            st["last"] = time.time()
            rec = {"classic": s["pts"], "speed": s["pts"], "survival": s["ok"], "chrono": s["ok"],
                   "ladder": Q["personal"].get(p["id"], {}).get("level", 0)}[mode]
            st["records"][mode] = max(st["records"].get(mode, 0), rec)
            for t, (ok, n) in s["themes"].items():
                th = st["themes"].setdefault(t, [0, 0])
                th[0] += ok
                th[1] += n
        _save_stats(data)


def leaderboard(limit: int = 20) -> dict:
    """Classement général et records par mode, pour l'écran d'accueil du quiz."""
    data = _load_stats()
    ps = list(data.get("players", {}).values())
    top = sorted(ps, key=lambda x: -x["pts"])[:limit]
    records = {}
    for m in MODES:
        best = max(ps, key=lambda x: x.get("records", {}).get(m, 0), default=None)
        if best and best.get("records", {}).get(m):
            records[m] = {"name": best["name"], "value": best["records"][m]}
    return {"top": [{"name": x["name"], "pts": x["pts"], "games": x["games"], "wins": x["wins"],
                     "rate": round(100 * x["ok"] / x["n"]) if x["n"] else 0, "streak": x["best_streak"]} for x in top],
            "records": records}


# --- Vue ---

def _qview(qid: str, choices: list[str]) -> dict:
    q = qb.BY_ID.get(qid, {})
    t = q.get("t", "culture")
    name, icon = qb.THEMES.get(t, ("", ""))
    return {"text": q.get("q", "?"), "theme": name, "icon": icon, "d": q.get("d", 2), "choices": choices}


def view(g: dict, gid: str) -> dict:
    init(g)
    Q = g["quiz"]
    s = Q["settings"]
    now = time.time()
    names = {p["id"]: p for p in g["players"]}
    me = names.get(gid)
    out = {
        "settings": s, "mode_label": MODES[s["mode"]][0], "mode_icon": MODES[s["mode"]][1], "diff_label": DIFFS[s["diff"]],
        "theme_labels": [f"{qb.THEMES[t][1]} {qb.THEMES[t][0]}" for t in s["themes"]] or ["🎲 Tous les thèmes"],
        "n": Q["n"], "server_now": now, "paused": bool(Q.get("paused")), "token": token(g, gid),
        "board": [{"pid": p["pid"], "name": p["name"], "pts": sc["pts"], "ok": sc["ok"], "n": sc["n"], "streak": sc["streak"],
                   "best": sc["best"], "lives": sc["lives"], "out": sc["out"], "me": p["id"] == gid,
                   "level": Q["personal"].get(p["id"], {}).get("level"), "done": Q["personal"].get(p["id"], {}).get("done", False)}
                  for p, sc in board(g)],
    }
    if g["phase"] == "lobby":
        out["catalog"] = {"themes": [{"id": t, "name": n, "icon": i, "count": len(qb.BANK[t])} for t, (n, i) in qb.THEMES.items() if qb.BANK[t]],
                          "modes": [{"id": m, "name": n, "icon": i} for m, (n, i) in MODES.items()], "diffs": DIFFS}
    if g["phase"] in ("lobby", "end"):
        out["leaderboard"] = leaderboard()
    c = Q["cur"]
    if g["phase"] in ("q", "rev") and c:
        mine = c["answers"].get(gid)
        out["q"] = {**_qview(c["qid"], c["choices"]), "left": max(0.0, c["end"] - now), "dur": s["time"],
                    "answered": len(c["answers"]) + len([x for x in c["locked"] if x not in c["answers"]]),
                    "players": len(_active(g)), "mine": mine["c"] if mine else None, "locked": gid in c["locked"],
                    "out": gid in Q["scores"] and Q["scores"][gid]["out"]}
        if g["phase"] == "rev":
            dist = [0, 0, 0, 0]
            for a in c["answers"].values():
                dist[a["c"]] += 1
            out["q"].update(correct=c["ans"], dist=dist, next_in=max(0.0, c.get("next_at", now) - now),
                            winner=names[c["winner"]]["name"] if c.get("winner") in names else None,
                            res=sorted([{"name": names[x]["name"], "ok": a["ok"] and (s["mode"] != "speed" or c["winner"] == x), "pts": a["pts"],
                                         "t": a["t"], "c": a["c"], "me": x == gid} for x, a in c["answers"].items() if x in names],
                                       key=lambda r: (not r["ok"], r["t"])))
    if g["phase"] == "run":
        out["deadline_in"] = max(0.0, Q["deadline"] - now) if Q["deadline"] else None
        P = Q["personal"].get(gid)
        if P:
            q = P["q"]
            mv = {"i": P["i"], "done": P["done"], "level": P["level"], "jokers": P["jokers"], "fell": P.get("fell", False),
                  "stopped": P.get("stopped", False), "streak": _sc(g, gid)["streak"], "pts": _sc(g, gid)["pts"]}
            if P.get("between"):
                mv["between_in"] = max(0.0, P["between"] - now)
                mv["paused"] = bool(P.get("paused"))
            if not P["done"]:
                mv["q"] = {**_qview(q["qid"], q["choices"]), "left": max(0.0, q["end"] - now), "cut": P["cut"],
                           "dur": LADDER_TIME if s["mode"] == "ladder" else s["chrono"]}
            if P.get("last"):
                L = P["last"]
                mv["last"] = {"ok": L["ok"], "c": L["c"], "ans": L["ans"], "answer": L["choices"][L["ans"]], "age": now - L["at"],
                              "text": qb.BY_ID.get(L["qid"], {}).get("q", "")}
            out["me"] = mv
        out["ladder"] = LADDER
        out["safe"] = list(LADDER_SAFE)
    if g["phase"] == "end" and s["mode"] == "ladder":
        out["ladder"] = LADDER
    return out


def summary_facts(g: dict) -> list[str]:
    init(g)
    s = g["quiz"]["settings"]
    facts = [f"{MODES[s['mode']][1]} {MODES[s['mode']][0]} · {DIFFS[s['diff']]}",
             "Thèmes : " + (", ".join(qb.THEMES[t][0] for t in s["themes"]) or "tous")]
    if g["quiz"]["n"]:
        facts.append(f"Question {g['quiz']['n']}" + (f"/{s['count']}" if s["mode"] in ("classic", "speed") else ""))
    return facts


def summary_extra(g: dict, gid: str) -> str:
    sc = g.get("quiz", {}).get("scores", {}).get(gid)
    return f"⭐ {sc['pts']}" if sc else ""
