"""Recette RÉELLE des nouveaux comptes (campagne du 14.11.2026) : vrai navigateur (390 × 844), vrai serveur Party avec les
drapeaux de la prod (Zicou, Discussions et Bar éteints, Invitations v2 allumées), base de TEST, CGU exigées comme en prod.
Chaque parcours part d'un compte NEUF (numéro de test à code fixe, compte supprimé à la fin par delete_my_account) :
1. lien « Inviter » (page du groupe) d'un groupe de test (créé ici, sans vrais membres) → connexion SMS → profil → le compte
   est dans le groupe, sur sa page dans Party ; puis il le quitte lui-même (Réglages du groupe) ;
2. lien « Partager » d'un événement public (/?tab=events&event=<id>) → connexion → profil → page rechargée : l'adresse garde
   l'événement → Présent ; puis l'agenda abonné : Présent dedans, Pas présent dehors, Peut-être « [Peut-être] » ;
3. sondage de dates public : jamais « Présent », on vote les dates, la carte compte les votants ; l'organisateur voit
   l'heure du vote en petit après le nom (avis 2f5abe63e8ff) ;
et pour chacun, « Nouveau compte » : l'Admin de test (members.approve) est prévenu UNE fois ; le compte supprimé, cette
notification (son nom) part avec lui (migration 20261114210000, à appliquer sur la base de TEST pour que ce soit vert).
ATTENTION : la base de TEST contient de vrais admins (members.approve) ; ils reçoivent aussi ce « Nouveau compte ».

Lancement : SUPABASE_LIVE_TESTS=1 PARTY_TEST_EVENTS_DIST=<module construit contre la base de test> python -m pytest <ce fichier>
Numéros neufs : NOUVEAUX_COMPTES_PHONES (défaut 41790000302,41790000303,41790000304 : code fixe, réservés à cette recette). Captures dans $NOUVEAUX_COMPTES_SHOTS."""
import json
import os
import re
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx
import pytest

from tests.supabase_live.party_shell import in_party, where_visible
from tests.supabase_live.test_audiences_live import ADMIN, create_event
from tests.supabase_live.test_inscription_complete_browser_live import browser, phone_page  # noqa: F401
from tests.supabase_live.test_member_admin_live import KEY_FILE, OTP, TEST_URL, Session, pytestmark as live  # noqa: F401

pw = pytest.importorskip('playwright.sync_api')
ROOT = Path(__file__).resolve().parents[2]
DIST = Path(os.environ.get('PARTY_TEST_EVENTS_DIST') or '/nonexistent')
SHOTS = Path(os.environ['NOUVEAUX_COMPTES_SHOTS']) if os.environ.get('NOUVEAUX_COMPTES_SHOTS') else None
PHONES = (os.environ.get('NOUVEAUX_COMPTES_PHONES') or '41790000302,41790000303,41790000304').split(',')
PREFIX = '[Test nouveaux comptes]'
pytestmark = [live, pytest.mark.skipif(not (DIST / 'index.html').exists(),
                                       reason='PARTY_TEST_EVENTS_DIST : module construit contre la base de test')]


def local(phone: str) -> str:
    """41790000301 → « 079 000 03 01 », comme on le tape dans l'app."""
    d = '0' + phone[2:]
    return f'{d[:3]} {d[3:6]} {d[6:8]} {d[8:]}'


def shot(page, name: str, focus=None):
    """Capture de l'étape ; `focus` : l'élément à montrer (le module défile dans son propre conteneur)."""
    if SHOTS:
        if focus is not None:
            focus.scroll_into_view_if_needed()
        page.wait_for_timeout(800)
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f'{name}.png'), full_page=True)


def otp_login(phone: str) -> dict:
    """Connexion par code fixe ; la réponse complète d'Auth (pour la mettre dans le navigateur de l'organisateur)."""
    base = {'apikey': KEY_FILE.read_text().strip(), 'Content-Type': 'application/json'}
    for _ in range(3):  # 429 : un code par minute et par numéro, et limite d'Auth par adresse IP (tests en parallèle)
        sent = httpx.post(f'{TEST_URL}/auth/v1/otp', headers=base, json={'phone': phone}, timeout=30)
        if sent.status_code != 429:
            break
        time.sleep(150)
    assert sent.status_code == 200, sent.text
    r = httpx.post(f'{TEST_URL}/auth/v1/verify', headers=base, json={'type': 'sms', 'phone': phone, 'token': OTP}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


def headers_of(token: str) -> dict:
    return {'apikey': KEY_FILE.read_text().strip(), 'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}


def delete_account(token: str):
    r = httpx.post(f'{TEST_URL}/rest/v1/rpc/delete_my_account', headers=headers_of(token), json={}, timeout=30)
    assert r.status_code in (200, 204), r.text


STORAGE_KEY = f'sb-{urlparse(TEST_URL).hostname.split(".")[0]}-auth-token'


def browser_token(page) -> str:
    """Jeton du compte connecté dans ce navigateur (même origine que le module Événements)."""
    raw = page.evaluate(f"() => localStorage.getItem('{STORAGE_KEY}')")
    assert raw, 'pas de session dans le navigateur'
    return json.loads(raw)['access_token']


def delete_from_browser(page):
    """Ménage : le compte neuf connecté dans ce navigateur est supprimé (rien s'il n'a pas pu se connecter ou s'il l'est déjà)."""
    raw = page.evaluate(f"() => localStorage.getItem('{STORAGE_KEY}')")
    if raw:
        httpx.post(f'{TEST_URL}/rest/v1/rpc/delete_my_account', headers=headers_of(json.loads(raw)['access_token']), json={}, timeout=30)


@pytest.fixture(scope='module')
def party(tmp_path_factory):
    """Serveur Party local branché sur la base de test, drapeaux EXACTS de la prod."""
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    bundle = b''.join(p.read_bytes() for p in (DIST / '_expo').rglob('*.js'))
    assert urlparse(TEST_URL).netloc.encode() in bundle and b'gsuetixzobooggeaubvb' not in bundle, \
        'PARTY_TEST_EVENTS_DIST doit être construit contre la base de test visée'
    env = {'PATH': os.environ['PATH'], 'HOME': os.environ.get('HOME', '/tmp'), 'LANG': 'C.UTF-8',
           'DATA_DIR': str(tmp_path_factory.mktemp('party-nouveaux')), 'EVENTS_WEB_DIR': str(DIST),
           'ADMIN_PIN': '9999', 'SPOTIFY_CLIENT_ID': '', 'SPOTIFY_CLIENT_SECRET': '',
           'COMPAGNON_ENABLED': '0', 'DISCUSSIONS_ENABLED': '0', 'INVITES_V2_ENABLED': '1', 'BAR_ENABLED': '0',
           'SUPABASE_URL': TEST_URL, 'SUPABASE_ANON_KEY': KEY_FILE.read_text().strip(), 'PYTHONDONTWRITEBYTECODE': '1'}
    process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(port),
                                '--lifespan', 'off'], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    origin = f'http://127.0.0.1:{port}'
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            try:
                if httpx.get(origin, timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(.1)
        else:
            raise AssertionError('Le serveur Party de recette ne démarre pas')
        assert httpx.get(f'{origin}/api/features', timeout=10).json() == {
            'compagnon': False, 'discussions': False, 'invites_v2': True, 'bar': False,
            'patates': False, 'agenda': False, 'pronos': False}
        yield origin
    finally:
        process.terminate()
        process.wait(timeout=10)


@pytest.fixture(scope='module')
def admin():
    """Admin de test : organisateur des événements de test, créateur du groupe de test, et valideur (members.approve)."""
    auth = otp_login(ADMIN)
    s = Session.__new__(Session)
    s.key, s.uid, s.headers = KEY_FILE.read_text().strip(), auth['user']['id'], headers_of(auth['access_token'])
    s.auth = auth
    assert s.rpc('accept_terms', p_version=s.rpc('my_terms').json()['version']).status_code in (200, 204)
    assert 'members.approve' in s.rpc('my_permissions').json()
    made = {'events': [], 'groups': []}
    s.made = made
    yield s
    for e in made['events']:
        httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{e}', headers=s.headers, timeout=30)
    for g in made['groups']:
        httpx.delete(f'{TEST_URL}/rest/v1/member_groups?id=eq.{g}', headers=s.headers, timeout=30)


def signed_in_page(browser, party, auth: dict):  # noqa: F811
    """Navigateur de l'organisateur, déjà connecté (sa session mise comme l'app la garde) : aucun code SMS de plus."""
    context, page, errors = phone_page(browser, alone=True)  # le module seul : ce n'est pas le parcours visé ici
    context.add_init_script(f"localStorage.setItem('{STORAGE_KEY}', {json.dumps(json.dumps(auth))})")
    return context, page, errors


def sign_in(root, page, number: str):
    """La page de connexion normale de l'app : pays, numéro, code SMS. `root` : la page ou le cadre du module."""
    pw.expect(root.get_by_text('Ton compte Party', exact=True)).to_be_visible(timeout=20000)
    root.get_by_label('Ton numéro de téléphone', exact=True).fill(number)
    code = root.get_by_placeholder('123456', exact=True)
    for _ in range(3):  # 429 : un code par minute et par numéro, et limite d'Auth par adresse IP (tests en parallèle)
        root.get_by_role('button', name='Recevoir un code par SMS').click()
        try:
            code.wait_for(timeout=15000)
            break
        except Exception:
            if not root.get_by_text(re.compile('^(Attends .*secondes|Trop de demandes de code)')).first.is_visible():
                shot(page, 'zz-echec-code-sms')
                raise
            page.wait_for_timeout(150000)
    code.fill(OTP)
    root.get_by_role('button', name='Se connecter', exact=True).click()


def complete_profile(root, first: str, last: str, nickname: str, page=None, name: str = ''):
    """« Faisons connaissance » (prénom, nom, surnom ; photo facultative), puis les CGU exigées comme en prod. Ce formulaire
    prouve aussi que le compte est neuf (profil vide) : chaque test supprime son compte à la fin (delete_my_account)."""
    pw.expect(root.get_by_text('Faisons connaissance', exact=True)).to_be_visible(timeout=20000)
    root.get_by_label('Prénom', exact=True).fill(first)
    root.get_by_label('Nom', exact=True).fill(last)
    root.get_by_label('Surnom', exact=False).fill(nickname)
    if page is not None:
        shot(page, name)
    root.get_by_role('button', name=re.compile('^Continuer')).click()
    accept = root.get_by_role('button', name='J’accepte')
    accept.wait_for(timeout=15000)
    accept.click()


def signups(admin, uid: str) -> list:
    """« Nouveau compte » reçus par l'Admin de test pour ce compte."""
    r = admin.get(f'notifications?select=id,title,body&kind=eq.member_signup&data->>member=eq.{uid}')
    assert r.status_code == 200, r.text
    return r.json()


def answer_time(iso: str) -> str:
    """Comme formatAnswerTime (lib/format.ts) : « 14.11 · 22:05 », heure de Zurich."""
    t = datetime.fromisoformat(iso).astimezone(ZoneInfo('Europe/Zurich'))
    return t.strftime('%d.%m · %H:%M')


def test_a_new_account_joins_a_group_by_its_invite_link_then_leaves_it(browser, party, admin):  # noqa: F811
    phone = PHONES[0]
    # Nom propre à ce passage : le compte Admin de test a souvent d'autres groupes (autres passages, autres tests), chacun
    # avec sa carte « Inviter avec un lien » en haut ; on vise la carte de CE groupe.
    name = f'{PREFIX} groupe {os.urandom(3).hex()}'
    r = httpx.post(f'{TEST_URL}/rest/v1/member_groups', headers={**admin.headers, 'Prefer': 'return=representation'}, timeout=30,
                   json={'name': name, 'created_by': admin.uid})
    assert r.status_code == 201, r.text
    group = r.json()[0]['id']
    admin.made['groups'].append(group)

    # L'organisateur ouvre « Inviter » de son groupe (page du groupe, 17.11) : le lien du groupe prêt tout de suite.
    context, page, errors = signed_in_page(browser, party, admin.auth)
    try:
        page.goto(f'{party}/events/group/{group}/invite', wait_until='domcontentloaded')
        panel = page.get_by_test_id('group-invite-panel')
        pw.expect(panel.get_by_text('/events/group-invite/', exact=False)).to_be_visible(timeout=30000)
        url = 'http://' + re.search(r'[^\s/]+/events/group-invite/[0-9a-zA-Z_-]+', panel.inner_text()).group(0)
        assert url.startswith(party), url
        shot(page, '01-groupe-inviter-avec-un-lien', panel)
        assert not errors, errors
    finally:
        context.close()

    context, page, errors = phone_page(browser)
    try:
        page.goto(url, wait_until='domcontentloaded')
        pw.expect(page.get_by_text('Tu es invité !', exact=True)).to_be_visible(timeout=20000)
        shot(page, '02-groupe-lien-ouvert-sans-compte')
        page.get_by_role('button', name='M’inscrire ou me connecter').click()
        sign_in(page, page, local(phone))
        complete_profile(where_visible(page, 'Faisons connaissance'), 'Noa', 'Groupe', 'Noa G.', page, '03a-groupe-faisons-connaissance')
        shot(page, '03-groupe-profil-complet')
        # Profil complet : il rejoint directement et arrive sur la page du groupe, dans Party (19.11 : jamais le module seul).
        frame = in_party(page, f'/events/group/{group}', timeout=45000)
        pw.expect(frame.get_by_role('heading', name=name)).to_be_visible(timeout=20000)
        token = browser_token(page)
        me = httpx.get(f'{TEST_URL}/auth/v1/user', headers=headers_of(token), timeout=30).json()['id']
        members = admin.get(f'member_group_members?select=user_id&group_id=eq.{group}').json()
        assert {m['user_id'] for m in members} == {me, admin.uid}, members  # le créateur et lui, personne d'autre
        shot(page, '04-groupe-rejoint')

        # Il quitte le groupe lui-même (Réglages du groupe), et revient à ses groupes, sans celui-ci.
        frame.get_by_test_id('group-settings').click()
        frame.get_by_role('button', name='Quitter le groupe').click()
        frame.get_by_role('button', name='Confirmer : quitter le groupe').click()
        pw.expect(frame.get_by_text(name, exact=True)).to_have_count(0, timeout=20000)
        assert admin.get(f'member_group_members?select=user_id&group_id=eq.{group}').json() == [{'user_id': admin.uid}]
        shot(page, '05-groupe-quitte')

        # « Nouveau compte » : l'Admin de test prévenu une fois ; un changement de surnom ensuite n'en refait pas.
        assert len(signups(admin, me)) == 1, signups(admin, me)
        r = httpx.patch(f'{TEST_URL}/rest/v1/profiles?id=eq.{me}', headers=headers_of(token), json={'display_name': 'Noa GG'}, timeout=30)
        assert r.status_code in (200, 204), r.text
        assert len(signups(admin, me)) == 1
        assert 'Noa G. (Noa Groupe) vient de créer son compte.' in signups(admin, me)[0]['body']
        assert not errors, errors

        # Il supprime son compte : tout part avec lui, ce « Nouveau compte » (son nom) aussi, chez chaque valideur.
        delete_account(token)
        assert signups(admin, me) == [], 'migration 20261114210000_nouveau_compte_suppression à appliquer sur la base de TEST'
    finally:
        try:
            delete_from_browser(page)
        finally:
            context.close()


def feed(party, token: str) -> str:
    r = httpx.get(f'{party}/api/calendar-feed/{token}.ics', timeout=30)
    assert r.status_code == 200, r.text
    return r.text


def test_a_new_account_from_a_shared_link_reloads_answers_present_and_fills_its_agenda(browser, party, admin):  # noqa: F811
    phone = PHONES[1]
    title, other = f'{PREFIX} soirée partagée', f'{PREFIX} autre soirée'
    event = create_event(admin, title, visibility='all', public_link=True, location_name='Salle de test, Vevey')
    second = create_event(admin, other, visibility='all', public_link=True, location_name='Salle de test, Vevey',
                          starts_at=(datetime.now(timezone.utc) + timedelta(days=33)).isoformat())
    admin.made['events'] += [event, second]

    context, page, errors = phone_page(browser)
    frame = page.frame_locator('#eventsFrame')
    try:
        page.goto(f'{party}/?tab=events&event={event}', wait_until='domcontentloaded')
        pw.expect(frame.get_by_text(title, exact=True).first).to_be_visible(timeout=30000)
        shot(page, '06-partage-sans-compte')
        frame.get_by_role('button', name=re.compile('^Se connecter')).first.click()
        sign_in(frame, page, local(phone))
        complete_profile(frame, 'Lou', 'Partage', 'Lou P.', page, '06a-partage-faisons-connaissance')
        pw.expect(frame.get_by_text('Tu viens ?', exact=True)).to_be_visible(timeout=30000)
        shot(page, '07-partage-fiche-apres-inscription')

        # Rechargée (iOS recharge l'app) : l'adresse garde l'événement, la fiche reste ouverte.
        page.reload(wait_until='domcontentloaded')
        assert page.evaluate('location.search') == f'?tab=events&event={event}'
        page.wait_for_function("() => (document.getElementById('eventsFrame')?.src || '').includes('/events/event/')", timeout=15000)
        assert page.evaluate("() => new URL(document.getElementById('eventsFrame').src).pathname") == f'/events/event/{event}'
        pw.expect(frame.get_by_text('Tu viens ?', exact=True)).to_be_visible(timeout=30000)
        frame.get_by_role('button', name=re.compile('^Présent')).first.click()
        pw.expect(frame.get_by_text('C’est noté, tu viens !', exact=True)).to_be_visible(timeout=15000)
        shot(page, '08-partage-recharge-present')
        token = browser_token(page)
        me = httpx.get(f'{TEST_URL}/auth/v1/user', headers=headers_of(token), timeout=30).json()['id']
        assert admin.get(f'rsvps?select=status&event_id=eq.{event}&user_id=eq.{me}').json() == [{'status': 'yes'}]

        # Agenda abonné : un toucher sur « Ajouter à mon agenda » l'active (ordinateur : Apple · Outlook).
        frame.get_by_role('button', name='Ajouter à mon agenda').first.click()
        frame.get_by_role('button', name='Apple · Outlook').click()
        page.wait_for_timeout(1500)
        r = httpx.post(f'{TEST_URL}/rest/v1/rpc/calendar_feed_token', headers=headers_of(token), json={'e': event}, timeout=30)
        assert r.status_code == 200 and r.json()['added'] is True, r.text
        feed_token = r.json()['token']
        ics = feed(party, feed_token)
        assert f'SUMMARY:{title}' in ics and other not in ics, ics
        shot(page, '09-agenda-active')

        # Présent ailleurs (première réponse, comme l'app) : l'événement entre tout seul ; Pas présent l'en retire ;
        # Peut-être : « [Peut-être] ».
        r = httpx.post(f'{TEST_URL}/rest/v1/rsvps', headers=headers_of(token), timeout=30,
                       json={'event_id': second, 'user_id': me, 'status': 'yes'})
        assert r.status_code in (200, 201, 204), r.text
        assert f'SUMMARY:{other}' in feed(party, feed_token)
        frame.get_by_role('button', name=re.compile('^Absent')).first.click()
        pw.expect(frame.get_by_text('Dommage ! Tu es noté absent.', exact=True)).to_be_visible(timeout=15000)
        assert title not in feed(party, feed_token).replace(other, '')
        shot(page, '10-agenda-pas-present')
        frame.get_by_role('button', name=re.compile('^Peut-être')).first.click()
        pw.expect(frame.get_by_text('Noté en peut-être. Pense à confirmer.', exact=True)).to_be_visible(timeout=15000)
        assert f'SUMMARY:[Peut-être] {title}' in feed(party, feed_token)
        shot(page, '11-agenda-peut-etre')

        assert len(signups(admin, me)) == 1
        assert not errors, errors
    finally:
        try:
            delete_from_browser(page)
        finally:
            context.close()


def test_a_new_account_votes_the_dates_of_a_public_poll_and_the_organizer_sees_when(browser, party, admin):  # noqa: F811
    phone = PHONES[2]
    title = f'{PREFIX} sondage'
    event = create_event(admin, title, visibility='all', public_link=True, date_mode='poll', starts_at=None)
    admin.made['events'].append(event)
    options = []
    for days in (21, 28):
        r = httpx.post(f'{TEST_URL}/rest/v1/date_options', timeout=30, headers={**admin.headers, 'Prefer': 'return=representation'},
                       json={'event_id': event, 'starts_at': (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()})
        assert r.status_code == 201, r.text
        options.append(r.json()[0]['id'])

    context, page, errors = phone_page(browser)
    try:
        page.goto(f'{party}/events/share/{event}', wait_until='domcontentloaded')
        pw.expect(page.get_by_text(title, exact=True)).to_be_visible(timeout=20000)
        pw.expect(page.get_by_role('button', name=re.compile('Présent'))).to_have_count(0)  # jamais « Présent » sur un sondage
        shot(page, '12-sondage-sans-compte')
        page.get_by_role('button', name='Se connecter pour choisir mes dates').click()
        sign_in(page, page, local(phone))
        complete_profile(page, 'Eli', 'Sondage', 'Eli S.', page, '12a-sondage-faisons-connaissance')
        page.wait_for_url(f'**/events/event/{event}', timeout=30000)
        pw.expect(page.get_by_text('Quelle date ?', exact=True)).to_be_visible(timeout=20000)
        pw.expect(page.get_by_role('button', name=re.compile('^Présent'))).to_have_count(0)
        page.get_by_role('button', name=re.compile('^Oui : ')).first.click()
        page.get_by_role('button', name=re.compile('^Non : ')).nth(1).click()
        pw.expect(page.get_by_text('1 votant', exact=True)).to_be_visible(timeout=15000)
        shot(page, '13-sondage-vote')
        token = browser_token(page)
        me = httpx.get(f'{TEST_URL}/auth/v1/user', headers=headers_of(token), timeout=30).json()['id']
        # La carte publique compte les votants (sans compte).
        anon = {'apikey': KEY_FILE.read_text().strip(), 'Content-Type': 'application/json'}
        public = httpx.post(f'{TEST_URL}/rest/v1/rpc/public_event', headers=anon, json={'e': event}, timeout=30).json()
        assert public['voters'] == 1, public
        assert len(signups(admin, me)) == 1
        assert not errors, errors

        # L'organisateur voit le vote et son heure, en petit après le nom.
        votes = admin.get(f'date_votes?select=option_id,vote,voted_at&user_id=eq.{me}').json()
        assert {v['option_id']: v['vote'] for v in votes} == {options[0]: 'yes', options[1]: 'no'}
        when = answer_time(next(v['voted_at'] for v in votes if v['option_id'] == options[0]))
        orga, opage, oerrors = signed_in_page(browser, party, admin.auth)
        try:
            opage.goto(f'{party}/events/event/{event}', wait_until='domcontentloaded')
            pw.expect(opage.get_by_text('Quelle date ?', exact=True)).to_be_visible(timeout=30000)
            pw.expect(opage.get_by_text(f'(Oui · {when})', exact=False).first).to_be_visible(timeout=15000)
            pw.expect(opage.get_by_text('Eli S.', exact=False).first).to_be_visible()
            shot(opage, '14-sondage-organisateur-heure-du-vote')
            assert not oerrors, oerrors
        finally:
            orga.close()
    finally:
        try:
            delete_from_browser(page)
        finally:
            context.close()
