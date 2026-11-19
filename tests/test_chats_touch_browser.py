"""Discussions web au doigt (avis de l'admin du 19.11, webapp iPhone : « on ne peut pas toucher une conversation, ça
sélectionne des noms »). Reproduit d'abord dans le vrai Safari du simulateur iPhone (journal des événements tactiles) :
  * un toucher normal (doigt qui bouge de 2-3 px, ~200 ms) n'ouvrait rien : au contact, la ligne affichait son « … » de
    survol, iOS prenait cette apparition pour un survol et n'envoyait pas le clic ; le doigt restait, l'appui long ouvrait
    le menu ;
  * l'appui long ouvrait le menu sous le doigt, puis iOS y sélectionnait un mot (poignées bleues, « Épingler »,
    « Supprimer »).
Ici, vrai navigateur (Chromium, gestes tactiles CDP, base simulée) : « … » jamais montré au doigt, un toucher ouvre la
conversation, appui long = menu sans sélection, aucun texte sélectionnable dans Discussions (menus compris), la saisie
reste éditable, et la règle ne s'applique qu'aux Discussions."""
from tests.test_chats_conversation_browser import conversation_services, maquette_messages, open_dm
from tests.test_chats_list_browser import G_BASKET, list_services, open_list, phone  # noqa: F401 (fixture)
from tests.test_events_browser import browser, events_origin, pw  # noqa: F401 (fixtures)

NO_SELECT = "e => [getComputedStyle(e).userSelect, getComputedStyle(e).webkitUserSelect]"


def touch(page, locator, hold_ms, before_release=None):
    """Doigt posé à gauche de l'élément (loin du bouton « Nouveau message »), qui bouge de 3 px (comme un vrai doigt),
    levé après hold_ms ; before_release vérifie l'écran doigt encore posé (Chromium envoie un clic au lever d'un appui
    long, iOS non : on regarde le menu avant)."""
    box = locator.bounding_box()
    x, y = box['x'] + min(90, box['width'] / 2), box['y'] + box['height'] / 2
    cdp = page.context.new_cdp_session(page)
    cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x, 'y': y}]})
    page.wait_for_timeout(60)
    cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': x + 2, 'y': y + 1}]})
    page.wait_for_timeout(60)
    cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': x + 3, 'y': y + 2}]})
    page.wait_for_timeout(max(hold_ms - 120, 0))
    if before_release:
        before_release()
    cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})


def test_a_finger_tap_opens_the_chat_and_a_long_press_opens_the_menu_without_selecting(phone, events_origin):  # noqa: F811
    page, errors = phone
    list_services(page)
    open_list(page, events_origin)
    row = page.get_by_role('button', name='Discussion Basket du mardi', exact=False)
    pw.expect(row).to_be_visible(timeout=15000)
    assert page.evaluate("document.documentElement.classList.contains('chats-touch')")
    for text in ('Basket du mardi', 'Discussions'):
        assert page.get_by_text(text, exact=True).first.evaluate(NO_SELECT) == ['none', 'none'], text

    # Toucher (~200 ms, doigt qui bouge un peu) : le « … » de survol ne paraît jamais, la conversation s'ouvre.
    more = page.get_by_role('button', name='Plus d’options : Basket du mardi')
    touch(page, row, 200, lambda: pw.expect(more).to_have_css('opacity', '0', timeout=1))
    pw.expect(page).to_have_url(f'{events_origin}/events/chats/{G_BASKET}', timeout=10000)

    # Appui long : le menu, sans aucune sélection (ni dans la ligne ni dans le menu ouvert sous le doigt).
    page.goto(f'{events_origin}/events/chats', wait_until='domcontentloaded')  # déjà connecté
    pw.expect(row).to_be_visible(timeout=15000)
    sheet = page.get_by_label('Options : Basket du mardi', exact=True)

    def menu_without_selection():
        pw.expect(sheet).to_be_visible()
        assert page.evaluate('getSelection().toString()') == ''
        assert sheet.get_by_role('menuitem', name='Épingler').evaluate(NO_SELECT) == ['none', 'none']
    touch(page, row, 900, menu_without_selection)
    assert not errors, errors


def test_conversation_bubbles_and_header_are_not_selectable_but_the_composer_is(phone, events_origin):  # noqa: F811
    page, errors = phone
    conversation_services(page, messages=maquette_messages())
    open_dm(page, events_origin)
    bubble = page.get_by_text('Hello ! Tu viens vendredi ? 🧀', exact=True)
    pw.expect(bubble).to_be_visible()
    assert bubble.evaluate(NO_SELECT) == ['none', 'none']
    assert page.get_by_role('button', name='Léa. Ouvrir son profil').evaluate(NO_SELECT) == ['none', 'none']
    assert page.get_by_label('Message', exact=True).evaluate(NO_SELECT) != ['none', 'none']  # saisie : on écrit, on sélectionne

    def menu_without_selection():  # « Copier » reste le moyen de copier un message
        pw.expect(page.get_by_role('menu').get_by_role('button', name='Copier')).to_be_visible()
        assert page.evaluate('getSelection().toString()') == ''
    touch(page, bubble, 900, menu_without_selection)
    # Hors des Discussions, rien ne change (la règle suit la page).
    page.goto(f'{events_origin}/events/', wait_until='domcontentloaded')
    page.wait_for_timeout(1500)
    assert not page.evaluate("document.documentElement.classList.contains('chats-touch')")
    assert not errors, errors
