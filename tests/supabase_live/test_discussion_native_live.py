"""Discussion d'un événement NATIVE (demande de l'admin du 17.11.2026, migration 20261117190000), sur la VRAIE base de TEST,
bots seulement, transactions ANNULÉES :
- niveau par discussion : par défaut celui de notification_prefs.chat (« mentions » d'office) ; all / mentions / none et la
  sourdine décident des lignes de public.notifications ; data gagne thread et can_reply ;
- « Qui peut écrire » = Organisation seulement : un invité ne peut plus écrire, sa notification n'offre pas « Répondre » ;
- description de la discussion : filtrée, 500 caractères au plus, réglée par l'organisation seulement, signalée avec l'événement ;
- non-lus et « marquer comme lu », médias (photos, vocaux, liens), recherche, droits.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_discussion_native_live.py -q"""
from tests.supabase_live.test_bar_options_live import as_bot, as_postgres, keep, note, run
from tests.supabase_live.test_discussion_evenement_live import CHAT as BASE, VICTOR_MAYBE, say
from tests.supabase_live.test_member_admin_live import pytestmark  # noqa: F401

# Discussion réservée à Présent / Peut-être (19.11) : Victor, l'invité ordinaire de ces tests, répond Peut-être.
CHAT = BASE + VICTOR_MAYBE


def count(label: str, who: str) -> str:
    return keep(label, f"(select count(*) from public.notifications where event_id = e and user_id = {who} and kind = 'message')")


def cite(who: str, body: str) -> str:
    return f"insert into public.messages (event_id, user_id, body, mentions) values (e, auth.uid(), '{body}', array[{who}]);"


def test_the_default_level_is_the_person_s_chat_setting_mentions_by_default():
    out = run(CHAT + "delete from public.notification_prefs where user_id = victor;"
              + as_bot("victor") + keep("victor", "public.event_chat_prefs_get(e)->>'level'")
              + as_bot("ada") + keep("ada", "public.event_chat_prefs_get(e)->>'level'")
              + as_bot("olga") + keep("olga", "public.event_chat_prefs_get(e)->>'level'")
              + keep("state", "(select string_agg(k, ',' order by k) from jsonb_object_keys(public.event_chat_state(e)) k)"))
    assert "victor=mentions" in out and "ada=mentions" in out and "olga=all" in out, out
    state = out.split("state=")[1].split(" |")[0].split("\n")[0]
    for k in ("unread", "level", "muted_until", "write_mode", "description", "can_write"):
        assert k in state.split(","), out


def test_levels_and_mute_decide_who_is_notified():
    out = run(CHAT + "update public.notification_prefs set chat = 'all' where user_id = come;"
              + as_bot("ada") + say("Salut") + as_bot("victor") + say("Coucou")
              + as_bot("victor") + keep("set_all", "public.event_chat_set_level(e, 'all')->>'level'")
              + as_bot("come") + keep("set_none", "public.event_chat_set_level(e, 'none')->>'level'")
              + note("bad_level", "perform public.event_chat_set_level(e, 'souvent')")
              + as_postgres() + "delete from public.notifications where event_id = e;"
              + as_bot("olga") + say("Rendez-vous à 20 h")
              + as_postgres() + count("plain_ada", "ada") + count("plain_victor", "victor") + count("plain_come", "come")
              + keep("data", "(select (data->>'thread') || '/' || (data->>'can_reply') from public.notifications "
                             "where event_id = e and user_id = victor and kind = 'message' limit 1)")
              + as_bot("olga") + say("@toutlemonde on bouge") + as_postgres() + count("all_come", "come")
              + "delete from public.notifications where event_id = e;"
              + as_bot("ada") + keep("muted", "public.event_chat_mute(e, now() + interval '7 days')->>'muted_until' is not null")
              + as_bot("olga") + cite("ada", "@Ada tu ramènes la sono ?")
              + as_postgres() + count("muted_ada", "ada")
              + as_bot("ada") + keep("unmuted", "public.event_chat_mute(e, null)->>'muted_until'")
              + keep("forever", "public.event_chat_mute(e, 'infinity')->>'muted_until'")
              + keep("again", "public.event_chat_mute(e, null)->>'muted_until'")
              + as_bot("olga") + cite("ada", "@Ada et les câbles ?")
              + as_postgres() + count("cited_ada", "ada"))
    assert "set_all=all" in out and "set_none=none" in out and "bad_level=invalid:" in out, out
    assert "plain_ada=0" in out and "plain_victor=1" in out and "plain_come=0" in out, out
    assert "data=event-chat:" in out and "/true" in out.split("data=")[1].split(" |")[0], out
    assert "all_come=0" in out, out
    assert "muted=true" in out and "muted_ada=0" in out, out
    assert "unmuted=null" in out and "forever=infinity" in out and "again=null" in out and "cited_ada=1" in out, out


def test_staff_only_writing_refuses_a_guest_and_hides_reply():
    out = run(CHAT + as_bot("victor") + say("Avant") + keep("lvl", "public.event_chat_set_level(e, 'all')->>'level'")
              + note("guest_settings", "perform public.event_chat_set_settings(e, 'staff')")
              + as_bot("olga") + keep("set", "public.event_chat_set_settings(e, 'staff')->>'write_mode'")
              + as_bot("victor") + note("guest_write", "insert into public.messages (event_id, user_id, body) values (e, victor, 'Moi aussi')")
              + keep("guest_state", "(public.event_chat_state(e)->>'write_mode') || '/' || (public.event_chat_state(e)->>'can_write') "
                                    "|| '/' || (public.event_chat_state(e)->>'write')")
              + as_postgres() + "delete from public.notifications where event_id = e;"
              + as_bot("come") + note("coorga_write", "insert into public.messages (event_id, user_id, body) values (e, come, 'Infos pratiques')")
              + keep("coorga_state", "public.event_chat_state(e)->>'can_write'")
              + as_postgres()
              + keep("reply_victor", "(select data->>'can_reply' from public.notifications where event_id = e and user_id = victor and kind = 'message' limit 1)")
              + keep("reply_olga", "(select data->>'can_reply' from public.notifications where event_id = e and user_id = olga and kind = 'message' limit 1)")
              + as_bot("come") + keep("back", "public.event_chat_set_settings(e, 'all')->>'write_mode'")
              + as_bot("victor") + note("guest_again", "insert into public.messages (event_id, user_id, body) values (e, victor, 'Enfin')"))
    assert "lvl=all" in out and "guest_settings=forbidden:" in out and "set=staff" in out, out
    assert "guest_write=forbidden: Seule l'organisation peut écrire dans cette discussion." in out, out
    assert "guest_state=staff/false/false" in out, out
    assert "coorga_write=ok" in out and "coorga_state=true" in out, out
    assert "reply_victor=false" in out and "reply_olga=true" in out, out
    assert "back=all" in out and "guest_again=ok" in out, out


def test_the_description_is_filtered_limited_reported_and_staff_only():
    out = run(CHAT + as_bot("olga")
              + note("hate", "perform public.event_chat_set_settings(e, null, 'Pas de sale arabe ici')")
              + note("long", f"perform public.event_chat_set_settings(e, null, '{'x' * 501}')")
              + keep("ok", "public.event_chat_set_settings(e, null, '  Parking derrière la salle  ')->>'description'")
              + keep("state", "public.event_chat_state(e)->>'description'")
              + as_bot("victor") + note("guest", "perform public.event_chat_set_settings(e, null, 'Hack')")
              + note("guest_direct", "update public.events set chat_description = 'Hack' where id = e")
              + keep("still", "(select chat_description from public.events where id = e)")
              + note("report", "perform public.report_content('event', e::text, 'spam', null)")
              + as_postgres()
              + keep("snapshot", "(select position('Description de la discussion : Parking derrière la salle' in snapshot->>'text') > 0 "
                                 "from public.content_reports where target_id = e::text and target_kind = 'event' limit 1)")
              + as_bot("olga") + keep("cleared", "public.event_chat_set_settings(e, null, '')->>'description'"))
    assert "hate=content_refused:" in out and "long=invalid:" in out, out
    assert "ok=Parking derrière la salle" in out and "state=Parking derrière la salle" in out, out
    assert "guest=forbidden:" in out and "still=Parking derrière la salle" in out, out
    assert "report=ok" in out and "snapshot=true" in out, out
    assert "cleared=null" in out, out


def test_unread_and_mark_read():
    later = ("insert into public.messages (event_id, user_id, body, created_at) values "
             "(e, olga, 'Un', now() + interval '1 minute'), (e, olga, 'Deux', now() + interval '2 minutes'), "
             "(e, victor, 'Le mien', now() + interval '3 minutes');")
    out = run(CHAT + as_bot("victor") + keep("read", "public.event_chat_mark_read(e)->>'unread'")
              + as_postgres() + later
              + "insert into public.notifications (user_id, kind, event_id, title, body) values (victor, 'message', e, 'T', 'B');"
              + as_bot("victor") + keep("unread", "public.event_chat_prefs_get(e)->>'unread'")
              + keep("state_unread", "public.event_chat_state(e)->>'unread'")
              + keep("level_kept", "public.event_chat_prefs_get(e)->>'level'")
              + keep("read2", "public.event_chat_mark_read(e)->>'unread'")
              + as_postgres() + keep("notif_read", "(select bool_and(read_at is not null) from public.notifications "
                                                   "where event_id = e and user_id = victor and kind = 'message')"))
    assert "read=0" in out and "unread=2" in out and "state_unread=2" in out, out
    assert "level_kept=mentions" in out and "read2=0" in out and "notif_read=true" in out, out


def test_media_and_search():
    out = run(CHAT + as_bot("olga")
              + "insert into public.messages (event_id, user_id, body, photo_path) values (e, olga, '', e::text || '/plan.jpg');"
              + "insert into public.messages (event_id, user_id, body, audio_path, audio_seconds) values (e, olga, '', e::text || '/v.m4a', 4);"
              + "insert into public.messages (event_id, user_id, body) values (e, olga, 'Le plan : https://exemple.ch/plan.');"
              + "insert into public.messages (event_id, user_id, body) values (e, olga, 'Remise de 50% au bar') returning id into srv;"
              + "insert into public.messages (event_id, user_id, body, photo_path) values (e, olga, 'Effacée', e::text || '/x.jpg') returning id into srv;"
              + "update public.messages set deleted_at = now() where id = srv;"
              + as_bot("victor")
              + keep("media", "(select string_agg(j->>'kind' || ':' || coalesce(j->>'path', j->>'url'), ',' order by j->>'kind') "
                              "from jsonb_array_elements(public.event_chat_media(e)) j)")
              + keep("media_author", "public.event_chat_media(e)->0->>'author_name'")
              + keep("search", "(select string_agg(j->>'snippet', ' / ') from jsonb_array_elements(public.event_chat_search(e, 'PLAN')) j)")
              + keep("percent", "jsonb_array_length(public.event_chat_search(e, '0%'))")
              + keep("wild", "jsonb_array_length(public.event_chat_search(e, '%%'))")
              + keep("short", "jsonb_array_length(public.event_chat_search(e, 'p'))")
              + keep("deleted", "jsonb_array_length(public.event_chat_search(e, 'Effac'))"))
    media = out.split("media=")[1].split(" |")[0].split("\n")[0]
    assert "photo:" in media and "/plan.jpg" in media and "audio:" in media and "link:https://exemple.ch/plan," in media + ",", out
    assert "x.jpg" not in media and "media_author=Bot Olga" in out, out
    assert "search=Le plan : https://exemple.ch/plan." in out, out
    assert "percent=1" in out and "wild=0" in out and "short=0" in out and "deleted=0" in out, out


def test_rights_a_guest_reads_only_his_own_prefs():
    out = run(CHAT + as_bot("olga") + "perform public.event_chat_set_level(e, 'none');"
              + as_bot("victor") + "perform public.event_chat_set_level(e, 'all');"
              + keep("mine", "(select count(*) from public.event_chat_prefs where event_id = e)")
              + note("steal", "update public.event_chat_prefs set level = 'all' where event_id = e and user_id = olga")
              + note("insert_other", "insert into public.event_chat_prefs (event_id, user_id, level) values (e, valentin, 'none')")
              + as_postgres() + keep("olga_level", "(select level from public.event_chat_prefs where event_id = e and user_id = olga)"))
    assert "mine=1" in out and "steal=ok" in out and "olga_level=none" in out, out
    assert "insert_other=new row violates row-level security" in out, out
