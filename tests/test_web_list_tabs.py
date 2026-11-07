"""Liste des événements (campagne 2, rapport 06 bug 2, rapport 10 bug 12) : un événement à venir ANNULÉ reste dans « À venir »
(barré, « Annulé ») pour l'organisateur, les invités et l'admin (ils le retrouvent pour le supprimer ou le rouvrir) ;
les présents ne bloquent plus la première carte. `web/events/src/lib/eventTime.ts` testé tel quel par Node."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TABS = ROOT / 'web/events/src/lib/eventTime.ts'
NOW = '2026-11-07T12:00:00Z'
ME = 'me'
node = pytest.mark.skipif(shutil.which('node') is None, reason='Node absent')


def tabs_of(event: dict) -> list:
    base = {'status': 'published', 'date_mode': 'fixed', 'created_by': 'other', 'starts_at': None}
    script = (f"import {{ inTab }} from {json.dumps(TABS.as_uri())};\n"
              f"const e = {json.dumps({**base, **event})};\n"
              f"console.log(JSON.stringify(['upcoming','polls','pending','drafts','past'].filter((t) => inTab(e, t, {json.dumps(ME)}, Date.parse({json.dumps(NOW)})))));")
    return json.loads(subprocess.run(['node', '--no-warnings', '--input-type=module', '-e', script],
                                     capture_output=True, text=True, timeout=30, check=True).stdout)


@node
def test_cancelled_upcoming_event_stays_in_upcoming():
    assert tabs_of({'status': 'cancelled', 'starts_at': '2026-11-20T19:00:00Z'}) == ['upcoming']


@node
def test_cancelled_past_event_is_in_past_only():
    assert tabs_of({'status': 'cancelled', 'starts_at': '2026-11-01T19:00:00Z'}) == ['past']


@node
def test_published_draft_pending_and_polls_unchanged():
    assert tabs_of({'starts_at': '2026-11-20T19:00:00Z'}) == ['upcoming']
    assert tabs_of({'date_mode': 'poll'}) == ['polls']
    assert tabs_of({'status': 'pending', 'created_by': ME, 'starts_at': '2026-11-20T19:00:00Z'}) == ['pending']
    assert tabs_of({'status': 'rejected', 'created_by': ME}) == ['drafts']
    assert tabs_of({'status': 'draft', 'created_by': 'other'}) == []


def test_list_uses_the_tab_rule_and_does_not_wait_for_attendance_before_the_first_card():
    src = (ROOT / 'web/events/src/app/(tabs)/index.tsx').read_text()
    assert 'inTab(' in src
    assert 'await fetchAttendance' not in src


def test_cancelled_card_title_is_struck_through_and_announced():
    src = (ROOT / 'web/events/src/components/EventCard.tsx').read_text()
    assert "textDecorationLine: 'line-through'" in src
    assert 'annulé' in src
