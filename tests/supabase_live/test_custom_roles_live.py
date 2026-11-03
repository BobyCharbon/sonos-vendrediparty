"""Rôles personnalisés et droit « Scanner les billets », sur la VRAIE base de test (jamais la prod) : créer, renommer,
réordonner (le rang suit l'ordre), supprimer en réaffectant, garde-fous (en dessous de soi seulement, Admin en haut,
Guest en bas, rôles de base non supprimables, droits qu'on a soi-même), et un compte au droit tickets.scan scanne
à l'entrée d'un événement qu'il n'organise pas.
Base de test : le rôle Admin y a roles.manage (donné une fois pour ces tests ; en prod, seul Root l'a).
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_custom_roles_live.py -q"""
import time

import httpx
import pytest

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, GUEST_B, complete_profile, create_event
from tests.supabase_live.test_event_tickets_live import answer
from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark  # noqa: F401

BUILTIN = ['guest', 'guestplus', 'basic', 'member', 'organizer', 'coadmin', 'admin']


def roles(s: Session) -> list[dict]:
    r = s.get('roles?select=key,label,color,icon,rank,builtin&order=rank')
    assert r.status_code == 200, r.text
    return r.json()


def keys(s: Session) -> list[str]:
    return [r['key'] for r in roles(s)]


def set_role(admin: Session, who: Session, role: str) -> httpx.Response:
    return httpx.patch(f'{TEST_URL}/rest/v1/profiles?id=eq.{who.uid}', headers=admin.headers, json={'role': role}, timeout=30)


def audit(admin: Session, action: str) -> list[dict]:
    return [e for e in admin.rpc('admin_member_audit', lim=50).json() if e['action'] == action]


@pytest.fixture(scope='module')
def people():
    admin, a, b = Session(ADMIN), Session(GUEST_A), Session(GUEST_B)
    for k in keys(admin):  # restes d'un passage interrompu
        if k.startswith('r_'):
            admin.rpc('delete_role', role_key=k, move_to='guest')
    yield admin, a, b
    for who in (a, b):
        set_role(admin, who, 'guest')
    for k in keys(admin):
        if k.startswith('r_'):
            admin.rpc('delete_role', role_key=k, move_to='guest')


@pytest.fixture()
def custom(people):
    """Un rôle personnalisé tout neuf, supprimé à la fin du test (ses comptes repassent Guest)."""
    admin = people[0]
    r = admin.rpc('create_role', role_label=f'Test videurs {time.time_ns() % 100000}', role_color='#12abef', role_icon='🎟️')
    assert r.status_code == 200, r.text
    key = r.json()
    yield key
    if key in keys(admin):
        assert admin.rpc('delete_role', role_key=key, move_to='guest').status_code in (200, 204)


def test_builtin_roles_are_a_table_in_the_old_order_and_ranks_follow_it(people):
    admin, a, _ = people
    rows = roles(a)  # lisible par tout compte connecté (noms des rôles dans l'app)
    assert [r['key'] for r in rows] == BUILTIN and all(r['builtin'] for r in rows)
    assert [r['rank'] for r in rows] == list(range(len(BUILTIN)))
    assert rows[3]['label'] == 'Membre VIP' and rows[-1]['label'] == 'Admin'
    by_key = {r['key']: r['rank'] for r in rows}
    assert admin.rpc('my_rank').json() == by_key['admin']
    assert a.rpc('my_rank').json() == by_key['guest']
    assert a.get('roles').status_code == 200 and httpx.post(f'{TEST_URL}/rest/v1/roles', headers=a.headers, timeout=30,
                                                            json={'key': 'hack', 'label': 'Hack', 'rank': 50}).status_code >= 400


def test_new_rights_are_in_the_catalog(people):
    admin = people[0]
    rows = {p['key']: p for p in admin.get('permissions?select=key,grp,label').json()}
    assert rows['tickets.scan']['label'] == 'Scanner les billets' and rows['tickets.pay']['label'] == 'Confirmer les paiements'
    assert rows['roles.delete']['label'] == 'Supprimer un rôle' and rows['roles.delete']['grp'] == rows['roles.manage']['grp']


def test_a_guest_cannot_manage_roles(people):
    _, a, _ = people
    for name, args in (('roles_overview', {}), ('create_role', {'role_label': 'Pirates'}),
                       ('reorder_roles', {'role_keys': BUILTIN}), ('delete_role', {'role_key': 'basic'}),
                       ('update_role', {'role_key': 'basic', 'role_label': 'Pirates'})):
        r = a.rpc(name, **args)
        assert r.status_code >= 400 and 'forbidden' in r.text, (name, r.text)


def test_create_a_role_just_above_guest_with_colour_and_icon(people, custom):
    admin = people[0]
    rows = roles(admin)
    assert [r['key'] for r in rows][:2] == ['guest', custom]
    mine = rows[1]
    assert mine['color'] == '#12ABEF' and mine['icon'] == '🎟️' and not mine['builtin']
    assert [r['rank'] for r in rows] == list(range(len(rows)))
    overview = {r['key']: r for r in admin.rpc('roles_overview').json()}
    assert overview[custom]['members'] == 0 and overview[custom]['editable'] and not overview['admin']['editable']
    assert admin.rpc('create_role', role_label=f"  {mine['label'].upper()} ").status_code >= 400  # même nom
    assert 'role_color' in admin.rpc('create_role', role_label='Couleur fausse', role_color='rouge').text
    assert 'role_label' in admin.rpc('create_role', role_label='   ').text
    assert any(e['details']['key'] == custom for e in audit(admin, 'role.created'))


def test_rename_and_permissions_of_a_custom_role(people, custom):
    admin, a, _ = people
    assert admin.rpc('update_role', role_key=custom, role_label='Videurs', role_color=None, role_icon='🚪').status_code in (200, 204)
    row = next(r for r in roles(admin) if r['key'] == custom)
    assert row['label'] == 'Videurs' and row['icon'] == '🚪' and row['color'] is None
    assert any(e['details']['key'] == custom and e['details']['to'] == 'Videurs' for e in audit(admin, 'role.updated'))
    assert admin.rpc('set_role_permission', target=custom, perm='tickets.scan', granted=True).status_code in (200, 204)
    grants = admin.get(f'role_permissions?select=perm&role=eq.{custom}').json()
    assert grants == [{'perm': 'tickets.scan'}]
    # Admin et Root restent hors d'atteinte : rang égal ou supérieur.
    assert 'forbidden' in admin.rpc('update_role', role_key='admin', role_label='Chef').text
    assert 'forbidden' in admin.rpc('set_role_permission', target='admin', perm='tickets.scan', granted=False).text
    assert 'role_unknown' in admin.rpc('set_role_permission', target='nexiste_pas', perm='tickets.scan', granted=True).text


def test_scan_and_payment_are_two_rights_on_any_event_entrance(people, custom):
    """« Scanner les billets » (scan, arrivée) et « Confirmer les paiements » (payé, Reçu) : deux droits séparés."""
    admin, a, b = people
    complete_profile(b, 'Guest B')
    eid = create_event(admin, 'Test droit scanner', public_link=True, price_chf=15)
    answer(a, eid, 'yes')
    try:
        refused = b.rpc('check_in_ticket', e=eid, scanned='ABCDEF')
        assert refused.status_code >= 400 and 'organisateurs' in refused.text
        assert b.rpc('event_checkins', e=eid).status_code >= 400
        assert set_role(admin, b, custom).status_code in (200, 204)
        # Paiements seulement : la liste de l'entrée et « payé », pas le scan.
        assert admin.rpc('set_role_permission', target=custom, perm='tickets.pay', granted=True).status_code in (200, 204)
        assert 'paiements' not in b.rpc('check_in_ticket', e=eid, scanned='ABCDEF').text
        assert b.rpc('check_in_ticket', e=eid, scanned='ABCDEF').status_code >= 400
        assert b.rpc('set_ticket_arrival', e=eid, member=a.uid, arrived=True).status_code >= 400
        assert b.rpc('event_checkins', e=eid).status_code == 200
        paid = b.rpc('set_ticket_paid', e=eid, member=a.uid, is_paid=True)
        assert paid.status_code == 200 and paid.json()['paid'] is True, paid.text
        assert b.rpc('confirm_ticket_payment', e=eid, member=a.uid, received=False).json()['paid'] is False
        assert b.rpc('event_pay_info', e=eid).json()['amount'] == 15
        # Scan seulement : arrivée oui, « payé » non.
        assert admin.rpc('set_role_permission', target=custom, perm='tickets.pay', granted=False).status_code in (200, 204)
        assert admin.rpc('set_role_permission', target=custom, perm='tickets.scan', granted=True).status_code in (200, 204)
        assert 'tickets.scan' in b.rpc('my_permissions').json() and 'tickets.pay' not in b.rpc('my_permissions').json()
        assert b.rpc('check_in_ticket', e=eid, scanned='ABCDEF').json() == {'result': 'unknown'}
        assert b.rpc('set_ticket_arrival', e=eid, member=a.uid, arrived=True).json()['checked_in_at']
        assert b.rpc('event_checkins', e=eid).status_code == 200
        no_pay = b.rpc('set_ticket_paid', e=eid, member=a.uid, is_paid=True)
        assert no_pay.status_code >= 400 and 'paiements' in no_pay.text
        assert 'paiements' in b.rpc('confirm_ticket_payment', e=eid, member=a.uid, received=True).text
    finally:
        httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{eid}', headers=admin.headers, timeout=30)
        set_role(admin, b, 'guest')


def test_reorder_changes_the_hierarchy_and_the_vip_group(people, custom):
    admin, a, _ = people
    complete_profile(a, 'Guest A')
    assert set_role(admin, a, custom).status_code in (200, 204)
    vip = admin.get('member_groups?select=id,member_group_members(user_id)&system_key=eq.vip').json()[0]
    assert a.uid not in {m['user_id'] for m in vip['member_group_members']}
    order = keys(admin)
    moved = [k for k in order if k != custom]
    moved.insert(moved.index('member') + 1, custom)  # juste au-dessus de Membre VIP
    r = admin.rpc('reorder_roles', role_keys=moved)
    assert r.status_code in (200, 204), r.text
    assert keys(admin) == moved
    assert a.rpc('my_rank').json() == moved.index(custom)
    rows = admin.get(f'member_group_members?select=user_id&group_id=eq.{vip["id"]}').json()
    assert a.uid in {m['user_id'] for m in rows}  # au-dessus de Membre VIP : dans Vendredi Party
    assert any(e['details']['order'] == moved for e in audit(admin, 'roles.reordered'))
    # Remis en bas : sort du groupe.
    assert admin.rpc('reorder_roles', role_keys=order).status_code in (200, 204)
    group = admin.get('member_groups?select=member_group_members(user_id)&system_key=eq.vip').json()[0]
    assert a.uid not in {m['user_id'] for m in group['member_group_members']}


def test_reorder_guards(people, custom):
    admin = people[0]
    order = keys(admin)
    swapped = order[:]
    swapped[0], swapped[1] = swapped[1], swapped[0]
    assert 'role_order' in admin.rpc('reorder_roles', role_keys=swapped).text  # Guest reste en bas
    top = order[:-2] + [order[-1], order[-2]]
    assert 'role_order' in admin.rpc('reorder_roles', role_keys=top).text  # Admin reste en haut
    assert 'role_order' in admin.rpc('reorder_roles', role_keys=order[:-1]).text  # liste incomplète
    assert 'role_order' in admin.rpc('reorder_roles', role_keys=order[:-1] + ['guest']).text  # doublon
    assert keys(admin) == order


def test_a_manager_below_admin_only_touches_roles_below_its_own(people, custom):
    """Un compte Organisateur avec roles.manage (donné par l'Admin) : range et crée sous lui, jamais au-dessus, ni le sien."""
    admin, a, _ = people
    complete_profile(a, 'Guest A')
    assert admin.rpc('set_role_permission', target='organizer', perm='roles.manage', granted=True).status_code in (200, 204)
    try:
        assert set_role(admin, a, 'organizer').status_code in (200, 204)
        order = keys(a)
        mine = order.index('organizer')
        # Le sien et au-dessus : intouchables.
        assert 'forbidden' in a.rpc('update_role', role_key='organizer', role_label='Chef').text
        assert 'forbidden' in a.rpc('set_role_permission', target='organizer', perm='roles.manage', granted=False).text
        assert 'forbidden' in a.rpc('update_role', role_key='coadmin', role_label='Chef').text
        swap = order[:]
        swap[mine], swap[mine + 1] = swap[mine + 1], swap[mine]
        assert 'forbidden' in a.rpc('reorder_roles', role_keys=swap).text
        above = [k for k in order if k != custom]
        above.insert(above.index('coadmin'), custom)  # glisser un rôle au-dessus de soi
        assert 'forbidden' in a.rpc('reorder_roles', role_keys=above).text
        # En dessous : permis, mais seulement des droits qu'il a lui-même.
        below = [k for k in order if k != custom]
        below.insert(below.index('member'), custom)
        assert a.rpc('reorder_roles', role_keys=below).status_code in (200, 204)
        assert 'tu n' in a.rpc('set_role_permission', target=custom, perm='party.settings', granted=True).text
        assert a.rpc('set_role_permission', target=custom, perm='events.create', granted=True).status_code in (200, 204)
        copied = a.rpc('create_role', role_label='Copie orga', copy_from='coadmin')  # copie de droits : seulement les siens
        assert copied.status_code == 200, copied.text
        mine_perms = set(a.rpc('my_permissions').json())
        got = {g['perm'] for g in a.get(f'role_permissions?select=perm&role=eq.{copied.json()}').json()}
        assert got and got <= mine_perms and 'members.ban' not in got
        # Supprimer : il faut en plus « Supprimer un rôle ».
        refused = a.rpc('delete_role', role_key=copied.json())
        assert refused.status_code >= 400 and 'Supprimer un rôle' in refused.text
        assert admin.rpc('set_role_permission', target='organizer', perm='roles.delete', granted=True).status_code in (200, 204)
        assert a.rpc('delete_role', role_key=copied.json()).status_code in (200, 204)
    finally:
        set_role(admin, a, 'guest')
        admin.rpc('set_role_permission', target='organizer', perm='roles.delete', granted=False)
        admin.rpc('set_role_permission', target='organizer', perm='roles.manage', granted=False)


def test_delete_a_role_moves_its_members_and_compacts_ranks(people, custom):
    admin, a, _ = people
    complete_profile(a, 'Guest A')
    assert set_role(admin, a, custom).status_code in (200, 204)
    assert 'role_not_empty' in admin.rpc('delete_role', role_key=custom).text
    assert 'forbidden' in admin.rpc('delete_role', role_key=custom, move_to='admin').text  # pas au-dessus de soi
    assert 'role_builtin' in admin.rpc('delete_role', role_key='basic').text
    assert 'forbidden' in admin.rpc('delete_role', role_key='admin').text
    r = admin.rpc('delete_role', role_key=custom, move_to='basic')
    assert r.status_code in (200, 204), r.text
    rows = roles(admin)
    assert custom not in [x['key'] for x in rows] and [x['rank'] for x in rows] == list(range(len(rows)))
    assert admin.get(f'profiles?select=role&id=eq.{a.uid}').json() == [{'role': 'basic'}]
    assert any(e['details']['key'] == custom and e['details']['moved'] == 1 for e in audit(admin, 'role.deleted'))
    set_role(admin, a, 'guest')


def test_a_custom_role_below_vip_can_ask_to_join_and_an_admin_cannot_promote_to_admin(people, custom):
    admin, a, _ = people
    complete_profile(a, 'Guest A')
    assert set_role(admin, a, custom).status_code in (200, 204)
    try:
        assert a.rpc('request_join', note='Je veux venir').status_code in (200, 204)
        assert a.rpc('cancel_join_request').status_code in (200, 204)
        assert set_role(admin, a, 'admin').status_code >= 400  # rang égal au sien : refusé
        card = a.rpc('member_card', target=a.uid).json()
        assert card['role'] == custom and card['role_label'].startswith('Test videurs') and card['role_color'] == '#12ABEF'
    finally:
        set_role(admin, a, 'guest')
