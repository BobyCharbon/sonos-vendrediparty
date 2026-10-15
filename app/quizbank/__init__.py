"""Banque de questions du Quiz : 14 thèmes, chacun fait de questions rédigées et de questions générées.

- Questions rédigées : un fichier texte par thème (app/quizbank/written/<thème>.txt), une question par ligne :
      difficulté|question|bonne réponse|mauvaise 1|mauvaise 2|mauvaise 3
  (difficulté : 1 facile, 2 moyen, 3 difficile ; les lignes vides et celles qui commencent par # sont ignorées).
- Questions générées : à partir de tables de données vérifiées (pays, cantons, éléments, films…), voir gen_*.py.
  Les mauvaises réponses sont tirées dans la même table, de façon reproductible (même question = mêmes choix).

Chaque question : {"id", "t" (thème), "q", "a" (bonne réponse), "w" (3 mauvaises), "d" (1-3)}.
L'identifiant ne dépend que du texte et des choix : il reste stable d'un déploiement à l'autre.
"""

import hashlib
import random
from pathlib import Path

THEMES = {
    "culture": ("Culture générale", "🧠"),
    "geo": ("Géographie", "🌍"),
    "histoire": ("Histoire", "🏛️"),
    "sciences": ("Sciences", "🔬"),
    "tech": ("Informatique & IA", "💻"),
    "corps": ("Corps humain", "🫀"),
    "animaux": ("Animaux", "🦁"),
    "espace": ("Espace", "🚀"),
    "cinema": ("Cinéma & séries", "🎬"),
    "musique": ("Musique", "🎵"),
    "jeux": ("Jeux vidéo", "🎮"),
    "bd": ("BD & mangas", "📚"),
    "sport": ("Sport", "⚽"),
    "cuisine": ("Cuisine", "🍽️"),
    "suisse": ("Suisse", "🇨🇭"),
}

WRITTEN = Path(__file__).parent / "written"


def qid(theme: str, q: str, a: str, w: list[str]) -> str:
    return f"{theme}:{hashlib.sha1('|'.join([q, a, *sorted(w)]).encode()).hexdigest()[:10]}"


def make(theme: str, q: str, a: str, wrong: list[str], d: int = 2) -> dict | None:
    """Une question à 4 choix ; None si elle est mal formée (moins de 3 mauvaises réponses distinctes)."""
    a = str(a)
    w = []
    for x in wrong:
        x = str(x)
        if x != a and x not in w:
            w.append(x)
    if len(w) < 3:
        return None
    w = w[:3]
    return {"id": qid(theme, q, a, w), "t": theme, "q": q, "a": a, "w": w, "d": max(1, min(3, int(d)))}


def pick(seed: str, pool, answer, n: int = 3, key=None) -> list:
    """n mauvaises réponses tirées dans pool (sans la bonne), toujours les mêmes pour une même question."""
    rng = random.Random(seed)
    key = key or (lambda x: x)
    cands = [x for x in dict.fromkeys(pool) if key(x) != key(answer)]
    rng.shuffle(cands)
    return cands[:n]


def load_written(theme: str) -> list[dict]:
    path = WRITTEN / f"{theme}.txt"
    out = []
    if not path.exists():
        return out
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 6 or parts[0] not in "123":
            raise ValueError(f"{path.name}:{n} : ligne mal formée ({len(parts)} champs)")
        q = make(theme, parts[1], parts[2], parts[3:], int(parts[0]))
        if q is None:
            raise ValueError(f"{path.name}:{n} : réponses en double")
        out.append(q)
    return out


def _build() -> dict[str, list[dict]]:
    from . import gen_culture, gen_cuisine, gen_divert, gen_geo, gen_histoire, gen_nature, gen_sciences, gen_sport, gen_suisse, gen_tech

    bank: dict[str, list[dict]] = {t: load_written(t) for t in THEMES}
    for mod in (gen_geo, gen_suisse, gen_sciences, gen_histoire, gen_culture, gen_cuisine, gen_divert, gen_sport, gen_nature, gen_tech):
        for q in mod.generate():
            if q:
                bank[q["t"]].append(q)
    # Pas deux fois la même question (même texte et mêmes choix) dans un thème.
    for t, qs in bank.items():
        seen, uniq = set(), []
        for q in qs:
            if q["id"] not in seen:
                seen.add(q["id"])
                uniq.append(q)
        bank[t] = uniq
    return bank


BANK = _build()
BY_ID = {q["id"]: q for qs in BANK.values() for q in qs}


def counts() -> dict[str, int]:
    return {t: len(qs) for t, qs in BANK.items()}
