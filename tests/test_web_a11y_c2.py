"""Accessibilité du module Événements (campagne 2, rapport 09) : pas de règle interdite sur « * » (zoom : décision de l'admin) ; ✕ des feuilles 44×44 sur le web ; contraste AA des pastilles
actives (blanc sur le rose foncé des gros boutons) ; page inconnue en français ; « + Proposer » effacé non focalisable."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'web/events/src'
POSTBUILD = (ROOT / 'web/events/scripts/postbuild.mjs').read_text()


def test_no_star_rules_for_touch_or_overscroll():
    # Le zoom reste coupé partout (décision « plus de zoom, l'app se sent native », test_ios_app.py) : le zoom à deux
    # doigts (WCAG 1.4.4, rapport 09 n°6) est une décision de l'admin, pas une correction de ce lot.
    assert not re.search(r'\*\s*\{[^}]*(overscroll-behavior|touch-action)', POSTBUILD)


def test_inputs_stay_at_16px_so_ios_does_not_zoom_on_focus():
    ui = (SRC / 'components/ui.tsx').read_text()
    block = ui[ui.index('  input: {'):ui.index('inputFocus:')]
    assert 'fontSize: 16' in block


def test_sheet_close_button_is_44_by_44_on_the_web():
    sheet = (SRC / 'components/SheetGesture.tsx').read_text()
    close = re.search(r'close: \{([^}]*)\}', sheet).group(1)
    assert 'width: 44' in close and 'height: 44' in close


def test_active_segments_and_tabs_use_the_deep_pink_of_main_buttons():
    ui = (SRC / 'components/ui.tsx').read_text()
    # Accueil (08.11) : les onglets du haut sont devenus des pastilles (HomeHeader), même rose profond.
    pills = (SRC / 'components/HomeHeader.tsx').read_text()
    assert re.search(r'segmentOn: \{ backgroundColor: colors\.action', ui)
    assert re.search(r'pillOn: \{ backgroundColor: colors\.action', pills)


def test_unknown_page_is_in_french():
    page = (SRC / 'app/+not-found.tsx').read_text()
    assert 'Page introuvable' in page and 'Retour aux événements' in page
    assert 'Unmatched' not in page


def test_hidden_propose_button_leaves_the_keyboard_order():
    home = (SRC / 'app/(tabs)/index.tsx').read_text()
    assert home.count('tabIndex={fabAway ? -1 : 0}') == 2


def test_entry_screen_says_what_cancel_cancels():
    entry = (SRC / 'components/EventEntry.tsx').read_text()
    assert 'Annuler l’arrivée' in entry
    assert not re.search(r"label=\"Annuler\"", entry)
