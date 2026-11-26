"""Accessibilité (WCAG 2.2 AA) du module Événements, pour de vrai : vrai navigateur, vrai serveur Party, base de TEST,
réglages de prod (Invitations v2, CGU exigées). axe-core : aucune violation « sérieuse » ou « critique » sur les pages
publiques (bienvenue, connexion, CGU, confidentialité, invitation à un événement et à un sondage) et, connecté (Admin de
test), sur l'accueil, l'activité, la fiche, le sondage, la création, la modification, l'étape 2, les groupes, les
réglages et la feuille « Inviter ». Exception unique : `meta-viewport` (voir tests/e2e/test_accessibility.py).
Événements « sur invitation » sans notification, supprimés à la fin.
Lancement : SUPABASE_LIVE_TESTS=1 PARTY_TEST_EVENTS_DIST=<module construit contre la base de test> python -m pytest <ce fichier>"""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from tests.e2e.test_accessibility import serious_violations
from tests.supabase_live.test_audiences_live import ADMIN, create_event
from tests.supabase_live.test_inscription_complete_browser_live import browser, party, phone_page, sign_in  # noqa: F401
from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark as live  # noqa: F401

pw = pytest.importorskip('playwright.sync_api')
DIST = Path(os.environ.get('PARTY_TEST_EVENTS_DIST') or '/nonexistent')
pytestmark = [live, pytest.mark.skipif(not (DIST / 'index.html').exists(),
                                        reason='PARTY_TEST_EVENTS_DIST : module construit contre la base de test')]


@pytest.fixture(scope='module')
def events():
    admin = Session(ADMIN)
    event = create_event(admin, 'Accessibilité recette', visibility='invited', description='Recette axe.')
    poll = create_event(admin, 'Sondage accessibilité', visibility='invited', date_mode='poll', starts_at=None)
    for days in (20, 27):
        r = httpx.post(f'{TEST_URL}/rest/v1/date_options', timeout=30, headers=admin.headers,
                       json={'event_id': poll, 'starts_at': (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()})
        assert r.status_code == 201, r.text
    links = [admin.rpc('create_event_invite', e=e, places=10, label='Recette axe').json()['token'] for e in (event, poll)]
    yield event, poll, links
    for e in (event, poll):
        httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{e}', headers=admin.headers, timeout=30)


def audit(page, url: str) -> list:
    page.goto(url, wait_until='load')
    page.wait_for_timeout(3500)  # module chargé et données reçues
    assert page.evaluate('document.documentElement.lang') == 'fr' and page.title()
    return serious_violations(page)


def test_public_pages_have_no_serious_axe_violation(browser, party, events):  # noqa: F811
    event, poll, (link, poll_link) = events
    context, page, errors = phone_page(browser)
    try:
        found = {path: audit(page, f'{party}/events{path}')
                 for path in ('/', '/sign-in', '/terms', '/privacy', f'/invite/{link}', f'/invite/{poll_link}')}
        assert {p: v for p, v in found.items() if v} == {}
        assert not errors, errors
    finally:
        context.close()


def test_signed_in_pages_and_invite_sheet_have_no_serious_axe_violation(browser, party, events):  # noqa: F811
    event, poll, _ = events
    context, page, errors = phone_page(browser, alone=True)  # pages du module seul (19.11 : sinon renvoyées dans Party)
    try:
        page.goto(f'{party}/events/sign-in', wait_until='domcontentloaded')
        sign_in(page, '079 000 00 04')
        pw.expect(page.get_by_text('Ton compte Party', exact=True)).to_have_count(0, timeout=30000)
        paths = ('/', '/activity', f'/event/{event}', f'/event/{poll}', '/event/new', f'/event/{event}/edit',
                 f'/event/{event}/invite', '/groups', '/settings/notifications', '/settings/profile')
        found = {path: audit(page, f'{party}/events{path}') for path in paths}
        page.goto(f'{party}/events/event/{event}', wait_until='load')
        page.get_by_role('button', name='Inviter', exact=True).first.click()
        pw.expect(page.get_by_role('button', name='Copier').first).to_be_visible(timeout=15000)
        found['feuille Inviter'] = serious_violations(page)
        assert {p: v for p, v in found.items() if v} == {}
        assert not errors, errors
    finally:
        context.close()
