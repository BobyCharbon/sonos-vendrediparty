"""Sondage de dates → toutes les dates proposées dans l'agenda en un toucher (avis 9ddbdea7fe8f du 10.11.2026).
Un seul fichier .ics avec une entrée par date : l'iPhone propose « Tout ajouter ». Chaque entrée commence par
« À confirmer · » et est marquée provisoire (STATUS:TENTATIVE) : on garde le créneau, rien n'est encore fixé."""
import json
import re

from fastapi.testclient import TestClient

from app import calendar_ics, main
from tests.test_events_browser import EVENT as EVENT_PAGE, browser, events_origin  # noqa: F401 (fixtures)

EVENT = "64d0880c-5379-42f8-8166-e259d25c7e7b"
OPT1, OPT2, OPT3 = ("11111111-2222-4333-8444-555555555551", "11111111-2222-4333-8444-555555555552",
                    "11111111-2222-4333-8444-555555555553")


def unfold(body: str) -> str:
    return body.replace("\r\n ", "")


def events(body: str) -> list[str]:
    return unfold(body).split("BEGIN:VEVENT")[1:]


def test_every_proposed_date_is_one_tentative_entry_marked_to_confirm():
    client = TestClient(main.app)
    result = client.get("/api/calendar-dates.ics", params=[
        ("uid", EVENT), ("title", "Paintball"), ("location", "Cobalt Project, Lutry"),
        ("url", "https://party.bobycharbon.ch/events/event/" + EVENT),
        ("d", f"{OPT1}|2026-12-04T19:00:00Z|"), ("d", f"{OPT2}|2026-12-11T19:00:00Z|2026-12-11T23:00:00Z"),
        ("d", f"{OPT3}|2026-12-18T19:00:00Z|"),
    ])
    assert result.status_code == 200, result.text
    assert result.headers["content-type"].startswith("text/calendar")
    entries = events(result.text)
    assert len(entries) == 3
    for opt, entry in zip((OPT1, OPT2, OPT3), entries):
        assert f"UID:{opt}@vendredi-party" in entry
        assert "SUMMARY:À confirmer · Paintball" in entry
        assert "STATUS:TENTATIVE" in entry
        assert "rien n'est encore fixé" in entry.replace("\\,", ",")
    assert "DTSTART:20261211T190000Z" in entries[1] and "DTEND:20261211T230000Z" in entries[1]
    assert "DTEND:20261204T220000Z" in entries[0]  # sans fin : 3 heures
    assert all(len(line.encode()) <= 75 for line in result.text.split("\r\n"))


def test_bad_or_too_many_dates_are_refused():
    client = TestClient(main.app)
    base = [("uid", EVENT), ("title", "Paintball")]
    assert client.get("/api/calendar-dates.ics", params=base).status_code == 400  # aucune date
    assert client.get("/api/calendar-dates.ics", params=base + [("d", "pas-une-date")]).status_code == 400
    many = [("d", f"{OPT1[:-2]}{i:02d}|2026-12-04T19:00:00Z|") for i in range(calendar_ics.MAX_DATES + 1)]
    assert client.get("/api/calendar-dates.ics", params=base + many).status_code == 400


TOKEN = "b" * 36


def _vote_yes(page, pw, count):
    """Oui sur les `count` premières dates du sondage (les votes partent à chaque toucher)."""
    for i in range(count):
        page.get_by_role('button', name=re.compile(r'^Oui : ')).nth(i).click()
    pw.expect(page.get_by_role('button', name='Valider mes dates', exact=True)).to_be_enabled()


def mock_agenda(page, subscribed: bool = False) -> list[bool]:
    """Le calendrier « Vendredi Party » de la personne (fonction calendar_feed_token) ; rend la liste des `add` reçus."""
    from tests.test_event_participant_browser import HEADERS, REST
    calls: list[bool] = []

    def answer(route):
        if route.request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=HEADERS)
        add = bool(json.loads(route.request.post_data or '{}').get('add'))
        calls.append(add)
        route.fulfill(status=200, content_type='application/json', headers=HEADERS,
                      body=json.dumps({'token': TOKEN, 'subscribed': subscribed, 'added': any(calls)}))
    page.route(REST + 'rpc/calendar_feed_token', answer)
    return calls


def _web_poll(browser, events_origin, token: bool, subscribed: bool = False):
    from tests.test_event_participant_browser import event_row, open_event, pw
    ev = event_row(date_mode='poll', starts_at=None, max_participants=None, location_name='Cobalt Project', date_options=[
        {'id': OPT1, 'event_id': EVENT_PAGE, 'starts_at': '2030-11-20T18:00:00Z', 'ends_at': None, 'proposed_by': None, 'date_votes': []},
        {'id': OPT2, 'event_id': EVENT_PAGE, 'starts_at': '2030-11-27T18:00:00Z', 'ends_at': None, 'proposed_by': None, 'date_votes': []},
        {'id': OPT3, 'event_id': EVENT_PAGE, 'starts_at': '2020-01-01T18:00:00Z', 'ends_at': None, 'proposed_by': None, 'date_votes': []},
    ])
    context, page = open_event(browser, events_origin, ev)
    calls = mock_agenda(page, subscribed) if token else []
    return context, page, pw, calls


def test_validate_confirms_then_subscribes_the_agenda_to_my_voted_dates(browser, events_origin):  # noqa: F811
    context, page, pw, calls = _web_poll(browser, events_origin, token=True)
    try:
        valider = page.get_by_role('button', name='Valider mes dates', exact=True)
        pw.expect(valider).to_be_disabled(timeout=15000)  # rien voté : on dit quoi faire
        pw.expect(page.get_by_text('Réponds Oui, Si besoin ou Non pour chaque date, puis valide.')).to_be_visible()
        _vote_yes(page, pw, 3)  # la date passée n'ira pas dans l'agenda
        valider.click()
        pw.expect(page.get_by_text('C’est validé !', exact=True)).to_be_visible()
        pw.expect(page.get_by_text('ton agenda se mettra à jour tout seul', exact=False)).to_be_visible()
        page.wait_for_timeout(300)
        assert calls and not any(calls)  # ouvrir la fenêtre n'ajoute rien
        page.get_by_role('button', name='Ajouter les 2 dates à mon agenda', exact=True).click()
        page.get_by_role('button', name='Calendrier Apple', exact=True).click()  # ordinateur : on choisit son agenda (19.11)
        pw.expect(page.get_by_text('Confirme l’abonnement « Vendredi Party » dans ton agenda', exact=False)).to_be_visible(timeout=10000)
        assert calls[-1] is True  # le toucher ajoute l'événement au calendrier
    finally:
        context.close()


def test_already_subscribed_validate_adds_the_event_without_opening_anything(browser, events_origin):  # noqa: F811
    context, page, pw, calls = _web_poll(browser, events_origin, token=True, subscribed=True)
    try:
        _vote_yes(page, pw, 3)  # la date passée n'ira pas dans l'agenda
        page.get_by_role('button', name='Valider mes dates', exact=True).click()
        page.get_by_role('button', name='Ajouter les 2 dates à mon agenda', exact=True).click()
        pw.expect(page.get_by_text('Ajouté à ton calendrier « Vendredi Party »', exact=False)).to_be_visible(timeout=10000)
        assert calls[-1] is True
        page.get_by_role('button', name='Terminé', exact=True).click()
        page.get_by_role('button', name='Valider mes dates', exact=True).click()
        pw.expect(page.get_by_text('Tes dates sont déjà dans ton agenda.', exact=False)).to_be_visible()
    finally:
        context.close()


def test_without_the_subscription_link_the_voted_dates_still_come_as_a_file(browser, events_origin):  # noqa: F811
    context, page, pw, _ = _web_poll(browser, events_origin, token=False)
    try:
        _vote_yes(page, pw, 3)  # la date passée n'ira pas dans l'agenda
        page.get_by_role('button', name='Valider mes dates', exact=True).click()
        with page.expect_download() as info:
            page.get_by_role('button', name='Ajouter les 2 dates à mon agenda', exact=True).click()
        body = unfold(open(info.value.path(), encoding='utf-8').read())
        assert [e.split('UID:')[1].split('@')[0] for e in events(body)] == [OPT1, OPT2]
    finally:
        context.close()


NATIVE = """
window.__cal = { calls: [], added: 0, denied: %s };
window.PartyNative = { tabs: { update() {} }, calendar: {
  add(req) { window.__cal.calls.push(['add', req]); if (window.__cal.denied) return Promise.resolve({ denied: true });
             window.__cal.added = req.dates.length; return Promise.resolve({ added: req.dates.length, total: req.dates.length }); },
  status(id) { window.__cal.calls.push(['status', id]); return Promise.resolve({ added: window.__cal.added }); },
  settle(req) { window.__cal.calls.push(['settle', req]); return Promise.resolve({ changed: true }); },
  pending() { window.__cal.calls.push(['pending']); return Promise.resolve([]); },
} };
"""


def _open_in_app(browser, origin, ev, denied=False, agenda=False):
    import json as _json

    from tests.test_event_participant_browser import HEADERS, REST, USER, login, mock_services, pw
    context = browser.new_context(viewport={'width': 402, 'height': 874}, user_agent=(  # l'app iPhone se présente comme un iPhone
        'Mozilla/5.0 (iPhone; CPU iPhone OS 26_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148'))
    context.add_init_script(NATIVE % ('true' if denied else 'false'))
    page = context.new_page()
    mock_services(page)
    if agenda:
        mock_agenda(page)

    def events(route):
        if route.request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=HEADERS)
        single = 'vnd.pgrst.object' in (route.request.headers.get('accept') or '')
        route.fulfill(status=200, content_type='application/json', body=_json.dumps(ev if single else [ev]), headers=HEADERS)
    page.route(REST + 'events?**', events)
    page.route(REST + 'profiles?**', lambda r: r.fulfill(status=200, content_type='application/json', headers=HEADERS,
                                                          body=_json.dumps([{'id': USER, 'display_name': 'Camille'}])))
    page.goto(origin + '/events/', wait_until='domcontentloaded')
    login(page)
    pw.expect(page.get_by_role('button', name='Se connecter', exact=True)).to_have_count(0, timeout=15000)
    page.goto(f'{origin}/events/event/{EVENT_PAGE}', wait_until='domcontentloaded')
    return context, page, pw


def _poll_event():
    from tests.test_event_participant_browser import event_row
    return event_row(date_mode='poll', starts_at=None, max_participants=None, location_name='Cobalt Project', date_options=[
        {'id': OPT1, 'event_id': EVENT_PAGE, 'starts_at': '2030-11-20T18:00:00Z', 'ends_at': None, 'proposed_by': None, 'date_votes': []},
        {'id': OPT2, 'event_id': EVENT_PAGE, 'starts_at': '2030-11-27T18:00:00Z', 'ends_at': None, 'proposed_by': None, 'date_votes': []},
    ])


def test_in_the_iphone_app_validate_subscribes_and_clears_dates_the_app_had_put_itself(browser, events_origin):  # noqa: F811
    """App iPhone : la même méthode (agenda abonné) ; les dates mises avant par l'app partent, sinon doublon."""
    context, page, pw = _open_in_app(browser, events_origin, _poll_event(), agenda=True)
    try:
        pw.expect(page.get_by_role('button', name='Valider mes dates', exact=True)).to_be_visible(timeout=15000)
        _vote_yes(page, pw, 2)
        page.get_by_role('button', name='Valider mes dates', exact=True).click()
        page.get_by_role('button', name='Ajouter les 2 dates à mon agenda', exact=True).click()
        pw.expect(page.get_by_text('Confirme l’abonnement « Vendredi Party »', exact=False)).to_be_visible(timeout=10000)
        calls = page.evaluate('window.__cal.calls')
        assert not [c for c in calls if c[0] == 'add']
        assert any(c[0] == 'settle' and c[1]['eventId'] == EVENT_PAGE and c[1].get('cancelled') for c in calls)
    finally:
        context.close()


def test_in_the_iphone_app_without_the_agenda_link_the_app_puts_the_dates_itself(browser, events_origin):  # noqa: F811
    context, page, pw = _open_in_app(browser, events_origin, _poll_event())
    try:
        pw.expect(page.get_by_role('button', name='Valider mes dates', exact=True)).to_be_visible(timeout=15000)
        _vote_yes(page, pw, 2)
        page.get_by_role('button', name='Valider mes dates', exact=True).click()
        page.get_by_role('button', name='Ajouter les 2 dates à mon agenda', exact=True).click()
        pw.expect(page.get_by_text('Party gardera la bonne et retirera les autres', exact=False)).to_be_visible(timeout=10000)
        add = next(c[1] for c in page.evaluate('window.__cal.calls') if c[0] == 'add')
        assert [d['id'] for d in add['dates']] == [OPT1, OPT2] and add['title'] == 'Soirée de test participant'
        assert add['location'] == 'Cobalt Project' and add['eventId'] == EVENT_PAGE
    finally:
        context.close()


def test_without_calendar_access_the_app_says_where_to_allow_it(browser, events_origin):  # noqa: F811
    context, page, pw = _open_in_app(browser, events_origin, _poll_event(), denied=True)
    try:
        pw.expect(page.get_by_role('button', name='Valider mes dates', exact=True)).to_be_visible(timeout=15000)
        _vote_yes(page, pw, 1)
        page.get_by_role('button', name='Valider mes dates', exact=True).click()
        page.get_by_role('button', name='Ajouter la date à mon agenda', exact=True).click()
        pw.expect(page.get_by_text('autorise-le dans Réglages › Party › Calendriers', exact=False)).to_be_visible(timeout=10000)
    finally:
        context.close()


def test_once_the_date_is_fixed_the_app_keeps_it_and_removes_the_others(browser, events_origin):  # noqa: F811
    from tests.test_event_participant_browser import event_row
    fixed = event_row(date_mode='fixed', starts_at='2030-11-27T18:00:00Z', max_participants=None)
    context, page, pw = _open_in_app(browser, events_origin, fixed)
    try:
        page.wait_for_function("() => window.__cal.calls.some((c) => c[0] === 'settle')", timeout=15000)
        settle = next(c[1] for c in page.evaluate('window.__cal.calls') if c[0] == 'settle')
        assert settle['eventId'] == EVENT_PAGE and settle['start'] == '2030-11-27T18:00:00Z'
        assert settle['title'] == 'Soirée de test participant' and not settle.get('cancelled')
    finally:
        context.close()


def test_someone_who_said_no_to_the_fixed_date_keeps_nothing_in_the_calendar(browser, events_origin):  # noqa: F811
    from tests.test_event_participant_browser import USER, event_row
    fixed = event_row(date_mode='fixed', starts_at='2030-11-27T18:00:00Z', max_participants=None)
    fixed['rsvps'] = [{'event_id': EVENT_PAGE, 'user_id': USER, 'status': 'no', 'plus_ones': 0, 'note': None, 'waitlisted': False}]
    context, page, pw = _open_in_app(browser, events_origin, fixed)
    try:
        page.wait_for_function("() => window.__cal.calls.some((c) => c[0] === 'settle')", timeout=15000)
        settle = next(c[1] for c in page.evaluate('window.__cal.calls') if c[0] == 'settle')
        assert settle['eventId'] == EVENT_PAGE and settle.get('cancelled') is True
    finally:
        context.close()


def _web_fixed(browser, events_origin, subscribed: bool):
    from tests.test_event_participant_browser import event_row, open_event, pw
    ev = event_row(date_mode='fixed', starts_at='2030-11-27T18:00:00Z', max_participants=None)
    context, page = open_event(browser, events_origin, ev)
    calls = mock_agenda(page, subscribed)
    page.reload(wait_until='domcontentloaded')  # le lien est demandé à l'ouverture de la fiche
    return context, page, pw, calls


def test_a_normal_event_goes_to_the_same_subscribed_calendar(browser, events_origin):  # noqa: F811
    """Retour de l'admin (11.11) : même méthode pour un événement normal. Ordinateur : on choisit son agenda (19.11)."""
    context, page, pw, calls = _web_fixed(browser, events_origin, subscribed=False)
    try:
        page.get_by_role('button', name='Ajouter à mon agenda', exact=True).click(timeout=15000)
        page.get_by_role('button', name='Calendrier Apple', exact=True).click()
        pw.expect(page.get_by_text('Confirme l’abonnement « Vendredi Party »', exact=False)).to_be_visible(timeout=10000)
        assert calls[0] is False and calls[-1] is True
    finally:
        context.close()


def test_once_subscribed_one_tap_adds_a_normal_event_and_says_it_follows_changes(browser, events_origin):  # noqa: F811
    context, page, pw, calls = _web_fixed(browser, events_origin, subscribed=True)
    try:
        page.get_by_role('button', name='Ajouter à mon agenda', exact=True).click(timeout=15000)
        pw.expect(page.get_by_text('Ajouté à ton calendrier « Vendredi Party »', exact=False)).to_be_visible(timeout=10000)
        pw.expect(page.get_by_role('button', name='Déjà dans ton agenda, mis à jour tout seul')).to_be_disabled()
        assert calls[-1] is True
        page.reload(wait_until='domcontentloaded')
        pw.expect(page.get_by_text('Se met à jour tout seul si l’événement change.', exact=True)).to_be_visible(timeout=15000)
    finally:
        context.close()


def test_a_date_poll_has_the_add_to_my_agenda_button_even_before_voting(browser, events_origin):  # noqa: F811
    """Retour de l'admin (11.11, soir) : sur un sondage, pas de bouton « Ajouter à mon agenda » → qui ne l'avait jamais
    activé ne le pouvait pas d'ici. Le même bouton abonne ; les dates votées Oui / Si besoin y arrivent ensuite seules."""
    context, page, pw, calls = _web_poll(browser, events_origin, token=True)
    try:
        page.reload(wait_until='domcontentloaded')  # le lien est demandé à l'ouverture de la fiche
        page.get_by_role('button', name='Ajouter à mon agenda', exact=True).click(timeout=15000)
        page.get_by_role('button', name='Calendrier Apple', exact=True).click()
        pw.expect(page.get_by_text('Confirme l’abonnement « Vendredi Party »', exact=False)).to_be_visible(timeout=10000)
        assert calls[-1] is True
    finally:
        context.close()


def test_a_poll_where_i_voted_no_everywhere_has_no_agenda_button(browser, events_origin):  # noqa: F811
    from tests.test_event_participant_browser import USER, event_row, open_event, pw
    no = lambda opt: [{'option_id': opt, 'user_id': USER, 'vote': 'no'}]  # noqa: E731
    ev = event_row(date_mode='poll', starts_at=None, max_participants=None, date_options=[
        {'id': OPT1, 'event_id': EVENT_PAGE, 'starts_at': '2030-11-20T18:00:00Z', 'ends_at': None, 'proposed_by': None, 'date_votes': no(OPT1)},
        {'id': OPT2, 'event_id': EVENT_PAGE, 'starts_at': '2030-11-27T18:00:00Z', 'ends_at': None, 'proposed_by': None, 'date_votes': no(OPT2)},
    ])
    context, page = open_event(browser, events_origin, ev)
    try:
        pw.expect(page.get_by_role('button', name=re.compile(r'^Non : ')).first).to_be_visible(timeout=15000)
        pw.expect(page.get_by_role('button', name='Ajouter à mon agenda', exact=True)).to_have_count(0)
    finally:
        context.close()


ANDROID = 'Mozilla/5.0 (Linux; Android 15; SM-S921B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36'


def _android_fixed(browser, events_origin, subscribed: bool):
    from tests.test_event_participant_browser import event_row, open_event, pw
    ev = event_row(date_mode='fixed', starts_at='2030-11-27T18:00:00Z', max_participants=None)
    context, page = open_event(browser, events_origin, ev, user_agent=ANDROID)
    calls = mock_agenda(page, subscribed)
    page.add_init_script("window.open = (u) => { window.__opened = (window.__opened || []).concat([String(u)]); return {}; };")
    page.reload(wait_until='domcontentloaded')
    return context, page, pw, calls, None


def test_android_chooses_its_agenda_and_never_lands_in_google_by_default(browser, events_origin):  # noqa: F811
    """Avis du 19.11 : sous Android, « Ajouter à mon agenda » partait d'office dans Google Agenda. Désormais on choisit :
    Google, Outlook, ou « Samsung ou autre agenda » (lien copié à coller), ou juste cet événement."""
    context, page, pw, calls, _ = _android_fixed(browser, events_origin, subscribed=False)
    try:
        context.grant_permissions(['clipboard-read', 'clipboard-write'])
        page.get_by_role('button', name='Ajouter à mon agenda', exact=True).click(timeout=15000)
        for name in ('Google Agenda', 'Outlook', 'Samsung ou autre agenda', 'Juste cet événement'):
            pw.expect(page.get_by_role('button', name=name, exact=True)).to_be_visible()
        pw.expect(page.get_by_role('button', name='Calendrier Apple', exact=True)).to_have_count(0)
        assert not page.evaluate('window.__opened || []')  # rien d'ouvert avant le choix
        page.get_by_role('button', name='Samsung ou autre agenda', exact=True).click()
        pw.expect(page.get_by_text(f'/api/calendar-feed/{TOKEN}.ics', exact=False)).to_be_visible(timeout=10000)
        pw.expect(page.get_by_text('ICSx⁵', exact=False)).to_be_visible()
        assert calls[-1] is True and not page.evaluate('window.__opened || []')
    finally:
        context.close()


IPHONE_STORE = ('Mozilla/5.0 (iPhone; CPU iPhone OS 26_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 '
                'PartyApp-iOS/1.0.0 PartyStore')


def test_on_the_iphone_the_other_agenda_never_speaks_of_samsung_or_an_android_app(browser, events_origin):  # noqa: F811
    """Contrôle Apple du 26.11 (2.3.10) : dans l'app App Store, ni « Samsung » ni ICSx⁵ (app Android) : « Autre agenda
    (copier le lien) »."""
    from tests.test_event_participant_browser import event_row, open_event, pw
    ev = event_row(date_mode='fixed', starts_at='2030-11-27T18:00:00Z', max_participants=None)
    context, page = open_event(browser, events_origin, ev, user_agent=IPHONE_STORE)
    try:
        context.grant_permissions(['clipboard-read', 'clipboard-write'])
        mock_agenda(page, False)
        page.reload(wait_until='domcontentloaded')
        page.get_by_role('button', name='Autre agenda : Google, Outlook…', exact=True).click(timeout=15000)
        pw.expect(page.get_by_role('button', name='Google Agenda', exact=True)).to_be_visible()
        pw.expect(page.get_by_text('Samsung', exact=False)).to_have_count(0)
        page.get_by_role('button', name='Autre agenda (copier le lien)', exact=True).click()
        pw.expect(page.get_by_text(f'/api/calendar-feed/{TOKEN}.ics', exact=False)).to_be_visible(timeout=10000)
        pw.expect(page.get_by_text('ICSx', exact=False)).to_have_count(0)
        pw.expect(page.get_by_text('Samsung', exact=False)).to_have_count(0)
    finally:
        context.close()


def test_android_outlook_opens_the_outlook_subscription_page(browser, events_origin):  # noqa: F811
    context, page, pw, calls, _ = _android_fixed(browser, events_origin, subscribed=False)
    try:
        page.get_by_role('button', name='Ajouter à mon agenda', exact=True).click(timeout=15000)
        page.get_by_role('button', name='Outlook', exact=True).click()
        pw.expect(page.get_by_text('Confirme l’abonnement « Vendredi Party »', exact=False)).to_be_visible(timeout=10000)
        opened = page.evaluate('window.__opened || []')
        assert opened and opened[0].startswith('https://outlook.live.com/calendar/0/addfromweb?url=') and TOKEN in opened[0], opened
    finally:
        context.close()


def test_said_in_the_agenda_but_it_is_not_one_tap_adds_it_again(browser, events_origin):  # noqa: F811
    """Avis du 19.11 : « Dans ton agenda » alors que le téléphone ne l'a pas : « Pas dans ton agenda ? Le rajouter »."""
    context, page, pw, calls, _ = _android_fixed(browser, events_origin, subscribed=True)
    try:
        page.get_by_role('button', name='Ajouter à mon agenda', exact=True).click(timeout=15000)
        pw.expect(page.get_by_role('button', name='Déjà dans ton agenda, mis à jour tout seul')).to_be_disabled()
        page.get_by_role('button', name='Pas dans ton agenda ? Le rajouter', exact=True).click()
        page.get_by_role('button', name='Google Agenda', exact=True).click()
        opened = page.evaluate('window.__opened || []')
        assert opened and opened[0].startswith('https://calendar.google.com/calendar/render?cid=webcal'), opened
    finally:
        context.close()


def test_settings_add_the_party_agenda_again_without_any_event(browser, events_origin):  # noqa: F811
    """Avis du 19.11 : Réglages › Agenda Vendredi Party, pour le rajouter dans l'agenda du téléphone à tout moment."""
    from tests.test_event_participant_browser import HEADERS, REST
    context, page, pw, _, _ = _android_fixed(browser, events_origin, subscribed=True)
    try:
        page.route(REST + 'rpc/calendar_feed_link', lambda r: r.fulfill(status=204, headers=HEADERS) if r.request.method == 'OPTIONS'
                   else r.fulfill(status=200, content_type='application/json', headers=HEADERS, body=json.dumps({'token': TOKEN, 'subscribed': True})))
        page.goto(f'{events_origin}/events/profile', wait_until='domcontentloaded')
        page.get_by_text('Agenda Vendredi Party', exact=True).click(timeout=15000)  # la ligne des Réglages
        pw.expect(page.get_by_text('Pas sur ce téléphone ? Ajoute-le ci-dessous.', exact=False)).to_be_visible(timeout=15000)
        page.get_by_role('button', name='Outlook', exact=True).click()
        opened = page.evaluate('window.__opened || []')
        assert opened and 'outlook.live.com' in opened[0] and TOKEN in opened[0], opened
        pw.expect(page.get_by_text('Confirme l’abonnement « Vendredi Party »', exact=False)).to_be_visible()
    finally:
        context.close()
