"""Recette iPhone du 27.11 : dans l'app, « ✨ Avec l'IA » flottait par-dessus « Absent » de la première carte d'Événements.
En haut de la liste, il est sous l'en-tête (jamais sur une carte) ; une fois défilé, il redevient flottant."""
import json

from tests.test_events_browser import browser, events_origin, login, mock_services, pw  # noqa: F401

SUPA = 'https://gsuetixzobooggeaubvb.supabase.co'


def overlap(a, b):
    return a['x'] < b['x'] + b['width'] and b['x'] < a['x'] + a['width'] and a['y'] < b['y'] + b['height'] and b['y'] < a['y'] + a['height']


def test_the_ai_button_never_covers_the_first_card(browser, events_origin):  # noqa: F811
    ctx = browser.new_context(viewport={'width': 390, 'height': 560})
    page = ctx.new_page()
    page.add_init_script("window.PartyNative = Object.assign(window.PartyNative || {}, {ai: {createEvent() { window.__ai = 1; }}});")
    mock_services(page, events=3)
    page.route(f'{SUPA}/rest/v1/rpc/my_permissions', lambda r: r.fulfill(
        status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'},
        body=json.dumps(['events.view', 'events.rsvp', 'events.create', 'ai.use'])))
    try:
        page.goto(events_origin, wait_until='domcontentloaded')
        page.get_by_role('button', name='Événements', exact=True).click()
        frame = page.frame_locator('#eventsFrame')
        login(frame)
        ai = frame.get_by_test_id('home-ai')
        pw.expect(ai).to_be_visible(timeout=15000)
        absent = frame.get_by_role('button', name='Absent').first
        pw.expect(absent).to_be_visible(timeout=10000)
        boxes = [frame.get_by_role('button', name=n).first.bounding_box() for n in ('Présent', 'Peut-être', 'Absent')]
        assert not any(overlap(ai.bounding_box(), b) for b in boxes if b)
        ai.click()
        assert page.frame_locator('#eventsFrame').locator('body').evaluate('() => window.__ai') == 1
    finally:
        ctx.close()
