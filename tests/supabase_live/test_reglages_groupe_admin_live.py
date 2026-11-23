"""Réglages du groupe pour son admin (demande du 23.11, migration 20261123110000), sur la VRAIE base de test (jamais la
prod) : rôles (Co-admin, Organisateur, Membre), « Qui peut… » respecté par la BASE pour chaque droit (inviter, événement du
groupe, @tout, écrire, épingler, nom / emoji, retirer), « Accepter chaque nouveau membre », transmettre le groupe ; par
défaut rien ne change ; jamais Membres Vendredi Party. Événements de test sans notification (conftest)."""
import httpx
import pytest

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, GUEST_B, VIP, complete_profile, make_vip, unmake_vip
from tests.supabase_live.test_groups_members_only_live import sql_test
from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark  # noqa: F401

QA = '41790000006'
DEFAULTS = {'invite': 'members', 'events': 'members', 'announce': 'members', 'write': 'members',
            'pin': 'admins', 'edit': 'admins', 'remove': 'admins'}


@pytest.fixture(scope='module')
def world():
    admin, ga, gb, vip, qa = Session(ADMIN), Session(GUEST_A), Session(GUEST_B), Session(VIP), Session(QA)
    make_vip(admin, vip)
    for who, nick in ((ga, 'Guest A'), (gb, 'Guest B'), (qa, 'QA Six')):
        complete_profile(who, nick)
    r = httpx.post(f'{TEST_URL}/rest/v1/member_groups', timeout=30, headers={**ga.headers, 'Prefer': 'return=representation'},
                   json={'name': 'Test réglages admin', 'created_by': ga.uid})
    assert r.status_code == 201, r.text
    gid = r.json()[0]['id']
    for who in (vip, qa):
        assert sql_test(f"insert into public.member_group_members (group_id, user_id) values ('{gid}', '{who.uid}') on conflict do nothing") == []
    yield admin, ga, gb, vip, qa, gid
    sql_test(f"delete from public.member_groups where id = '{gid}'")
    unmake_vip(admin, vip)


def right(s: Session, gid: str, k: str, level: str):
    r = s.rpc('set_group_right', grp=gid, k=k, level=level)
    assert r.status_code in (200, 204), r.text


def send(s: Session, gid: str, body: str, **extra) -> httpx.Response:
    return httpx.post(f'{TEST_URL}/rest/v1/group_messages', timeout=30, headers={**s.headers, 'Prefer': 'return=representation'},
                      json={'group_id': gid, 'body': body, **extra})


def test_defaults_keep_todays_behaviour_and_the_panel_tells_each_one_its_rights(world):
    _, ga, gb, vip, qa, gid = world
    panel = ga.rpc('group_admin_panel', grp=gid).json()
    assert panel['rights'] == DEFAULTS
    assert panel['join_approval'] is False and panel['events_need_approval'] is False
    assert panel['me']['role'] == 'creator' and panel['me']['manage'] and panel['me']['owner'] and panel['me']['rules']
    roles = {m['id']: m['role'] for m in panel['members']}
    assert roles == {ga.uid: 'creator', vip.uid: 'member', qa.uid: 'member'}
    mine = qa.rpc('group_admin_panel', grp=gid).json()['me']
    assert mine['role'] == 'member' and not mine['manage'] and not mine['rules'] and not mine['owner']
    assert mine['write'] and mine['invite'] and mine['events'] and mine['announce']
    assert not mine['pin'] and not mine['edit'] and not mine['remove']
    assert gb.rpc('group_admin_panel', grp=gid).json() is None  # pas dedans : rien
    # Anciennes colonnes gardées en accord (anciennes apps).
    assert sql_test(f"select members_invite, everyone_tag from public.member_groups where id = '{gid}'") == [
        {'members_invite': True, 'everyone_tag': 'all'}]


def test_only_the_admin_and_co_admins_change_rights_and_roles(world):
    _, ga, _, vip, qa, gid = world
    assert qa.rpc('set_group_right', grp=gid, k='write', level='admins').status_code in (401, 403)
    assert qa.rpc('set_group_role', grp=gid, member=vip.uid, role='coadmin').status_code in (401, 403)
    httpx.patch(f'{TEST_URL}/rest/v1/member_groups?id=eq.{gid}', headers=qa.headers, json={'who_write': 'admins'}, timeout=30)
    assert sql_test(f"select who_write from public.member_groups where id = '{gid}'") == [{'who_write': 'members'}]
    assert ga.rpc('set_group_role', grp=gid, member=vip.uid, role='coadmin').status_code in (200, 204)
    try:
        me = vip.rpc('group_my_rights', grp=gid).json()
        assert me['role'] == 'coadmin' and me['manage'] and me['rules'] and not me['owner']
        right(vip, gid, 'pin', 'staff')  # un co-admin règle le groupe…
        assert vip.rpc('set_group_role', grp=gid, member=qa.uid, role='organizer').status_code in (200, 204)
        assert qa.rpc('group_my_rights', grp=gid).json()['role'] == 'organizer'
        # … mais ne touche jamais au créateur, ne supprime ni ne transmet le groupe.
        assert vip.rpc('set_group_role', grp=gid, member=ga.uid, role='member').status_code in (401, 403)
        assert vip.rpc('transfer_group', grp=gid, member=qa.uid).status_code in (401, 403)
        httpx.delete(f'{TEST_URL}/rest/v1/member_groups?id=eq.{gid}', headers=vip.headers, timeout=30)
        assert sql_test(f"select count(*) n from public.member_groups where id = '{gid}'") == [{'n': 1}]
    finally:
        ga.rpc('set_group_role', grp=gid, member=qa.uid, role='member')
        ga.rpc('set_group_role', grp=gid, member=vip.uid, role='member')
        right(ga, gid, 'pin', 'admins')
    assert qa.rpc('group_my_rights', grp=gid).json()['role'] == 'member'


def test_write_and_pin_are_kept_by_the_base(world):
    _, ga, _, _, qa, gid = world
    right(ga, gid, 'write', 'admins')
    try:
        assert send(qa, gid, 'coucou').status_code in (401, 403)
        assert qa.rpc('group_my_rights', grp=gid).json()['write'] is False
        mine = send(ga, gid, 'Seuls les admins écrivent ici')
        assert mine.status_code == 201, mine.text
    finally:
        right(ga, gid, 'write', 'members')
    msg = send(qa, gid, 'à épingler')
    assert msg.status_code == 201, msg.text
    mid = msg.json()[0]['id']
    assert qa.rpc('pin_group_message', msg=mid, pin=True).status_code in (401, 403)
    right(ga, gid, 'pin', 'members')
    try:
        assert qa.rpc('pin_group_message', msg=mid, pin=True).status_code in (200, 204)
    finally:
        right(ga, gid, 'pin', 'admins')


def test_everyone_tag_follows_the_announce_right(world):
    _, ga, _, _, qa, gid = world
    right(ga, gid, 'announce', 'staff')
    try:
        assert sql_test(f"select everyone_tag from public.member_groups where id = '{gid}'") == [{'everyone_tag': 'staff'}]
        r = send(qa, gid, '@tout ce soir ?', mention_all=True)
        assert r.status_code == 201 and r.json()[0]['mention_all'] is False, r.text
        r = send(qa, gid, '@annonce on se voit', mention_all=True)
        assert r.json()[0]['announcement'] is False
    finally:
        right(ga, gid, 'announce', 'members')
    assert send(qa, gid, '@tout ce soir ?', mention_all=True).json()[0]['mention_all'] is True
    # Ancienne app : set_group_everyone_tag change aussi le droit.
    assert ga.rpc('set_group_everyone_tag', grp=gid, who='staff').status_code in (200, 204)
    assert ga.rpc('group_admin_panel', grp=gid).json()['rights']['announce'] == 'staff'
    assert ga.rpc('set_group_everyone_tag', grp=gid, who='all').status_code in (200, 204)


def test_name_and_photo_need_the_edit_right(world):
    _, ga, _, _, qa, gid = world
    assert qa.rpc('update_group_look', grp=gid, group_name='Pirates', group_emoji='🎸', group_color='sky').status_code in (401, 403)
    right(ga, gid, 'edit', 'members')
    try:
        r = qa.rpc('update_group_look', grp=gid, group_name='Test réglages admin', group_emoji='🎸', group_color='sky')
        assert r.status_code in (200, 204), r.text
        assert sql_test(f"select emoji, color from public.member_groups where id = '{gid}'") == [{'emoji': '🎸', 'color': 'sky'}]
    finally:
        right(ga, gid, 'edit', 'admins')


def test_remove_a_member_follows_the_remove_right_and_never_the_creator(world):
    _, ga, _, vip, qa, gid = world

    def remove(s: Session, who: str) -> list:
        return httpx.delete(f'{TEST_URL}/rest/v1/member_group_members?group_id=eq.{gid}&user_id=eq.{who}', timeout=30,
                            headers={**s.headers, 'Prefer': 'return=representation'}).json()

    assert remove(qa, vip.uid) == []  # simple membre : non (par défaut, admins seulement)
    right(ga, gid, 'remove', 'members')
    try:
        assert remove(qa, ga.uid) == []  # jamais le créateur
        ga.rpc('set_group_role', grp=gid, member=vip.uid, role='organizer')
        assert remove(qa, vip.uid) == []  # un membre ne retire qu'un simple membre
        ga.rpc('set_group_role', grp=gid, member=vip.uid, role='member')
        assert len(remove(qa, vip.uid)) == 1
    finally:
        right(ga, gid, 'remove', 'admins')
        sql_test(f"insert into public.member_group_members (group_id, user_id) values ('{gid}', '{vip.uid}') on conflict do nothing")


def test_creating_an_event_for_the_group_follows_the_events_right(world):
    admin, ga, _, vip, _, gid = world
    ev = httpx.post(f'{TEST_URL}/rest/v1/events', timeout=30, headers={**vip.headers, 'Prefer': 'return=representation'},
                    json={'title': 'Test droit événement de groupe', 'status': 'draft', 'visibility': 'invited', 'notify_on_publish': False})
    assert ev.status_code == 201, ev.text
    eid = ev.json()[0]['id']
    try:
        right(ga, gid, 'events', 'admins')
        r = httpx.post(f'{TEST_URL}/rest/v1/event_groups', headers=vip.headers, timeout=30, json={'event_id': eid, 'group_id': gid})
        assert r.status_code in (401, 403) and 'co-admins' in r.text, r.text
        assert vip.rpc('group_my_rights', grp=gid).json()['events'] is False
        right(ga, gid, 'events', 'members')
        r = httpx.post(f'{TEST_URL}/rest/v1/event_groups', headers=vip.headers, timeout=30, json={'event_id': eid, 'group_id': gid})
        assert r.status_code == 201, r.text
    finally:
        right(ga, gid, 'events', 'members')
        httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{eid}', headers=admin.headers, timeout=30)


def test_invite_right_keeps_the_old_setting_in_step(world):
    _, ga, gb, vip, _, gid = world
    right(ga, gid, 'invite', 'admins')
    try:
        assert sql_test(f"select members_invite from public.member_groups where id = '{gid}'") == [{'members_invite': False}]
        assert vip.rpc('group_invite_link', grp=gid, renew=False).status_code in (401, 403)
        ga.rpc('set_group_role', grp=gid, member=vip.uid, role='organizer')
        assert vip.rpc('group_invite_link', grp=gid, renew=False).status_code in (401, 403)  # admins seulement
    finally:
        ga.rpc('set_group_role', grp=gid, member=vip.uid, role='member')
        assert ga.rpc('set_group_members_invite', grp=gid, allowed=True).status_code in (200, 204)  # ancienne app
    assert ga.rpc('group_admin_panel', grp=gid).json()['rights']['invite'] == 'members'


def test_accept_each_new_member(world):
    _, ga, gb, _, qa, gid = world
    assert qa.rpc('set_group_join_approval', grp=gid, approval=True).status_code in (401, 403)
    assert ga.rpc('set_group_join_approval', grp=gid, approval=True).status_code in (200, 204)
    try:
        token = ga.rpc('group_invite_link', grp=gid, renew=False).json()
        assert gb.rpc('group_invite_info', token=token).json()['approval'] is True
        assert gb.rpc('join_group_by_link', token=token).status_code == 200
        assert gb.rpc('group_invite_info', token=token).json()['requested'] is True
        assert sql_test(f"select count(*) n from public.member_group_members where group_id = '{gid}' and user_id = '{gb.uid}'") == [{'n': 0}]
        requests = ga.rpc('group_admin_panel', grp=gid).json()['requests']
        assert [r['id'] for r in requests] == [gb.uid]
        assert qa.rpc('group_admin_panel', grp=gid).json()['requests'] == []  # un simple membre ne les voit pas
        assert qa.rpc('decide_group_join', grp=gid, member=gb.uid, accept=True).status_code in (401, 403)
        assert ga.rpc('decide_group_join', grp=gid, member=gb.uid, accept=True).status_code in (200, 204)
        assert gb.rpc('group_my_rights', grp=gid).json()['role'] == 'member'
    finally:
        ga.rpc('set_group_join_approval', grp=gid, approval=False)
        sql_test(f"delete from public.member_group_members where group_id = '{gid}' and user_id = '{gb.uid}';"
                 f"delete from private.group_join_requests where group_id = '{gid}'")


def test_transfer_the_group(world):
    _, ga, _, vip, qa, gid = world
    assert qa.rpc('transfer_group', grp=gid, member=vip.uid).status_code in (401, 403)
    assert ga.rpc('transfer_group', grp=gid, member=vip.uid).status_code in (200, 204)
    try:
        assert vip.rpc('group_my_rights', grp=gid).json()['role'] == 'creator'
        assert ga.rpc('group_my_rights', grp=gid).json()['role'] == 'coadmin'  # l'ancien admin reste co-admin
    finally:
        assert vip.rpc('transfer_group', grp=gid, member=ga.uid).status_code in (200, 204)
        ga.rpc('set_group_role', grp=gid, member=vip.uid, role='member')
    assert ga.rpc('group_my_rights', grp=gid).json()['role'] == 'creator'


def test_vendredi_party_never_has_these_settings(world):
    admin = world[0]
    vp = sql_test("select id from public.member_groups where system_key = 'vip'")[0]['id']
    assert admin.rpc('set_group_right', grp=vp, k='write', level='admins').status_code in (401, 403)
    assert admin.rpc('set_group_join_approval', grp=vp, approval=True).status_code in (401, 403)
    assert admin.rpc('transfer_group', grp=vp, member=admin.uid).status_code in (401, 403)
    assert sql_test(f"select who_write, join_approval from public.member_groups where id = '{vp}'") == [
        {'who_write': 'members', 'join_approval': False}]
