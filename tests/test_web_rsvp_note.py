"""Petit mot, sondages, « Qui amène quoi » (campagne 2, correction G) : le mot est lu dans `rsvp_notes` (personne +
organisation), envoyé seulement s'il change ('' l'efface, null = inchangé), après les CGU ; mot, sondage, choix et objet
sont signalables ; l'écran Signalements connaît ces types. `lib/rsvpNote.ts` testé tel quel par Node."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'web/events/src'
NOTE = SRC / 'lib/rsvpNote.ts'
node = pytest.mark.skipif(shutil.which('node') is None, reason='Node absent')


def run(expr: str):
    script = (f"import * as m from {json.dumps(NOTE.as_uri())};\n"
              f"console.log(JSON.stringify({expr} ?? null));")
    out = subprocess.run(['node', '--no-warnings', '--input-type=module', '-e', script],
                         capture_output=True, text=True, timeout=30, check=True).stdout
    return json.loads(out)


@node
def test_unchanged_note_is_not_sent():
    assert run("m.noteToSend('Je viens avec du vin', '  Je viens avec du vin ')") is None
    assert run("m.noteToSend(null, '')") is None
    assert run("m.noteToSend(undefined, '   ')") is None


@node
def test_cleared_note_sends_an_empty_string_not_null():
    assert run("m.noteToSend('Je viens avec du vin', '')") == ''
    assert run("m.noteToSend('Je viens', '   ')") == ''


@node
def test_new_or_changed_note_is_sent_trimmed():
    assert run("m.noteToSend(null, ' Salut ')") == 'Salut'
    assert run("m.noteToSend('Salut', 'Salut à tous')") == 'Salut à tous'


@node
def test_who_comes_card_shows_the_others_notes_in_answer_order():
    notes = [{'id': 'n1', 'user_id': 'b', 'note': 'B'}, {'id': 'n2', 'user_id': 'me', 'note': 'moi'},
             {'id': 'n3', 'user_id': 'a', 'note': 'A'}, {'id': 'n4', 'user_id': 'c', 'note': '  '}]
    got = run(f"m.othersNotes({json.dumps(notes)}, 'me', ['a', 'b', 'c'])")
    assert [n['id'] for n in got] == ['n3', 'n1']


def test_notes_are_read_from_rsvp_notes_and_rsvps_note_is_never_read():
    rsvp = (SRC / 'lib/rsvp.ts').read_text()
    assert "from('rsvp_notes')" in rsvp
    sections = (SRC / 'components/EventSections.tsx').read_text()
    assert 'r.note' not in sections and 'mine?.note' not in sections and 'mine.note' not in sections


def test_save_rsvp_sends_the_note_only_when_given():
    rsvp = (SRC / 'lib/rsvp.ts').read_text()
    assert 'current?.note' not in rsvp  # null = inchangé : on ne renvoie jamais l'ancien mot
    assert "patch.note !== undefined ? { note: patch.note }" in rsvp


def test_note_poll_option_and_bring_item_ask_the_terms_and_can_be_reported():
    sections = (SRC / 'components/EventSections.tsx').read_text()
    assert sections.count('terms.ensure()') >= 3
    for kind in ("'rsvp_note'", "'poll'", "'poll_option'", "'bring_item'"):
        assert kind in sections, kind
    assert '<ReportSheet' in sections
    moderation = (SRC / 'lib/moderation.ts').read_text()
    for kind in ('rsvp_note', 'poll', 'poll_option', 'bring_item'):
        assert f"'{kind}'" in moderation, kind


def test_db_refusal_keys_are_removed_from_the_message():
    sections = (SRC / 'components/EventSections.tsx').read_text()
    assert 'dbMessage(' in sections


def test_admin_reports_screen_names_the_new_kinds_and_opens_the_event():
    reports = (SRC / 'app/admin/reports.tsx').read_text()
    for label in ('Petit mot', 'Sondage', 'Choix de sondage', 'Objet à amener'):
        assert label in reports, label
    assert 'EVENT_KINDS' in reports
