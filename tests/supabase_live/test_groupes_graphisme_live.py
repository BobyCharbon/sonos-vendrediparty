"""Groupes : nouveau graphisme (17.11.2026, migration 20261117100000), sur la VRAIE base de test (jamais la prod) :
- emoji (liste fermée) et couleur (6 couleurs) du groupe, refusés hors liste ; « Vendredi Party » garde 🎉 lavande ;
- my_groups_overview : mes groupes, membres, prochain événement que JE peux voir ; my_chats porte emoji et couleur ;
- group_events : réservé aux membres du groupe (un autre compte n'y voit rien) ;
- group_invite_suggestions : seulement des personnes croisées à un événement, jamais déjà membres ; réservé à qui gère.
Événements de test sans notification (conftest)."""
import httpx
import pytest

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, VIP, complete_profile, create_event, make_vip, unmake_vip
from tests.supabase_live.test_groups_members_only_live import sql_test
from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark  # noqa: F401


def patch_group(s: Session, gid: str, **fields) -> httpx.Response:
    return httpx.patch(f'{TEST_URL}/rest/v1/member_groups?id=eq.{gid}', headers={**s.headers, 'Prefer': 'return=representation'},
                       json=fields, timeout=30)


@pytest.fixture(scope='module')
def world():
    admin, vip, ga = Session(ADMIN), Session(VIP), Session(GUEST_A)
    make_vip(admin, vip)
    complete_profile(ga, 'Guest A')
    r = httpx.post(f'{TEST_URL}/rest/v1/member_groups', timeout=30, headers={**vip.headers, 'Prefer': 'return=representation'},
                   json={'name': 'Test graphisme', 'emoji': '⚽', 'color': 'mint', 'created_by': vip.uid})
    assert r.status_code == 201, r.text
    gid = r.json()[0]['id']
    # Événement du groupe (l'admin publie sans validation ; les membres du groupe y sont invités par la base).
    event = create_event(admin, 'Test graphisme : match', visibility='invited')
    added = httpx.post(f'{TEST_URL}/rest/v1/event_groups', headers=admin.headers, timeout=30, json={'event_id': event, 'group_id': gid})
    assert added.status_code == 201, added.text
    # Le VIP croise l'admin à un événement de l'admin (réponse « Présent ») : l'admin devient une suggestion d'invitation.
    met = create_event(admin, 'Test graphisme : apéro')
    yes = httpx.post(f'{TEST_URL}/rest/v1/rsvps', headers=vip.headers, timeout=30, json={'event_id': met, 'user_id': vip.uid, 'status': 'yes'})
    assert yes.status_code == 201, yes.text
    yield admin, vip, ga, gid, event
    for e in (event, met):
        httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{e}', headers=admin.headers, timeout=30)
    httpx.delete(f'{TEST_URL}/rest/v1/member_groups?id=eq.{gid}', headers=vip.headers, timeout=30)
    unmake_vip(admin, vip)


def test_a_group_carries_an_emoji_and_a_color_from_closed_lists(world):
    _, vip, _, gid, _ = world
    mine = next(g for g in vip.rpc('my_groups_overview').json() if g['id'] == gid)
    assert (mine['emoji'], mine['color'], mine['member'], mine['manage'], mine['creator']) == ('⚽', 'mint', True, True, True)
    assert mine['members'] >= 1 and any(f['id'] == vip.uid for f in mine['faces'])
    assert patch_group(vip, gid, emoji='💣').status_code == 400  # hors de la liste fermée
    assert patch_group(vip, gid, color='red').status_code == 400
    ok = patch_group(vip, gid, emoji='🍕', color='lemon')
    assert ok.status_code == 200 and ok.json()[0]['emoji'] == '🍕' and ok.json()[0]['color'] == 'lemon', ok.text
    chat = next(c for c in vip.rpc('my_chats').json() if c['id'] == gid)
    assert (chat['emoji'], chat['color']) == ('🍕', 'lemon')  # lignes de Discussions de l'app iPhone


def test_vendredi_party_keeps_its_fixed_look():
    # Même la base (fonctions, admin) ne peut pas le changer : le déclencheur remet 🎉 lavande (mise à jour sans effet).
    rows = sql_test("""
    with u as (update public.member_groups set emoji = '⚽', color = 'mint' where system_key = 'vip' returning emoji, color)
    select emoji, color from u""")
    assert rows == [{'emoji': '🎉', 'color': 'lavender'}], rows


def test_group_events_are_for_the_group_members_only(world):
    _, vip, ga, gid, event = world
    assert [e['id'] for e in vip.rpc('group_events', grp=gid).json()] == [event]
    nxt = next(g for g in vip.rpc('my_groups_overview').json() if g['id'] == gid)['next_event']
    assert nxt and nxt['id'] == event and nxt['title'] == 'Test graphisme : match'
    assert ga.rpc('group_events', grp=gid).json() == []  # pas membre : rien
    assert all(g['id'] != gid for g in ga.rpc('my_groups_overview').json())


def test_invite_suggestions_are_people_met_at_events_never_the_whole_site(world):
    admin, vip, ga, gid, _ = world
    refused = ga.rpc('group_invite_suggestions', grp=gid)
    assert refused.status_code in (401, 403), refused.text  # seul qui gère le groupe invite
    people = vip.rpc('group_invite_suggestions', grp=gid).json()
    ids = {p['id'] for p in people}
    assert admin.uid in ids and vip.uid not in ids
    assert next(p for p in people if p['id'] == admin.uid)['together'] >= 1
    # Chaque suggestion a VRAIMENT croisé le VIP (présent / peut-être, organisateur ou créateur d'un même événement publié).
    met = sql_test(f"""
    with mine as (select id from private.met_events('{vip.uid}') m(id))
    select distinct p.id::text as id from public.profiles p
    where exists (select 1 from mine join public.events e on e.id = mine.id and e.status = 'published'
                  where e.id in (select private.met_events(p.id)))""")
    assert ids <= {r['id'] for r in met}, ids - {r['id'] for r in met}
    total = sql_test("select count(*)::int as n from public.profiles where status = 'active'")[0]['n']
    assert len(ids) < total  # jamais tout le site
