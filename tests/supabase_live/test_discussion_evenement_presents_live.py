"""Discussion d'un événement réservée à ceux qui viennent (décision de l'admin du 19.11, migration 20261119120000), sur la
VRAIE base de TEST, bots seulement, transactions ANNULÉES : Présent / Peut-être et l'organisation la voient dans
Discussions, la lisent, y écrivent, la trouvent et en reçoivent les notifications ; pas répondu ou Absent : rien ; dès
Présent / Peut-être, tout revient. Aussi : chat_search (recherche « Messages » des Discussions).
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_discussion_evenement_presents_live.py -q"""
from tests.supabase_live.test_bar_options_live import as_bot, as_postgres, keep, note, run
from tests.supabase_live.test_discussion_evenement_live import CHAT, say
from tests.supabase_live.test_member_admin_live import pytestmark  # noqa: F401


def sees(label: str) -> str:
    """Ce que voit le bot courant : messages lus, ligne dans la liste, résultat de recherche, état « open »."""
    return (keep(f"{label}_read", "(select count(*) from public.messages where event_id = e)")
            + keep(f"{label}_list", "(select count(*) from jsonb_array_elements(public.chat_list(false)) c where c->>'id' = e::text)")
            + keep(f"{label}_find", "(select count(*) from jsonb_array_elements(public.chat_event_search('[Recette] Discussion')) c where c->>'id' = e::text)")
            + keep(f"{label}_msg", "(select count(*) from jsonb_array_elements(public.chat_search('cachalot')) c where c->>'id' = e::text)")
            + keep(f"{label}_open", "public.event_chat_state(e)->>'open'"))


def notified(label: str, who: str) -> str:
    return keep(label, f"(select count(*) from public.notifications where event_id = e and user_id = {who} and kind = 'message')")


def test_only_present_maybe_and_the_organisation_have_the_event_chat():
    # CHAT : Olga crée, Côme co-organise, Ada Présent, Victor Absent, Valentin invité sans réponse.
    out = run(CHAT + as_bot("olga") + say("Le cachalot arrive à 20 h") + say("@toutlemonde on bouge")
              + as_postgres() + notified("n_ada", "ada") + notified("n_victor", "victor") + notified("n_valentin", "valentin")
              + as_bot("ada") + sees("ada") + note("ada_write", "insert into public.messages (event_id, user_id, body) values (e, auth.uid(), 'Je viens')")
              + as_bot("come") + sees("come")
              + as_bot("victor") + sees("victor") + note("victor_write", "insert into public.messages (event_id, user_id, body) values (e, auth.uid(), 'Et moi ?')")
              + note("victor_media", "perform public.event_chat_media(e, null, 10)")
              + as_bot("valentin") + sees("valentin")
              # Valentin répond Peut-être : il retrouve tout ; puis Absent : il perd tout.
              + as_postgres() + "insert into public.rsvps (event_id, user_id, status) values (e, valentin, 'maybe');"
              + as_bot("valentin") + sees("valentin_maybe")
              + as_postgres() + "update public.rsvps set status = 'no' where event_id = e and user_id = valentin;"
              + as_bot("valentin") + sees("valentin_no"))
    for who in ("ada", "come", "valentin_maybe"):
        for what, want in (("read", "3" if who == "come" else None), ("list", "1"), ("find", "1"), ("msg", "1"), ("open", "true")):
            if want:
                assert f"{who}_{what}={want}" in out, (who, what, out)
    assert "ada_read=2" in out and "ada_write=ok" in out, out  # avant le « Je viens » d'Ada
    for who in ("victor", "valentin", "valentin_no"):
        for what in ("read", "list", "find", "msg"):
            assert f"{who}_{what}=0" in out, (who, what, out)
        assert f"{who}_open=false" in out, (who, out)
    assert "victor_write=new row violates" in out and "victor_media=forbidden" in out, out
    assert "n_ada=1" in out and "n_victor=0" in out and "n_valentin=0" in out, out  # @toutlemonde : seulement qui vient
