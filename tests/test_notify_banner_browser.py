"""Bandeau « Active les notifications » en haut d'un événement (avis c77d117ab172 de l'admin, 13.11.2026), vrai navigateur
(Supabase simulé) : notifications éteintes → bandeau ; « Plus tard » le cache ; app iPhone (pont PartyNative simulé) :
« Activer » demande à iOS et le bandeau disparaît ; refusées → « Ouvrir les réglages »."""
import os
from pathlib import Path

import pytest

from tests.test_event_participant_browser import event_row, open_event, rsvp
from tests.test_events_browser import DIST, USER, browser, events_origin  # noqa: F401

pw = pytest.importorskip('playwright.sync_api')
pytestmark = pytest.mark.skipif(not (DIST / 'index.html').exists(), reason='Construire web/events avant les tests navigateur')
SHOTS = Path(os.environ['NOTIFY_SHOTS']) if os.environ.get('NOTIFY_SHOTS') else None
TITLE = 'Ne rate rien de cet événement'


def native(status: str) -> str:
    """Pont de l'app iPhone (NativeBridge.swift) : status() puis enable() → « granted » (ou reste refusé)."""
    return """window.__enabled = 0; window.PartyNative = { platform: 'ios', push: {
      status: () => Promise.resolve({ status: window.__enabled ? 'granted' : '%s' }),
      enable: () => { window.__enabled = '%s' === 'denied' ? 0 : 1; window.__asked = true;
                      return Promise.resolve({ status: window.__enabled ? 'granted' : 'denied' }); },
      register: () => Promise.reject(new Error('non')) } };""" % (status, status)


def test_web_banner_offers_notifications_and_later_hides_it(browser, events_origin):  # noqa: F811
    context, page = open_event(browser, events_origin, event_row(rsvps=[rsvp(USER, 'yes')]))
    try:
        # Jamais demandé (le Chromium des tests refuse d'office) : « Activer ».
        page.add_init_script("Object.defineProperty(Notification, 'permission', { get: () => 'default' });")
        page.reload(wait_until='domcontentloaded')
        pw.expect(page.get_by_text(TITLE, exact=True)).to_be_visible(timeout=15000)
        pw.expect(page.get_by_role('button', name='Activer les notifications')).to_be_visible()
        if SHOTS:
            SHOTS.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(SHOTS / '01-bandeau-web.png'))
        # En haut : au-dessus du titre de l'événement.
        assert page.get_by_text(TITLE, exact=True).bounding_box()['y'] < page.get_by_role('heading', level=1).bounding_box()['y']
        page.get_by_role('button', name='Plus tard').click()
        pw.expect(page.get_by_text(TITLE, exact=True)).to_have_count(0)
        page.reload(wait_until='domcontentloaded')
        pw.expect(page.get_by_role('heading', level=1)).to_be_visible(timeout=15000)
        page.wait_for_timeout(800)
        pw.expect(page.get_by_text(TITLE, exact=True)).to_have_count(0)  # caché 24 h
    finally:
        context.close()


def test_iphone_app_enable_asks_ios_and_the_banner_goes_away(browser, events_origin):  # noqa: F811
    context, page = open_event(browser, events_origin, event_row(rsvps=[rsvp(USER, 'yes')]))
    try:
        page.add_init_script(native('default'))
        page.reload(wait_until='domcontentloaded')
        pw.expect(page.get_by_text(TITLE, exact=True)).to_be_visible(timeout=15000)
        page.get_by_role('button', name='Activer les notifications').click()
        pw.expect(page.get_by_text(TITLE, exact=True)).to_have_count(0, timeout=5000)
        assert page.evaluate('window.__asked') is True
    finally:
        context.close()


def test_iphone_app_blocked_opens_the_settings(browser, events_origin):  # noqa: F811
    context, page = open_event(browser, events_origin, event_row(rsvps=[rsvp(USER, 'yes')]))
    try:
        page.add_init_script(native('denied'))
        page.reload(wait_until='domcontentloaded')
        pw.expect(page.get_by_text('Tes notifications sont bloquées', exact=True)).to_be_visible(timeout=15000)
        page.get_by_role('button', name='Ouvrir les réglages').click()
        page.wait_for_timeout(300)
        assert page.evaluate('window.__asked') is True
    finally:
        context.close()


def test_already_on_no_banner(browser, events_origin):  # noqa: F811
    context, page = open_event(browser, events_origin, event_row(rsvps=[rsvp(USER, 'yes')]))
    try:
        page.add_init_script(native('granted'))
        page.reload(wait_until='domcontentloaded')
        pw.expect(page.get_by_role('heading', level=1)).to_be_visible(timeout=15000)
        page.wait_for_timeout(800)
        pw.expect(page.get_by_text(TITLE, exact=True)).to_have_count(0)
    finally:
        context.close()


def test_web_blocked_says_where_to_allow_them(browser, events_origin):  # noqa: F811
    context, page = open_event(browser, events_origin, event_row(rsvps=[rsvp(USER, 'yes')]))  # refusées par défaut
    try:
        pw.expect(page.get_by_text('Tes notifications sont bloquées', exact=True)).to_be_visible(timeout=10000)
        pw.expect(page.get_by_text('le cadenas à côté de l’adresse', exact=False)).to_be_visible()
        pw.expect(page.get_by_role('button', name='Activer les notifications')).to_have_count(0)
    finally:
        context.close()
