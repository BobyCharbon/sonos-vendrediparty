"""Un événement terminé ne prend plus de réponses à l'écran (campagne 2, rapport 06 bug 4) : `rsvpClosed` regarde aussi la
fin de l'événement (6 h après, comme « Passés »). `web/events/src/lib/eventTime.ts` testé tel quel par Node."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TIME = ROOT / 'web/events/src/lib/eventTime.ts'
pytestmark = pytest.mark.skipif(shutil.which('node') is None, reason='Node absent')
NOW = '2026-11-07T12:00:00Z'


def closed(event: dict) -> bool:
    script = (f"import {{ answersClosed }} from {json.dumps(TIME.as_uri())};\n"
              f"console.log(JSON.stringify(answersClosed({json.dumps(event)}, Date.parse({json.dumps(NOW)}))));")
    return json.loads(subprocess.run(['node', '--no-warnings', '--input-type=module', '-e', script],
                                     capture_output=True, text=True, timeout=30, check=True).stdout)


def test_event_ended_two_days_ago_is_closed():
    assert closed({'rsvp_deadline': None, 'date_mode': 'fixed', 'starts_at': '2026-11-05T19:00:00Z', 'ends_at': '2026-11-05T23:00:00Z'})


def test_event_in_progress_or_ended_less_than_6_hours_ago_stays_open():
    assert not closed({'rsvp_deadline': None, 'date_mode': 'fixed', 'starts_at': '2026-11-07T08:00:00Z', 'ends_at': None})
    assert not closed({'rsvp_deadline': None, 'date_mode': 'fixed', 'starts_at': '2026-11-07T02:00:00Z', 'ends_at': '2026-11-07T07:00:00Z'})


def test_deadline_still_closes_and_date_polls_without_date_stay_open():
    assert closed({'rsvp_deadline': '2026-11-07T11:00:00Z', 'date_mode': 'fixed', 'starts_at': '2026-11-10T19:00:00Z', 'ends_at': None})
    assert not closed({'rsvp_deadline': None, 'date_mode': 'poll', 'starts_at': None, 'ends_at': None})


def test_rsvp_closed_uses_the_end_of_the_event():
    src = (ROOT / 'web/events/src/lib/rsvp.ts').read_text()
    assert 'answersClosed' in src
