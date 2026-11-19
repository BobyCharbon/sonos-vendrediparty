"""Module Événements ouvert SEUL (lien d'invitation, notification…) : toute page « de l'app » repart dans la page Party,
le module dans le cadre #eventsFrame, barre d'onglets comprise (web/events/src/lib/partyShell.ts, leaveIfAlone /
openInParty ; retour de l'admin du 19.11 : un invité restait coincé dans le module seul). Aides des recettes réelles."""
import re
import time
from urllib.parse import quote, urlparse

import pytest

pw = pytest.importorskip('playwright.sync_api')

# Recettes qui ne visent pas ce parcours : le module reste seul (comme mock_services, tests/test_events_browser.py).
ALONE_INIT = "try { if (window.top === window) localStorage.setItem('party_module_alone', '1'); } catch (e) {}"
PARTY = re.compile(r'^https?://[^/]+/\?tab=events')
# Page Party à la racine : la liste (« /?tab=events » sans page précise) redevient « / » une fois ouverte (index.html).
PARTY_PAGE = re.compile(r'^https?://[^/]+/(\?tab=events.*)?$')


def party_event(event: str) -> re.Pattern:
    """Adresse de Party qui ouvre la fiche (partyUrl de partyShell.ts, lue par PartyEvents.target)."""
    return re.compile(rf'^https?://[^/]+/\?tab=events&event={event}$')


def party_path(path: str) -> re.Pattern:
    """Adresse de Party qui ouvre une autre page du module (`?path=`)."""
    return re.compile(r'^https?://[^/]+/\?tab=events&path=' + re.escape(quote(path, safe='')) + '$')


def in_party(page, frame_path: str, timeout: int = 30000):
    """La page Party (/?tab=events…), sa barre d'onglets (onglet Événements allumé) et, dans le cadre #eventsFrame, la
    page `frame_path` du module (« /events/event/<id> »…). Rend ce cadre (Frame) pour la suite du parcours."""
    page.wait_for_url(PARTY_PAGE, timeout=timeout)
    tab = page.locator('#tabs [data-tab="events"]')
    pw.expect(tab).to_be_visible(timeout=timeout)
    pw.expect(tab).to_have_attribute('aria-current', 'page')
    deadline = time.monotonic() + timeout / 1000
    while True:
        frame = page.locator('#eventsFrame').element_handle(timeout=timeout).content_frame()
        if frame is not None and urlparse(frame.url).path.rstrip('/') == frame_path.rstrip('/'):
            return frame
        assert time.monotonic() < deadline, f'cadre du module sur {frame and frame.url}, attendu {frame_path}'
        page.wait_for_timeout(200)


def where_visible(page, text, timeout: int = 40000):
    """Le module là où il montre `text` : seul (la page) ou dans Party (le cadre). Après la connexion SMS d'un lien
    d'invitation, le routeur passe un instant par « / » et leaveIfAlone renvoie déjà dans Party (rapport du 19.11) :
    on suit la personne là où elle est (même endroit deux fois de suite, à 1 s d'écart)."""
    deadline, last = time.monotonic() + timeout / 1000, None
    while time.monotonic() < deadline:
        found = None
        for scope in [page, *[f for f in page.frames if f != page.main_frame]]:
            try:
                found_text = scope.get_by_text(text, exact=True) if isinstance(text, str) else scope.get_by_text(text)
                if found_text.first.is_visible():
                    found = scope
                    break
            except Exception:  # cadre détaché pendant une navigation
                pass
        if found is not None and found is last and (found is not page or not PARTY.match(page.url)):
            return found
        last = found
        page.wait_for_timeout(1000)
    raise AssertionError(f'« {text} » introuvable (page {page.url}) : {page.locator("body").inner_text()[:600]!r}')
