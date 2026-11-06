"""Un organisateur ne réserve un événement qu'aux groupes dont il fait partie (question de l'admin, 06.11.2026 ;
migration 20261106090000), sur la VRAIE base de test (jamais la prod) :
- un Membre VIP ne peut pas ajouter par l'API un groupe dont il ne fait pas partie (même par invite_people) ;
- il ajoute le sien, une fois membre ; un admin (events.manage_all) garde la main sur tous les groupes ;
- « Membres Vendredi Party » : refusé à un compte hors du groupe Vendredi Party (transaction annulée, rien ne reste).
Événements de test en brouillon, sans notification (conftest)."""
import json
import subprocess
from pathlib import Path

import httpx
import pytest

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, VIP, create_event, make_vip, unmake_vip
from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]


def sql_test(query: str) -> list:
    out = subprocess.run(["python3", str(ROOT / "supabase/tools/sbq.py"), "test", "rw"], input=query,
                         capture_output=True, text=True, timeout=120)
    return json.loads(out.stdout or "[]") if out.returncode == 0 else [{"error": out.stdout + out.stderr}]


def add_group(s: Session, event: str, group: str) -> httpx.Response:
    return httpx.post(f'{TEST_URL}/rest/v1/event_groups', headers=s.headers, timeout=30, json={'event_id': event, 'group_id': group})


@pytest.fixture(scope='module')
def world():
    admin, vip = Session(ADMIN), Session(VIP)
    make_vip(admin, vip)
    made = []
    for owner, name in ((admin, 'Test groupe de l’admin'), (vip, 'Test groupe du VIP')):
        r = httpx.post(f'{TEST_URL}/rest/v1/member_groups', timeout=30, headers={**owner.headers, 'Prefer': 'return=representation'},
                       json={'name': name, 'created_by': owner.uid})
        assert r.status_code == 201, r.text
        made.append((owner, r.json()[0]['id']))
    event = create_event(vip, 'Test groupes membres seulement', visibility='invited', status='draft')
    yield admin, vip, made[0][1], made[1][1], event
    httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{event}', headers=vip.headers, timeout=30)
    for owner, group in made:
        httpx.delete(f'{TEST_URL}/rest/v1/member_groups?id=eq.{group}', headers=owner.headers, timeout=30)
    unmake_vip(admin, vip)


def test_an_organizer_cannot_force_a_group_he_is_not_in(world):
    _, vip, admins_group, own_group, event = world
    refused = add_group(vip, event, admins_group)
    assert refused.status_code in (401, 403) and 'groupes dont tu fais partie' in refused.text, refused.text
    rpc = vip.rpc('invite_people', e=event, people=[], groups=[admins_group])
    assert rpc.status_code in (400, 401, 403), rpc.text
    # Son groupe (le créateur en fait partie) : accepté.
    inside = vip.get(f'member_group_members?select=user_id&group_id=eq.{own_group}&user_id=eq.{vip.uid}').json()
    if not inside:
        joined = httpx.post(f'{TEST_URL}/rest/v1/member_group_members', headers=vip.headers, timeout=30,
                            json={'group_id': own_group, 'user_id': vip.uid})
        assert joined.status_code == 201, joined.text
    assert add_group(vip, event, own_group).status_code == 201
    assert vip.get(f'event_groups?select=group_id&event_id=eq.{event}').json() == [{'group_id': own_group}]


def test_an_admin_keeps_every_group(world):
    admin, vip, _, own_group, _ = world
    event = create_event(admin, 'Test groupe par l’admin', visibility='invited', status='draft')
    try:
        assert add_group(admin, event, own_group).status_code == 201  # l'admin n'est pas dans le groupe du VIP
    finally:
        httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{event}', headers=admin.headers, timeout=30)


def test_vendredi_party_visibility_is_refused_outside_the_group():
    """Tous les comptes qui créent des événements sont aujourd'hui dans Vendredi Party (rang ≥ Guest+) : on donne
    « créer » à un Guest le temps d'une transaction annulée, avec sa propre session (règles de la base)."""
    guest = Session(GUEST_A).uid
    claims = json.dumps({"sub": guest, "role": "authenticated"})
    def attempt(fields: str) -> str:
        rows = sql_test(f"""
        begin;
        insert into public.role_permissions (role, perm) values ('guest', 'events.create') on conflict do nothing;
        set local role authenticated;
        set local request.jwt.claims = '{claims}';
        do $$ begin
          insert into public.events (title, created_by, status, notify_on_publish, {fields.split('|')[0]})
            values ('Test VIP interdit', '{guest}', 'draft', false, {fields.split('|')[1]});
          raise exception 'accepté';
        end $$;
        rollback;""")
        return json.dumps(rows, ensure_ascii=False)
    assert 'Vendredi Party' in attempt("visibility, public_link|'all', false")
    assert 'accepté' in attempt("visibility, public_link|'all', true")  # public + lien : permis
    assert 'accepté' in attempt("visibility, public_link|'invited', false")  # sur invitation : permis
    assert sql_test(f"select count(*) as n from public.events where title = 'Test VIP interdit' and created_by = '{guest}'") == [{"n": 0}]
