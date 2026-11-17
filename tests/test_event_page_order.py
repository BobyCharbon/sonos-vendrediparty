"""Ordre de la fiche d'un événement (demande de l'admin du 17.11) : les sondages viennent juste après « Présent /
Absent » (et le billet), avant la carte Invités, les infos, les participants et le reste ; ils étaient trop bas."""
from pathlib import Path

PAGE = (Path(__file__).resolve().parents[1] / "web/events/src/app/event/[id]/index.tsx").read_text(encoding="utf-8")


def test_polls_come_right_after_the_answer_buttons():
    rsvp, polls = PAGE.index("<RsvpCard"), PAGE.index("<PollSection")
    assert rsvp < polls
    for later in ("<GuestListCard", "<CarpoolCard", "infoRows.map", "<ParticipantsSection", "<BringSection", "<EventPronos"):
        assert polls < PAGE.index(later), later
