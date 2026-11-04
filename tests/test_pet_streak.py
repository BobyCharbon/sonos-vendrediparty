"""Série 🔥 protégée (app/pet_streak.py), calendrier simulé : jours qui comptent, samedi en répit, gels ❄️,
rattrapage sous 48 h (1×/mois), paliers."""
from datetime import date, timedelta

from app import pet_streak as ps

WED = date(2026, 11, 4)          # un mercredi
FRI, SAT, SUN = date(2026, 11, 6), date(2026, 11, 7), date(2026, 11, 8)


def run(days, streak=None):
    s, events = streak or {**ps.new(), "freezes": 0}, []   # sans le gel de départ (testé à part)
    for d in days:
        s, ev = ps.note_day(s, d)
        events += ev
    return s, events


def kinds(events):
    return [e["kind"] for e in events]


def test_a_new_streak_starts_with_one_freeze_that_saves_the_first_missed_day():
    assert ps.new()["freezes"] == ps.START_FREEZES == 1
    s, events = run([WED, WED + timedelta(days=2)], ps.new())   # jeudi manqué : protégé par le gel offert
    assert s["count"] == 2 and s["freezes"] == 0 and "protected" in kinds(events)


def test_days_in_a_row_grow_and_the_same_day_counts_once():
    s, _ = run([WED, WED, WED + timedelta(days=1)])
    assert s["count"] == 2 and s["best"] == 2 and s["last"] == "2026-11-05"


def test_an_old_streak_without_the_new_fields_still_works():
    s, _ = ps.note_day({"count": 4, "last": "2026-11-03", "best": 6}, WED)
    assert s["count"] == 5 and s["best"] == 6 and s["freezes"] == 0


def test_saturday_is_protected_when_you_came_on_friday():
    s, events = run([FRI, SUN])
    assert s["count"] == 2 and s["freezes"] == 0
    assert events == [{"kind": "protected", "day": "2026-11-07", "by": "saturday"}]
    assert ps.current(s, SUN) == 2
    assert ps.current(run([FRI])[0], SUN) == 1   # dimanche, avant de passer : samedi protégé, la série tient


def test_saturday_is_not_protected_without_friday():
    s, events = run([FRI - timedelta(days=1), SUN])   # jeudi puis dimanche : vendredi et samedi manqués
    assert s["count"] == 1 and "broken" in kinds(events)


def test_a_freeze_every_seven_days_at_most_two():
    days = [WED + timedelta(days=i) for i in range(21)]
    s, events = run(days)
    assert s["count"] == 21 and s["freezes"] == 2
    assert kinds(events).count("freeze_earned") == 2   # 7 et 14 ; à 21 on en a déjà 2


def test_a_freeze_protects_one_missed_day_and_is_spent():
    days = [WED + timedelta(days=i) for i in range(7)]   # mer → mar : 7 jours, 1 gel
    s, _ = run(days)
    assert s["freezes"] == 1
    tue = days[-1]
    assert ps.current(s, tue + timedelta(days=2)) == 7    # mercredi manqué, jeudi pas encore fini
    s, events = ps.note_day(s, tue + timedelta(days=2))
    assert s["count"] == 8 and s["freezes"] == 0
    assert events[0] == {"kind": "protected", "day": (tue + timedelta(days=1)).isoformat(), "by": "freeze"}


def test_freezes_are_not_wasted_on_a_break():
    s, _ = run([WED + timedelta(days=i) for i in range(7)])
    s, events = ps.note_day(s, WED + timedelta(days=10))  # 3 jours manqués, 1 gel : cassée, le gel reste
    assert s["count"] == 1 and s["freezes"] == 1 and "protected" not in kinds(events)


def test_a_broken_streak_can_be_repaired_within_48_hours_with_brain_and_care():
    s, _ = run([WED + timedelta(days=i) for i in range(5)])        # mer → dim : 5 jours
    back = WED + timedelta(days=7)                                   # mardi (lundi manqué)
    s, events = ps.note_day(s, back)
    assert events[-1] == {"kind": "broken", "was": 5, "repair": True} and s["count"] == 1
    assert s["lost"] == {"count": 5, "until": (back + timedelta(days=1)).isoformat(), "brain": False, "care": False}
    s, ev = ps.repair_progress(s, "care", back)
    assert ev == [] and s["lost"]["care"]
    s, ev = ps.note_day(s, back + timedelta(days=1))                 # le lendemain : toujours possible
    s, ev = ps.repair_progress(s, "brain", back + timedelta(days=1))
    assert ev == [{"kind": "repaired", "count": 7}, {"kind": "milestone", "days": 7}]
    assert s["count"] == 7 and s["lost"] is None and s["repair_month"] == "2026-11"


def test_repair_expires_after_48_hours():
    s, _ = run([WED, WED + timedelta(days=1)])
    back = WED + timedelta(days=3)
    s, _ = ps.note_day(s, back)
    s, ev = ps.repair_progress(s, "care", back + timedelta(days=2))   # trop tard
    assert ev == [] and s["lost"] is None


def test_repair_once_a_month_and_only_after_a_short_break():
    s, _ = run([WED, WED + timedelta(days=1)])
    s, _ = ps.note_day(s, WED + timedelta(days=3))
    s, _ = ps.repair_progress(s, "care", WED + timedelta(days=3))
    s, _ = ps.repair_progress(s, "brain", WED + timedelta(days=3))
    assert s["count"] == 3
    s, events = ps.note_day(s, WED + timedelta(days=6))               # nouvelle casse le même mois
    assert events[-1] == {"kind": "broken", "was": 3, "repair": False} and s["lost"] is None
    s2, _ = run([WED, WED + timedelta(days=1)])
    s2, events = ps.note_day(s2, WED + timedelta(days=6))             # 4 jours manqués : trop long
    assert events[-1]["repair"] is False


def test_brain_already_played_today_counts_for_the_repair():
    s, _ = run([WED, WED + timedelta(days=1)])
    s, _ = ps.note_day(s, WED + timedelta(days=3), brain_today=True)
    s, ev = ps.repair_progress(s, "care", WED + timedelta(days=3))
    assert ev and ev[0]["kind"] == "repaired" and s["count"] == 3


def test_milestones_and_the_next_one():
    _, events = run([WED + timedelta(days=i) for i in range(14)])
    assert [e["days"] for e in events if e["kind"] == "milestone"] == [3, 7, 14]
    assert ps.next_milestone(0) == 3 and ps.next_milestone(7) == 14 and ps.next_milestone(365) is None


def test_the_clock_going_back_changes_nothing():
    s, _ = run([WED + timedelta(days=1)])
    s2, ev = ps.note_day(s, WED)
    assert s2 == ps.normalized(s) and ev == []
