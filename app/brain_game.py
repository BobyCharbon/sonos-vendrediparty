"""Méninges — statistiques d'UN jeu (écran de fin enrichi et fiche du jeu ; réponse de /api/brain/game et
/api/brain/game/local). Mêmes calculs que app/brain.py (indice du jeu = moyenne des 5 meilleures parties des 30 jours)."""
from datetime import datetime, timezone
from statistics import mean

from . import brain

GAME_HISTORY = 30   # parties de ce jeu renvoyées pour la courbe (les plus récentes)


def _mean_or_none(values: list[float]) -> float | None:
    return mean(values) if values else None


def game_detail(sessions: list[dict], game: str, percentile: int | None = None, now: datetime | None = None) -> dict:
    """Un jeu : record, moyenne, niveau max et palier max, parties, indice du jeu, précision et temps de réaction moyens, et les 30
    dernières parties (score + indice) pour la courbe de progression."""
    if game not in brain.CATALOG:
        raise brain.BrainError("Jeu inconnu")
    now = now or datetime.now(timezone.utc)
    rows = [s for s in brain._clean(sessions) if s["game"] == game]
    # Horloge du téléphone parfois en avance (parties locales) : la dernière partie compte toujours.
    index = brain._game_raw(rows, max([now, *(s["at"] for s in rows)])).get(game)
    accs = [float(s["accuracy"]) for s in rows if s.get("accuracy") is not None]
    rts = [int(s.get("avg_rt_ms") or 0) for s in rows if int(s.get("avg_rt_ms") or 0) > 0]
    avg_acc, avg_rt = _mean_or_none(accs), _mean_or_none(rts)
    g = brain.CATALOG[game]
    max_level = max((int(s.get("level") or 1) for s in rows), default=0)
    return {
        "game": game, "name": g.name, "domain": g.domain,
        "plays": len(rows),
        "best": max((s["score"] for s in rows), default=0),
        "avg": brain.round_half_up(mean(s["score"] for s in rows)) if rows else 0,
        "level": max_level,
        "max_tier": brain.tier_of(max_level),   # palier le plus haut débloqué (ajouté le 03.11)
        "last_level": int(rows[-1].get("level") or 1) if rows else 0,
        "index": brain.round_half_up(index) if index is not None else 0,
        "accuracy": round(avg_acc, 4) if avg_acc is not None else None,
        "avg_rt_ms": brain.round_half_up(avg_rt) if avg_rt is not None else None,
        "percentile": percentile,
        "history": [{"day": brain._day(s["at"]).isoformat(), "score": s["score"],
                     "index": brain.round_half_up(s["raw"]), "level": int(s.get("level") or 1)}
                    for s in rows[-GAME_HISTORY:]],
    }
