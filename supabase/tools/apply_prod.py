#!/usr/bin/env python3
"""apply_prod.py supabase/prod/<fichier>.sql : applique UN fichier préparé de supabase/prod/ sur la base de PRODUCTION.

Seul chemin d'écriture en prod (sbq.py reste en lecture seule). Règle du projet (CLAUDE.md) : à lancer uniquement après
l'accord explicite de l'admin (« Ok prod ») pour cette migration précise.
Garde-fous : fichier obligatoirement dans supabase/prod/ ; une migration déjà enregistrée en prod n'est pas rejouée
(sauf --force) ; un retour arrière (-rollback.sql) n'est lancé que si la migration est bien en prod.
Affiche l'historique des migrations avant et après, et note chaque passage dans supabase/prod/journal.log.
"""
import datetime
import json
import pathlib
import re
import sys
import urllib.error
import urllib.request

PROD_REF = "gsuetixzobooggeaubvb"
ROOT = pathlib.Path(__file__).resolve().parents[2]
PROD_DIR = ROOT / "supabase" / "prod"
TOKEN_FILE = pathlib.Path.home() / ".config/supabase-claude/token"
TIMEOUT_S = 180
HISTORY_SQL = ("select coalesce(string_agg(version, ',' order by version), '') as v "
               "from supabase_migrations.schema_migrations where version >= '20261020'")


def query(sql: str, read_only: bool) -> list:
    path = "database/query/read-only" if read_only else "database/query"
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{PROD_REF}/{path}",
        data=json.dumps({"query": sql}).encode(), method="POST",
        headers={"Authorization": f"Bearer {TOKEN_FILE.read_text().strip()}",
                 "Content-Type": "application/json", "User-Agent": "party-claude"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            return json.loads(r.read().decode() or "[]")
    except urllib.error.HTTPError as e:
        sys.exit(f"ÉCHEC (HTTP {e.code}) — rien n'est appliqué si le fichier est en begin/commit :\n{e.read().decode()[:2000]}")


def history() -> set[str]:
    rows = query(HISTORY_SQL, read_only=True)
    return set(filter(None, (rows[0]["v"] if rows else "").split(",")))


def target_file(arg: str) -> pathlib.Path:
    raw = pathlib.Path(arg)
    path = (raw if raw.is_absolute() else ROOT / raw).resolve()
    if path.parent != PROD_DIR or path.suffix != ".sql" or not path.is_file():
        sys.exit(f"Refusé : seul un fichier .sql existant de supabase/prod/ peut être appliqué ({arg}).")
    return path


def versions_in(sql: str, rollback: bool) -> set[str]:
    pattern = (r"delete from supabase_migrations\.schema_migrations where version = '(\d{14})'" if rollback
               else r"insert into supabase_migrations\.schema_migrations[^;]*?values \('(\d{14})'")
    return set(re.findall(pattern, sql, flags=re.IGNORECASE))


def main():
    args = [a for a in sys.argv[1:] if a != "--force"]
    if len(args) != 1:
        sys.exit(__doc__)
    path = target_file(args[0])
    sql = path.read_text(encoding="utf-8")
    rollback = path.stem.endswith("-rollback")
    versions = versions_in(sql, rollback)
    if not versions:
        sys.exit("Refusé : aucune version de migration trouvée dans ce fichier (enregistrement schema_migrations absent).")
    before = history()
    print(f"Avant : {', '.join(sorted(before)) or '(aucune)'}")
    if rollback and not versions <= before:
        sys.exit(f"Refusé : {', '.join(sorted(versions - before))} n'est pas en prod, rien à annuler.")
    if not rollback and versions <= before and "--force" not in sys.argv:
        sys.exit(f"Déjà en prod : {', '.join(sorted(versions))}. Rien fait (--force pour rejouer).")
    print(f"Application de {path.name} ({'retour arrière de ' if rollback else ''}{', '.join(sorted(versions))})…")
    result = query(sql, read_only=False)
    after = history()
    print(f"Après : {', '.join(sorted(after)) or '(aucune)'}")
    ok = versions.isdisjoint(after) if rollback else versions <= after
    with (PROD_DIR / "journal.log").open("a", encoding="utf-8") as log:
        log.write(f"{datetime.datetime.now().isoformat(timespec='seconds')} {path.name} "
                  f"{'OK' if ok else 'ÉCHEC'} {','.join(sorted(versions))}\n")
    if result:
        print("Résultat :", json.dumps(result, ensure_ascii=False)[:1500])
    sys.exit(0 if ok else "ÉCHEC : l'historique des migrations n'a pas changé comme prévu.")


if __name__ == "__main__":
    main()
