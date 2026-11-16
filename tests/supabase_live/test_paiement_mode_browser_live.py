"""Recette RÉELLE du mode de paiement (maquette du 15.11.2026, migration 20261115120000) : vrai navigateur (390 × 844),
vrai serveur Party, base de TEST, comptes de test à code fixe, réglages de prod (Invitations v2, CGU exigées, Zicou,
discussions et bar éteints). Événement « sur invitation », sans annonce : seuls les comptes de test le voient.

Comptes : Admin test (organisateur, admin), VIP test (simple membre, Membre VIP le temps de la recette, puis
co-organisateur), Guest A et Guest B (Guest). Parcours, dans l'ordre :
1. formulaire : les trois choix, erreurs (en ligne sans lien, lien http, lien avec une espace), « On me paie » + Revolut ;
2. « On me paie » : l'invité ouvre le lien, « J'ai payé », « Annuler », de nouveau ; l'organisateur est prévenu,
   « Reçu ✓ » et « Pas reçu » ;
3. événement publié modifié en « Paiement en ligne » + Billets QR : billetterie, « J'ai payé », « Reçu ✓ » remet le billet,
   l'écran d'entrée lit le code court ;
4. « Sur place » : aucun bouton (la base refuse « J'ai payé »), l'entrée coche « payé » ; liste d'attente sans paiement ;
5. co-organisateur (simple membre) confirme ; prix enlevé : plus rien à payer.
Lancement : SUPABASE_LIVE_TESTS=1 PARTY_TEST_EVENTS_DIST=<module construit contre la base de test> python -m pytest <ce fichier>
Captures dans $PAY_SHOTS si la variable est définie."""
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
import pytest

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, GUEST_B, VIP, complete_profile, make_vip, unmake_vip
from tests.supabase_live.test_event_tickets_live import answer, notes, ticket
from tests.supabase_live.test_inscription_complete_browser_live import browser, party, phone_page  # noqa: F401
from tests.supabase_live.test_invitations_v2_live import terms_version
from tests.supabase_live.test_member_admin_live import KEY_FILE, OTP, TEST_URL, Session, pytestmark as live  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql

pw = pytest.importorskip('playwright.sync_api')
DIST = Path(os.environ.get('PARTY_TEST_EVENTS_DIST') or '/nonexistent')
pytestmark = [live, pytest.mark.skipif(not (DIST / 'index.html').exists(),
                                        reason='PARTY_TEST_EVENTS_DIST : module construit contre la base de test')]
SHOTS = Path(os.environ['PAY_SHOTS']) if os.environ.get('PAY_SHOTS') else None
TITLE = 'Paintball paiement recette'
REVOLUT = 'https://revolut.me/test-party-recette'
TICKETING = 'https://billetterie.example.ch/paintball-recette'
STORAGE_KEY = f"sb-{urlparse(TEST_URL).hostname.split('.')[0]}-auth-token"  # session du module (supabase-js)


class Account(Session):
    """Compte de test connecté UNE fois (code fixe) : la même session sert à l'API et au navigateur (un seul code SMS
    par numéro : la limite d'Auth est d'un code par minute, et d'autres recettes tournent en parallèle)."""

    def __init__(self, phone: str):
        self.key = KEY_FILE.read_text().strip()
        base = {'apikey': self.key, 'Content-Type': 'application/json'}
        for _ in range(4):
            sent = httpx.post(f'{TEST_URL}/auth/v1/otp', headers=base, json={'phone': phone}, timeout=30)
            if sent.status_code != 429:
                break
            time.sleep(31)
        assert sent.status_code == 200, sent.text
        r = httpx.post(f'{TEST_URL}/auth/v1/verify', headers=base, json={'type': 'sms', 'phone': phone, 'token': OTP}, timeout=30)
        assert r.status_code == 200, r.text
        self.auth = r.json()
        self.uid = self.auth['user']['id']
        self.headers = {**base, 'Authorization': f"Bearer {self.auth['access_token']}"}


def shot(page, name: str):
    if SHOTS:
        page.wait_for_timeout(900)
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f'{name}.png'), full_page=True)


@pytest.fixture(scope='module')
def people():
    admin, a, b, vip = Account(ADMIN), Account(GUEST_A), Account(GUEST_B), Account(VIP)
    for s in (admin, a, b, vip):
        assert s.rpc('accept_terms', p_version=terms_version()).status_code in (200, 204)
    complete_profile(a, 'Guest A')
    complete_profile(b, 'Guest B')
    make_vip(admin, vip)
    yield {'admin': admin, 'a': a, 'b': b, 'vip': vip}
    unmake_vip(admin, vip)


@pytest.fixture(scope='module')
def pages(browser, party, people):  # noqa: F811
    """Une page connectée par compte (un seul code SMS par numéro pour toute la recette)."""
    opened = {}

    def page_of(who: str):
        if who not in opened:
            context, page, errors = phone_page(browser)
            page.set_default_navigation_timeout(90000)  # machine chargée (recettes en parallèle)
            page.on('dialog', lambda d: (errors.append(f'dialogue {d.type} : {d.message}'), d.accept()))
            context.route('https://revolut.me/**', lambda r: r.fulfill(status=200, body='Revolut (simulé)'))  # jamais le vrai site
            context.route('https://billetterie.example.ch/**', lambda r: r.fulfill(status=200, body='Billetterie (simulée)'))
            page.goto(f'{party}/events/sign-in', wait_until='domcontentloaded')
            page.evaluate('([k, v]) => localStorage.setItem(k, v)', [STORAGE_KEY, json.dumps(people[who].auth)])
            opened[who] = (page, errors)
        return opened[who]
    yield page_of
    for page, _ in opened.values():
        page.context.close()


@pytest.fixture(scope='module')
def state(people):
    found = {}
    yield found
    if found.get('event'):
        sql(f"delete from public.events where id = '{found['event']}'")
    sql(f"delete from public.events where title = '{TITLE}' and created_by = '{people['admin'].uid}'")


def event_row(eid: str) -> dict:
    return sql(f"select price_chf::float price, payment_mode, payment_url, payment_info, tickets_enabled, notify_on_publish, "
               f"visibility from public.events where id = '{eid}'")[0]


def open_event(page, party, eid):  # noqa: F811
    page.goto(f'{party}/events/event/{eid}', wait_until='domcontentloaded')
    pw.expect(page.get_by_text(TITLE, exact=True).first).to_be_visible(timeout=30000)


def form_error(page, text: str):
    page.get_by_role('button', name='Publier', exact=True).click()
    pw.expect(page.get_by_text(text, exact=True)).to_be_visible(timeout=10000)


def test_1_the_form_offers_three_ways_to_pay_and_refuses_bad_links(pages, party, people, state):  # noqa: F811
    page, errors = pages('admin')
    page.goto(f'{party}/events/event/new', wait_until='domcontentloaded')
    page.get_by_label('Titre', exact=True).fill(TITLE)
    page.get_by_role('tab', name='Avancé', exact=True).click()
    page.get_by_label('Début : jour', exact=True).fill('2030-11-14')
    page.get_by_label('Début : heure', exact=True).select_option('19:00')
    page.get_by_role('button', name='Sur invitation', exact=True).click()
    assert page.get_by_text('Comment on paie ?', exact=True).count() == 0  # gratuit : pas de choix
    page.get_by_label('Prix / pers. (CHF)', exact=True).fill('25')
    pw.expect(page.get_by_text('Comment on paie ?', exact=True)).to_be_visible()
    on_me = page.get_by_role('radio', name=re.compile('^On me paie'))
    pw.expect(on_me).to_have_attribute('aria-checked', 'true')  # défaut
    page.get_by_text('Comment on paie ?', exact=True).scroll_into_view_if_needed()
    shot(page, '01-formulaire-trois-choix')

    page.get_by_role('radio', name=re.compile('^Paiement en ligne')).click()
    pw.expect(page.get_by_label('Lien de paiement', exact=True)).to_be_visible()
    form_error(page, 'Paiement en ligne : ajoute le lien (billetterie, Revolut…)')
    shot(page, '02-formulaire-en-ligne-sans-lien')
    page.get_by_label('Lien de paiement', exact=True).fill('http://billetterie.example.ch/x')
    form_error(page, 'Le lien de paiement doit commencer par https://')
    page.get_by_label('Lien de paiement', exact=True).fill('https://revolut.me/test party')
    form_error(page, 'Le lien de paiement ne doit pas contenir d’espace')
    shot(page, '03-formulaire-lien-avec-espace')
    page.get_by_label('Lien de paiement', exact=True).fill('javascript:alert(1)')
    page.get_by_role('button', name='Publier', exact=True).click()
    pw.expect(page.get_by_text(re.compile('^Le lien de paiement doit'))).to_be_visible()
    page.get_by_role('radio', name=re.compile('^Sur place')).click()
    pw.expect(page.get_by_label('Lien de paiement', exact=True)).to_have_count(0)
    page.get_by_role('radio', name=re.compile('^On me paie')).click()
    page.get_by_label('Lien de paiement (facultatif)', exact=True).fill(REVOLUT)
    page.get_by_label('Précision (facultatif)', exact=True).fill('Twint ou Revolut, avant le jour J')
    shot(page, '04-formulaire-on-me-paie')
    page.get_by_role('button', name='Publier', exact=True).click()
    page.wait_for_url(re.compile(r'.*/events/event/[0-9a-f-]{36}.*'), timeout=30000)
    eid = re.search(r'/event/([0-9a-f-]{36})', page.url).group(1)
    state['event'] = eid
    # Aucune annonce : la base de test contient de vrais comptes (personne n'était invité à la publication).
    sql(f"update public.events set notify_on_publish = false where id = '{eid}'")
    shot(page, '05-publie')
    row = event_row(eid)
    assert row['price'] == 25 and row['payment_mode'] == 'organizer' and row['payment_url'] == REVOLUT, row
    assert row['visibility'] == 'invited', row
    for who in ('a', 'b', 'vip'):
        r = httpx.post(f'{TEST_URL}/rest/v1/event_invites', headers=people['admin'].headers,
                       json={'event_id': eid, 'user_id': people[who].uid}, timeout=30)
        assert r.status_code == 201, r.text
    assert not errors, errors


def name(who: Session) -> str:
    """Surnom actuel (d'autres recettes, en parallèle, renomment les comptes de test « Testeur 1 »…)."""
    return sql(f"select display_name from public.profiles where id = '{who.uid}'")[0]['display_name']


def person_row(page, who: Session, button: str):
    """La ligne d'une personne (la plus petite qui contient son surnom et le bouton)."""
    return page.locator('div').filter(has_text=name(who)).filter(has=page.get_by_role('button', name=button, exact=True)).last


def test_2_on_me_paie_the_guest_notes_it_and_the_organizer_confirms(pages, party, people, state):  # noqa: F811
    eid = state['event']
    page, errors = pages('a')
    open_event(page, party, eid)
    pw.expect(page.get_by_text('À payer à l’organisateur · Twint ou Revolut, avant le jour J', exact=True)).to_be_visible()
    page.get_by_role('button', name='Présent', exact=True).click()
    pay = page.get_by_role('button', name=f"Payer {name(people['admin'])} · 25 CHF", exact=True)
    pw.expect(pay).to_be_visible(timeout=15000)
    pay.scroll_into_view_if_needed()
    shot(page, '06-invite-on-me-paie')
    pay.click()
    revolut = page.get_by_role('link', name='Payer avec Revolut', exact=True)
    pw.expect(revolut).to_have_count(1, timeout=10000)
    shot(page, '07-feuille-payer')
    with page.expect_popup() as popup:
        revolut.click()
    assert popup.value.url.startswith(REVOLUT)
    popup.value.close()
    page.get_by_role('button', name='J’ai payé', exact=True).click()
    pw.expect(page.get_by_text('Payé · en attente de confirmation', exact=True).first).to_be_visible(timeout=15000)
    pw.expect(page.get_by_text('L’organisateur confirme dès qu’il a reçu tes 25 CHF.', exact=True)).to_be_visible()
    shot(page, '08-invite-en-attente')
    page.get_by_role('button', name='Annuler', exact=True).click()
    pw.expect(pay).to_be_visible(timeout=15000)
    assert ticket(people['a'], eid).get('pay_pending') is not True
    pay.click()
    page.get_by_role('button', name='J’ai payé', exact=True).click()
    pw.expect(page.get_by_text('Payé · en attente de confirmation', exact=True).first).to_be_visible(timeout=15000)
    assert not errors, errors

    answer(people['vip'], eid, 'yes')
    assert people['vip'].rpc('declare_ticket_payment', e=eid, declared=True).json()['pay_pending'] is True
    bodies = [n['body'] for n in notes(people['admin'], eid, 'ticket_pay_declared')]
    said = f"{name(people['a'])} dit avoir payé sa place (25 CHF) : confirme quand tu l'as vérifié."
    assert said in bodies, bodies

    page, errors = pages('admin')
    page.goto(f'{party}/events/activity', wait_until='domcontentloaded')
    pw.expect(page.get_by_text(said, exact=True).first).to_be_visible(timeout=20000)
    shot(page, '09-activite-organisateur')
    open_event(page, party, eid)
    pw.expect(page.get_by_text('2 à confirmer · 25 CHF chacun', exact=True)).to_be_visible(timeout=20000)
    page.get_by_text('2 à confirmer · 25 CHF chacun', exact=True).scroll_into_view_if_needed()
    shot(page, '10-organisateur-a-confirmer')
    person_row(page, people['a'], 'Reçu ✓').get_by_role('button', name='Reçu ✓', exact=True).click()
    pw.expect(page.get_by_text('1 à confirmer · 25 CHF chacun', exact=True)).to_be_visible(timeout=15000)
    person_row(page, people['vip'], 'Pas reçu').get_by_role('button', name='Pas reçu', exact=True).click()
    pw.expect(page.get_by_text('Aucun paiement à confirmer. Quand quelqu’un touche « J’ai payé », il apparaît ici.', exact=True)).to_be_visible(timeout=15000)
    shot(page, '11-organisateur-confirme')
    assert not errors, errors
    assert ticket(people['a'], eid)['paid'] is True
    vip = ticket(people['vip'], eid)
    assert vip['paid'] is False and vip.get('pay_pending') is not True

    page, errors = pages('a')
    open_event(page, party, eid)
    pw.expect(page.get_by_text('✓ Place payée · 25 CHF', exact=True)).to_be_visible(timeout=15000)
    page.get_by_text('✓ Place payée · 25 CHF', exact=True).scroll_into_view_if_needed()
    shot(page, '12-invite-place-payee')
    assert not errors, errors


def save_form(page, label='Enregistrer'):
    page.get_by_role('button', name=label, exact=True).click()


def test_3_published_event_switched_to_online_with_qr_tickets(pages, party, people, state):  # noqa: F811
    eid = state['event']
    page, errors = pages('admin')
    page.goto(f'{party}/events/event/{eid}/edit', wait_until='domcontentloaded')
    link = page.get_by_label('Lien de paiement (facultatif)', exact=True)
    pw.expect(link).to_have_value(REVOLUT, timeout=30000)
    page.get_by_role('radio', name=re.compile('^Paiement en ligne')).click()
    online_link = page.get_by_label('Lien de paiement', exact=True)
    online_link.fill('')
    save_form(page)
    pw.expect(page.get_by_text('Paiement en ligne : ajoute le lien (billetterie, Revolut…)', exact=True)).to_be_visible(timeout=10000)
    online_link.fill(TICKETING)
    page.get_by_label('Précision (facultatif)', exact=True).fill('Choisis « Paintball 2 h »')
    page.get_by_label('Billets QR', exact=True).click()
    online_link.scroll_into_view_if_needed()
    shot(page, '13-modifier-en-ligne')
    save_form(page)
    page.wait_for_url(re.compile(rf'.*/events/event/{eid}$'), timeout=30000)
    row = event_row(eid)
    assert (row['payment_mode'], row['payment_url'], row['tickets_enabled']) == ('online', TICKETING, True), row
    state['a_ticket_after_qr'] = ticket(people['a'], eid)
    assert not errors, errors

    page, errors = pages('b')
    open_event(page, party, eid)
    pw.expect(page.get_by_text('Paiement en ligne · Choisis « Paintball 2 h »', exact=True)).to_be_visible()
    page.get_by_role('button', name='Présent', exact=True).click()
    online = page.get_by_role('link', name='Payer en ligne · 25 CHF ↗', exact=True)
    pw.expect(online).to_be_visible(timeout=15000)
    pw.expect(page.get_by_text('billetterie.example.ch · Choisis « Paintball 2 h »', exact=True)).to_be_visible()
    online.scroll_into_view_if_needed()
    shot(page, '14-invite-en-ligne-billet-en-attente')
    with page.expect_popup() as popup:
        online.click()
    assert popup.value.url.startswith(TICKETING)
    popup.value.close()
    # Avis du 16.11 : rien à noter dans Party (le site n'est pas à l'organisateur) ; l'entrée coche « payé ».
    pw.expect(page.get_by_role('button', name='J’ai payé', exact=True)).to_have_count(0)
    shot(page, '15-invite-en-ligne-rien-a-noter')
    assert not errors, errors
    refused = people['b'].rpc('declare_ticket_payment', e=eid, declared=True)
    assert refused.status_code == 400 and 'en ligne' in refused.text, refused.text

    page, errors = pages('admin')
    open_event(page, party, eid)
    pw.expect(page.get_by_text('Paiement en ligne · Choisis « Paintball 2 h »', exact=True)).to_be_visible(timeout=15000)
    assert page.get_by_text('Aucun paiement à confirmer. Quand quelqu’un touche « J’ai payé », il apparaît ici.', exact=True).count() == 0
    page.goto(f'{party}/events/event/{eid}/scan', wait_until='domcontentloaded')
    row = person_row(page, people['b'], 'Payé ?')
    pw.expect(row).to_be_visible(timeout=20000)
    row.get_by_role('button', name='Payé ?', exact=True).click()
    pw.expect(person_row(page, people['b'], 'Payé ✓')).to_be_visible(timeout=15000)
    mine = ticket(people['b'], eid)
    assert mine['paid'] is True and mine['state'] == 'ok' and mine.get('code'), mine  # place payée = billet remis

    page_b, errors_b = pages('b')
    open_event(page_b, party, eid)
    pw.expect(page_b.get_by_text('✓ Place payée · 25 CHF', exact=True)).to_be_visible(timeout=15000)
    page_b.get_by_text('Ton billet', exact=True).first.scroll_into_view_if_needed()
    shot(page_b, '16-invite-billet-qr')
    assert not errors_b, errors_b

    page.goto(f'{party}/events/event/{eid}/scan', wait_until='domcontentloaded')
    page.get_by_label('Code du billet', exact=True).fill(mine['code'])
    page.get_by_role('button', name='Valider', exact=True).click()
    pw.expect(page.get_by_text('✓ Payé', exact=True)).to_be_visible(timeout=15000)
    shot(page, '17-entree-code-court')
    assert not errors, errors


def test_4_on_site_has_no_button_and_the_entry_ticks_paid(pages, party, people, state):  # noqa: F811
    eid = state['event']
    page, errors = pages('admin')
    page.goto(f'{party}/events/event/{eid}/edit', wait_until='domcontentloaded')
    pw.expect(page.get_by_label('Lien de paiement', exact=True)).to_have_value(TICKETING, timeout=30000)
    page.get_by_role('radio', name=re.compile('^Sur place')).click()
    pw.expect(page.get_by_label('Lien de paiement', exact=True)).to_have_count(0)
    page.get_by_label('Précision (facultatif)', exact=True).fill('Cash ou carte à l’accueil')
    page.get_by_text('Comment on paie ?', exact=True).scroll_into_view_if_needed()
    shot(page, '18-modifier-sur-place')
    save_form(page)
    page.wait_for_url(re.compile(rf'.*/events/event/{eid}$'), timeout=30000)
    row = event_row(eid)
    assert (row['payment_mode'], row['payment_url']) == ('on_site', None), row
    pw.expect(page.get_by_text('À payer sur place · Cash ou carte à l’accueil', exact=True)).to_be_visible()
    assert page.get_by_text('Aucun paiement à confirmer. Quand quelqu’un touche « J’ai payé », il apparaît ici.', exact=True).count() == 0
    assert not errors, errors

    vpage, verrors = pages('vip')
    open_event(vpage, party, eid)
    pw.expect(vpage.get_by_text('📍 25 CHF · à payer sur place', exact=True)).to_be_visible(timeout=15000)
    assert vpage.get_by_role('button', name='J’ai payé', exact=True).count() == 0
    assert vpage.get_by_text(re.compile('^Paie ta place')).count() == 0
    vpage.get_by_text('📍 25 CHF · à payer sur place', exact=True).scroll_into_view_if_needed()
    shot(vpage, '19-membre-sur-place')
    assert not verrors, verrors
    refused = people['vip'].rpc('declare_ticket_payment', e=eid, declared=True)
    assert refused.status_code == 400 and 'sur place' in refused.text, refused.text

    page.goto(f'{party}/events/event/{eid}/scan', wait_until='domcontentloaded')
    row = person_row(page, people['vip'], 'Payé ?')
    pw.expect(row).to_be_visible(timeout=20000)
    row.get_by_role('button', name='Payé ?', exact=True).click()
    pw.expect(person_row(page, people['vip'], 'Payé ✓')).to_be_visible(timeout=15000)
    shot(page, '20-entree-sur-place-paye')
    assert ticket(people['vip'], eid)['paid'] is True
    assert not errors, errors


def patch_event(people, eid, **row):
    r = httpx.patch(f'{TEST_URL}/rest/v1/events?id=eq.{eid}', headers=people['admin'].headers, json=row, timeout=30)
    assert r.status_code in (200, 204), r.text


def test_5_a_co_organizer_confirms_and_removing_the_price_leaves_nothing_to_pay(pages, party, people, state):  # noqa: F811
    eid = state['event']
    patch_event(people, eid, payment_mode='organizer', payment_url=None, tickets_enabled=False)
    r = httpx.post(f'{TEST_URL}/rest/v1/event_organizers', headers=people['admin'].headers,
                   json={'event_id': eid, 'user_id': people['vip'].uid}, timeout=30)
    assert r.status_code == 201, r.text
    answer(people['b'], eid, 'yes')
    people['admin'].rpc('confirm_ticket_payment', e=eid, member=people['b'].uid, received=False)
    assert people['b'].rpc('declare_ticket_payment', e=eid, declared=True).json()['pay_pending'] is True

    page, errors = pages('vip')
    open_event(page, party, eid)
    receipt = person_row(page, people['b'], 'Reçu ✓')
    pw.expect(receipt).to_be_visible(timeout=20000)
    receipt.scroll_into_view_if_needed()
    shot(page, '21-co-organisateur-a-confirmer')
    receipt.get_by_role('button', name='Reçu ✓', exact=True).click()
    pw.expect(page.get_by_text('Aucun paiement à confirmer. Quand quelqu’un touche « J’ai payé », il apparaît ici.', exact=True)).to_be_visible(timeout=15000)
    assert ticket(people['b'], eid)['paid'] is True
    assert not errors, errors

    page, errors = pages('admin')
    page.goto(f'{party}/events/event/{eid}/edit', wait_until='domcontentloaded')
    price = page.get_by_label('Prix / pers. (CHF)', exact=True)
    pw.expect(price).to_have_value('25', timeout=30000)
    price.fill('0')
    pw.expect(page.get_by_text('Comment on paie ?', exact=True)).to_have_count(0)
    save_form(page)
    page.wait_for_url(re.compile(rf'.*/events/event/{eid}$'), timeout=30000)
    row = event_row(eid)
    assert (row['price'], row['payment_mode'], row['payment_url']) == (0, 'organizer', None), row
    pw.expect(page.get_by_text('Gratuit', exact=True)).to_be_visible(timeout=15000)
    page.get_by_text('Gratuit', exact=True).scroll_into_view_if_needed()
    shot(page, '22-prix-enleve-organisateur')
    # La précision du paiement, cachée dans le formulaire une fois l'événement gratuit, ne reste pas sous « Gratuit ».
    assert row['payment_info'] is None, row
    assert page.get_by_text(re.compile('Cash ou carte|Twint ou Revolut')).count() == 0
    assert not errors, errors

    gpage, gerrors = pages('a')
    open_event(gpage, party, eid)
    pw.expect(gpage.get_by_text('Gratuit', exact=True)).to_be_visible(timeout=15000)
    assert gpage.get_by_role('button', name=re.compile('^Payer')).count() == 0
    assert gpage.get_by_text(re.compile('Place payée|à payer')).count() == 0
    shot(gpage, '23-prix-enleve-invite')
    assert not gerrors, gerrors

    page.goto(f'{party}/events/event/{eid}/edit', wait_until='domcontentloaded')
    pw.expect(price).to_have_value('0', timeout=30000)
    price.fill('')
    save_form(page)
    page.wait_for_url(re.compile(rf'.*/events/event/{eid}$'), timeout=30000)
    assert event_row(eid)['price'] is None


def test_6_the_waitlist_has_nothing_to_pay(pages, party, people, state):  # noqa: F811
    """Guest A (place remise à payer) libère sa place, l'événement se remplit, puis il revient : liste d'attente, rien à payer."""
    eid = state['event']
    a = people['a']
    people['admin'].rpc('confirm_ticket_payment', e=eid, member=a.uid, received=False)
    answer(a, eid, 'no')
    heads = sql(f"select count(*)::int n from public.rsvps where event_id = '{eid}' and status = 'yes' and not waitlisted")[0]['n']
    patch_event(people, eid, price_chf=25, payment_mode='organizer', payment_url=REVOLUT, max_participants=heads, waitlist_enabled=True)

    page, errors = pages('a')
    open_event(page, party, eid)
    page.get_by_role('button', name=re.compile('^(Présent|Liste d’attente)')).first.click()
    pw.expect(page.get_by_text(re.compile('liste d’attente', re.I)).first).to_be_visible(timeout=15000)
    assert sql(f"select waitlisted from public.rsvps where event_id = '{eid}' and user_id = '{a.uid}'") == [{'waitlisted': True}]
    page.wait_for_timeout(1500)
    shot(page, '24-liste-attente')
    assert page.get_by_role('button', name=re.compile('^Payer')).count() == 0
    assert page.get_by_role('button', name='J’ai payé', exact=True).count() == 0
    assert not errors, errors
    refused = a.rpc('declare_ticket_payment', e=eid, declared=True)
    assert refused.status_code == 400 and 'présents' in refused.text, refused.text
