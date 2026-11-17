"""Agenda (17.11.2026, migration 20261117140000) sur la VRAIE base de TEST, comptes de test à code fixe :
rendez-vous à soi, partage des dispos groupe par groupe (« Qui est libre ? »), liens publics, demandes de rendez-vous
(anti-abus, filtre, accepter / refuser / signaler / bloquer, annuler et effacer par l'inconnu), effacements planifiés.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_agenda_live.py -q"""
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
import pytest

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, GUEST_B, complete_profile
from tests.supabase_live.test_member_admin_live import KEY_FILE, TEST_URL, Session, pytestmark  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql

SWISS = ZoneInfo('Europe/Zurich')
WEEKDAYS_ALL = {'days': [1, 2, 3, 4, 5, 6, 7], 'from': '08:00', 'to': '20:00'}


def anon(name: str, **args) -> httpx.Response:
    """Appel sans compte (l'inconnu de la page publique, ou le serveur avec la clé publique)."""
    key = KEY_FILE.read_text().strip()
    return httpx.post(f'{TEST_URL}/rest/v1/rpc/{name}', headers={'apikey': key, 'Content-Type': 'application/json'},
                      json=args, timeout=30)


def ok(r: httpx.Response):
    assert r.status_code in (200, 204), r.text
    return r.json() if r.content else None


def refused(r: httpx.Response, code: str) -> str:
    assert r.status_code >= 400, r.text
    message = r.json().get('message', '')
    assert message.startswith(code + ':'), message
    return message


def at(r) -> datetime:
    return datetime.fromisoformat(str(r).replace('Z', '+00:00'))


@pytest.fixture(scope='module')
def people():
    owner, friend, admin = Session(GUEST_A), Session(GUEST_B), Session(ADMIN)
    complete_profile(owner, 'Agenda Léa')
    complete_profile(friend, 'Agenda Marc')
    ok(owner.rpc('agenda_stop_sharing'))
    ok(friend.rpc('agenda_stop_sharing'))
    sql(f"delete from private.agenda_links where user_id in ('{owner.uid}', '{friend.uid}')")
    sql(f"delete from public.agenda_items where user_id in ('{owner.uid}', '{friend.uid}')")
    sql(f"delete from private.agenda_sender_blocks where owner_id = '{owner.uid}'")
    yield owner, friend, admin
    ok(owner.rpc('agenda_stop_sharing'))
    ok(friend.rpc('agenda_stop_sharing'))
    sql(f"delete from private.agenda_links where user_id in ('{owner.uid}', '{friend.uid}')")
    sql(f"delete from public.agenda_items where user_id in ('{owner.uid}', '{friend.uid}')")
    sql(f"delete from private.agenda_sender_blocks where owner_id = '{owner.uid}'")
    sql(f"delete from public.notifications where user_id = '{owner.uid}' and kind like 'booking%'")


@pytest.fixture(scope='module')
def group(people):
    owner, friend, _ = people
    r = httpx.post(f'{TEST_URL}/rest/v1/member_groups', headers={**owner.headers, 'Prefer': 'return=representation'},
                   json={'name': 'Agenda recette'}, timeout=30)
    assert r.status_code == 201, r.text
    gid = r.json()[0]['id']
    sql(f"insert into public.member_group_members (group_id, user_id) values ('{gid}', '{friend.uid}') on conflict do nothing")
    yield gid
    sql(f"delete from public.member_groups where id = '{gid}'")


def test_an_appointment_is_seen_by_its_owner_only_and_repeats_skip_a_date(people):
    owner, friend, _ = people
    start = datetime.now(SWISS).replace(hour=19, minute=0, second=0, microsecond=0) + timedelta(days=2)
    item = ok(owner.rpc('agenda_item_save', item={'title': 'Badminton', 'starts_at': start.isoformat(),
                                                   'ends_at': (start + timedelta(hours=1)).isoformat(), 'repeat': 'weekly'}))
    cals = ok(owner.rpc('agenda_calendars_list'))
    assert [c['kind'] for c in cals][:2] == ['party', 'personal'] and item['calendar_id'] == cals[1]['id']
    assert friend.get(f"agenda_items?id=eq.{item['id']}").json() == []           # RLS : à soi seul
    window = ok(owner.rpc('agenda_window', from_ts=datetime.now(timezone.utc).isoformat(),
                          to_ts=(datetime.now(timezone.utc) + timedelta(days=22)).isoformat()))
    dates = [at(i['starts_at']).astimezone(SWISS).date() for i in window['items'] if i['id'] == item['id']]
    assert len(dates) == 3 and dates[1] - dates[0] == timedelta(days=7)
    ok(owner.rpc('agenda_item_delete', id=item['id'], scope='one', occurrence=str(dates[1])))
    window = ok(owner.rpc('agenda_window', from_ts=datetime.now(timezone.utc).isoformat(),
                          to_ts=(datetime.now(timezone.utc) + timedelta(days=22)).isoformat()))
    assert [at(i['starts_at']).astimezone(SWISS).date() for i in window['items'] if i['id'] == item['id']] == [dates[0], dates[2]]
    ok(owner.rpc('agenda_item_delete', id=item['id']))


def test_busy_times_need_an_explicit_share_and_are_rounded_to_half_hours(people, group):
    owner, friend, _ = people
    soon = datetime.now(timezone.utc).replace(second=0, microsecond=0) + timedelta(days=3)
    block = {'s': (soon.replace(minute=7)).isoformat(), 'e': (soon.replace(minute=7) + timedelta(minutes=50)).isoformat()}
    refused(owner.rpc('agenda_set_busy', source='device', blocks=[block]), 'forbidden')  # rien ne part sans accord
    other = httpx.post(f'{TEST_URL}/rest/v1/member_groups', headers={**friend.headers, 'Prefer': 'return=representation'},
                       json={'name': 'Agenda autre'}, timeout=30).json()[0]['id']
    try:
        refused(owner.rpc('agenda_set_sharing', groups=[other]), 'forbidden')     # seulement ses propres groupes
    finally:
        sql(f"delete from public.member_groups where id = '{other}'")
    sharing = ok(owner.rpc('agenda_sharing'))
    assert not any(g['shared'] for g in sharing['groups'])                         # tout décoché au départ
    sharing = ok(owner.rpc('agenda_set_sharing', groups=[group], share_party=True, share_manual=False))
    shared = [g for g in sharing['groups'] if g['shared']]
    assert [g['id'] for g in shared] == [group] and shared[0]['consented_at']       # accord daté
    assert ok(owner.rpc('agenda_set_busy', source='device', blocks=[block]))['saved'] == 1
    free = ok(friend.rpc('agenda_group_free', grp=group))
    lea = next(m for m in free['members'] if m['id'] == owner.uid)
    marc = next(m for m in free['members'] if m['id'] == friend.uid)
    assert lea['shares'] and marc['shares'] is False and 'busy' not in marc           # ne partage pas : sans état
    s, e = at(lea['busy'][0][0]), at(lea['busy'][0][1])
    assert s.minute == 0 and e.minute == 0 and e - s == timedelta(hours=1)           # 0:07–0:57 → 0:00–1:00
    assert set(lea) == {'id', 'name', 'avatar_url', 'me', 'shares', 'updated_at', 'busy'}  # jamais un titre


def test_blocked_people_never_see_each_other_and_leaving_the_group_stops_sharing(people, group):
    owner, friend, _ = people
    ok(owner.rpc('agenda_set_sharing', groups=[group]))
    ok(friend.rpc('set_direct_block', target=owner.uid, blocked=True))
    try:
        assert owner.uid not in {m['id'] for m in ok(friend.rpc('agenda_group_free', grp=group))['members']}
        assert friend.uid not in {m['id'] for m in ok(owner.rpc('agenda_group_free', grp=group))['members']}
    finally:
        ok(friend.rpc('set_direct_block', target=owner.uid, blocked=False))
        sql(f"delete from public.content_reports where reporter_id = '{friend.uid}' and target_id = '{owner.uid}'")
    ok(friend.rpc('agenda_set_sharing', groups=[group]))
    sql(f"delete from public.member_group_members where group_id = '{group}' and user_id = '{friend.uid}'")
    assert sql(f"select count(*) n from private.agenda_group_shares where user_id = '{friend.uid}'")[0]['n'] == 0
    sql(f"insert into public.member_group_members (group_id, user_id) values ('{group}', '{friend.uid}')")
    refused(friend.rpc('agenda_group_free', grp='00000000-0000-0000-0000-000000000000'), 'forbidden')


def test_stopping_erases_everything_that_was_sent(people, group):
    owner, _, _ = people
    ok(owner.rpc('agenda_set_sharing', groups=[group]))
    soon = datetime.now(timezone.utc) + timedelta(days=2)
    ok(owner.rpc('agenda_set_busy', source='device', blocks=[{'s': soon.isoformat(), 'e': (soon + timedelta(hours=2)).isoformat()}]))
    after = ok(owner.rpc('agenda_stop_sharing'))
    assert after['busy_count'] == 0 and not any(g['shared'] for g in after['groups'])


def link_body(**over) -> dict:
    return {'name': 'Rendez-vous pro', 'rules': [WEEKDAYS_ALL], 'horizon_days': 14, 'duration_min': 60, **over}


def test_a_public_link_shows_free_slots_from_tomorrow_only_and_stops_at_the_same_address(people):
    owner, _, _ = people
    link = ok(owner.rpc('agenda_link_save', link=link_body()))
    assert len(link['token']) >= 24 and link['status'] == 'active' and link['path'] == '/d/' + link['token']
    assert link['display_name'] == 'Agenda'                                          # le prénom par défaut
    page = ok(anon('agenda_public_page', t=link['token'], count_view=True))
    assert page['name'] == 'Agenda' and page['booking'] is None and page['slots']
    tomorrow = (datetime.now(SWISS) + timedelta(days=1)).date()
    for s, e in page['slots']:
        s, e = at(s), at(e)
        assert s.astimezone(SWISS).date() >= tomorrow and s >= datetime.now(timezone.utc) + timedelta(hours=12)
        assert s.minute in (0, 30) and e.minute in (0, 30) and e - s >= timedelta(minutes=30)
    ok(anon('agenda_public_page', t=link['token'], count_view=False))
    assert next(x for x in ok(owner.rpc('agenda_links'))['links'] if x['id'] == link['id'])['views'] == 1
    ok(owner.rpc('agenda_link_set', id=link['id'], action='stop'))
    assert anon('agenda_public_page', t=link['token']).json() is None                 # arrêté = comme inconnu
    assert anon('agenda_public_page', t='x' * 24).json() is None
    again = ok(owner.rpc('agenda_link_set', id=link['id'], action='restart'))
    assert again['token'] == link['token'] and anon('agenda_public_page', t=link['token']).json()
    sql(f"update private.agenda_links set expires_at = now() - interval '1 minute' where id = '{link['id']}'")
    assert anon('agenda_public_page', t=link['token']).json() is None                 # expiré
    assert at(ok(owner.rpc('agenda_link_set', id=link['id'], action='extend'))['expires_at']) > datetime.now(timezone.utc) + timedelta(days=89)
    ok(owner.rpc('agenda_link_set', id=link['id'], action='delete'))


def free_at(token: str, when: datetime) -> bool:
    """Le moment `when` est-il dans une plage libre de la page publique ?"""
    page = ok(anon('agenda_public_page', t=token, count_view=False))
    return any(at(s) <= when < at(e) for s, e in page['slots'])


def test_each_link_chooses_the_calendars_that_make_me_busy(people, group):
    """Migration 20261117150000 : un lien ne compte que ses calendriers ; « Qui est libre ? » que ceux des groupes."""
    owner, friend, _ = people
    ok(owner.rpc('agenda_set_sharing', groups=[group]))
    day = (datetime.now(SWISS) + timedelta(days=3)).replace(hour=10, minute=0, second=0, microsecond=0)
    work, perso = 'ios:TRAVAIL-1', 'ios:PERSO-2'
    pro = ok(owner.rpc('agenda_link_save', link=link_body(name='Pro', calendars=[work])))
    every = ok(owner.rpc('agenda_link_save', link=link_body(name='Tout', calendars=[work, perso])))
    assert pro['calendars'] == [work]
    ok(owner.rpc('agenda_set_busy', source='device', blocks=[
        {'s': day.isoformat(), 'e': (day + timedelta(hours=1)).isoformat(), 'c': work, 'g': False},
        {'s': (day + timedelta(hours=3)).isoformat(), 'e': (day + timedelta(hours=4)).isoformat(), 'c': perso, 'g': True},
    ]))
    assert not free_at(pro['token'], day) and free_at(pro['token'], day + timedelta(hours=3))   # perso ne compte pas
    assert not free_at(every['token'], day) and not free_at(every['token'], day + timedelta(hours=3))
    # « Qui est libre ? » : seulement le calendrier qui compte pour les groupes (perso), jamais celui du lien seul.
    me = next(m for m in ok(friend.rpc('agenda_group_free', grp=group))['members'] if m['id'] == owner.uid)
    busy = [(at(s), at(e)) for s, e in me['busy']]
    assert any(s <= day + timedelta(hours=3) < e for s, e in busy) and not any(s <= day < e for s, e in busy)
    # Rendez-vous noté dans Party (« Juste pour moi ») : compte seulement si ce calendrier est choisi.
    cals = {c['kind']: c['id'] for c in ok(owner.rpc('agenda_calendars_list'))}
    later = day + timedelta(hours=6)
    ok(owner.rpc('agenda_item_save', item={'title': 'Dentiste', 'starts_at': later.isoformat(),
                                           'ends_at': (later + timedelta(hours=1)).isoformat(), 'calendar_id': cals['personal']}))
    assert free_at(pro['token'], later)
    ok(owner.rpc('agenda_link_save', link={'calendars': [work, cals['personal']]}, id=pro['id']))
    assert not free_at(pro['token'], later)
    refused(owner.rpc('agenda_link_save', link=link_body(calendars=['Travail perso'])), 'forbidden')   # jamais un nom
    refused(owner.rpc('agenda_set_busy', source='device', blocks=[{'s': day.isoformat(), 'e': later.isoformat(), 'c': 'Agenda de Léa'}]), 'forbidden')
    ok(owner.rpc('agenda_stop_sharing'))
    sql(f"delete from private.agenda_links where user_id = '{owner.uid}'")
    sql(f"delete from public.agenda_items where user_id = '{owner.uid}'")


def test_margins_before_and_after_and_old_app_ranges_count_for_every_link(people, group):
    """Migration 20261117160000 : marges par lien (30 min avant, 30 min après chaque rendez-vous) ; plages envoyées
    sans calendrier par l'app d'avant (bug du 17.11 : lien qui choisit ses calendriers toujours libre)."""
    owner, _, _ = people
    ok(owner.rpc('agenda_set_sharing', groups=[group]))
    day = (datetime.now(SWISS) + timedelta(days=3)).replace(hour=12, minute=0, second=0, microsecond=0)
    plain = ok(owner.rpc('agenda_link_save', link=link_body(name='Sans marge', calendars=['ios:TRAVAIL-1'])))
    margin = ok(owner.rpc('agenda_link_save', link=link_body(name='Marges', calendars=['ios:TRAVAIL-1'],
                                                             buffer_before_min=30, buffer_after_min=30)))
    assert margin['buffer_before_min'] == 30 and margin['buffer_after_min'] == 30
    # L'app d'avant : ni « c » ni « g ».
    ok(owner.rpc('agenda_set_busy', source='device', blocks=[{'s': day.isoformat(), 'e': (day + timedelta(hours=1)).isoformat()}]))
    assert not free_at(plain['token'], day)                                         # compte même sans calendrier
    assert free_at(plain['token'], day - timedelta(minutes=30)) and free_at(plain['token'], day + timedelta(hours=1))
    assert not free_at(margin['token'], day - timedelta(minutes=30))                # 11 h 30 – 12 h : marge avant
    assert not free_at(margin['token'], day + timedelta(hours=1, minutes=15))       # 13 h – 13 h 30 : marge après
    assert free_at(margin['token'], day + timedelta(hours=1, minutes=30))
    assert free_at(margin['token'], day - timedelta(minutes=31))
    # Changer seulement le nom garde les marges ; valeurs hors limites refusées.
    assert ok(owner.rpc('agenda_link_save', link={'name': 'Renommé'}, id=margin['id']))['buffer_after_min'] == 30
    refused(owner.rpc('agenda_link_save', link={'buffer_before_min': 7}, id=margin['id']), 'forbidden')
    refused(owner.rpc('agenda_link_save', link={'buffer_after_min': 300}, id=margin['id']), 'forbidden')
    ok(owner.rpc('agenda_stop_sharing'))
    sql(f"delete from private.agenda_links where user_id = '{owner.uid}'")


def test_a_readable_address_agenda_name_link(people):
    """Migration 20261117170000 : /agenda/<nom>/<lien> ; nom unique sur le site, réservés et filtre ; nom du lien unique
    pour soi ; lien arrêté ou nom changé : plus rien ; l'adresse en lettres marche toujours."""
    owner, friend, _ = people
    ok(owner.rpc('agenda_handle_set', handle=''))
    ok(friend.rpc('agenda_handle_set', handle=''))
    link = ok(owner.rpc('agenda_link_save', link=link_body(name='Semaine')))
    refused(owner.rpc('agenda_link_set_slug', id=link['id'], slug='semaine'), 'forbidden')        # nom d'abord
    for bad, code in (('ab', 'invalid'), ('Ludo Vic', 'invalid'), ('a--b', 'invalid'), ('admin-party', 'duplicate'), ('vendrediparty', 'duplicate')):
        refused(owner.rpc('agenda_handle_set', handle=bad), code)
    assert ok(owner.rpc('agenda_handle_set', handle='Recette-Lea'))['handle'] == 'recette-lea'
    refused(friend.rpc('agenda_handle_set', handle='recette-lea'), 'duplicate')                  # unique sur le site
    nice = ok(owner.rpc('agenda_link_set_slug', id=link['id'], slug='Semaine'))
    assert nice['slug'] == 'semaine' and nice['nice_path'] == '/agenda/recette-lea/semaine'
    assert ok(anon('agenda_resolve', handle='Recette-Lea', slug='semaine')) == link['token']
    other = ok(owner.rpc('agenda_link_save', link=link_body(name='Autre')))
    refused(owner.rpc('agenda_link_set_slug', id=other['id'], slug='semaine'), 'duplicate')       # unique pour soi
    ok(friend.rpc('agenda_handle_set', handle='recette-marc'))
    friend_link = ok(friend.rpc('agenda_link_save', link=link_body(name='Semaine')))
    assert ok(friend.rpc('agenda_link_set_slug', id=friend_link['id'], slug='semaine'))['nice_path'] == '/agenda/recette-marc/semaine'
    assert ok(owner.rpc('agenda_links'))['handle'] == 'recette-lea'
    ok(owner.rpc('agenda_link_set', id=link['id'], action='stop'))
    assert anon('agenda_resolve', handle='recette-lea', slug='semaine').json() is None           # arrêté
    ok(owner.rpc('agenda_link_set', id=link['id'], action='restart'))
    ok(owner.rpc('agenda_handle_set', handle='recette-lea-2'))
    assert anon('agenda_resolve', handle='recette-lea', slug='semaine').json() is None           # ancien nom : plus rien
    assert ok(anon('agenda_resolve', handle='recette-lea-2', slug='semaine')) == link['token']
    assert anon('agenda_public_page', t=link['token']).json()                                    # en lettres : toujours
    assert ok(owner.rpc('agenda_link_set_slug', id=link['id'], slug=''))['nice_path'] is None
    ok(owner.rpc('agenda_handle_set', handle=''))
    ok(friend.rpc('agenda_handle_set', handle=''))
    sql(f"delete from private.agenda_links where user_id in ('{owner.uid}', '{friend.uid}')")


def test_a_link_can_be_permanent(people):
    owner, _, _ = people
    link = ok(owner.rpc('agenda_link_save', link=link_body(permanent=True)))
    assert link['permanent'] and link['expires_at'] is None and link['status'] == 'active'
    assert anon('agenda_public_page', t=link['token']).json()
    # Rallumé après un arrêt : toujours permanent, même adresse.
    ok(owner.rpc('agenda_link_set', id=link['id'], action='stop'))
    again = ok(owner.rpc('agenda_link_set', id=link['id'], action='restart'))
    assert again['permanent'] and anon('agenda_public_page', t=link['token']).json()
    # Repasser à 90 jours, puis de nouveau permanent ; modifier autre chose ne touche pas à la durée.
    timed = ok(owner.rpc('agenda_link_save', link={'permanent': False}, id=link['id']))
    assert not timed['permanent'] and at(timed['expires_at']) > datetime.now(timezone.utc) + timedelta(days=89)
    assert not ok(owner.rpc('agenda_link_save', link={'name': 'Renommé'}, id=link['id']))['permanent']
    assert ok(owner.rpc('agenda_link_save', link={'permanent': True}, id=link['id']))['expires_at'] is None
    ok(owner.rpc('agenda_link_set', id=link['id'], action='delete'))


def test_ten_links_at_most(people):
    owner, _, _ = people
    for i in range(10):
        ok(owner.rpc('agenda_link_save', link=link_body(name=f'Lien {i}')))
    refused(owner.rpc('agenda_link_save', link=link_body(name='Onzième')), 'forbidden')
    sql(f"delete from private.agenda_links where user_id = '{owner.uid}'")


@pytest.fixture
def bookable(people):
    owner, _, _ = people
    sql(f"delete from private.agenda_sender_blocks where owner_id = '{owner.uid}'")
    link = ok(owner.rpc('agenda_link_save', link=link_body(booking_enabled=True, booking_fields={
        'first_name': 'required', 'last_name': 'optional', 'email': 'required', 'phone': 'optional', 'message': 'optional'})))
    page = ok(anon('agenda_public_page', t=link['token'], count_view=False))
    yield owner, link, page
    sql(f"delete from private.agenda_links where id = '{link['id']}'")
    sql(f"delete from private.agenda_ip_hits where ip_hash is not null and at > now() - interval '1 hour' and link_id is null")


def ask(token: str, slot: list, email: str, ip: str = '203.0.113.10', **answers) -> httpx.Response:
    return anon('agenda_booking_request', t=token, starts_at=slot[0], ip=ip,
                answers={'first_name': 'Marc', 'last_name': 'Rochat', 'email': email, **answers})


def test_slots_follow_the_link_duration_and_a_request_reserves_its_slot(bookable):
    owner, link, page = bookable
    assert page['booking']['fields']['email'] == 'required' and not page['booking']['full']
    for s, e in page['slots']:
        assert at(e) - at(s) == timedelta(hours=1) and at(s).astimezone(SWISS).minute == 0   # alignés sur 8 h
    slot = page['slots'][0]
    sent = ok(ask(link['token'], slot, 'marc@example.com', message='Un appel d’une heure ?'))
    assert len(sent['secret']) >= 32 and sent['status'] == 'pending'
    assert slot not in ok(anon('agenda_public_page', t=link['token'], count_view=False))['slots']   # réservé
    assert ok(owner.rpc('agenda_badge'))['pending'] == 1
    note = sql(f"select title, body from public.notifications where user_id = '{owner.uid}' and kind = 'booking_request' "
               f"and dedupe_key like 'booking_request:%' order by created_at desc limit 1")[0]
    assert note['title'] == 'Nouvelle demande de rendez-vous' and note['body'].startswith('Rendez-vous pro · ')
    assert 'Marc' not in note['body'] and 'appel' not in note['body'] and '@' not in note['body']  # ni coordonnée ni texte libre
    mine = ok(owner.rpc('agenda_booking_requests'))[0]
    assert mine['email'] == 'marc@example.com' and mine['verified'] is False and mine['status'] == 'pending'
    status = ok(anon('agenda_booking_status', secret=sent['secret']))
    assert status['status'] == 'pending' and status['answers']['first_name'] == 'Marc' and status['can_cancel']
    refused(ask(link['token'], page['slots'][1], 'MARC@example.com '), 'duplicate')   # 1 en attente par e-mail
    refused(ask(link['token'], slot, 'autre@example.com', ip='203.0.113.11'), 'slot_taken')


def test_filter_formats_and_rate_limits_answer_the_stranger(bookable):
    owner, link, page = bookable
    message = refused(ask(link['token'], page['slots'][0], 'a@example.com', message='Voir www.plans-alpes.ch/projet'), 'content_refused')
    assert 'lien' in message and 'Rien n' in message
    refused(ask(link['token'], page['slots'][0], 'pas-un-email'), 'invalid')
    refused(anon('agenda_booking_request', t=link['token'], starts_at=page['slots'][0][0], answers={'email': 'b@example.com'}), 'invalid')
    refused(ask(link['token'], [page['slots'][0][0][:11] + '08:10:00+00:00'], 'c@example.com'), 'slot_taken')  # hors grille
    ip = f'198.51.100.{int(time.time()) % 200}'
    for i in range(3):
        ok(ask(link['token'], page['slots'][i], f'ip{i}@example.com', ip=ip))
    refused(ask(link['token'], page['slots'][3], 'ip3@example.com', ip=ip), 'rate_limited')     # 3 / h par IP
    ok(ask(link['token'], page['slots'][3], 'd@example.com', ip='192.0.2.1'))
    ok(ask(link['token'], page['slots'][4], 'e@example.com', ip='192.0.2.2'))
    refused(ask(link['token'], page['slots'][5], 'f@example.com', ip='192.0.2.3'), 'full')        # 5 en attente par lien
    assert ok(anon('agenda_public_page', t=link['token'], count_view=False))['booking']['full'] is True
    assert sql(f"select count(*) n from private.agenda_bookings where link_id = '{link['id']}' and ip_hash like '%.%'")[0]['n'] == 0


def test_accept_refuse_report_block_and_the_strangers_own_controls(bookable):
    owner, link, page = bookable
    a = ok(ask(link['token'], page['slots'][0], 'acc@example.com', ip='192.0.2.10'))
    r = ok(ask(link['token'], page['slots'][1], 'ref@example.com', ip='192.0.2.11', message='Bonjour'))
    b = ok(ask(link['token'], page['slots'][2], 'spam@example.com', ip='192.0.2.12', phone='+41 79 123 45 67'))
    ids = {x['email']: x['id'] for x in ok(owner.rpc('agenda_booking_requests', link=link['id']))}
    accepted = ok(owner.rpc('agenda_booking_decide', id=ids['acc@example.com'], accept=True))
    assert accepted['status'] == 'accepted'
    item = owner.get(f"agenda_items?id=eq.{accepted['item_id']}&select=title,starts_at").json()[0]
    assert item['title'] == 'Rendez-vous · Marc R.'
    assert ok(anon('agenda_booking_status', secret=a['secret']))['status'] == 'accepted'
    ok(owner.rpc('agenda_booking_decide', id=ids['ref@example.com'], accept=False))
    gone = ok(anon('agenda_booking_status', secret=r['secret']))
    assert gone['status'] == 'refused' and gone['answers'] is None                     # effacé aussitôt
    assert page['slots'][1] in ok(anon('agenda_public_page', t=link['token'], count_view=False))['slots']   # libéré
    report = ok(owner.rpc('agenda_booking_report', id=ids['spam@example.com'], reason='spam'))
    row = sql(f"select target_kind, target_user, snapshot->>'text' t from public.content_reports where id = '{report}'")[0]
    assert row['target_kind'] == 'booking_request' and row['target_user'] is None and 'Marc' in row['t']
    sql(f"delete from public.content_reports where id = '{report}'")
    again = ok(ask(link['token'], page['slots'][3], 'spam@example.com', ip='192.0.2.13'))
    ids2 = {x['email']: x['id'] for x in ok(owner.rpc('agenda_booking_requests', link=link['id'])) if x['email']}
    ok(owner.rpc('agenda_booking_block', id=ids2['spam@example.com']))
    refused(ask(link['token'], page['slots'][4], 'spam@example.com', ip='192.0.2.14'), 'full')     # expéditeur bloqué
    refused(ask(link['token'], page['slots'][4], 'autre@example.com', ip='192.0.2.13'), 'full')    # même IP (24 h)
    assert ok(anon('agenda_booking_status', secret=again['secret']))['status'] == 'refused'
    # L'inconnu annule son rendez-vous accepté : retiré de l'agenda du membre, qui est prévenu.
    assert ok(anon('agenda_booking_cancel', secret=a['secret']))['status'] == 'cancelled'
    assert owner.get(f"agenda_items?id=eq.{accepted['item_id']}").json() == []
    assert sql(f"select count(*) n from public.notifications where user_id = '{owner.uid}' and kind = 'booking_cancelled'")[0]['n'] >= 1
    # « Effacer mes données » : la demande disparaît.
    c = ok(ask(link['token'], page['slots'][5], 'erase@example.com', ip='192.0.2.15'))
    ok(anon('agenda_booking_erase', secret=c['secret']))
    assert anon('agenda_booking_status', secret=c['secret']).json() is None
    ok(owner.rpc('agenda_unblock_senders'))


def test_scheduled_erasures(bookable):
    owner, link, page = bookable
    p = ok(ask(link['token'], page['slots'][0], 'late@example.com', ip='192.0.2.20'))
    k = ok(ask(link['token'], page['slots'][1], 'kept@example.com', ip='192.0.2.21'))
    kid = next(x['id'] for x in ok(owner.rpc('agenda_booking_requests', link=link['id'])) if x['email'] == 'kept@example.com')
    item = ok(owner.rpc('agenda_booking_decide', id=kid, accept=True))['item_id']
    sql(f"update private.agenda_bookings set expires_at = now() - interval '1 minute' where secret = '{p['secret']}'")
    sql(f"update private.agenda_bookings set created_at = now() - interval '25 hours', starts_at = now() - interval '31 days 2 hours', "
        f"ends_at = now() - interval '31 days 1 hour' where secret = '{k['secret']}'")
    sql('select private.agenda_tick()')
    expired = ok(anon('agenda_booking_status', secret=p['secret']))
    assert expired['status'] == 'expired' and expired['answers'] is None              # 48 h sans réponse : effacé
    assert anon('agenda_booking_status', secret=k['secret']).json() is None           # 30 jours après : parti
    assert owner.get(f"agenda_items?id=eq.{item}&select=title").json()[0]['title'] == 'Rendez-vous · Marc R.'
    assert sql("select count(*) n from private.agenda_ip_hits where at < now() - interval '24 hours'")[0]['n'] == 0


def test_everything_goes_with_the_account_and_the_notification_has_its_switch():
    rows = sql("""select t.relname t, c.confdeltype d from pg_constraint c join pg_class t on t.oid = c.conrelid
                  where c.contype = 'f' and c.confrelid = 'public.profiles'::regclass and t.relname like 'agenda\\_%'""")
    assert len(rows) == 9 and {r['d'] for r in rows} == {'c'}, rows
    assert sql("select column_default d from information_schema.columns where table_name = 'notification_prefs' "
               "and column_name = 'booking_requests'")[0]['d'] == 'true'
    defs = sql("select pg_get_functiondef('private.web_push_allowed(public.notifications)'::regprocedure) w, "
               "pg_get_functiondef('private.may_receive_push(uuid, text)'::regprocedure) m")[0]
    assert "when 'booking_request' then coalesce(prefs.booking_requests, true)" in defs['w'] and "'booking_request'" in defs['m']
    assert sql("select count(*) n from cron.job where jobname = 'agenda-tick'")[0]['n'] == 1
