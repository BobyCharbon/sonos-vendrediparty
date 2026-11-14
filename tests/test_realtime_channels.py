"""Temps réel du module Événements : une table hors de la publication `supabase_realtime` fait échouer TOUT son canal.

Constaté sur la base de TEST (recette du 14.11) : un canal qui écoute `rsvps` ET une table non publiée reçoit
« Unable to subscribe to changes with given parameters » et plus aucun changement, `rsvps` compris. Donc :
- toute table écoutée doit être publiée par une migration ;
- une table publiée par une migration pas encore en production (la prod n'a pas les migrations du 14.11) s'écoute
  dans SON canal : sans la migration, seul ce canal reste muet ; la fiche garde ses réponses, votes, messages en direct."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "web/events/src"
# Migrations de publication pas encore appliquées en production (à retirer une fois le « Ok prod » appliqué).
NOT_YET_IN_PROD = ("20261114110000_temps_reel_quantites.sql",)


def published() -> dict[str, str]:
    """Table → migration qui l'ajoute à la publication."""
    tables = {}
    for path in sorted((ROOT / "supabase/migrations").glob("*.sql")):
        sql = path.read_text()
        if "supabase_realtime" not in sql:
            continue
        found = re.findall(r"alter publication supabase_realtime add table ([^;]+);", sql)
        names = [t.strip().removeprefix("public.") for group in found if "%" not in group for t in group.split(",")]
        for block in re.findall(r"array\[([^\]]+)\][^;]*loop[\s\S]*?supabase_realtime add table", sql):
            names += re.findall(r"'(\w+)'", block)
        for name in names:
            tables.setdefault(name, path.name)
    return tables


def channels() -> list[tuple[str, list[str]]]:
    """(fichier, tables) de chaque appel à useRealtime."""
    calls = []
    for path in SRC.rglob("*.tsx"):
        text = path.read_text()
        for m in re.finditer(r"useRealtime\(", text):
            depth, i = 0, m.end() - 1
            while True:
                depth += {"(": 1, ")": -1}.get(text[i], 0)
                if depth == 0:
                    break
                i += 1
            calls.append((path.relative_to(SRC).as_posix(), re.findall(r"table: '(\w+)'", text[m.end():i])))
    return calls + [(p.relative_to(SRC).as_posix(), re.findall(r"table: '(\w+)'", p.read_text()))
                    for p in SRC.rglob("*.ts") if "useRealtime(" in p.read_text() and "export function useRealtime" not in p.read_text()]


def test_every_listened_table_is_published():
    tables = published()
    missing = {(f, t) for f, ts in channels() for t in ts if t not in tables}
    assert not missing, f"tables écoutées mais jamais publiées (canal entier muet) : {sorted(missing)}"


def test_a_table_not_yet_published_in_production_listens_alone():
    tables = published()
    mixed = [(f, ts) for f, ts in channels() if len(set(ts)) > 1 and any(tables.get(t) in NOT_YET_IN_PROD for t in ts)]
    assert not mixed, f"sans la migration en prod, ces canaux entiers seraient muets : {mixed}"
    assert any(ts == ["bring_claims"] for _, ts in channels()), "les quantités « Qui amène quoi » ne sont plus en direct"
