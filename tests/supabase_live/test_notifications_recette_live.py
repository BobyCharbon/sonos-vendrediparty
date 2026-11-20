"""Recette RÉELLE de la logique des notifications (campagne du 14.11.2026), sur la base de TEST, par l'API comme l'app :
vrais comptes de test (bots), vrais jetons, vraies règles ; chacun relit SES notifications (table public.notifications).
Rien n'est annulé : les événements (tous « sur invitation », seuls des comptes de test y sont) et le groupe créés ici
sont supprimés à la fin. Aucun vrai membre n'est jamais prévenu : jamais d'événement public qui notifie, groupe à soi.

- événement public : personne n'est prévenu à la publication (ni invité un à un, ni groupe, même « Prévenir le groupe ») ;
- invitation directe : l'invité est prévenu une fois ; modification → les participants ; annulation → participants et
  invités sans réponse, une fois ;
- groupe : rien sans « Prévenir le groupe » ; avec : demande aux valideurs (créateur et admin du groupe), première réponse
  gagne, chaque membre prévenu une fois, l'organisateur informé ; couper / rallumer ne redemande pas ;
- accord de l'organisateur : la demande prévient l'organisateur une fois par personne, la décision prévient la personne ;
- réponses regroupées (une notification au bout de 5 minutes, état final) et rappel « 2 h avant » (tâches planifiées).
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_notifications_recette_live.py -q"""
import re
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
import pytest

from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark  # noqa: F401

ADMIN, OSCAR, VERA, MIA, MAX, GUS, GINA = ('41790000004', '41790000104', '41790000106', '41790000110', '41790000111',
                                          '41790000112', '41790000113')


def post(s: Session, table: str, body: dict) -> list:
    r = httpx.post(f'{TEST_URL}/rest/v1/{table}', headers={**s.headers, 'Prefer': 'return=representation'}, json=body, timeout=30)
    assert r.status_code == 201, r.text
    return r.json()


def patch(s: Session, table: str, where: str, body: dict):
    r = httpx.patch(f'{TEST_URL}/rest/v1/{table}?{where}', headers=s.headers, json=body, timeout=30)
    assert r.status_code in (200, 204), r.text


def event(s: Session, title: str, status: str = 'published', starts_in: timedelta = timedelta(days=30), **fields) -> str:
    """Toujours « sur invitation » : seuls les comptes de test ajoutés ici le voient."""
    start = (datetime.now(timezone.utc) + starts_in).isoformat()
    return post(s, 'events', {'title': title, 'status': status, 'visibility': 'invited', 'public_link': False,
                              'notify_on_publish': False, 'starts_at': start, **fields})[0]['id']


def notes(s: Session, e: str, kind: str | None = None) -> list:
    """Les notifications de ce compte pour cet événement (event_id, ou data.target_event pour les demandes au groupe)."""
    q = f'notifications?select=kind,title,body,event_id,data&or=(event_id.eq.{e},data->>target_event.eq.{e})&order=created_at'
    return [n for n in s.get(q).json() if kind is None or n['kind'] == kind]


def answer(s: Session, e: str, status: str):
    r = httpx.patch(f'{TEST_URL}/rest/v1/rsvps?event_id=eq.{e}&user_id=eq.{s.uid}', timeout=30,
                    headers={**s.headers, 'Prefer': 'return=representation'}, json={'status': status})
    if r.status_code == 200 and r.json():
        return
    post(s, 'rsvps', {'event_id': e, 'user_id': s.uid, 'status': status})


def login(phone: str) -> Session:
    """Base de test partagée (même adresse IP pour tous) : après un 429 d'Auth, attendre 2 min et demie avant un nouvel essai."""
    for _ in range(3):
        try:
            return Session(phone)
        except AssertionError as e:
            if '429' not in str(e):
                raise
            time.sleep(150)
    return Session(phone)


@pytest.fixture(scope='module')
def w():
    who = {name: login(phone) for name, phone in (('admin', ADMIN), ('oscar', OSCAR), ('vera', VERA), ('mia', MIA),
                                                    ('max', MAX), ('gus', GUS), ('gina', GINA))}
    for s in (who['oscar'], who['vera']):  # CGU exigées (comme en prod) pour publier un événement ou créer un groupe
        s.rpc('accept_terms', p_version=s.rpc('my_terms').json()['version'])
    group = post(who['vera'], 'member_groups', {'name': 'Test notifs recette', 'created_by': who['vera'].uid})[0]['id']
    for name in ('oscar', 'mia', 'max', 'gus', 'gina'):
        post(who['vera'], 'member_group_members', {'group_id': group, 'user_id': who[name].uid})
    assert who['vera'].rpc('set_group_admin', grp=group, member=who['gus'].uid, admin=True).status_code in (200, 204)
    made: list[str] = []
    yield who, group, made
    for e in made:  # l'admin supprime sans annuler : aucune notification de plus
        httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{e}', headers=who['admin'].headers, timeout=30)
    httpx.delete(f'{TEST_URL}/rest/v1/member_groups?id=eq.{group}', headers=who['vera'].headers, timeout=30)


def test_a_public_event_tells_nobody_even_with_people_invited_and_the_group_announced(w):
    who, group, made = w
    oscar = who['oscar']
    e = event(oscar, 'Test notifs public', status='draft', public_link=True, notify_on_publish=True, announce_group=True)
    made.append(e)
    post(oscar, 'event_invites', {'event_id': e, 'user_id': who['gina'].uid})
    post(oscar, 'event_groups', {'event_id': e, 'group_id': group})
    patch(oscar, 'events', f'id=eq.{e}', {'status': 'published'})
    assert oscar.get(f'events?select=notify_on_publish&id=eq.{e}').json() == [{'notify_on_publish': False}]
    assert oscar.get(f'event_announcements?select=id&event_id=eq.{e}').json() == []
    for name in ('vera', 'mia', 'max', 'gus', 'gina'):
        assert notes(who[name], e) == [], name


def test_a_direct_invitation_is_told_once_then_changes_and_cancellation(w):
    who, _, made = w
    oscar, gus, gina = who['oscar'], who['gus'], who['gina']
    e = event(oscar, 'Test notifs invitation', status='draft', notify_on_publish=True)
    made.append(e)
    for s in (gus, gina):
        post(oscar, 'event_invites', {'event_id': e, 'user_id': s.uid})
    assert notes(gus, e) == []  # brouillon : rien encore
    patch(oscar, 'events', f'id=eq.{e}', {'status': 'published'})
    assert oscar.rpc('invite_people', e=e, people=[gus.uid]).status_code == 200  # réinvité : pas de doublon
    for s in (gus, gina):
        assert [n['kind'] for n in notes(s, e)] == ['private_invite']
    answer(gus, e, 'yes')
    later = (datetime.now(timezone.utc) + timedelta(days=31)).isoformat()
    patch(oscar, 'events', f'id=eq.{e}', {'starts_at': later})
    assert [n['title'] for n in notes(gus, e, 'event_changed')] == ['Événement modifié']  # il vient : prévenu
    assert notes(gina, e, 'event_changed') == []  # sans réponse : pas d'une modification
    patch(oscar, 'events', f'id=eq.{e}', {'status': 'cancelled'})
    for s in (gus, gina):  # annulation : participants ET invités sans réponse, une fois
        assert [n['title'] for n in notes(s, e, 'event_changed')][-1:] == ['Événement annulé']
        assert len([n for n in notes(s, e, 'event_changed') if n['title'] == 'Événement annulé']) == 1
    assert notes(oscar, e) == []  # jamais pour sa propre action



def test_only_place_date_or_a_new_vote_tell_participants_of_a_change(w):
    """Avis 27b5eea5121c (20.11) : description, titre, prix, heure de fin ou lien du lieu : rien. Lieu, date de début,
    retour au sondage de dates : une notification qui dit ce qui change."""
    who, _, made = w
    oscar, gus = who['oscar'], who['gus']
    e = event(oscar, 'Test notifs modif', location_name='Salle A', location_address='Rue A 1, 1000 Lausanne')
    made.append(e)
    post(oscar, 'event_invites', {'event_id': e, 'user_id': gus.uid})
    answer(gus, e, 'yes')
    later = (datetime.now(timezone.utc) + timedelta(days=40)).isoformat()
    for change in ({'description': 'Nouvelle description'}, {'title': 'Test notifs modif (renommé)'}, {'price_chf': 15},
                   {'ends_at': later}, {'location_url': 'https://maps.example.ch/a'}):
        patch(oscar, 'events', f'id=eq.{e}', change)
    assert notes(gus, e, 'event_changed') == []  # rien de tout cela ne prévient
    patch(oscar, 'events', f'id=eq.{e}', {'location_name': 'Salle B', 'location_address': 'Rue B 2, 1000 Lausanne'})
    patch(oscar, 'events', f'id=eq.{e}', {'location_address': 'Rue B 4, 1000 Lausanne'})
    start = (datetime.now(timezone.utc) + timedelta(days=35)).replace(hour=19, minute=30, second=0, microsecond=0)
    patch(oscar, 'events', f'id=eq.{e}', {'starts_at': start.isoformat(), 'description': 'encore'})
    shown = start.astimezone(ZoneInfo('Europe/Zurich')).strftime('%d.%m à %H:%M')
    patch(oscar, 'events', f'id=eq.{e}', {'date_mode': 'poll'})
    bodies = [n['body'] for n in notes(gus, e, 'event_changed')]
    assert bodies == ['« Test notifs modif (renommé) » : nouveau lieu : Salle B.',
                      '« Test notifs modif (renommé) » : nouvelle adresse : Rue B 4, 1000 Lausanne.',
                      f'« Test notifs modif (renommé) » : nouvelle date : {shown}.',
                      '« Test notifs modif (renommé) » : date à revoter.'], bodies
    assert notes(oscar, e, 'event_changed') == []  # jamais pour sa propre modification

def test_a_group_hears_nothing_without_prevenir_then_validators_decide_and_first_answer_wins(w):
    who, group, made = w
    oscar, vera, gus = who['oscar'], who['vera'], who['gus']
    e = event(oscar, 'Test notifs groupe', status='draft')
    made.append(e)
    post(oscar, 'event_groups', {'event_id': e, 'group_id': group})
    patch(oscar, 'events', f'id=eq.{e}', {'status': 'published'})
    for name in ('vera', 'mia', 'max', 'gus', 'gina'):
        assert notes(who[name], e) == [], name  # sans « Prévenir le groupe » : personne

    patch(oscar, 'events', f'id=eq.{e}', {'announce_group': True})  # Oscar, simple membre : il faut valider
    for name in ('vera', 'gus'):
        assert [n['kind'] for n in notes(who[name], e)] == ['announce_request'], name
    for name in ('mia', 'max', 'gina'):
        assert notes(who[name], e) == [], name  # les membres attendent la décision
    a = oscar.get(f'event_announcements?select=id,status&event_id=eq.{e}').json()
    assert [x['status'] for x in a] == ['pending']

    first = gus.rpc('answer_announcement', a=a[0]['id'], accept=True).json()
    second = vera.rpc('answer_announcement', a=a[0]['id'], accept=False).json()
    assert first['status'] == 'accepted' and second.get('already') is True and second['status'] == 'accepted'
    for name in ('vera', 'mia', 'max', 'gina'):
        assert len(notes(who[name], e, 'private_invite')) == 1, name
    assert notes(gus, e, 'private_invite') == []  # sa propre décision ne lui revient pas
    assert [n['kind'] for n in notes(oscar, e)] == ['announce_accepted']

    patch(oscar, 'events', f'id=eq.{e}', {'announce_group': False})  # couper puis rallumer : rien de plus
    patch(oscar, 'events', f'id=eq.{e}', {'announce_group': True})
    for name in ('vera', 'gus'):
        assert len(notes(who[name], e, 'announce_request')) == 1, name
    for name in ('vera', 'mia', 'max', 'gina'):
        assert len(notes(who[name], e, 'private_invite')) == 1, name


def test_a_join_request_tells_the_organizer_once_and_the_decision_tells_the_person(w):
    who, _, made = w
    oscar, gus, mia, maxi = who['oscar'], who['gus'], who['mia'], who['max']
    e = event(oscar, 'Test notifs accord')
    made.append(e)
    assert oscar.rpc('invite_people', e=e, people=[gus.uid]).status_code == 200
    assert [n['kind'] for n in notes(gus, e)] == ['private_invite']  # ajouté d'ici : toujours prévenu
    token = gus.rpc('create_event_invite', e=e, places=0, label='Recette notifs').json()['token']
    for s, status in ((mia, 'yes'), (maxi, 'maybe'), (mia, 'maybe')):  # Mia répond deux fois : une seule demande
        r = s.rpc('accept_invite', token=token, answer=status)
        assert r.status_code == 200 and r.json().get('pending') is True, r.text
    asks = notes(oscar, e, 'join_request')
    assert len(asks) == 2 and all('aimerait venir' in n['body'] for n in asks), asks
    assert notes(mia, e) == [] and notes(maxi, e) == []  # en attente : rien pour elles

    assert oscar.rpc('decide_join_request', e=e, person=mia.uid, accept=True).status_code == 200
    ok = notes(mia, e)
    assert len(ok) == 1 and ok[0]['title'].startswith('✅') and 'a accepté ta venue' in ok[0]['body'], ok
    assert oscar.rpc('decide_join_request', e=e, person=maxi.uid, accept=False).status_code == 200
    no = maxi.get('notifications?select=kind,body,event_id&body=like.*pas pu accepter*&order=created_at.desc&limit=1').json()
    assert no and 'pas pu accepter ta venue' in no[0]['body'], no
    assert len(notes(oscar, e, 'join_request')) == 2  # rien de plus pour l'organisateur


def test_the_refusal_reaches_the_phone_of_someone_who_cannot_see_the_event(w):
    """Refusée, la personne ne voit pas l'événement : une notification liée à l'événement est écartée de l'envoi
    (private.web_push_allowed ne pousse que ce que l'on voit). Le refus doit donc venir sans lien vers l'événement."""
    who, _, made = w
    oscar, gus, gina = who['oscar'], who['gus'], who['gina']
    e = event(oscar, 'Test notifs refus')
    made.append(e)
    assert oscar.rpc('invite_people', e=e, people=[gus.uid]).status_code == 200
    token = gus.rpc('create_event_invite', e=e, places=1).json()['token']
    assert gina.rpc('accept_invite', token=token, answer='yes').json().get('pending') is True
    assert oscar.rpc('decide_join_request', e=e, person=gina.uid, accept=False).status_code == 200
    no = gina.get(f'notifications?select=event_id,data,body&dedupe_key=eq.join_refused:{e}').json()
    assert len(no) == 1 and no[0]['event_id'] is None, no


def test_someone_waiting_for_approval_learns_the_cancellation_once_without_a_link(w):
    """Décision de l'admin (14.11) : la personne en attente d'accord apprend l'annulation, une fois, sans lien vers
    l'événement qu'elle ne voit pas (migration 20261114220000)."""
    who, _, made = w
    oscar, gus, maxi = who['oscar'], who['gus'], who['max']
    e = event(oscar, 'Test notifs annulation en attente')
    made.append(e)
    assert oscar.rpc('invite_people', e=e, people=[gus.uid]).status_code == 200
    token = gus.rpc('create_event_invite', e=e, places=1).json()['token']
    assert maxi.rpc('accept_invite', token=token, answer='yes').json().get('pending') is True
    patch(oscar, 'events', f'id=eq.{e}', {'status': 'cancelled'})
    told = maxi.get(f'notifications?select=kind,title,event_id&dedupe_key=eq.join_cancelled:{e}').json()
    assert told == [{'kind': 'event_changed', 'title': 'Événement annulé', 'event_id': None}], told
    assert [n['title'] for n in notes(gus, e, 'event_changed')] == ['Événement annulé']  # l'invité, comme avant


def test_answers_are_grouped_and_the_two_hours_reminder_comes_once(w):
    """Tâches planifiées de la base (chaque minute pour les réponses, toutes les 5 minutes pour les rappels) : jusqu'à
    8 minutes d'attente."""
    who, _, made = w
    oscar, gus, gina = who['oscar'], who['gus'], who['gina']
    # Le rappel que Bot Gus a choisi (Réglages), l'événement dans sa fenêtre : 10 minutes après son début.
    chosen = (gus.get(f'notification_prefs?select=reminders&user_id=eq.{gus.uid}').json() or [{}])[0].get('reminders') or []
    off = next((o for o in ('2h', '1d', '7d') if o in chosen), None)
    before = {'2h': timedelta(hours=2), '1d': timedelta(days=1), '7d': timedelta(days=7)}.get(off, timedelta(days=30))
    e = event(oscar, 'Test notifs réponses', starts_in=before - timedelta(minutes=10), reminders=[off] if off else [])
    made.append(e)
    for s in (gus, gina):
        post(oscar, 'event_invites', {'event_id': e, 'user_id': s.uid})
    for status in ('yes', 'maybe', 'no', 'yes'):
        answer(gus, e, status)
    answer(gina, e, 'no')
    assert notes(oscar, e, 'rsvp') == []  # rien pendant la fenêtre de 5 minutes
    deadline = time.time() + 8 * 60
    while time.time() < deadline and not (notes(oscar, e, 'rsvp') and (notes(gus, e, 'reminder') or not off)):
        time.sleep(20)
    digest = notes(oscar, e, 'rsvp')
    # « ne vient pas » ne prévient plus l'organisateur (20.11, migration 20261120090000) : Gus seul.
    assert len(digest) == 1 and re.fullmatch(r'Bot Gus vient', digest[0]['body']), digest
    title = {'2h': 'Dans 2 heures', '1d': "C'est demain", '7d': 'Dans une semaine'}.get(off)
    assert [n['title'] for n in notes(gus, e, 'reminder')] == ([title] if off else [])
    assert notes(gina, e, 'reminder') == []  # ne vient pas : pas de rappel
    time.sleep(70)  # une tâche de plus : toujours une seule
    assert len(notes(oscar, e, 'rsvp')) == 1 and len(notes(gus, e, 'reminder')) == (1 if off else 0)


def test_a_brand_new_account_tells_the_approvers_once_then_is_deleted(w):
    """« Nouveau compte » avec un compte VRAIMENT neuf (41790000501, réservé à cette recette) : connexion SMS, profil vide,
    puis prénom, nom et surnom comme « Faisons connaissance ». Ceux qui ont members.approve (Admin test, Bot Oscar
    organisateur) sont prévenus une fois ; le compte est supprimé à la fin."""
    who, _, _ = w
    admin, oscar = who['admin'], who['oscar']
    new = login('41790000501')

    def told(s: Session) -> int:
        return len(s.get(f'notifications?select=id&kind=eq.member_signup&data->>member=eq.{new.uid}').json())

    try:
        assert told(admin) == 0 and told(oscar) == 0  # compte neuf : profil vide, personne prévenu
        new.rpc('accept_terms', p_version=new.rpc('my_terms').json()['version'])  # CGU au premier surnom
        patch(new, 'profiles', f'id=eq.{new.uid}', {'first_name': 'Nina', 'last_name': 'Recette', 'display_name': 'Nina notifs'})
        assert told(admin) == 1 and told(oscar) == 1
        body = admin.get(f'notifications?select=body&kind=eq.member_signup&data->>member=eq.{new.uid}').json()[0]['body']
        assert body == 'Nina notifs (Nina Recette) vient de créer son compte.', body
        patch(new, 'profiles', f'id=eq.{new.uid}', {'display_name': 'Nina R'})  # déjà complet : rien de plus
        assert told(admin) == 1 and told(oscar) == 1
        assert new.get('notifications?select=id&kind=eq.member_signup').json() == []  # jamais pour soi
    finally:
        nick = next((p.get('display_name') or '' for p in admin.rpc('admin_member_list').json() if p['id'] == new.uid), '')
        r = admin.rpc('admin_delete_member', member=new.uid, confirm_name=nick)
        assert r.status_code in (200, 204), r.text
