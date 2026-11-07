"""Fiche d'un événement légère et robuste (campagne 2, rapports 06, 09, 10) :
- elle ne lit plus TOUS les profils, résultats et votes de Party, seulement ceux de l'événement (personnes concernées) ;
- le temps réel des votes est filtré sur l'événement (un vote ailleurs ne recharge plus chaque fiche ouverte) ;
- une requête secondaire qui échoue ne remplace plus toute la fiche ; hors ligne / supprimé : message clair.
`web/events/src/lib/eventPeople.ts` est testé tel quel par Node ; le reste est vérifié dans la source de la fiche."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'web/events/src'
PEOPLE = SRC / 'lib/eventPeople.ts'
SCREEN = (SRC / 'app/event/[id]/index.tsx')
node = pytest.mark.skipif(shutil.which('node') is None, reason='Node absent')

A, B, C, D, E = (f'{c * 8}-aaaa-4aaa-8aaa-{c * 12}' for c in 'abcde')


def run(expr: str):
    script = f"import {{ eventPeopleIds }} from {json.dumps(PEOPLE.as_uri())};\nconsole.log(JSON.stringify({expr}));"
    out = subprocess.run(['node', '--no-warnings', '--input-type=module', '-e', script], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout)


@node
def test_people_of_an_event_are_collected_from_every_nested_part():
    event = {'id': 'x', 'created_by': A, 'event_organizers': [{'user_id': B}], 'rsvps': [{'user_id': C, 'status': 'yes'}],
             'date_options': [{'proposed_by': D, 'date_votes': [{'user_id': E, 'option_id': 'o'}]}],
             'bring_items': [{'created_by': A, 'bring_claims': [{'user_id': B}]}], 'title': 'pas un id', 'category': None}
    ids = run(f"eventPeopleIds({json.dumps(event)}, [{{ user_id: {json.dumps(E)} }}])")
    assert sorted(ids) == sorted([A, B, C, D, E])


@node
def test_non_uuid_values_and_empty_events_give_no_ids():
    assert run("eventPeopleIds({ created_by: 'moi', rsvps: [] }, [])") == []


def screen() -> str:
    return SCREEN.read_text()


def test_screen_no_longer_reads_every_profile_poll_result_or_vote_of_party():
    src = screen()
    assert not re.search(r"from\('profiles'\)\.select\('id, display_name'\)\s*,", src)  # plus de lecture sans filtre
    assert ".from('profiles').select('id, display_name').in('id'" in src
    assert ".from('poll_results').select('*').in('poll_id'" in src
    assert ".from('poll_votes').select('option_id, user_id').in('poll_id'" in src
    assert "from('poll_results').select('*')," not in src


def test_realtime_votes_are_filtered_on_this_event():
    src = screen()
    assert "{ table: 'date_votes' }" not in src and "{ table: 'poll_votes' }" not in src
    assert 'option_id=in.(' in src and 'poll_id=in.(' in src


def test_secondary_requests_never_replace_the_whole_screen():
    src = screen()
    # Seul l'événement lui-même est obligatoire (must) ; le reste se lit avec un repli.
    assert src.count('must(') == 1


def test_gone_and_offline_states_have_clear_french_messages():
    src = screen()
    assert 'isGoneError' in src and 'GONE_TEXT' in src
    assert 'Pas de connexion' in src
    assert "addEventListener('online'" in src or 'useOnline' in src


def test_refuse_asks_for_confirmation_and_a_reason_like_administration():
    src = screen()
    assert "reject_event', { e: ev.id, reason: null }" not in src
    assert 'RejectProposal' in src
    comp = (SRC / 'components/RejectProposal.tsx').read_text()
    assert 'Confirmer le refus' in comp and "reason.trim() || null" in comp


def test_payments_refresh_without_reloading_the_page():
    src = screen()
    assert 'usePaymentsTick' in src or 'paymentsTick' in src
