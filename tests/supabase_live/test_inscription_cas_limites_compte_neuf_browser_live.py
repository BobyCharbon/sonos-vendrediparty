"""Cas limites de l'inscription par lien avec des comptes NEUFS (campagne du 14.11.2026) : vrai navigateur (390 × 844),
vrai serveur Party, base de TEST, réglages de la prod (CGU exigées, Invitations v2).

1. abandon au milieu de « Faisons connaissance » puis retour par le lien : la réponse choisie (lib/inviteIntent.ts) ramène
   à l'invitation ; surnom de jeu trop long jamais pré-rempli au-delà de 12 caractères ; CGU refusées puis acceptées ;
2. plus de 10 minutes après : la carte, sans réponse envoyée à l'insu ; profil incomplet refusé par la base (rsvps,
   date_votes : profile_required) et page publique qui demande le profil ; surnom fait d'espaces, avec emoji ;
3. déjà invité qui rouvre le lien sur un deuxième appareil et change sa réponse ; lien d'une place ouvert en même temps
   par deux personnes ; personne qui a bloqué l'organisateur ; surnom refusé sans les CGU ;
   surnom de 13 caractères refusé par la base, surnom déjà porté par un autre accepté (rien d'unique).

Numéros neufs à code fixe 123456 (sms_test_otp de la base de TEST) : $INSCRIPTION_NEW_PHONES, par défaut
41790000402,41790000403,41790000404 (aucun compte au départ). Les comptes créés sont supprimés à la fin
(delete_my_account) ; INSCRIPTION_WIPE_FIRST=1 les supprime aussi avant (passage précédent interrompu).
Compléter un profil prévient les comptes « members.approve » de la base de TEST (« Nouveau compte ») : 2 par passage.

Lancement : SUPABASE_LIVE_TESTS=1 PARTY_TEST_EVENTS_DIST=<dist> python -m pytest \
  tests/supabase_live/test_inscription_cas_limites_compte_neuf_browser_live.py -q"""
import os
import re
import time
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from tests.supabase_live.test_audiences_live import ADMIN, create_event
from tests.supabase_live.test_inscription_cas_limites_browser_live import (  # noqa: F401
    SESSIONS, TECHNICAL, assert_clear, browser, party, phone_page, pytestmark, pw, session, shot)
from tests.supabase_live.test_member_admin_live import TEST_URL, Session

PHONES = (os.environ.get('INSCRIPTION_NEW_PHONES') or '41790000402,41790000403,41790000404').split(',')
LOCAL = lambda phone: f'0{phone[2:4]} {phone[4:7]} {phone[7:9]} {phone[9:]}'  # 41790000402 → 079 000 04 02


def wipe(phone: str):
    """Compte du numéro supprimé : la prochaine connexion crée un compte neuf (profil vide, CGU pas acceptées)."""
    s = session(phone)
    for _ in range(4):  # la suppression verrouille la table des profils : base chargée par d'autres tests → délai dépassé
        r = s.rpc('delete_my_account')
        if '57014' not in r.text:
            break
        time.sleep(30)
    SESSIONS.pop(phone, None)
    assert r.status_code in (200, 204), r.text


def profile_of(s: Session) -> dict:
    """Son propre profil (prénom et nom ne se lisent pas dans la table : get_member_directory, comme l'app)."""
    row = s.rpc('get_member_directory').json()[0]
    return {k: row[k] for k in ('first_name', 'last_name', 'display_name', 'status')}


SIGNED: set[str] = set()  # numéros connectés dans le navigateur : leur compte existe, il est supprimé à la fin


def sign_in(page, phone: str):
    """La page de connexion normale de l'app : pays, numéro, code SMS (code fixe du numéro de test)."""
    SIGNED.add(phone)
    pw.expect(page.get_by_text('Ton compte Party', exact=True)).to_be_visible(timeout=20000)
    page.get_by_label('Ton numéro de téléphone', exact=True).fill(LOCAL(phone))
    code = page.get_by_placeholder('123456', exact=True)
    for _ in range(5):  # un code par numéro et par minute ; Auth limite aussi les demandes par adresse IP (autres tests)
        page.get_by_role('button', name='Recevoir un code par SMS').click()
        try:
            code.wait_for(timeout=15000)
            break
        except Exception:
            pw.expect(page.get_by_text(re.compile('^(Attends|Trop de demandes)'))).to_be_visible()
            page.wait_for_timeout(31000 if page.get_by_text(re.compile('^Attends')).count() else 150000)
    code.fill('123456')
    page.get_by_role('button', name='Se connecter', exact=True).click()


def fill_identity(page, first: str, last: str, nickname: str | None = None):
    pw.expect(page.get_by_text('Faisons connaissance', exact=True)).to_be_visible(timeout=20000)
    page.get_by_label('Prénom', exact=True).fill(first)
    page.get_by_label('Nom', exact=True).fill(last)
    if nickname is not None:
        page.get_by_label('Surnom', exact=False).fill(nickname)


@pytest.fixture(scope='module')
def world():
    admin = session(ADMIN)
    assert admin.rpc('accept_terms', p_version=admin.rpc('my_terms').json()['version']).status_code in (200, 204)
    if os.environ.get('INSCRIPTION_WIPE_FIRST'):
        for phone in PHONES:
            wipe(phone)
    soon = (datetime.now(timezone.utc) + timedelta(days=21)).isoformat()
    events = {
        'main': create_event(admin, 'Recette cas limites inscription', visibility='invited', starts_at=soon),
        'seat': create_event(admin, 'Recette une place', visibility='invited', starts_at=soon),
        'public': create_event(admin, 'Recette public cas limites', visibility='all', public_link=True, starts_at=soon),
    }
    link = admin.rpc('create_event_invite', e=events['main'], places=10, label='Recette').json()['token']
    seat = admin.rpc('create_event_invite', e=events['seat'], places=1, label='Une place').json()['token']
    yield admin, events, link, seat
    for e in events.values():
        httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{e}', headers=admin.headers, timeout=30)
    for phone in PHONES:
        if phone in SESSIONS or phone in SIGNED:  # compte créé par ce passage
            wipe(phone)


def test_1_leaving_in_the_middle_of_the_profile_then_coming_back_by_the_link_resumes_the_invitation(browser, party, world):
    admin, events, link, _seat = world
    context, page, errors = phone_page(browser)
    try:
        # Surnom de jeu de 19 caractères déjà choisi sur ce téléphone (jeux de Party, même origine).
        page.goto(f'{party}/events/invite/{link}', wait_until='domcontentloaded')
        page.evaluate("localStorage.setItem('vp_name', 'Superlongpseudo2026')")
        page.get_by_role('button', name='Je viens !').click()
        sign_in(page, PHONES[0])
        pw.expect(page.get_by_text('Faisons connaissance', exact=True)).to_be_visible(timeout=20000)
        nickname = page.get_by_label('Surnom', exact=False)
        assert len(nickname.input_value()) <= 12, nickname.input_value()
        shot(page, 'n1-faisons-connaissance')

        # Abandon : la personne ferme et va ailleurs, puis rouvre le lien reçu (moins de 10 minutes plus tard).
        page.goto(f'{party}/events/', wait_until='domcontentloaded')
        page.wait_for_timeout(2000)
        page.goto(f'{party}/events/invite/{link}', wait_until='domcontentloaded')
        fill_identity(page, 'Recette', 'Abandon')
        # Surnom : jamais plus de 12 caractères à l'écran.
        nickname.fill('')
        nickname.press_sequentially('Abcdefghijklmnop')
        assert nickname.input_value() == 'Abcdefghijkl'
        pw.expect(page.get_by_text(re.compile(r'12 / 12$'))).to_be_visible()
        nickname.fill('Recette A')

        # CGU : « Plus tard » → rien d'enregistré ; nouvel essai → « J’accepte » → la réponse part d'elle-même.
        page.get_by_role('button', name=re.compile('^Continuer')).click()
        page.get_by_role('button', name='Plus tard').click()
        pw.expect(page.get_by_text('Faisons connaissance', exact=True)).to_be_visible()
        me = session(PHONES[0])
        assert profile_of(me)['display_name'] == ''
        page.get_by_role('button', name=re.compile('^Continuer')).click()
        page.get_by_role('button', name='J’accepte').click()
        pw.expect(page.get_by_text('C’est noté, Recette !', exact=True)).to_be_visible(timeout=20000)
        shot(page, 'n1-reponse-apres-abandon')
        assert_clear(page, errors)
    finally:
        context.close()
    assert profile_of(me) == {'first_name': 'Recette', 'last_name': 'Abandon', 'display_name': 'Recette A', 'status': 'active'}
    assert me.get(f'rsvps?select=status&event_id=eq.{events["main"]}&user_id=eq.{me.uid}').json() == [{'status': 'yes'}]


def test_2_after_ten_minutes_the_card_comes_back_and_an_incomplete_profile_cannot_answer(browser, party, world):
    admin, events, link, _seat = world
    context, page, errors = phone_page(browser)
    try:
        page.goto(f'{party}/events/invite/{link}', wait_until='domcontentloaded')
        page.get_by_role('button', name='Je viens !').click()
        sign_in(page, PHONES[1])
        pw.expect(page.get_by_text('Faisons connaissance', exact=True)).to_be_visible(timeout=20000)

        # Profil incomplet : la base refuse toute réponse et tout vote créés pour soi.
        me = session(PHONES[1])
        r = httpx.post(f'{TEST_URL}/rest/v1/rsvps', headers=me.headers, timeout=30,
                       json={'event_id': events['public'], 'user_id': me.uid, 'status': 'yes'})
        assert r.status_code >= 400 and 'profile_required' in r.text, r.text
        option = httpx.post(f'{TEST_URL}/rest/v1/date_options', timeout=30, headers={**admin.headers, 'Prefer': 'return=representation'},
                            json={'event_id': events['public'], 'starts_at': (datetime.now(timezone.utc) + timedelta(days=22)).isoformat()})
        assert option.status_code == 201, option.text
        r = httpx.post(f'{TEST_URL}/rest/v1/date_votes', headers=me.headers, timeout=30,
                       json={'option_id': option.json()[0]['id'], 'user_id': me.uid, 'vote': 'yes'})
        assert r.status_code >= 400 and 'profile_required' in r.text, r.text

        # Plus de 10 minutes après : la carte revient, sans réponse partie à l'insu de la personne.
        page.evaluate("""() => { const k = 'party-invite-answer'; const v = JSON.parse(sessionStorage.getItem(k));
                                 sessionStorage.setItem(k, JSON.stringify({ ...v, at: Date.now() - 11 * 60 * 1000 })); }""")
        page.goto(f'{party}/events/invite/{link}', wait_until='domcontentloaded')
        pw.expect(page.get_by_role('button', name='Je viens !')).to_be_visible(timeout=20000)
        pw.expect(page.get_by_text('Faisons connaissance', exact=True)).to_have_count(0)
        shot(page, 'n2-apres-dix-minutes')
        assert me.get(f'rsvps?select=status&user_id=eq.{me.uid}').json() == []

        # Lien public ouvert avec un profil incomplet : le profil est demandé, jamais une page vide ou une erreur.
        page.goto(f'{party}/events/share/{events["public"]}', wait_until='domcontentloaded')
        pw.expect(page.get_by_text('Recette public cas limites', exact=True)).to_be_visible(timeout=20000)
        pw.expect(page.get_by_text('Pour répondre, complète ton profil Party', exact=False)).to_be_visible()
        shot(page, 'n2-lien-public-profil-incomplet')
        assert_clear(page, errors)

        # Réponse « Peut-être » ; surnom fait d'espaces : bouton éteint ; avec emoji et espaces autour : gardé, sans les espaces.
        page.goto(f'{party}/events/invite/{link}', wait_until='domcontentloaded')
        page.get_by_role('button', name='Peut-être').click()
        fill_identity(page, 'Zoé', 'Emoji', '     ')
        pw.expect(page.get_by_role('button', name=re.compile('^Continuer'))).to_be_disabled()
        page.get_by_label('Surnom', exact=False).fill('  🎉 Zoé 🎉  ')
        page.get_by_role('button', name=re.compile('^Continuer')).click()
        page.get_by_role('button', name='J’accepte').click()
        pw.expect(page.get_by_text('C’est noté, Zoé !', exact=True)).to_be_visible(timeout=20000)
        shot(page, 'n2-emoji')
        assert_clear(page, errors)
    finally:
        context.close()
    assert profile_of(me)['display_name'] == '🎉 Zoé 🎉'
    assert me.get(f'rsvps?select=status&event_id=eq.{events["main"]}&user_id=eq.{me.uid}').json() == [{'status': 'maybe'}]


def test_3_nickname_rules_in_the_database(world):
    """13 caractères : refusé en clair ; le surnom d'un autre : accepté (aucune règle d'unicité)."""
    first, second = session(PHONES[0]), session(PHONES[1])
    r = httpx.patch(f'{TEST_URL}/rest/v1/profiles?id=eq.{second.uid}', headers=second.headers, json={'display_name': 'Treize carac.'}, timeout=30)
    assert r.status_code >= 400 and 'nickname_too_long' in r.text, r.text
    taken = profile_of(first)['display_name']
    r = httpx.patch(f'{TEST_URL}/rest/v1/profiles?id=eq.{second.uid}', headers=second.headers, json={'display_name': taken}, timeout=30)
    assert r.status_code in (200, 204), r.text
    assert profile_of(second)['display_name'] == taken


def test_4_already_invited_on_a_second_device_changes_the_answer_and_the_first_device_follows(browser, party, world):
    _admin, events, link, _seat = world
    one, page1, errors1 = phone_page(browser)
    two, page2, errors2 = phone_page(browser)
    try:
        for page in (page1, page2):
            page.goto(f'{party}/events/sign-in', wait_until='domcontentloaded')
            sign_in(page, PHONES[0])
            page.wait_for_timeout(1500)
            page.goto(f'{party}/events/invite/{link}', wait_until='domcontentloaded')
            pw.expect(page.get_by_text('Ta réponse : Je viens. Tu peux la changer.', exact=True)).to_be_visible(timeout=20000)
        page2.get_by_role('button', name='Je ne peux pas').click()
        pw.expect(page2.get_by_text(re.compile('^Tu ne viens pas à'))).to_be_visible(timeout=20000)
        page1.reload(wait_until='domcontentloaded')
        pw.expect(page1.get_by_text('Ta réponse : Je ne peux pas. Tu peux la changer.', exact=True)).to_be_visible(timeout=20000)
        shot(page1, 'n4-deux-appareils')
        assert_clear(page1, errors1)
        assert_clear(page2, errors2)
    finally:
        one.close()
        two.close()
    me = session(PHONES[0])
    assert me.get(f'rsvps?select=status&event_id=eq.{events["main"]}&user_id=eq.{me.uid}').json() == [{'status': 'no'}]


def test_5_a_one_place_link_opened_by_two_people_at_once_keeps_one_and_tells_the_other(browser, party, world):
    _admin, events, _link, seat = world
    pages = [phone_page(browser) for _ in PHONES[:2]]
    try:
        for (_c, page, _e), phone in zip(pages, PHONES):
            page.goto(f'{party}/events/sign-in', wait_until='domcontentloaded')
            sign_in(page, phone)
            page.wait_for_timeout(1500)
            page.goto(f'{party}/events/invite/{seat}', wait_until='domcontentloaded')
            pw.expect(page.get_by_role('button', name='Je viens !')).to_be_visible(timeout=20000)
        for _c, page, _e in pages:  # les deux touchent presque en même temps
            page.get_by_role('button', name='Je viens !').click(no_wait_after=True)
        done = []
        for _c, page, errors in pages:
            yes = page.get_by_text(re.compile('^C’est noté, '))
            full = page.get_by_text(re.compile('déjà servi|places de ce lien'))
            pw.expect(yes.or_(full).first).to_be_visible(timeout=20000)
            done.append(yes.count() > 0)
            assert_clear(page, errors)
        assert sorted(done) == [False, True], done
        shot(pages[done.index(False)][1], 'n5-lien-une-place-pris')
    finally:
        for context, _p, _e in pages:
            context.close()
    answered = [session(p).get(f'rsvps?select=status&event_id=eq.{events["seat"]}').json() for p in PHONES[:2]]
    assert sorted(len(a) for a in answered) == [0, 1], answered


def test_6_a_person_who_blocked_the_organizer_cannot_answer_and_is_told_so(browser, party, world):
    admin, events, _link, _seat = world
    token = admin.rpc('create_event_invite', e=events['public'], places=3, label='Bloqué').json()['token']
    me = session(PHONES[0])
    assert me.rpc('set_block', target=admin.uid, blocked=True).status_code in (200, 204)
    context, page, errors = phone_page(browser)
    try:
        page.goto(f'{party}/events/sign-in', wait_until='domcontentloaded')
        sign_in(page, PHONES[0])
        page.wait_for_timeout(1500)
        page.goto(f'{party}/events/invite/{token}', wait_until='domcontentloaded')
        page.get_by_role('button', name='Je viens !').click()
        pw.expect(page.get_by_text('Tu ne peux pas répondre à cette invitation.', exact=False)).to_be_visible(timeout=20000)
        shot(page, 'n6-bloque')
        assert_clear(page, errors)
    finally:
        context.close()
    assert me.get(f'rsvps?select=status&event_id=eq.{events["public"]}&user_id=eq.{me.uid}').json() == []


def test_7_a_new_account_cannot_take_a_nickname_before_the_terms(world):
    """CGU exigées (prod) : un compte neuf ne peut pas enregistrer de surnom sans les avoir acceptées (la feuille des CGU
    de « Faisons connaissance » passe donc toujours avant, test 1). Le cas « profil complet sans CGU » n'existe que pour
    les comptes d'avant les CGU : écran testé avec des faux (test_an_account_without_the_terms_sees_the_terms_sheet_before_its_answer)."""
    me = session(PHONES[2])
    assert me.rpc('my_terms').json()['accepted'] is False
    r = httpx.patch(f'{TEST_URL}/rest/v1/profiles?id=eq.{me.uid}', headers=me.headers, timeout=30,
                    json={'first_name': 'Recette', 'last_name': 'Cgu', 'display_name': 'Recette C'})
    assert r.status_code == 403 and 'terms_required' in r.text, r.text
    assert profile_of(me) == {'first_name': '', 'last_name': '', 'display_name': '', 'status': 'active'}
