"""Refus Apple 1.4.3 (contrôle final du 25.11) : dans l'app App Store (« PartyStore »), un événement PUBLIC dont le titre, la
description, le lieu ou les mini-sondages parlent d'alcool n'apparaît ni dans la liste ni dans la recherche ; ses invités,
participants et organisateurs le voient toujours ; le site le montre à tous (web/events/src/lib/storeEvents.ts)."""
from tests.test_events_browser import EVENT, USER, browser, events_origin, login, mock_services, pw  # noqa: F401 (fixtures)

STORE_UA = ('Mozilla/5.0 (iPhone; CPU iPhone OS 26_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 '
            'PartyApp-iOS/1.0.0 PartyStore')
OTHER = '11111111-2222-4333-8444-555555555555'
DRINKY = {'created_by': OTHER, 'visibility': 'all', 'title': 'Anniversaire de démonstration',
          'polls': [{'question': 'Est-ce que tu vas boire de l’alcool fort ?', 'poll_options': [{'label': 'Une bouteille (50 €)'}]}],
          'event_organizers': [], 'event_invites': []}


def open_list(browser, events_origin, ua, extra, events=2):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844}, **({'user_agent': ua} if ua else {}))
    page = context.new_page()
    mock_services(page, events=events, event_extra=extra)
    page.goto(events_origin, wait_until='domcontentloaded')
    page.get_by_role('button', name='Événements', exact=True).click()
    frame = page.frame_locator('#eventsFrame')
    login(frame)
    pw.expect(frame.get_by_text('À venir', exact=True).first).to_be_visible(timeout=15000)
    page.wait_for_timeout(1500)
    return context, frame


def test_store_app_hides_a_public_drinking_event_from_strangers_but_the_web_shows_it(browser, events_origin):  # noqa: F811
    ctx, frame = open_list(browser, events_origin, STORE_UA, DRINKY)
    try:
        pw.expect(frame.get_by_text('Anniversaire de démonstration')).to_have_count(0)
    finally:
        ctx.close()
    ctx, frame = open_list(browser, events_origin, None, DRINKY)
    try:
        pw.expect(frame.get_by_text('Anniversaire de démonstration').first).to_be_visible(timeout=15000)
    finally:
        ctx.close()


def test_store_app_still_shows_it_to_a_participant_and_to_the_organisers(browser, events_origin):  # noqa: F811
    for extra in ({**DRINKY, 'rsvps': [{'event_id': EVENT, 'user_id': USER, 'status': 'yes', 'plus_ones': 0, 'note': None, 'waitlisted': False}]},
                  {**DRINKY, 'event_organizers': [{'user_id': USER}]}):
        ctx, frame = open_list(browser, events_origin, STORE_UA, extra)
        try:
            pw.expect(frame.get_by_text('Anniversaire de démonstration').first).to_be_visible(timeout=15000)
        finally:
            ctx.close()
