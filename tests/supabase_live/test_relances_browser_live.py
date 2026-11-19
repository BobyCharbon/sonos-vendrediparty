"""Recette RÉELLE des relances (demande de l'admin du 19.11.2026) : vrai navigateur, vrai serveur Party, base de TEST,
comptes de test à code fixe, réglages de prod (Invitations v2 allumées). Événement privé de l'admin ; Guest A n'a que la
webapp (abonnement Web Push factice, clés invalides : rien ne part vraiment), Guest B n'a ni app ni notifications.
L'admin ouvre sa fiche dans Party, touche « ↻ Relancer les 2 qui n'ont pas répondu », confirme : Guest A est prévenu
dans Party (notification en base, texte sans culpabilisation), Guest B reçoit le lien par le partage (« Copier le
message »), noté relancé aujourd'hui.
Lancement : SUPABASE_LIVE_TESTS=1 PARTY_TEST_EVENTS_DIST=<module construit contre la base de test> python -m pytest <ce fichier>
Captures dans $RELANCES_SHOTS si la variable est définie."""
import os
import secrets
from pathlib import Path

import pytest

from tests.supabase_live.party_shell import in_party
from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, GUEST_B, create_event
from tests.supabase_live.test_inscription_complete_browser_live import browser, party, phone_page, sign_in  # noqa: F401
from tests.supabase_live.test_member_admin_live import Session, pytestmark as live  # noqa: F401
from tests.supabase_live.test_relances_live import last_session
from tests.supabase_live.test_rsvp_digest_live import sql

pw = pytest.importorskip('playwright.sync_api')
DIST = Path(os.environ.get('PARTY_TEST_EVENTS_DIST') or '/nonexistent')
pytestmark = [live, pytest.mark.skipif(not (DIST / 'index.html').exists(),
                                        reason='PARTY_TEST_EVENTS_DIST : module construit contre la base de test')]
SHOTS = Path(os.environ['RELANCES_SHOTS']) if os.environ.get('RELANCES_SHOTS') else None


def shot(page, name: str):
    if SHOTS:
        page = getattr(page, 'page', page)  # cadre du module dans Party : capture de la page
        page.wait_for_timeout(900)
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f'{name}.png'))


@pytest.fixture(scope='module')
def event():
    admin, ga, gb = Session(ADMIN), Session(GUEST_A), Session(GUEST_B)
    tag = secrets.token_hex(4)
    e = create_event(admin, f'Relances recette {tag}', visibility='invited')
    assert admin.rpc('invite_people', e=e, people=[ga.uid, gb.uid]).json() == {'people': 2, 'groups': 0}
    sub = sql(f"""insert into private.web_push_subscriptions (user_id, session_id, endpoint, subscription, origin)
        values ('{ga.uid}', '{last_session(ga.uid)}', 'https://fcm.googleapis.com/fcm/send/relances-recette-{tag}',
          '{{"endpoint": "https://fcm.googleapis.com/fcm/send/relances-recette-{tag}", "keys": {{"auth": "x", "p256dh": "y"}}}}'::jsonb,
          'https://partytest.bobycharbon.ch') returning id""")[0]['id']
    yield ga, gb, e, f'Relances recette {tag}'
    sql(f"delete from private.web_push_subscriptions where id = '{sub}'; delete from public.notifications where event_id = '{e}'; "
        f"delete from public.events where id = '{e}'")


def test_the_organizer_nudges_everyone_without_an_answer_in_one_gesture(browser, party, event):  # noqa: F811
    ga, gb, e, title = event
    name = {r['id']: r['display_name'] for r in sql(f"select id, display_name from public.profiles where id in ('{ga.uid}', '{gb.uid}')")}
    context, page, errors = phone_page(browser)
    context.grant_permissions(['clipboard-read', 'clipboard-write'])
    try:
        page.goto(f'{party}/events/event/{e}', wait_until='domcontentloaded')
        frame = in_party(page, f'/events/share/{e}')  # sans compte : la page publique de l'événement, dans Party
        frame.get_by_role('button', name='Se connecter', exact=True).click()
        sign_in(frame, '079 000 00 04')
        pw.expect(frame.get_by_role('button', name='Se connecter', exact=True)).to_have_count(0, timeout=30000)
        page.goto(f'{party}/events/event/{e}', wait_until='domcontentloaded')
        frame = in_party(page, f'/events/event/{e}')
        card = frame.get_by_label('Invités', exact=True)
        button = card.get_by_role('button', name='↻ Relancer les 2 qui n’ont pas répondu')
        pw.expect(button).to_be_visible(timeout=30000)
        button.scroll_into_view_if_needed()
        shot(frame, '10-recette-bouton')
        button.click()
        sheet = frame.get_by_label('Relancer les invités sans réponse', exact=True)
        pw.expect(sheet.get_by_text('1 avec Party : une notification', exact=True)).to_be_visible(timeout=10000)
        shot(frame, '11-recette-confirmation')
        sheet.get_by_role('button', name='Confirmer la relance').click()
        pw.expect(sheet.get_by_text(f"{name[ga.uid]} est prévenu dans Party", exact=True)).to_be_visible(timeout=15000)
        pw.expect(sheet.get_by_text(f"{name[gb.uid]} n’a pas l’app : envoie-lui le lien", exact=True)).to_be_visible()
        shot(frame, '12-recette-bilan')
        sheet.get_by_role('button', name='Copier le message').click()
        pw.expect(sheet.get_by_text('Message copié', exact=False)).to_be_visible(timeout=10000)
        sheet.get_by_role('button', name='Fermer', exact=True).last.click()
        pw.expect(card.get_by_role('button', name='↻ Relancer', exact=False)).to_have_count(0, timeout=15000)  # tout le monde relancé
        assert not errors, errors
    finally:
        context.close()

    notes = sql(f"select user_id, title, body from public.notifications where event_id = '{e}' and dedupe_key like 'invite_nudge:%'")
    assert notes == [{'user_id': ga.uid, 'title': f'📬 {title}',
                      'body': 'Invitation de Admin test · Tu viens ? Réponds en un geste.'}]
    channels = sql(f"select user_id, channel from private.invite_nudges where event_id = '{e}' order by channel")
    assert channels == [{'user_id': ga.uid, 'channel': 'push'}, {'user_id': gb.uid, 'channel': 'share'}]
