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
TABLES = {'events', 'event_invites', 'event_groups', 'member_group_members', 'event_organizers', 'bring_items', 'date_options',
          'bring_claims', 'rsvps'}


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


def probe(who, table: str, filt: str, name: str) -> tuple[subprocess.Popen, Path]:
    """Abonné de l'app, prêt : (processus, fichier copié à effacer)."""
    path = ROOT / f'web/events/rt-probe-{name}.mjs'
    shutil.copy(ROOT / 'tests/supabase_live/realtime_probe.mjs', path)
    p = subprocess.Popen(['node', path.name, TEST_URL, KEY_FILE.read_text().strip(), who.headers['Authorization'].split()[1], who.uid,
                          table, filt], cwd=path.parent, stdout=subprocess.PIPE, text=True)
    assert p.stdout.readline().strip() == 'READY'
    return p, path


@pytest.mark.skipif(not shutil.which('node') or not (ROOT / 'web/events/node_modules/@supabase').exists(), reason='node et web/events/node_modules requis')
def test_an_invited_guest_sees_the_others_answers_and_quantities_live():
    """Avis ead4902642da : sur la fiche ouverte, la réponse d'un autre invité et ce qu'il amène (« 2 bouteilles ») arrivent
    en direct, sans recharger. Vraies écritures sur la base de TEST, effacées à la fin."""
    who = Session('41790000001')
    olga = sql("select id from public.profiles where phone = '41790000103'")[0]['id']
    event = sql(f"""insert into public.events (title, status, visibility, notify_on_publish, starts_at, created_by)
        values ('[Recette] Temps réel fiche', 'published', 'invited', false, now() + interval '9 days', '{olga}') returning id""")[0]['id']
    probes = []
    try:
        sql(f"insert into public.event_invites (event_id, user_id) values ('{event}', '{who.uid}')")
        item = sql(f"insert into public.bring_items (event_id, label, quantity, added_by) values ('{event}', 'Bouteilles', 10, '{olga}') returning id")[0]['id']
        probes = [probe(who, 'rsvps', f'event_id=eq.{event}', 'rsvps'), probe(who, 'bring_claims', f'item_id=eq.{item}', 'bring')]
        time.sleep(3)  # abonnements établis côté serveur
        sql(f"insert into public.rsvps (event_id, user_id, status) values ('{event}', '{olga}', 'yes')")
        sql(f"insert into public.bring_claims (item_id, user_id, quantity) values ('{item}', '{olga}', 2)")
        sql(f"update public.bring_claims set quantity = 3 where item_id = '{item}' and user_id = '{olga}'")
        got = [json.loads(p.communicate(timeout=30)[0].strip()) for p, _ in probes]
        # La réponse arrive (INSERT), puis la base range la liste d'attente (UPDATE) : la fiche se relit dans les deux cas.
        assert got[0][:1] == ['INSERT'], f'réponse d’Olga non reçue : {got[0]}'
        assert got[1] == ['INSERT', 'UPDATE'], f'quantités non reçues : {got[1]}'
    finally:
        for p, path in probes:
            p.kill()
            path.unlink(missing_ok=True)
        sql(f"delete from public.events where id = '{event}'")
