"""Réglages › Notifications du module (campagne 2, rapport 07 bugs 4 et 5) :
- heures de silence : Début / Fin s'enregistrent au départ du champ ou à Entrée (onEndEditing n'existe pas sur le web) ;
- Membres (sans events.view) et Guests : les interrupteurs que la base refuse toujours (`private.may_receive_push`)
  ne sont plus affichés. `web/events/src/lib/notificationPrefs.ts` testé tel quel par Node, et comparé à la base."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'web/events/src'
PREFS = SRC / 'lib/notificationPrefs.ts'
SCREEN = (SRC / 'app/settings/notifications.tsx').read_text()
node = pytest.mark.skipif(shutil.which('node') is None, reason='Node absent')

# Interrupteur → types de notification qu'il commande.
PREF_KINDS = {'poll_new': ['poll_new'], 'poll_nudge': ['poll_nudge'], 'rsvp_set': ['rsvp_set'],
              'ticket_pay_confirmed': ['ticket_pay_confirmed'], 'ticket_issued': ['ticket_issued'], 'rsvp_mine': ['rsvp'],
              'proposal_result': ['approved', 'rejected'], 'ticket_pay_declared': ['ticket_pay_declared'], 'proposals': ['proposal'],
              'chat': ['message'], 'new_event': ['new_event'],
              'event_changed': ['event_changed'], 'date_fixed': ['date_fixed'], 'invites': ['private_invite'], 'waitlist': ['waitlist'],
              'link_join': ['link_join'], 'announce_results': ['announce_accepted', 'announce_refused', 'group_event_accepted', 'group_event_refused'],
              'announce_requests': ['announce_request'], 'group_event_requests': ['group_event_request'], 'reminders': ['reminder']}


def members_only() -> list:
    script = f"import {{ MEMBERS_ONLY_PREFS }} from {json.dumps(PREFS.as_uri())};\nconsole.log(JSON.stringify([...MEMBERS_ONLY_PREFS]));"
    return json.loads(subprocess.run(['node', '--no-warnings', '--input-type=module', '-e', script],
                                     capture_output=True, text=True, timeout=30, check=True).stdout)


def kinds_open_to_non_members() -> set:
    """Types que la base envoie aussi aux non-Membres VIP (dernière définition de private.may_receive_push)."""
    files = sorted(p for p in (ROOT / 'supabase/migrations').glob('*.sql') if 'function private.may_receive_push' in p.read_text())
    body = files[-1].read_text().split('function private.may_receive_push', 1)[1].split('$$;', 1)[0]
    return set(re.findall(r"'([a-z_]+)'", body))


@node
def test_hidden_switches_are_exactly_those_the_base_refuses_to_non_members():
    hidden = set(members_only())
    open_kinds = kinds_open_to_non_members()
    for pref, kinds in PREF_KINDS.items():
        refused = not any(k in open_kinds for k in kinds)
        assert (pref in hidden) == refused, pref


def test_screen_hides_members_only_switches_for_members_and_guests():
    assert 'mayShow(' in SCREEN
    for key in ('poll_new', 'poll_nudge', 'rsvp_set', 'ticket_pay_confirmed', 'ticket_issued', 'rsvp_mine', 'ticket_pay_declared', 'proposal_result'):
        assert re.search(rf"mayShow\('{key}'\)", SCREEN), key


def test_quiet_hours_save_on_blur_and_enter_on_the_web():
    assert 'onEndEditing=' not in SCREEN
    # Un seul champ réutilisé pour Début et Fin (timeField) : les deux enregistrent au départ du champ et à Entrée.
    assert 'onBlur={() => setTime(key)}' in SCREEN and 'onSubmitEditing={() => setTime(key)}' in SCREEN
    assert "timeField('quiet_start'" in SCREEN and "timeField('quiet_end'" in SCREEN


def test_quiet_hours_messages_are_shown_next_to_the_fields():
    assert 'timeError' in SCREEN


def test_invitation_switch_also_covers_being_added_as_co_organizer():
    # La base range coorganizer_added sous l'interrupteur « invites » (20261107100000_campagne2_invitations.sql).
    assert 'ou on t’ajoute comme co-organisateur' in SCREEN


def test_activity_lists_every_event_notification_kind_including_new_ones():
    """« Co-organisateur » (coorganizer_added) et « Événement rétabli » (event_changed) s'affichent : l'Activité ne filtre
    que les annonces admin (affichées à part) et montre le titre / texte écrits par la base."""
    activity = (SRC / 'app/(tabs)/activity.tsx').read_text()
    assert re.findall(r"\.(?:neq|eq|in|not)\('kind'", activity) == [".neq('kind'"]
    assert "{n.title}" in activity and "{n.body}" in activity


def test_cancel_is_hidden_when_edit_is_hidden_except_for_the_creator():
    fiche = (SRC / 'app/event/[id]/index.tsx').read_text()
    assert "canEdit || ev.created_by === me.id ? <ConfirmButton" in fiche
