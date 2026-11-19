"""Recette RÉELLE : un inconnu invité n'est JAMAIS coincé dans le module Événements ouvert seul (retour de l'admin du
19.11 : après « Voir l'événement », plus de barre d'onglets, aucun moyen de voir les autres événements ; il a fallu
changer l'adresse à la main). Vrai navigateur (écran d'iPhone 390×844), vrai serveur Party, base de TEST, réglages de
prod (Invitations v2 allumées, Zicou / Discussions / Bar éteints, CGU exigées). Deux comptes NEUFS (numéros de test à
code fixe jamais inscrits, comme test_nouveaux_comptes_invitation_browser_live.py), supprimés à la fin avec tout le reste.

a. lien d'invitation → « Je viens ! » → connexion SMS → « Faisons connaissance » → CGU → « Voir l'événement » : la
   page Party (barre d'onglets), la fiche dans le cadre ; l'onglet Événements montre la liste (un autre événement public) ;
b. même chose avec « Peut-être » puis « Je ne peux pas », sur deux autres événements ;
c. /events/event/<id>, /events/, /events/groups, /events/pronos ouverts en page principale : renvoyés dans Party, même
   page, dans le cadre ; recharger la page la garde ;
d. lien d'invitation de groupe (/events/group-invite/<jeton>) : il rejoint le groupe et arrive dans Party (cadre) ;
e. « Demande envoyée » (événement sans lien public, lien d'un invité) → « Découvrir Party » → Party, la liste.

Lancement : SUPABASE_LIVE_TESTS=1 PARTY_TEST_EVENTS_DIST=<module construit contre la base de test> python -m pytest <ce fichier>
Captures de chaque étape dans $IMPASSES_SHOTS si la variable est définie."""
import os
import random
import time
from pathlib import Path

import httpx
import pytest

from tests.supabase_live.party_shell import PARTY, in_party, party_event, party_path, where_visible
from tests.supabase_live.test_audiences_live import GUEST_A, create_event
from tests.supabase_live.test_inscription_complete_browser_live import browser, complete_profile, party, sign_in  # noqa: F401
from tests.supabase_live.test_invitations_v2_live import terms_version
from tests.supabase_live.test_member_admin_live import ADMIN_PHONE, KEY_FILE, TEST_URL, Session, pytestmark as live
from tests.supabase_live.test_nouveaux_comptes_invitation_browser_live import (NEW_PHONES, browser_token, login_raw, national,
                                                                              open_card, phone_context, rpc)

pw = pytest.importorskip('playwright.sync_api')
DIST = Path(os.environ.get('PARTY_TEST_EVENTS_DIST') or '/nonexistent')
pytestmark = [live, pytest.mark.skipif(not (DIST / 'index.html').exists(),
                                        reason='PARTY_TEST_EVENTS_DIST : module construit contre la base de test')]
SHOTS = Path(os.environ['IMPASSES_SHOTS']) if os.environ.get('IMPASSES_SHOTS') else None
ADDRESS = 'Rue des Impasses 3, 1200 Genève'
PUBLIC = 'Impasses : concert public'  # l'« autre » événement, qu'on doit pouvoir trouver dans la liste


def shot(page, name: str):
    if SHOTS:
        page = getattr(page, 'page', page)  # cadre du module : capture de toute la page Party
        page.wait_for_timeout(900)
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f'{name}.png'))


@pytest.fixture(scope='module')
def world(browser, party):  # noqa: F811
    raw = login_raw(ADMIN_PHONE)
    org = Session.__new__(Session)
    org.uid = raw['user']['id']
    org.headers = {'apikey': KEY_FILE.read_text().strip(), 'Content-Type': 'application/json',
                   'Authorization': f"Bearer {raw['access_token']}"}
    terms = org.rpc('my_terms').json()
    assert terms['accepted'] or org.rpc('accept_terms', p_version=terms['version']).status_code in (200, 204)
    used = {r['phone'] for r in org.rpc('admin_member_list').json() if r.get('phone')}
    fresh = [p for p in NEW_PHONES if p not in used]
    assert len(fresh) >= 2, f'plus assez de numéros de test neufs (déjà inscrits : {sorted(set(NEW_PHONES) & used)})'
    phones = dict(zip('ab', random.sample(fresh, 2)))
    state = {'org': org, 'phones': phones, 'events': [], 'tokens': {}, 'contexts': [], 'group': None}
    try:
        ev = lambda title, **f: state['events'].append(create_event(org, title, **f)) or state['events'][-1]  # noqa: E731
        state['public'] = ev(PUBLIC, visibility='all', public_link=True, location_name='Parc', location_address=ADDRESS)
        for key, title in (('yes', 'Impasses : soirée'), ('maybe', 'Impasses : brunch'), ('no', 'Impasses : apéro')):
            e = ev(title, visibility='invited', public_link=False, location_name='Chez Olga', location_address=ADDRESS)
            link = org.rpc('create_event_invite', e=e, places=0, label=f'Impasses {key}')
            assert link.status_code == 200, link.text
            state[key] = (e, title, link.json()['token'])
        # « Demande envoyée » : événement sans lien public ; Testeur 1 invité crée SON lien (accord de l'organisateur).
        guest = Session(GUEST_A)
        assert guest.rpc('accept_terms', p_version=terms_version()).status_code in (200, 204)
        e = ev('Impasses : sur accord', visibility='invited', public_link=False)
        assert org.rpc('invite_people', e=e, people=[guest.uid], groups=[]).status_code == 200
        state['accord'] = (e, guest.rpc('create_event_invite', e=e, places=1, label='Impasses accord').json()['token'])
        # Groupe de l'organisateur et son lien d'invitation (fonctions de la base, comme l'app).
        r = httpx.post(f'{TEST_URL}/rest/v1/member_groups', timeout=30, headers={**org.headers, 'Prefer': 'return=representation'},
                       json={'name': 'Impasses recette', 'emoji': '⚽', 'color': 'mint', 'created_by': org.uid})
        assert r.status_code == 201, r.text
        state['group'] = r.json()[0]['id']
        link = org.rpc('group_invite_link', grp=state['group'])
        assert link.status_code == 200, link.text
        state['group_token'] = link.json()
        yield state
    finally:
        for c in state['contexts']:
            c.close()
        left = []
        for e in state['events']:
            r = httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{e}', timeout=60, headers={**org.headers, 'Prefer': 'return=representation'})
            if not (r.status_code == 200 and len(r.json()) == 1):
                left.append(f'événement {e} : {r.status_code} {r.text}')
        if state['group']:
            r = httpx.delete(f"{TEST_URL}/rest/v1/member_groups?id=eq.{state['group']}", timeout=60,
                             headers={**org.headers, 'Prefer': 'return=representation'})
            if not (r.status_code == 200 and len(r.json()) == 1):
                left.append(f"groupe {state['group']} : {r.status_code} {r.text}")
        for who, jwt in state['tokens'].items():  # comptes neufs supprimés : leurs numéros resservent
            for _ in range(2):
                r = rpc(jwt, 'delete_my_account')
                if r.status_code in (200, 204):
                    break
                time.sleep(5)
            else:
                left.append(f"compte {state['phones'][who]} : {r.text}")
        assert not left, left


def person(world, browser):  # noqa: F811
    context, page, errors = phone_context(browser)
    world['contexts'].append(context)
    return page, errors


def sees_the_list(page):
    """Dans Party, l'onglet Événements (retouché si on y est déjà) montre la liste : l'autre événement public y est."""
    page.locator('#tabs [data-tab="events"]').click()
    frame = in_party(page, '/events/')
    pw.expect(frame.get_by_text(PUBLIC, exact=True).first).to_be_visible(timeout=30000)
    return frame


def answer_from_card(page, party: str, world: dict, key: str, label: str, shots: str):  # noqa: F811
    """Compte déjà connecté : la carte d'invitation (seule, comme le lien reçu) → réponse → « Voir l'événement »."""
    e, title, token = world[key]
    open_card(page, f'{party}/events/invite/{token}')
    page.get_by_role('button', name=label, exact=True).click()
    pw.expect(page.get_by_text('C’est noté', exact=False).first).to_be_visible(timeout=30000)
    shot(page, f'{shots}-1-c-est-note')
    page.get_by_role('button', name='Voir l’événement', exact=True).click()
    fiche = in_party(page, f'/events/event/{e}')
    pw.expect(fiche.get_by_text(title, exact=True).first).to_be_visible(timeout=30000)
    shot(page, f'{shots}-2-fiche-dans-party')
    return fiche


def test_a_a_stranger_answers_yes_and_lands_in_party_with_the_tab_bar_and_the_list(browser, party, world):  # noqa: F811
    page, errors = person(world, browser)
    world['a'] = page
    e, title, token = world['yes']
    open_card(page, f'{party}/events/invite/{token}')
    shot(page, 'a-1-carte-sans-compte')
    page.get_by_role('button', name='Je viens !').click()
    page.wait_for_url('**/sign-in', timeout=20000)
    sign_in(page, national(world['phones']['a']))
    here = where_visible(page, 'Faisons connaissance')
    world['tokens']['a'] = browser_token(page)  # compte créé : supprimé à la fin, même si la suite échoue
    shot(page, 'a-2-faisons-connaissance')
    complete_profile(here, 'Inès', 'Neuve', 'Inès N.')
    # L'invitation reprend (intention gardée) : la réponse « Je viens ! » part seule, l'adresse s'affiche.
    pw.expect(here.get_by_text('C’est noté, Inès !', exact=True)).to_be_visible(timeout=30000)
    pw.expect(here.get_by_text(ADDRESS, exact=True)).to_be_visible()
    shot(page, 'a-3-c-est-note')
    here.get_by_role('button', name='Voir l’événement', exact=True).click()
    fiche = in_party(page, f'/events/event/{e}')  # Party autour : barre d'onglets, la fiche dans le cadre
    assert PARTY.match(page.url) and page.url.endswith(f'event={e}'), page.url
    pw.expect(fiche.get_by_text(title, exact=True).first).to_be_visible(timeout=30000)
    pw.expect(fiche.get_by_text(ADDRESS, exact=False).first).to_be_visible()
    for tab in ('Musique', 'Jeux', 'Événements', 'Réglages'):
        pw.expect(page.locator('#tabs').get_by_role('button', name=tab, exact=False).first).to_be_visible()
    shot(page, 'a-4-fiche-dans-party')
    listing = sees_the_list(page)
    pw.expect(listing.get_by_text(title, exact=True).first).to_be_visible()  # son invitation y est aussi
    shot(page, 'a-5-liste-des-evenements')
    assert not errors, errors
    rsvp = world['org'].rpc('event_guest_list', e=e).json()['people']
    assert [p['status'] for p in rsvp if p['name'] == 'Inès N.'] == ['yes'], rsvp


@pytest.mark.parametrize('key,label', [('maybe', 'Peut-être'), ('no', 'Je ne peux pas')])
def test_b_maybe_and_cannot_come_also_land_in_party(browser, party, world, key, label):  # noqa: F811
    page = world['a']
    answer_from_card(page, party, world, key, label, f'b-{key}')
    sees_the_list(page)
    shot(page, f'b-{key}-3-liste')
    e = world[key][0]
    rsvp = world['org'].rpc('event_guest_list', e=e).json()['people']
    assert [p['status'] for p in rsvp if p['name'] == 'Inès N.'] == [key], rsvp


def test_c_module_pages_opened_alone_go_back_into_party_and_survive_a_reload(browser, party, world):  # noqa: F811
    page = world['a']
    e = world['yes'][0]
    cases = [(f'/events/event/{e}', f'/events/event/{e}', party_event(e)), ('/events/', '/events/', None),
             ('/events/groups', '/events/groups', party_path('/groups')), ('/events/pronos', '/events/pronos', party_path('/pronos'))]
    for n, (opened, framed, address) in enumerate(cases):
        page.goto(f'{party}{opened}', wait_until='domcontentloaded')
        in_party(page, framed)
        if address:
            assert address.match(page.url), page.url
        shot(page, f'c-{n}-{framed.strip("/").replace("/", "-") or "liste"}')
        page.reload(wait_until='domcontentloaded')
        frame = in_party(page, framed)  # même page après le rechargement (adresse gardée par index.html)
        if address:
            assert address.match(page.url), page.url
        if framed == f'/events/event/{e}':
            pw.expect(frame.get_by_text(world['yes'][1], exact=True).first).to_be_visible(timeout=30000)
        if framed == '/events/':
            pw.expect(frame.get_by_text(PUBLIC, exact=True).first).to_be_visible(timeout=30000)


def test_d_a_group_invitation_link_lands_in_the_group_inside_party(browser, party, world):  # noqa: F811
    page = world['a']
    page.goto(f"{party}/events/group-invite/{world['group_token']}", wait_until='domcontentloaded')
    frame = in_party(page, f"/events/group/{world['group']}", timeout=45000)
    assert party_path(f"/group/{world['group']}").match(page.url), page.url
    pw.expect(frame.get_by_text('Impasses recette', exact=False).first).to_be_visible(timeout=30000)
    shot(page, 'd-1-groupe-dans-party')
    members = httpx.get(f"{TEST_URL}/rest/v1/member_group_members?group_id=eq.{world['group']}&select=user_id", timeout=30,
                        headers=world['org'].headers)
    assert members.status_code == 200 and len(members.json()) >= 2, members.text  # l'organisateur et Inès
    sees_the_list(page)
    shot(page, 'd-2-liste')


def test_e_request_sent_then_discover_party(browser, party, world):  # noqa: F811
    page, errors = person(world, browser)
    e, token = world['accord']
    open_card(page, f'{party}/events/invite/{token}')
    pw.expect(page.get_by_text('accepte chaque invité', exact=False)).to_be_visible(timeout=30000)
    page.get_by_role('button', name='Je viens !').click()
    page.wait_for_url('**/sign-in', timeout=20000)
    sign_in(page, national(world['phones']['b']))
    here = where_visible(page, 'Faisons connaissance')
    world['tokens']['b'] = browser_token(page)
    complete_profile(here, 'Basile', 'Neuf', 'Basile N.')
    pw.expect(here.get_by_text('Demande envoyée', exact=True)).to_be_visible(timeout=30000)
    pw.expect(here.get_by_role('button', name='Voir l’événement', exact=True)).to_have_count(0)
    shot(page, 'e-1-demande-envoyee')
    here.get_by_role('button', name='Découvrir Party', exact=True).click()
    frame = in_party(page, '/events/')
    pw.expect(frame.get_by_text(PUBLIC, exact=True).first).to_be_visible(timeout=30000)
    shot(page, 'e-2-party-liste')
    assert not errors, errors
