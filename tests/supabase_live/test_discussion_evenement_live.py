"""Discussion d'un événement façon WhatsApp (demande de l'admin du 16.11.2026, migration 20261116180000), sur la VRAIE base
de TEST, bots seulement, transactions ANNULÉES :
- @toutlemonde et @present : réservés à l'organisation (organisatrice Olga, co-organisateur Côme) et aux admins ; d'un
  simple invité (Victor), le mot ne prévient personne ;
- annonce (interrupteur ou « @annonce ») : épinglée d'office, notifiée à tous, invités sans réponse compris ; d'un invité :
  message normal ;
- en mode « Mentions », @present prévient les Présents / Peut-être, pas les « Pas présent » ;
- photo seule permise, mais seulement dans le dossier de SON événement ; supprimer efface la photo ;
- event_chat_people : un invité ne voit pas les noms des invités sans réponse, l'organisation oui.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_discussion_evenement_live.py -q"""
from tests.supabase_live.test_bar_options_live import as_bot, as_postgres, keep, note, run
from tests.supabase_live.test_member_admin_live import pytestmark  # noqa: F401

# Olga organise, Côme co-organise (co-admin) ; Ada (admin) Présente ; Victor (membre) Pas présent ; Valentin (membre) invité
# sans réponse.
CHAT = as_postgres() + """
      insert into public.events (title, status, visibility, notify_on_publish, starts_at, created_by, forum_enabled)
        values ('[Recette] Discussion', 'published', 'invited', false, now() + interval '2 days', olga, true) returning id into e;
      insert into public.event_organizers (event_id, user_id) values (e, come);
      insert into public.event_invites (event_id, user_id) select e, x from unnest(array[ada, victor, valentin]) x;
      insert into public.rsvps (event_id, user_id, status) values (e, ada, 'yes'), (e, victor, 'no');
      update public.notification_prefs set chat = 'mentions' where user_id in (ada, victor, valentin);
      update public.notification_prefs set chat = 'all' where user_id = olga;
      delete from public.notifications where event_id = e;"""

# Discussion réservée à Présent / Peut-être (19.11) : pour qu'un invité ordinaire écrive, Victor répond Peut-être.
VICTOR_MAYBE = as_postgres() + "update public.rsvps set status = 'maybe' where event_id = e and user_id = victor;"

LAST = "srv"  # dernier message écrit (même instant pour toute la transaction : on garde son id)


def flags(label: str) -> str:
    return keep(label, f"(select concat_ws(',', mention_all::text, mention_present::text, announcement::text, pinned::text) from public.messages where id = {LAST})")


def notified(label: str, who: str) -> str:
    return keep(label, f"(select string_agg(coalesce(data->>'mentioned', '?'), ',') from public.notifications "
                       f"where event_id = e and user_id = {who} and kind = 'message')")


def say(body: str, extra: str = "") -> str:
    cols, vals = ("event_id, user_id, body" + (", " + extra.split("=")[0] if extra else ""),
                  f"e, auth.uid(), '{body}'" + (", " + extra.split("=")[1] if extra else ""))
    return f"insert into public.messages ({cols}) values ({vals}) returning id into srv;"


def test_only_the_organisation_tags_everyone_and_the_present():
    out = run(CHAT + VICTOR_MAYBE + as_bot("victor") + say("@toutlemonde ce soir ?") + flags("victor_all")
              + say("@present vous venez ?") + flags("victor_present")
              + as_bot("come") + say("@toutlemonde ça commence à 20 h") + flags("coorga_all")
              + say("Rappel @présents : apportez un plat") + flags("coorga_present"))
    assert "victor_all=false,false,false,false" in out and "victor_present=false,false,false,false" in out, out
    assert "coorga_all=true,false,false,false" in out and "coorga_present=false,true,false,false" in out, out


def test_present_tags_yes_and_maybe_only_and_nobody_without_access_is_notified():
    out = run(CHAT + as_bot("olga") + say("@present on se retrouve à la gare")
              + as_postgres() + notified("present_ada", "ada") + notified("present_victor", "victor")
              + notified("present_valentin", "valentin")
              + "delete from public.notifications where event_id = e;"
              + as_bot("olga") + say("@toutlemonde le lieu a changé")
              + as_postgres() + notified("all_valentin", "valentin") + notified("all_victor", "victor"))
    assert "present_ada=true" in out and "present_victor=null" in out and "present_valentin=null" in out, out
    # @toutlemonde ne touche plus les invités sans réponse ni les absents : la discussion leur est fermée (19.11).
    assert "all_valentin=null" in out and "all_victor=null" in out, out


def test_an_announcement_is_pinned_and_titled_and_a_guest_cannot_announce():
    out = run(CHAT + VICTOR_MAYBE + as_bot("victor") + say("Mon annonce", "announcement=true") + flags("guest")
              + say("@annonce moi aussi") + flags("guest_tag")
              + as_bot("olga") + say("Parking derrière la salle", "announcement=true") + flags("staff")
              + as_postgres() + keep("title", "(select title from public.notifications where event_id = e and user_id = ada "
                                              "and kind = 'message' order by created_at desc limit 1)")
              + as_bot("olga") + say("@annonce Dress code blanc") + flags("staff_tag")
              + as_postgres() + keep("text", "(select string_agg(body, ' / ') from public.notifications where event_id = e and user_id = ada "
                                             "and kind = 'message' and body like '%Dress%')"))
    assert "guest=false,false,false,false" in out and "guest_tag=false,false,false,false" in out, out
    assert "staff=false,false,true,true" in out and "staff_tag=false,false,true,true" in out, out
    assert "title=📣 Annonce · [Recette] Discussion" in out, out
    assert "text=Bot Olga : Dress code blanc" in out, out


def test_a_photo_alone_lives_in_its_own_event_folder_and_leaves_with_the_message():
    out = run(CHAT + as_bot("ada")
              + note("elsewhere", "insert into public.messages (event_id, user_id, body, photo_path) "
                                  "values (e, ada, '', gen_random_uuid()::text || '/x.jpg')")
              + note("empty", "insert into public.messages (event_id, user_id, body) values (e, ada, '')")
              + note("photo", "insert into public.messages (event_id, user_id, body, photo_path) values (e, ada, '', e::text || '/x.jpg') returning id into srv")
              + as_postgres() + notified("photo_note", "olga")
              + keep("olga_text", "(select body from public.notifications where event_id = e and user_id = olga and kind = 'message' limit 1)")
              + as_bot("ada") + f"update public.messages set deleted_at = now() where id = {LAST};"
              + keep("gone", f"(select photo_path is null and body = '•' from public.messages where id = {LAST})"))
    assert "elsewhere=Photo invalide." in out and "empty=" in out and "messages_content" in out.split("empty=")[1].split("|")[0], out
    assert "photo=ok" in out and "📷 Photo" in out and "gone=true" in out, out


def test_people_to_cite_hide_unanswered_guests_from_guests_but_not_from_the_organisation():
    who = "(select string_agg(display_name || ':' || coalesce(rsvp, '-'), ',' order by display_name) from public.event_chat_people(e))"
    out = run(CHAT + VICTOR_MAYBE + as_bot("victor") + keep("guest", who) + as_bot("olga") + keep("staff", who)
              + as_bot("olga") + keep("state", "public.event_chat_state(e)->>'staff'")
              + as_bot("victor") + keep("ada_state", "(public.event_chat_state(e)->>'staff') || '/' || (public.event_chat_state(e)->>'write')"))

    guest = out.split("guest=")[1].split(" |")[0]
    staff = out.split("staff=")[1].split(" |")[0]
    assert "Valentin" not in guest and "Ada:yes" in guest and "Victor:maybe" in guest, out
    assert "Valentin:-" in staff, out
    assert "state=true" in out and "ada_state=false/true" in out, out
