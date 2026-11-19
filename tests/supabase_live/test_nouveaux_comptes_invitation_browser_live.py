"""Recette RÉELLE des NOUVEAUX COMPTES venus par un lien d'invitation d'événement (campagne du 14.11.2026) : vrai navigateur
(écran d'iPhone 390×844), vrai serveur Party, base de TEST, réglages de prod (Invitations v2 allumées, Zicou, Discussions
et Bar éteints, CGU exigées). Chaque passage prend des numéros de test NEUFS (41790000 2xx jamais inscrits, lus dans la
liste des membres de l'admin de test) et les supprime à la fin (« Supprimer mon compte »), avec les événements créés.
Aucun SQL : tout passe par l'app et les fonctions de la base, comme un vrai utilisateur.

1. L'organisateur (admin de test) a un événement « sur invitation » (sans notification) ; dans l'app, il crée un lien
   « Plusieurs » nommé. Un compte NEUF l'ouvre → connexion normale (pays, numéro, code) → « Faisons connaissance »
   (prénom, nom, surnom court, sans photo) → CGU → sa réponse « Je viens ! » part seule → l'adresse → la fiche.
2. Ce nouvel invité crée SON lien ; un 2e compte neuf l'ouvre → attend l'accord (ni fiche ni adresse) → l'organisateur
   accepte dans « À accepter » → il voit la fiche. Un 3e compte neuf : refusé → ne voit jamais rien.
3. Événement public : le lien d'un invité fait entrer directement un 4e compte neuf.
4. Lien « Plusieurs » à 2 places plein ; lien arrêté par l'organisateur (« Arrêter ») : la carte le dit, sans compte.

Lancement : SUPABASE_LIVE_TESTS=1 PARTY_TEST_EVENTS_DIST=<module construit contre la base de test> python -m pytest <ce fichier>
Captures de chaque étape dans $NOUVEAUX_SHOTS si la variable est définie."""
import json
import os
import random
import re
import time
from pathlib import Path

import httpx
import pytest

from tests.supabase_live.party_shell import in_party, where_visible
from tests.supabase_live.test_inscription_complete_browser_live import browser, complete_profile, party, sign_in  # noqa: F401
from tests.supabase_live.test_member_admin_live import ADMIN_PHONE, KEY_FILE, OTP, TEST_URL, Session, pytestmark as live
from tests.supabase_live.test_audiences_live import create_event

pw = pytest.importorskip('playwright.sync_api')
DIST = Path(os.environ.get('PARTY_TEST_EVENTS_DIST') or '/nonexistent')
pytestmark = [live, pytest.mark.skipif(not (DIST / 'index.html').exists(),
                                        reason='PARTY_TEST_EVENTS_DIST : module construit contre la base de test')]
SHOTS = Path(os.environ['NOUVEAUX_SHOTS']) if os.environ.get('NOUVEAUX_SHOTS') else None
STORAGE_KEY = f"sb-{httpx.URL(TEST_URL).host.split('.')[0]}-auth-token"  # clé de session de supabase-js (AsyncStorage web)
ADDRESS = 'Rue des Recettes 12, 1200 Genève'
CLOSED = 'Cet événement n’existe plus ou ne t’est pas ouvert.'  # fiche d'un événement qu'on ne voit pas
# Numéros à code fixe réservés à cette recette (base de TEST) ; un compte créé ici est supprimé à la fin.
NEW_PHONES = [f'417900002{n:02d}' for n in range(1, 11)]
PEOPLE = {  # surnoms de 12 caractères au plus
    'a': ('Anouk', 'Neuve', 'Anouk N.'), 'b': ('Bastien', 'Neuf', 'Bastien N.'),
    'c': ('Chloé', 'Neuve', 'Chloé N.'), 'd': ('Dario', 'Neuf', 'Dario N.'),
}


def shot(page, name: str):
    if SHOTS:
        page = getattr(page, 'page', page)  # cadre du module dans Party : capture de toute la page
        page.wait_for_timeout(800)
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f'{name}.png'), full_page=True)


def national(phone: str) -> str:
    """41790000207 → « 079 000 02 07 », comme on le tape sur la page de connexion (Suisse +41)."""
    n = '0' + phone[2:]
    return f'{n[:3]} {n[3:6]} {n[6:8]} {n[8:]}'


def login_raw(phone: str) -> dict:
    """Connexion par code fixe ; rend la session complète (à poser dans le navigateur de l'organisateur)."""
    base = {'apikey': KEY_FILE.read_text().strip(), 'Content-Type': 'application/json'}
    for _ in range(2):  # limite d'Auth par adresse (toutes les recettes sortent par la même) : 3 min, puis UN nouvel essai
        sent = httpx.post(f'{TEST_URL}/auth/v1/otp', headers=base, json={'phone': phone}, timeout=30)
        if sent.status_code != 429:
            break
        time.sleep(180)
    if sent.status_code == 429:
        pytest.skip('non vérifié : limite de demandes de code de la base de TEST (même adresse IP pour toutes les recettes)')
    assert sent.status_code == 200, sent.text
    r = httpx.post(f'{TEST_URL}/auth/v1/verify', headers=base, json={'type': 'sms', 'phone': phone, 'token': OTP}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


def rpc(jwt: str, name: str, **args) -> httpx.Response:
    return httpx.post(f'{TEST_URL}/rest/v1/rpc/{name}', json=args, timeout=60,
                      headers={'apikey': KEY_FILE.read_text().strip(), 'Authorization': f'Bearer {jwt}'})


def browser_token(page) -> str:
    """Jeton du compte connecté dans ce navigateur (pour le supprimer à la fin, sans redemander de code)."""
    raw = page.evaluate(f'localStorage.getItem({json.dumps(STORAGE_KEY)})')
    assert raw, 'aucune session dans le navigateur'
    return json.loads(raw)['access_token']


def phone_context(browser, session: dict | None = None):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark', locale='fr-CH')
    if session:  # organisateur : sa session posée une fois (jamais réécrite : supabase-js renouvelle ses jetons)
        context.add_init_script(f'if (!localStorage.getItem({json.dumps(STORAGE_KEY)})) '
                                f'localStorage.setItem({json.dumps(STORAGE_KEY)}, {json.dumps(json.dumps(session))});')
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    return context, page, errors


@pytest.fixture(scope='module')
def world(browser, party):  # noqa: F811
    """Organisateur connecté dans son navigateur ; événement privé « sur invitation » ; 4 numéros neufs."""
    raw = login_raw(ADMIN_PHONE)  # une seule demande de code pour l'organisateur (limite d'Auth par numéro et par adresse)
    organizer = Session.__new__(Session)
    organizer.uid = raw['user']['id']
    organizer.headers = {'apikey': KEY_FILE.read_text().strip(), 'Content-Type': 'application/json',
                         'Authorization': f"Bearer {raw['access_token']}"}
    terms = organizer.rpc('my_terms').json()  # sans SQL : la version en cours, comme l'app
    assert terms['accepted'] or organizer.rpc('accept_terms', p_version=terms['version']).status_code in (200, 204)
    used = {r['phone'] for r in organizer.rpc('admin_member_list').json() if r.get('phone')}
    fresh = [p for p in NEW_PHONES if p not in used]
    assert len(fresh) >= 4, f'plus assez de numéros de test neufs (déjà inscrits : {sorted(set(NEW_PHONES) & used)})'
    phones = dict(zip('abcd', random.sample(fresh, 4)))
    context, page, errors = phone_context(browser, raw)
    context.grant_permissions(['clipboard-read', 'clipboard-write'], origin=party)
    private = create_event(organizer, 'Soirée nouveaux comptes', visibility='invited', public_link=False,
                           location_name='Chez Olga', location_address=ADDRESS)
    state = {'organizer': organizer, 'org_page': page, 'org_errors': errors, 'phones': phones, 'private': private,
             'events': [private], 'tokens': {}, 'contexts': [context]}
    yield state
    for c in state['contexts']:
        c.close()
    left = []  # tout est tenté, même après un échec (base lente : « statement timeout ») ; un seul nouvel essai
    for e in state['events']:
        for _ in range(2):
            r = httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{e}', timeout=60,
                             headers={**organizer.headers, 'Prefer': 'return=representation'})
            if r.status_code == 200 and len(r.json()) == 1:  # vraiment supprimé (RLS : sinon 0 ligne, sans erreur)
                break
            time.sleep(5)
        else:
            left.append(f'événement {e} : {r.text}')
    for who, jwt in state['tokens'].items():  # les comptes neufs sont supprimés : leurs numéros resservent
        for _ in range(2):
            r = rpc(jwt, 'delete_my_account')
            if r.status_code in (200, 204):
                break
            time.sleep(5)
        else:
            left.append(f"compte {state['phones'][who]} : {r.text}")
    assert not left, left


def new_person(state: dict, browser, who: str):  # noqa: F811
    context, page, errors = phone_context(browser)
    state['contexts'].append(context)
    return context, page, errors


def open_event_as_organizer(state: dict, party: str, event: str):  # noqa: F811
    """La fiche ouverte par son adresse du module : renvoyée dans Party (cadre, barre d'onglets). Rend le cadre."""
    page = state['org_page']
    page.goto(f'{party}/events/event/{event}', wait_until='domcontentloaded')
    frame = in_party(page, f'/events/event/{event}')
    card = frame.get_by_label('Invités', exact=True)
    pw.expect(card.get_by_text(re.compile(r'^Invités · \d+$'))).to_be_visible(timeout=60000)
    return frame, card


def open_card(page, url: str):
    """Ouvre la carte d'invitation comme un invité. Base de TEST surchargée (recettes en parallèle : « statement
    timeout ») : l'app dit « Connexion difficile » avec « Réessayer » ; on touche « Réessayer » une fois, comme lui."""
    page.goto(url, wait_until='domcontentloaded')
    trouble = page.get_by_text('Connexion difficile', exact=True)
    pw.expect(trouble.or_(page.get_by_text('t’invite', exact=False))).to_be_visible(timeout=30000)
    if trouble.is_visible():
        page.get_by_role('button', name='Réessayer').click()
        pw.expect(page.get_by_text('t’invite', exact=False)).to_be_visible(timeout=30000)


def rpc_ok(jwt: str, name: str, **args) -> httpx.Response:
    """Appel à la base ; un seul nouvel essai sur « statement timeout » (base de TEST surchargée, annulé sans effet)."""
    r = rpc(jwt, name, **args)
    if r.status_code == 500 and '57014' in r.text:
        time.sleep(5)
        r = rpc(jwt, name, **args)
    return r


def copy_new_link(page, title: str, name: str):
    """Feuille « Inviter » : lien « Plusieurs » nommé, « Copier » → le lien (presse-papiers) → son jeton."""
    page.get_by_label('Invités', exact=True).get_by_role('button', name='Inviter', exact=True).click()
    sheet = page.get_by_label(f'Inviter à {title}')
    sheet.get_by_role('tab', name='Plusieurs').click()
    sheet.get_by_label('Nom du lien (facultatif)').fill(name)
    pw.expect(sheet.get_by_label('Sans limite', exact=True).first).to_be_visible()  # ∞ par défaut (11.11)
    top = getattr(page, 'page', page)  # presse-papiers lu par la page (le cadre du module est de la même origine)
    top.evaluate('navigator.clipboard.writeText("")')
    sheet.get_by_role('button', name='Copier').click()
    pw.expect(sheet.get_by_text('✓ Lien prêt', exact=False)).to_be_visible(timeout=15000)
    url = top.evaluate('navigator.clipboard.readText()')
    m = re.search(r'/events/invite/([0-9a-f-]{36})$', url)
    assert m, url
    return m.group(1), sheet


def answer_as_new_account(state: dict, who: str, page, party: str, token: str, shots: str):
    """Compte neuf : la carte (sans compte) → « Je viens ! » → connexion normale → « Faisons connaissance » → CGU.
    Rend l'endroit où le module continue (la page, ou le cadre de Party : voir party_shell.where_visible)."""
    open_card(page, f'{party}/events/invite/{token}')
    pw.expect(page.get_by_role('button', name='Je viens !')).to_be_visible(timeout=30000)
    assert page.get_by_text(ADDRESS, exact=False).count() == 0  # l'adresse exacte seulement après la réponse
    shot(page, f'{shots}-1-carte-sans-compte')
    page.get_by_role('button', name='Je viens !').click()
    page.wait_for_url('**/sign-in', timeout=20000)
    shot(page, f'{shots}-2-connexion')
    sign_in(page, national(state['phones'][who]))
    here = where_visible(page, 'Faisons connaissance')
    state['tokens'][who] = browser_token(page)  # compte créé : supprimé à la fin, même si la suite échoue
    shot(page, f'{shots}-3-faisons-connaissance')
    complete_profile(here, *PEOPLE[who])
    return here


def test_0_the_organizer_creates_a_named_several_link(party, world):  # noqa: F811
    page, _card = open_event_as_organizer(world, party, world['private'])
    token, sheet = copy_new_link(page, 'Soirée nouveaux comptes', 'Copains du foot')
    shot(page, '0-organisateur-lien-plusieurs')
    sheet.get_by_role('button', name='Fermer').first.click()
    links = {l['label']: l for l in world['organizer'].rpc('event_guest_list', e=world['private']).json()['links']}
    assert links['Copains du foot']['token'] == token and links['Copains du foot']['max_uses'] == 10000, links
    world['org_link'] = token
    assert not world['org_errors'], world['org_errors']


def test_1_a_new_account_answers_the_organizers_several_link_and_sees_the_address_and_the_event(browser, party, world):  # noqa: F811
    token = world['org_link']
    context, guest, errors = new_person(world, browser, 'a')
    context.grant_permissions(['clipboard-read', 'clipboard-write'], origin=party)
    here = answer_as_new_account(world, 'a', guest, party, token, '1')
    pw.expect(here.get_by_text('C’est noté, Anouk !', exact=True)).to_be_visible(timeout=30000)
    pw.expect(here.get_by_text(ADDRESS, exact=True)).to_be_visible()
    shot(guest, '1-4-c-est-note-adresse')
    here.get_by_role('button', name='Voir l’événement', exact=True).click()
    fiche = in_party(guest, f"/events/event/{world['private']}")  # la fiche DANS Party, barre d'onglets
    world['a_page'] = fiche
    pw.expect(fiche.get_by_text('Soirée nouveaux comptes', exact=True).first).to_be_visible(timeout=30000)
    pw.expect(fiche.get_by_text(ADDRESS, exact=False).first).to_be_visible()
    # Sans accompagnant ni groupe : jamais « réservé aux membres du groupe » (texte faux vu le 14.11 sur cette fiche).
    pw.expect(fiche.get_by_text('Pas d’accompagnant pour cet événement.', exact=True)).to_be_visible()
    shot(guest, '1-5-fiche')
    assert not errors, errors

    listed = {p['id']: p for p in world['organizer'].rpc('event_guest_list', e=world['private']).json()['people']}
    (me,) = [p for p in listed.values() if p['name'] == 'Anouk N.']
    assert me['source'] == 'link' and me['status'] == 'yes', me


def test_2_a_new_account_from_a_guests_link_waits_then_is_accepted(browser, party, world):  # noqa: F811
    guest = world['a_page']
    token, sheet = copy_new_link(guest, 'Soirée nouveaux comptes', 'Mes collègues')
    pw.expect(sheet.get_by_text('Chaque personne que tu invites attend l’accord de l’organisateur', exact=False)).to_be_visible()
    shot(guest, '2-0-invite-cree-son-lien')
    sheet.get_by_role('button', name='Fermer').first.click()
    world['guest_link'] = token

    _context, page, errors = new_person(world, browser, 'b')
    world['b_page'] = page
    here = answer_as_new_account(world, 'b', page, party, token, '2b')
    pw.expect(here.get_by_text('Demande envoyée', exact=True)).to_be_visible(timeout=30000)
    assert here.get_by_text(ADDRESS, exact=False).count() == 0
    shot(page, '2b-4-demande-envoyee')
    page.goto(f"{party}/events/event/{world['private']}", wait_until='domcontentloaded')
    fiche = in_party(page, f"/events/event/{world['private']}")
    pw.expect(fiche.get_by_text(CLOSED, exact=True)).to_be_visible(timeout=30000)
    assert fiche.get_by_text(ADDRESS, exact=False).count() == 0  # ni fiche ni adresse avant l'accord
    shot(page, '2b-5-fiche-fermee-avant-accord')

    org, card = open_event_as_organizer(world, party, world['private'])
    pw.expect(card.get_by_text('Bastien N. attend ton accord', exact=True)).to_be_visible(timeout=30000)
    shot(org, '2b-6-organisateur-a-accepter')
    card.get_by_role('button', name='Accepter Bastien N.').click()
    pw.expect(org.get_by_text('Bastien N. est invité : il voit l’événement', exact=True)).to_be_visible(timeout=15000)
    shot(org, '2b-7-organisateur-accepte')

    page.reload(wait_until='domcontentloaded')  # Party garde la fiche au rechargement
    fiche = in_party(page, f"/events/event/{world['private']}")
    pw.expect(fiche.get_by_text(ADDRESS, exact=False).first).to_be_visible(timeout=30000)
    shot(page, '2b-8-fiche-apres-accord')
    assert not errors, errors


def test_2_a_new_account_refused_never_sees_the_event(browser, party, world):  # noqa: F811
    _context, page, errors = new_person(world, browser, 'c')
    here = answer_as_new_account(world, 'c', page, party, world['guest_link'], '2c')
    pw.expect(here.get_by_text('Demande envoyée', exact=True)).to_be_visible(timeout=30000)

    org, card = open_event_as_organizer(world, party, world['private'])
    pw.expect(card.get_by_text('Chloé N. attend ton accord', exact=True)).to_be_visible(timeout=30000)
    card.get_by_role('button', name='Refuser Chloé N.').click()
    card.get_by_role('button', name='Confirmer le refus de Chloé N.').click()
    pw.expect(org.get_by_text('Chloé N. ne verra pas l’événement', exact=True)).to_be_visible(timeout=15000)
    shot(org, '2c-5-organisateur-refuse')

    open_card(page, f"{party}/events/invite/{world['guest_link']}")
    pw.expect(page.get_by_text('n’a pas pu accepter ta venue cette fois', exact=False)).to_be_visible(timeout=30000)
    pw.expect(page.get_by_role('button', name='Je viens !')).to_have_count(0)
    shot(page, '2c-6-carte-refusee')
    page.goto(f"{party}/events/event/{world['private']}", wait_until='domcontentloaded')
    fiche = in_party(page, f"/events/event/{world['private']}")
    pw.expect(fiche.get_by_text(CLOSED, exact=True)).to_be_visible(timeout=30000)
    assert fiche.get_by_text(ADDRESS, exact=False).count() == 0
    shot(page, '2c-7-fiche-fermee')
    assert not errors, errors


def test_3_a_guests_link_to_a_public_event_lets_a_new_account_in_directly(browser, party, world):  # noqa: F811
    public = create_event(world['organizer'], 'Fête publique nouveaux', visibility='all', public_link=True,
                          location_name='Parc', location_address=ADDRESS)
    world['events'].append(public)
    world['public'] = public
    made = rpc_ok(world['tokens']['a'], 'create_event_invite', e=public, places=0, label='Voisins')  # lien d'un simple invité
    assert made.status_code == 200, made.text

    _context, page, errors = new_person(world, browser, 'd')
    open_card(page, f"{party}/events/invite/{made.json()['token']}")
    pw.expect(page.get_by_role('button', name='Je viens !')).to_be_visible(timeout=30000)
    pw.expect(page.get_by_text('accepte chaque invité', exact=False)).to_have_count(0)  # public : aucun accord
    here = answer_as_new_account(world, 'd', page, party, made.json()['token'], '3')
    pw.expect(here.get_by_text('C’est noté, Dario !', exact=True)).to_be_visible(timeout=30000)
    pw.expect(here.get_by_text(ADDRESS, exact=True)).to_be_visible()
    here.get_by_role('button', name='Voir l’événement', exact=True).click()
    fiche = in_party(page, f'/events/event/{public}')
    pw.expect(fiche.get_by_text(ADDRESS, exact=False).first).to_be_visible(timeout=30000)
    shot(page, '3-5-fiche-publique')
    assert not errors, errors


def test_4_a_full_several_link_says_so_without_an_account(browser, party, world):  # noqa: F811
    # Lien « Plusieurs » à 2 places (le minimum de l'app) sur l'événement public : Bastien et Chloé (inscrits, pas encore
    # venus à cet événement) prennent les 2 places ; la 3e personne lit « déjà servi » avant même de se connecter.
    two = world['organizer'].rpc('create_event_invite', e=world['public'], places=2, label='Deux places').json()['token']
    for who in ('b', 'c'):
        r = rpc_ok(world['tokens'][who], 'accept_invite', token=two, answer='yes')
        assert r.status_code == 200 and not r.json().get('pending'), r.text
    _context, page, errors = new_person(world, browser, 'x')
    open_card(page, f'{party}/events/invite/{two}')
    pw.expect(page.get_by_text('Ce lien a déjà servi : toutes ses places sont prises.', exact=False)).to_be_visible(timeout=30000)
    pw.expect(page.get_by_role('button', name='Je viens !')).to_have_count(0)
    shot(page, '4-1-lien-plein')
    assert not errors, errors


def test_4_b_a_stopped_link_says_so_without_an_account(browser, party, world):  # noqa: F811
    o, card = open_event_as_organizer(world, party, world['private'])
    card.get_by_role('button', name='Voir le détail des invités').click()
    stop = card.get_by_role('button', name=re.compile('^Arrêter .*Copains du foot'))
    stop.click()
    card.get_by_role('button', name=re.compile('^Confirmer .*Copains du foot')).click()
    pw.expect(card.get_by_role('button', name=re.compile('^Arrêter .*Copains du foot'))).to_have_count(0, timeout=15000)
    shot(o, '4-2-organisateur-arrete')

    _context, page, errors = new_person(world, browser, 'y')
    open_card(page, f"{party}/events/invite/{world['org_link']}")
    pw.expect(page.get_by_text('La personne qui t’a invité a arrêté ce lien.', exact=False)).to_be_visible(timeout=30000)
    pw.expect(page.get_by_role('button', name='Je viens !')).to_have_count(0)
    shot(page, '4-3-lien-arrete')
    assert not errors, errors
    assert not world['org_errors'], world['org_errors']
