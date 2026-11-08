"""Événements en temps réel (retour de l'admin du 08.11), sur la VRAIE base de TEST : ajouté à un groupe, le compte le
reçoit en direct (la liste des événements se recharge seule) ; retiré, aussi. Abonné = la bibliothèque Supabase de l'app.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_temps_reel_live.py -q"""
import json
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from tests.supabase_live.test_member_admin_live import KEY_FILE, TEST_URL, Session, pytestmark  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql

ROOT = Path(__file__).resolve().parents[2]
TABLES = {'events', 'event_invites', 'event_groups', 'member_group_members', 'event_organizers', 'bring_items', 'date_options'}


def test_the_event_tables_are_published_in_real_time():
    rows = sql("select tablename from pg_publication_tables where pubname = 'supabase_realtime' and schemaname = 'public'")
    assert TABLES <= {r['tablename'] for r in rows}


@pytest.mark.skipif(not shutil.which('node') or not (ROOT / 'web/events/node_modules/@supabase').exists(), reason='node et web/events/node_modules requis')
def test_added_to_a_group_the_account_is_told_live():
    who = Session('41790000001')
    group = sql("select id from public.member_groups where name like 'Bots%' order by name limit 1")[0]['id']
    gone = f"delete from public.member_group_members where group_id = '{group}' and user_id = '{who.uid}'"
    sql(gone)
    probe = ROOT / 'web/events/rt-probe-test.mjs'
    shutil.copy(ROOT / 'tests/supabase_live/realtime_probe.mjs', probe)
    try:
        p = subprocess.Popen(['node', probe.name, TEST_URL, KEY_FILE.read_text().strip(), who.headers['Authorization'].split()[1], who.uid],
                             cwd=probe.parent, stdout=subprocess.PIPE, text=True)
        assert p.stdout.readline().strip() == 'READY'
        time.sleep(3)  # abonnement établi côté serveur
        sql(f"insert into public.member_group_members (group_id, user_id) values ('{group}', '{who.uid}') on conflict do nothing")
        time.sleep(3)
        sql(gone)
        assert json.loads(p.communicate(timeout=30)[0].strip()) == ['INSERT', 'DELETE']
    finally:
        probe.unlink(missing_ok=True)
        sql(gone)
