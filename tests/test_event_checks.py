"""Campagne 2, lot C1 (web : création et publication, 07.11.2026).

- web/events/src/lib/eventChecks.ts testé tel quel par Node : dates incohérentes, accompagnants / prix / places jamais
  corrigés en silence, rang dans la liste d'attente (même ordre que la base).
- Gardes lues dans le code des écrans : double toucher « Publier », brouillon repris, publication de l'étape 2 sans état
  à moitié, interrupteurs « Prévenir » indépendants, réponse confirmée après l'enregistrement, « + » sans perte, CGU avant
  le petit mot, « Abandonner les changements ? ».
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / 'web/events/src'
CHECKS = WEB / 'lib/eventChecks.ts'
node = pytest.mark.skipif(shutil.which('node') is None, reason='Node absent')

NOW = '2026-11-07T12:00:00.000Z'


def run(exprs: dict) -> dict:
    body = ',\n'.join(f'{json.dumps(k)}: {v}' for k, v in exprs.items())
    script = (f"import * as c from {json.dumps(CHECKS.as_uri())};\nconst now = Date.parse({json.dumps(NOW)});\n"
              f"console.log(JSON.stringify({{{body}}}));")
    out = subprocess.run(['node', '--no-warnings', '--input-type=module', '-e', script],
                         capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout)


def dates(**kw) -> str:
    base = {'starts': None, 'rsvpDeadline': None, 'pollDeadline': None, 'slots': [], 'startsChanged': True}
    base.update(kw)
    return f'c.dateProblem({{now, ...{json.dumps(base)}}})'


def src(rel: str) -> str:
    return (WEB / rel).read_text(encoding='utf-8')


@node
def test_incoherent_dates_are_refused_with_a_clear_sentence():
    r = run({
        'yesterday': dates(starts='2026-11-06T12:00:00.000Z'),
        'just_started': dates(starts='2026-11-07T11:30:00.000Z'),
        'old_but_unchanged': dates(starts='2026-11-01T12:00:00.000Z', startsChanged=False),
        'deadline_after_start': dates(starts='2026-11-20T18:00:00.000Z', rsvpDeadline='2026-11-21T10:00:00.000Z'),
        'deadline_before_start': dates(starts='2026-11-20T18:00:00.000Z', rsvpDeadline='2026-11-19T10:00:00.000Z'),
        'vote_after_slots': dates(pollDeadline='2026-11-25T10:00:00.000Z',
                                  slots=[{'iso': '2026-11-20T18:00:00.000Z', 'isNew': True}, {'iso': '2026-11-27T18:00:00.000Z', 'isNew': True}]),
        'vote_ok': dates(pollDeadline='2026-11-18T10:00:00.000Z', slots=[{'iso': '2026-11-20T18:00:00.000Z', 'isNew': True}]),
        'past_new_slot': dates(slots=[{'iso': '2026-11-01T18:00:00.000Z', 'isNew': True}]),
        'past_old_slot': dates(slots=[{'iso': '2026-11-01T18:00:00.000Z', 'isNew': False}]),
    })
    assert r['yesterday'] == 'Le début est déjà passé : choisis une date à venir'
    assert r['just_started'] is None and r['old_but_unchanged'] is None
    assert r['deadline_after_start'] == 'La date limite de réponse doit être avant le début de l’événement'
    assert r['deadline_before_start'] is None
    assert r['vote_after_slots'] == 'La fin du vote doit être avant le premier créneau proposé'
    assert r['vote_ok'] is None
    assert r['past_new_slot'].endswith(': déjà passé') and r['past_old_slot'] is None


@node
def test_plus_ones_price_and_places_are_never_corrected_silently():
    r = run({
        'p_empty': 'c.plusOnesProblem("", 9)', 'p_ok': 'c.plusOnesProblem("2", 9)', 'p_zero': 'c.plusOnesProblem("0", 9)',
        'p_neg': 'c.plusOnesProblem("-3", 9)', 'p_big': 'c.plusOnesProblem("50", 9)', 'p_dec': 'c.plusOnesProblem("2.7", 9)',
        'price_ok': 'c.priceProblem("12,50")', 'price_3dec': 'c.priceProblem("12.345")', 'price_huge': 'c.priceProblem("1000000000")',
        'price_neg': 'c.priceProblem("-5")', 'price_txt': 'c.priceProblem("abc")', 'price_apos': 'c.priceProblem("1\'000")',
        'places_ok': 'c.placesProblem("12")', 'places_huge': 'c.placesProblem("99999999999")', 'places_dec': 'c.placesProblem("2.5")',
    })
    assert r['p_empty'] is None and r['p_ok'] is None
    assert 'coupe « Accompagnants (+1) »' in r['p_zero'] and r['p_neg'].startswith('Accompagnants max')
    assert r['p_big'] == 'Accompagnants max : 9 au plus (vide = illimité)' and r['p_dec'].startswith('Accompagnants max')
    assert r['price_ok'] is None and 'deux chiffres après la virgule' in r['price_3dec']
    assert r['price_huge'].startswith('Le prix ne peut pas dépasser')
    assert r['price_neg'] == r['price_txt'] == r['price_apos'] == 'Le prix doit être un montant positif ou zéro'
    assert r['places_ok'] is None and r['places_huge'].startswith('Nombre de places :') and r['places_dec'] == 'Nombre de places invalide'


@node
def test_waitlist_rank_follows_the_database_order():
    rsvps = [
        {'user_id': 'a', 'status': 'yes', 'waitlisted': False, 'updated_at': '2026-11-01T10:00:00Z',
         'plus_ones_waitlisted': 1, 'plus_ones_waitlisted_since': '2026-11-02T10:00:00Z'},
        {'user_id': 'b', 'status': 'yes', 'waitlisted': True, 'updated_at': '2026-11-03T10:00:00Z'},
        {'user_id': 'c', 'status': 'yes', 'waitlisted': True, 'updated_at': '2026-11-01T12:00:00Z'},
        {'user_id': 'd', 'status': 'maybe', 'waitlisted': False, 'updated_at': '2026-11-01T09:00:00Z'},
    ]
    r = run({k: f'c.waitlistRank({json.dumps(rsvps)}, {json.dumps(k)})' for k in 'abcd'})
    assert r == {'a': None, 'b': 3, 'c': 1, 'd': None}  # l'accompagnant de a (02.11) passe entre c et b


def test_double_tap_on_publish_is_guarded_before_the_terms_wait():
    form = src('components/EventForm.tsx')
    guard, terms = form.index('saving.current = true;'), form.index('await terms.ensure()')
    assert form.index('if (saving.current) return;') < guard < terms
    step = src('components/InviteStep.tsx')
    assert 'if (publishing.current) return;' in step and 'publishing.current = true;' in step
    sheet = src('components/InviteSheet.tsx')
    assert 'if (inviting.current) return;' in sheet and 'if (creating.current) return null;' in sheet


def test_form_checks_are_wired_and_never_clamp_silently():
    form = src('components/EventForm.tsx')
    for name in ('dateProblem(', 'plusOnesProblem(', 'priceProblem(', 'placesProblem('):
        assert name in form, name
    assert 'Math.max(1, Math.min(UNLIMITED_PLUS_ONES - 1' not in form


def test_a_failed_publish_keeps_one_draft_and_says_so():
    form = src('components/EventForm.tsx')
    assert 'savedEventId.current = id;' in form and 'orphanDraft.current = id;' in form
    assert 'L’événement n’est pas encore publié' in form
    # Quitter après un échec : le brouillon commencé est supprimé avec « Abandonner ».
    assert "supabase.from('events').delete().eq('id', orphan)" in form


def test_leaving_a_changed_form_asks_first():
    form = src('components/EventForm.tsx')
    guard = src('components/LeaveGuard.tsx')
    assert 'useLeaveGuard(' in form and '(dirty || !!orphan) && !doneAt' in form
    assert "from 'expo-router/react-navigation'" in guard and 'usePreventRemove(' in guard
    assert 'Abandonner les changements ?' in guard and "'beforeunload'" in guard
    # En-tête : « Annuler » à la place du titre (long) de l'événement, qui chevauchait « Modifier ».
    assert 'label="Annuler" iconOnly={!eventId}' in form


def test_invite_step_publishes_without_a_half_changed_draft():
    step = src('components/InviteStep.tsx')
    assert ".update({ status, announce_group: announceGroup })" in step
    assert 'restoreDraft(' in step and 'Rien n’est publié' in step


def test_announce_switches_are_independent_and_named():
    step = src('components/InviteStep.tsx')
    assert 'useState({ vip: false, group: false });  // « Prévenir » : éteints par défaut, chacun le sien' in step
    choice = src('components/VisibilityChoice.tsx')
    assert 'label="Prévenir les Membres Vendredi Party"' in choice and 'announce.vip' in choice and 'announce.group' in choice


def test_invite_sheet_error_is_shown_next_to_its_button():
    sheet = src('components/InviteSheet.tsx')
    assert "errorAt === 'link'" in sheet and "errorAt === 'people'" in sheet
    assert 'dbMessage(' in sheet


def test_nudge_all_skips_people_without_the_app():
    card = src('components/GuestListCard.tsx')
    assert 'people.filter((p) => p.has_app)' in card


def test_rsvp_card_confirms_only_after_the_save():
    ui = src('components/EventSections.tsx')
    assert 'choosing\n      ? confirmations[choosing]' not in ui and 'Enregistrement…' in ui
    assert 'guestsTarget.current' in ui and 'terms.ensure()' in ui and '{terms.sheet}' in ui
    assert 'Tu seras en liste d’attente' in ui and 'waitlistRank(' in ui
    shared = src('components/BringShared.tsx')
    assert 'target.current' in shared


def test_plus_minus_buttons_are_44_points_wide():
    assert 'minWidth: 44' in src('components/EventSections.tsx') and 'minWidth: 44' in src('components/BringShared.tsx')


def test_invite_sheet_announces_only_the_groups_added_there():
    sheet = src('components/InviteSheet.tsx')
    assert 'turnOnAnnounce' not in sheet
    assert 'groups.map((g) => g.id), groups.length > 0 && announce && !event.announce_group)' in sheet
    assert "...(announce ? { announce } : {})" in src('lib/invites.ts')


def test_co_organizers_are_only_accounts_that_can_edit():
    form = src('components/EventForm.tsx')
    assert "from('role_permissions').select('role').in('perm', ['events.edit_own_published', 'events.manage_all'])" in form
    assert "ctx.editors.has(m.role ?? '')" in form


def test_screen_reader_names_and_theme_pink():
    ui = src('components/EventSections.tsx')
    assert "self ? 'Ton profil'" in ui and 'accessibilityRole="progressbar"' in ui
    assert 'pillLead: { backgroundColor: colors.action }' in ui
    sheet = src('components/InviteSheet.tsx')
    assert 'aria-label={`Inviter à ${event.title}`}' in sheet and "party.bobycharbon.ch/events/invite/…" not in sheet
    assert 'aria-label="Abandonner les changements ?"' in src('components/LeaveGuard.tsx')
