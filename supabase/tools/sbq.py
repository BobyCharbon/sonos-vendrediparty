#!/usr/bin/env python3
"""sbq.py <prod|test> [rw] < requete.sql : SQL via l'API de gestion Supabase. Prod : toujours en lecture seule."""
import json
import sys
import urllib.request
import pathlib
REFS = {"prod": "gsuetixzobooggeaubvb", "test": "ewromqfsmcqsthftyhzm"}
target = sys.argv[1]
rw = len(sys.argv) > 2 and sys.argv[2] == "rw"
if target == "prod" and rw:
    sys.exit("Écriture en prod refusée par ce script (accord explicite requis, à faire à part).")
token = (pathlib.Path.home() / ".config/supabase-claude/token").read_text().strip()
path = "database/query" if rw else "database/query/read-only"
req = urllib.request.Request(f"https://api.supabase.com/v1/projects/{REFS[target]}/{path}",
    data=json.dumps({"query": sys.stdin.read()}).encode(), method="POST",
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": "party-claude"})
try:
    with urllib.request.urlopen(req, timeout=120) as r:
        print(r.read().decode())
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}: {e.read().decode()[:2000]}"); sys.exit(1)
