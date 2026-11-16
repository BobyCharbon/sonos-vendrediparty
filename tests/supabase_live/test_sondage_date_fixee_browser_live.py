"""Recette RÉELLE (15.11.2026) : fixer la date d'un sondage puis modifier l'événement ne fait plus perdre les créneaux ni
les votes (paintball, prod, 13.11 ; correction caf0e37). Vrai navigateur, vrai serveur Party, base de TEST, comptes de
test à code fixe, réglages de prod. Événement « sur invitation », sans annonce ni notification de publication.

Parcours : sondage à trois dates ; trois comptes votent (Oui / Si besoin / Non, l'un sur la fiche dans le navigateur) ;
l'organisateur fixe une date (bouton), modifie l'événement (titre, heure), repasse en « Date à définir » : tout revient.
Puis passage direct du sondage à une date fixe par le formulaire, et retour.
Lancement : SUPABASE_LIVE_TESTS=1 PARTY_TEST_EVENTS_DIST=<module construit contre la base de test> python -m pytest <ce fichier>
Captures dans $SONDAGE_SHOTS si la variable est définie."""
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, GUEST_B, VIP, complete_profile, create_event
from tests.supabase_live.test_inscription_complete_browser_live import browser, party, phone_page, sign_in  # noqa: F401
from tests.supabase_live.test_invitations_v2_live import terms_version
from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark as live  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql

pw = pytest.importorskip('playwright.sync_api')
DIST = Path(os.environ.get('PARTY_TEST_EVENTS_DIST') or '/nonexistent')
pytestmark = [live, pytest.mark.skipif(not (DIST / 'index.html').exists(),
                                        reason='PARTY_TEST_EVENTS_DIST : module construit contre la base de test')]
SHOTS = Path(os.environ['SONDAGE_SHOTS']) if os.environ.get('SONDAGE_SHOTS') else None


def shot(page, name: str):
    if SHOTS:
        page.wait_for_timeout(900)
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f'{name}.png'), full_page=True)


def votes_of(e: str) -> set:
    return {(r['starts_at'], r['user_id'], r['vote']) for r in sql(
        f"select o.starts_at::text, v.user_id::text, v.vote::text from public.date_options o "
        f"join public.date_votes v on v.option_id = o.id where o.event_id = '{e}'")}


def event_row(e: str) -> dict:
    return sql(f"select title, date_mode::text, starts_at::text, (select count(*) from public.date_options "
               f"where event_id = '{e}') options from public.events where id = '{e}'")[0]


@pytest.fixture(scope='module')
def poll():
    admin, ga, gb, vip = Session(ADMIN), Session(GUEST_A), Session(GUEST_B), Session(VIP)
    for s, name in ((ga, 'Testeur 1'), (gb, 'Testeur 2'), (vip, 'Testeur 3')):
        assert s.rpc('accept_terms', p_version=terms_version()).status_code in (200, 204)
        if not sql(f"select private.identity_complete('{s.uid}') ok")[0]['ok']:
            complete_profile(s, name)  # voter exige un profil complet (comme en prod)
    assert admin.rpc('accept_terms', p_version=terms_version()).status_code in (200, 204)
    e = create_event(admin, 'Sondage recette', visibility='invited', date_mode='poll', starts_at=None)
    day = (datetime.now(timezone.utc) + timedelta(days=20)).replace(hour=18, minute=0, second=0, microsecond=0)
    options = []
    for week in range(3):
        r = httpx.post(f'{TEST_URL}/rest/v1/date_options', timeout=30, headers={**admin.headers, 'Prefer': 'return=representation'},
                       json={'event_id': e, 'starts_at': (day + timedelta(weeks=week)).isoformat()})
        assert r.status_code == 201, r.text
        options.append(r.json()[0]['id'])
    r = httpx.post(f'{TEST_URL}/rest/v1/event_invites', headers=admin.headers, timeout=30,
                   json=[{'event_id': e, 'user_id': s.uid} for s in (ga, gb, vip)])
    assert r.status_code == 201, r.text
    for s, picks in ((gb, ('yes', 'no', 'if_needed')), (vip, ('no', 'yes', 'yes'))):
        r = httpx.post(f'{TEST_URL}/rest/v1/date_votes', headers=s.headers, timeout=30,
                       json=[{'option_id': o, 'user_id': s.uid, 'vote': v} for o, v in zip(options, picks)])
        assert r.status_code == 201, r.text
    yield admin, ga, gb, vip, e, options
    sql(f"delete from public.events where id = '{e}'")


def open_event(browser, party, e: str, number: str, wait_for: str):  # noqa: F811
    context, page, errors = phone_page(browser)
    page.goto(f'{party}/events/sign-in', wait_until='domcontentloaded')
    sign_in(page, number)
    pw.expect(page.get_by_text('Ton compte Party', exact=True)).to_have_count(0, timeout=30000)
    page.goto(f'{party}/events/event/{e}', wait_until='domcontentloaded')
    pw.expect(page.get_by_text(wait_for, exact=True).first).to_be_visible(timeout=30000)
    return context, page, errors


def edit(page, mode: str | None = None):
    page.get_by_role('button', name='Modifier', exact=True).click()
    pw.expect(page.get_by_label('Titre', exact=True)).not_to_have_value('', timeout=20000)
    if mode:
        advanced = page.get_by_role('tab', name='Avancé', exact=True)
        if advanced.count() and advanced.get_attribute('aria-disabled') != 'true':  # sondage : déjà en Avancé
            advanced.click()
        page.get_by_role('tab', name=mode, exact=True).click()


def tallies_shown(page):
    """Les comptes de chaque date, tels que l'organisateur les voit (il n'a pas voté lui-même)."""
    # Seulement l'écran affiché : les fiches précédentes restent dans la pile, cachées.
    pw.expect(page.get_by_text('2 oui · 0 si besoin · 1 non', exact=True).locator('visible=true')).to_have_count(1, timeout=20000)
    pw.expect(page.get_by_text('1 oui · 1 si besoin · 1 non', exact=True).locator('visible=true')).to_have_count(2)


def save(page, title: str):
    page.get_by_role('button', name='Enregistrer', exact=True).click()
    pw.expect(page.get_by_role('heading', name=title, exact=True).locator('visible=true')).to_have_count(1, timeout=20000)
    page.wait_for_timeout(1500)


def test_fixing_then_editing_then_back_to_a_poll_keeps_every_date_and_every_vote(browser, party, poll):  # noqa: F811
    admin, ga, gb, vip, e, options = poll
    # 1. Testeur 1 vote sur la fiche : Oui, Si besoin, Non.
    context, page, errors = open_event(browser, party, e, '079 000 00 01', 'Quelle date ?')
    try:
        shot(page, '01-invite-avant-vote')
        for i, label in enumerate(('Oui', 'Si besoin', 'Non')):
            page.get_by_role('button', name=re.compile(f'^{label} : ')).nth(i).click()
            page.wait_for_timeout(800)
        pw.expect(page.get_by_text('3 votants', exact=True)).to_be_visible(timeout=15000)
        shot(page, '02-invite-a-vote')
        assert not errors, errors
    finally:
        context.close()
    before = votes_of(e)
    assert len(before) == 9, before

    # 2. L'organisateur fixe la première date (bouton), puis modifie le titre et l'heure.
    context, page, errors = open_event(browser, party, e, '079 000 00 04', 'Quelle date ?')
    try:
        tallies_shown(page)
        shot(page, '03-organisateur-sondage')
        page.get_by_role('button', name='Fixer cette date', exact=True).first.click()
        pw.expect(page.get_by_text('Quelle date ?', exact=True).locator('visible=true')).to_have_count(0, timeout=20000)
        shot(page, '04-date-fixee')
        row = event_row(e)
        assert row['date_mode'] == 'fixed' and row['options'] == 3 and votes_of(e) == before
        answers = {r['user_id']: r['status'] for r in sql(f"select user_id::text, status::text from public.rsvps where event_id = '{e}'")}
        assert answers == {ga.uid: 'yes', gb.uid: 'yes', vip.uid: 'no'}, answers

        edit(page)
        shot(page, '05-formulaire-date-fixe')
        page.get_by_label('Titre', exact=True).fill('Paintball recette')
        page.get_by_label('Début : heure', exact=True).select_option('21:00')
        save(page, 'Paintball recette')
        shot(page, '06-modifie')
        row = event_row(e)
        assert row['title'] == 'Paintball recette' and row['date_mode'] == 'fixed'
        assert row['options'] == 3 and votes_of(e) == before, 'créneaux ou votes perdus en modifiant la date fixée'

        # 3. Retour en « Date à définir » : les trois créneaux reviennent, avec tous leurs votes.
        edit(page, 'Date à définir')
        page.get_by_label('Créneau 3 : jour', exact=True).scroll_into_view_if_needed()
        pw.expect(page.get_by_label('Créneau 3 : jour', exact=True)).to_be_visible()
        shot(page, '07-formulaire-retour-sondage')
        save(page, 'Paintball recette')
        pw.expect(page.get_by_text('Quelle date ?', exact=True).locator('visible=true')).to_have_count(1, timeout=20000)
        tallies_shown(page)
        shot(page, '08-sondage-retrouve')
        row = event_row(e)
        assert row['date_mode'] == 'poll' and row['starts_at'] is None and row['options'] == 3 and votes_of(e) == before

        # 4. Du sondage directement à une date fixe par le formulaire, puis retour : rien n'est perdu non plus.
        edit(page, 'Date fixée')
        day = (datetime.now(timezone.utc) + timedelta(days=40)).strftime('%Y-%m-%d')
        page.get_by_label('Début : jour', exact=True).fill(day)
        page.get_by_label('Début : heure', exact=True).select_option('20:00')
        save(page, 'Paintball recette')
        pw.expect(page.get_by_text('Quelle date ?', exact=True).locator('visible=true')).to_have_count(0, timeout=20000)
        shot(page, '09-formulaire-date-fixe-directe')
        row = event_row(e)
        assert row['date_mode'] == 'fixed' and row['options'] == 3 and votes_of(e) == before
        edit(page, 'Date à définir')
        save(page, 'Paintball recette')
        tallies_shown(page)
        shot(page, '10-sondage-retrouve-encore')
        assert event_row(e)['date_mode'] == 'poll' and votes_of(e) == before
        assert not errors, errors
    finally:
        context.close()
