"""Groupes plus simples (avis f0e9bf158133, migration 20261122134000), sur la VRAIE base de test (jamais la prod) :
- group_people_search : numéro complet ou nom (3 lettres), 5 personnes au plus, JAMAIS le numéro ; ni membres, ni blocages ;
  30 recherches différentes par heure ;
- « Tous les membres peuvent inviter » (members_invite, allumé par défaut) : respecté par la base (lien, invitation,
  recherche), changé par le créateur seulement ;
- « Événements à valider » (events_need_approval) : l'événement d'un simple membre attend l'accord du créateur.
Événements de test sans notification (conftest)."""
import httpx
import pytest

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, GUEST_B, VIP, complete_profile, create_event, make_vip, unmake_vip
from tests.supabase_live.test_groups_members_only_live import sql_test
from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark  # noqa: F401

NICK_B = 'Zébulon B'


@pytest.fixture(scope='module')
def world():
    admin, ga, gb, vip = Session(ADMIN), Session(GUEST_A), Session(GUEST_B), Session(VIP)
    make_vip(admin, vip)
    complete_profile(ga, 'Guest A')
    complete_profile(gb, NICK_B)
    # Guest A crée le groupe (il le gère) ; le VIP en est un simple membre.
    r = httpx.post(f'{TEST_URL}/rest/v1/member_groups', timeout=30, headers={**ga.headers, 'Prefer': 'return=representation'},
                   json={'name': 'Test groupes simples', 'created_by': ga.uid})
    assert r.status_code == 201, r.text
    gid = r.json()[0]['id']
    assert sql_test(f"insert into public.member_group_members (group_id, user_id) values ('{gid}', '{vip.uid}') on conflict do nothing") == []
    # Le VIP et Guest B se croisent à une soirée publique : Guest B peut recevoir une demande du VIP.
    met = create_event(admin, 'Test groupes simples : soirée', public_link=True)
    for who in (vip, gb):
        yes = httpx.post(f'{TEST_URL}/rest/v1/rsvps', headers=who.headers, timeout=30, json={'event_id': met, 'user_id': who.uid, 'status': 'yes'})
        assert yes.status_code == 201, yes.text
    yield admin, ga, gb, vip, gid
    sql_test(f"delete from private.group_search_log where user_id in ('{vip.uid}', '{ga.uid}')")
    httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{met}', headers=admin.headers, timeout=30)
    httpx.delete(f'{TEST_URL}/rest/v1/member_groups?id=eq.{gid}', headers=ga.headers, timeout=30)
    unmake_vip(admin, vip)


def search(s: Session, gid: str, q: str) -> httpx.Response:
    sql_test(f"delete from private.group_search_log where user_id = '{s.uid}'")  # chaque test part de zéro
    return s.rpc('group_people_search', grp=gid, q=q)


def test_search_by_name_returns_nickname_photo_and_initial_never_the_number(world):
    _, ga, gb, vip, gid = world
    r = search(vip, gid, 'zébul')
    assert r.status_code == 200, r.text
    found = [p for p in r.json() if p['id'] == gb.uid]
    assert found and set(found[0]) == {'id', 'display_name', 'avatar_url', 'initial', 'invited'}
    assert found[0]['display_name'] == NICK_B and found[0]['initial'] == 'T' and found[0]['avatar_url']
    assert '0000002' not in r.text  # jamais le numéro
    assert len(r.json()) <= 5
    assert search(vip, gid, 'zé').json() == []  # moins de 3 lettres : rien
    # Jamais un membre du groupe ni soi-même.
    ids = {p['id'] for p in search(vip, gid, 'guest a').json()} | {p['id'] for p in search(vip, gid, 'vip test').json()}
    assert ga.uid not in ids and vip.uid not in ids


def test_search_by_full_number_only(world):
    _, _, gb, vip, gid = world
    whole = search(vip, gid, '+41 79 000 00 02')
    assert [p['id'] for p in whole.json()] == [gb.uid], whole.text
    assert '41790000002' not in whole.text
    assert search(vip, gid, '079 000 00 02').json()[0]['id'] == gb.uid  # format suisse, comme la connexion SMS
    assert search(vip, gid, '+41 79 000').json() == []  # numéro incomplet : rien


def test_blocked_people_are_never_found(world):
    _, _, gb, vip, gid = world
    sql_test(f"insert into public.direct_blocks (user_id, blocked_id) values ('{gb.uid}', '{vip.uid}') on conflict do nothing")
    try:
        assert all(p['id'] != gb.uid for p in search(vip, gid, 'zébul').json())
        assert search(vip, gid, '+41790000002').json() == []
    finally:
        sql_test(f"delete from public.direct_blocks where user_id = '{gb.uid}' and blocked_id = '{vip.uid}'")


def test_searches_are_limited_to_30_per_hour(world):
    _, _, _, vip, gid = world
    sql_test(f"delete from private.group_search_log where user_id = '{vip.uid}';"
             f"insert into private.group_search_log (user_id, q) select '{vip.uid}', 'q' || i from generate_series(1, 30) i")
    try:
        r = vip.rpc('group_people_search', grp=gid, q='zébulon')
        assert r.status_code >= 400 and 'limit' in r.text, r.text
        again = vip.rpc('group_people_search', grp=gid, q='q7')  # la même recherche répétée ne compte pas
        assert again.status_code == 200, again.text
    finally:
        sql_test(f"delete from private.group_search_log where user_id = '{vip.uid}'")


def test_members_invite_setting_is_kept_by_the_base(world):
    _, ga, gb, vip, gid = world
    assert sql_test(f"select members_invite from public.member_groups where id = '{gid}'") == [{'members_invite': True}]
    assert vip.rpc('group_invite_link', grp=gid, renew=False).status_code == 200  # allumé par défaut : un membre partage
    assert next(g for g in vip.rpc('my_groups_overview').json() if g['id'] == gid)['invite'] is True
    # Un simple membre ne change pas le réglage (fonction refusée, écriture directe sans effet).
    assert vip.rpc('set_group_members_invite', grp=gid, allowed=False).status_code in (401, 403)
    httpx.patch(f'{TEST_URL}/rest/v1/member_groups?id=eq.{gid}', headers=vip.headers, json={'members_invite': False}, timeout=30)
    assert sql_test(f"select members_invite from public.member_groups where id = '{gid}'") == [{'members_invite': True}]
    assert ga.rpc('set_group_members_invite', grp=gid, allowed=False).status_code in (200, 204)
    try:
        assert vip.rpc('group_invite_link', grp=gid, renew=False).status_code in (401, 403)
        assert vip.rpc('invite_to_group', grp=gid, member=gb.uid).status_code in (401, 403)
        assert search(vip, gid, 'zébul').status_code in (401, 403)
        assert next(g for g in vip.rpc('my_groups_overview').json() if g['id'] == gid)['invite'] is False
        assert next(g for g in ga.rpc('my_groups_overview').json() if g['id'] == gid)['invite'] is True
        assert ga.rpc('group_invite_link', grp=gid, renew=False).status_code == 200  # qui gère invite toujours
    finally:
        assert ga.rpc('set_group_members_invite', grp=gid, allowed=True).status_code in (200, 204)


def test_vendredi_party_has_no_members_invite_setting(world):
    admin = world[0]
    vp = sql_test("select id from public.member_groups where system_key = 'vip'")[0]['id']
    assert admin.rpc('set_group_members_invite', grp=vp, allowed=False).status_code in (401, 403)


def test_a_member_invites_someone_found_by_the_search(world):
    _, _, gb, vip, gid = world
    try:
        r = vip.rpc('invite_to_group', grp=gid, member=gb.uid)
        assert r.status_code == 200 and r.json() == {'invited': 'member'}, r.text
        found = next(p for p in search(vip, gid, 'zébul').json() if p['id'] == gb.uid)
        assert found['invited'] is True
        assert any(i['group_id'] == gid for i in gb.rpc('my_group_invitations').json())
    finally:
        sql_test(f"delete from private.group_invitations where group_id = '{gid}';"
                 f"delete from private.group_invite_log where user_id = '{vip.uid}'")


def test_events_to_approve_wait_for_the_creator(world):
    admin, ga, _, vip, gid = world
    assert ga.rpc('set_group_event_rules', grp=gid, need_approval=True, mode='request').status_code in (200, 204)
    event = create_event(vip, 'Test groupes simples : à valider', visibility='invited')
    # Base de TEST : la modération du site peut laisser l'événement « pending » ; l'admin du site le publie.
    httpx.patch(f'{TEST_URL}/rest/v1/events?id=eq.{event}', headers=admin.headers, json={'status': 'published'}, timeout=30)
    try:
        added = httpx.post(f'{TEST_URL}/rest/v1/event_groups', headers={**vip.headers, 'Prefer': 'return=representation'}, timeout=30,
                           json={'event_id': event, 'group_id': gid})
        assert added.status_code == 201 and added.json()[0]['status'] == 'pending', added.text
        asks = [x for x in ga.rpc('my_group_requests').json() if x['kind'] == 'event' and x['event_id'] == event]
        assert asks, 'le créateur du groupe voit la demande'
        ok = ga.rpc('answer_group_event', e=event, g=gid, accept=True)
        assert ok.status_code == 200 and ok.json()['status'] == 'approved', ok.text
        assert sql_test(f"select status from public.event_groups where event_id = '{event}'") == [{'status': 'approved'}]
    finally:
        httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{event}', headers=vip.headers, timeout=30)
        ga.rpc('set_group_event_rules', grp=gid, need_approval=False, mode='request')
