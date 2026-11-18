"""Groupes en natif dans l'app iPhone (18.11, « tout en natif ») sur la VRAIE base de TEST (jamais la prod) : le relais
POST /api/account/chats/rpc + app/group_pages.py créent, montrent, modifient, invitent, retirent, posent une photo,
font quitter et suppriment un groupe avec la session du membre — la base décide (RLS, gardes, filtre, Vendredi Party)."""
import base64

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import accounts as accounts_mod, chat_rpc, group_admin as ga, group_chats as gc
from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, GUEST_B
from tests.supabase_live.test_member_admin_live import KEY_FILE, TEST_URL, Session, pytestmark  # noqa: F401

# Petit JPEG valide (2 × 2) : la garde de la photo exige un vrai fichier dans group-photos/<groupe>/.
JPEG = base64.b64decode('/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAoHBwgHBgoICAgLCgoLDhgQDg0NDh0VFhEYIx8lJCIfIiEmKzcvJik0KSEiMEExNDk7Pj4+JS5ESUM8SDc9Pjv/2wBDAQoLCw4NDhwQEBw7KCIoOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozv/wAARCAACAAIDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwC1RRRWx+hH/9k=')


@pytest.fixture(scope='module')
def relay():
    mp = pytest.MonkeyPatch()
    key = KEY_FILE.read_text().strip()
    for mod in (accounts_mod, ga, gc, chat_rpc):
        mp.setattr(mod, 'SUPABASE_URL', TEST_URL, raising=False)
    mp.setattr(accounts_mod, 'SUPABASE_ANON_KEY', key)
    a, b = Session(GUEST_A), Session(GUEST_B)
    admin = ga.GroupAdmin(accounts_mod.Accounts(b'secret', httpx.Client(timeout=30)))
    app = FastAPI()
    app.include_router(chat_rpc.chat_rpc_router(gc.GroupChats(admin), lambda t: f'https://party.test/events/group-invite/{t}'))
    token = lambda s: s.headers['Authorization'].removeprefix('Bearer ')  # noqa: E731
    created = []
    yield TestClient(app), token(a), token(b), b.uid, created
    for group in created:
        httpx.delete(f'{TEST_URL}/rest/v1/member_groups?id=eq.{group}', headers=a.headers, timeout=30)
    mp.undo()


def call(client, token, fn, **args):
    return client.post('/api/account/chats/rpc', json={'token': token, 'fn': fn, 'args': args})


def ok(r):
    assert r.status_code == 200, r.text
    return r.json()['result']


def test_a_native_group_from_creation_to_deletion(relay):
    client, ta, tb, b_uid, created = relay
    group = ok(call(client, ta, 'group_create', name='  Test   natif ', emoji='🎸', color='sky'))['group']
    created.append(group)
    page = ok(call(client, ta, 'group_page', grp=group))
    assert page['group']['name'] == 'Test natif' and page['group']['emoji'] == '🎸' and page['group']['color'] == 'sky'
    assert page['member'] and page['manage'] and page['creator'] and page['can_set_rules'] and not page['group']['system']
    assert [m['me'] for m in page['members']] == [True]  # le créateur en fait partie d'office

    # Modifier : nom filtré par la base, emoji et couleur des listes fermées.
    ok(call(client, ta, 'group_update', grp=group, name='Test natif bis', emoji='🍕', color='coral'))
    assert ok(call(client, ta, 'group_page', grp=group))['group']['name'] == 'Test natif bis'

    # Inviter : le lien réutilisable (adresse publique), un lien unique et sa liste, puis Testeur 2 par invitation.
    link = ok(call(client, ta, 'group_link', grp=group))
    assert link['url'] == f"https://party.test/events/group-invite/{link['token']}"
    single = ok(call(client, ta, 'group_single_link', grp=group))
    assert any(l['token'] == single['token'] and l['status'] == 'pending' for l in ok(call(client, ta, 'group_links', grp=group)))
    ok(call(client, ta, 'revoke_invite_link', tok=single['token']))
    assert isinstance(ok(call(client, ta, 'group_invite_suggestions', grp=group)), list)
    invited = call(client, ta, 'invite_to_group', grp=group, member=b_uid, phone=None)
    if invited.status_code == 200:
        home_b = ok(call(client, tb, 'groups_home'))
        invitation = next(i for i in home_b['invitations'] if i['group_id'] == group)
        ok(call(client, tb, 'answer_group_invitation', inv=invitation['id'], accept=True))
    else:  # la base n'invite que les personnes déjà en lien direct (dm_link) : son refus garde son code et sa phrase
        assert invited.status_code == 403 and invited.json()['code'] == 'link_required', invited.text
        httpx.post(f'{TEST_URL}/rest/v1/member_group_members', timeout=30, json={'group_id': group, 'user_id': b_uid},
                   headers={'apikey': KEY_FILE.read_text().strip(), 'Authorization': f'Bearer {ta}', 'Content-Type': 'application/json'})

    # Testeur 2, simple membre : il voit la page sans la gérer, ne la renomme pas, montre son numéro et peut quitter.
    page_b = ok(call(client, tb, 'group_page', grp=group))
    assert page_b['member'] and not page_b['manage'] and not page_b['can_set_rules']
    assert {m['name'] for m in page_b['members']} >= {'Testeur 1', 'Testeur 2'}
    assert call(client, tb, 'group_update', grp=group, name='Pirate', emoji='🎸', color='sky').json()['code'] == 'forbidden'
    assert call(client, tb, 'group_remove_member', grp=group, member=page['me']).json()['code'] == 'forbidden'
    ok(call(client, tb, 'set_group_phone_share', grp=group, visible=True))
    assert ok(call(client, tb, 'group_page', grp=group))['phone_shared']

    # Photo du groupe : déposée par le serveur, posée, signée ; un simple membre ne la change pas ; puis retirée.
    r = client.post('/api/account/chats/group-photo', json={'token': ta, 'group_id': group, 'photo': base64.b64encode(JPEG).decode()})
    assert r.status_code == 200, r.text
    signed = ok(call(client, tb, 'group_page', grp=group))['group']['photo']
    assert signed.startswith(TEST_URL) and httpx.get(signed, timeout=30).status_code == 200
    r = client.post('/api/account/chats/group-photo', json={'token': tb, 'group_id': group, 'photo': base64.b64encode(JPEG).decode()})
    assert r.status_code == 403
    ok(call(client, ta, 'group_photo_remove', grp=group))
    assert ok(call(client, ta, 'group_page', grp=group))['group']['photo'] is None

    # Règles des événements (créateur), retirer puis quitter, supprimer.
    ok(call(client, ta, 'set_group_event_rules', grp=group, need_approval=True, mode='free'))
    rules = ok(call(client, ta, 'group_page', grp=group))['group']
    assert rules['events_need_approval'] and rules['announce_mode'] == 'free'
    ok(call(client, tb, 'group_leave', grp=group))  # (le créateur, lui, n'a pas « Quitter » : il supprime son groupe)
    assert call(client, tb, 'group_page', grp=group).json()['code'] == 'not_found'
    ok(call(client, ta, 'group_delete', grp=group))
    created.remove(group)
    assert call(client, ta, 'group_page', grp=group).json()['code'] == 'not_found'


def test_members_vendredi_party_is_never_renamed_left_nor_given_a_photo(relay):
    client = relay[0]
    ta = Session(ADMIN).headers['Authorization'].removeprefix('Bearer ')  # Admin de test : dans Membres Vendredi Party
    home = ok(call(client, ta, 'groups_home'))
    vp = next((g for g in home['groups'] if g['system']), None)
    if vp is None:
        pytest.skip("L'Admin de test n'est pas dans Membres Vendredi Party sur la base de test")
    page = ok(call(client, ta, 'group_page', grp=vp['id']))
    assert page['group']['system'] and page['group']['photo'] is None and not page['manage']
    assert call(client, ta, 'group_update', grp=vp['id'], name='Pirate', emoji='🎸', color='sky').json()['code'] == 'forbidden'
    assert call(client, ta, 'group_leave', grp=vp['id']).json()['code'] == 'forbidden'
    r = client.post('/api/account/chats/group-photo', json={'token': ta, 'group_id': vp['id'], 'photo': base64.b64encode(JPEG).decode()})
    assert r.status_code == 403
