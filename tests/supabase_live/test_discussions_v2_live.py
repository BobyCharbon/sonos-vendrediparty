"""Discussions v2 (contrat du 18.11.2026, migration 20261118120000_discussions_v2) sur la VRAIE base de TEST, comptes des
BOTS seulement, transactions ANNULÉES (rien ne reste, aucune notification envoyée) :
- qui peut écrire à qui (direct / demande / impossible) : Guests sans lien, événement public, sur invitation, Vendredi
  Party seul, groupe choisi, organisateur ↔ réponse, blocage, compte banni, profil incomplet, CGU, « Demandes : personne » ;
- demande de message : un seul texte (photo, lien, numéro, carte refusés), le destinataire n'écrit pas avant d'accepter,
  une seule notification message_request sans le contenu, pas de « Nouveau message » ; accepter ; refuser (l'expéditeur
  n'en sait rien, message effacé) ; purge des 30 jours ; plafonds 10 / 24 h et 30 en attente ;
- chat_list : groupes, directs, soirées, mention, épinglées (5 au plus), archivées, non lu manuel, sourdine, pastille,
  « Vu » réciproque, soirée passée de plus de 7 jours, Root ;
- suggestions et recherche (jamais par numéro, jamais un bloqué ni un Guest sans lien), member_mini (« Déjà vu », 3
  dernières soirées dans l'ordre, liste des participants cachée respectée, À venir, blocage) ;
- groupe privé (Root ne le lit pas ; les admins le voient avec ses membres, jamais ses messages (22.11) ; demande = refusée), chat_group_with ;
- modifier après 15 minutes refusé ; carte d'événement invisible sans can_see_event ; citation nettoyée ;
- devinette de numéro : bloquée après 20 empreintes ratées en 24 h.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_discussions_v2_live.py -q"""
import json

from tests.supabase_live.test_groups_members_only_live import sql_test
from tests.supabase_live.test_member_admin_live import ROOT_ID, pytestmark  # noqa: F401

BOTS = {"ada": "41790000101", "come": "41790000102", "olga": "41790000103", "oscar": "41790000104",
        "victor": "41790000105", "vera": "41790000106", "valentin": "41790000107", "violette": "41790000108",
        "marc": "41790000109", "mia": "41790000110", "max": "41790000111", "gus": "41790000112", "gina": "41790000113",
        "nobody": "41790000114", "nobody2": "41790000115", "nobody3": "41790000116", "nobody4": "41790000117"}
IDS = "array[" + ", ".join(BOTS) + "]"
DECLARE = ("e uuid; e2 uuid; g uuid; g2 uuid; c uuid; c2 uuid; m uuid; r jsonb; n int; h text; out text := ''; msg text; "
           f"i int; root uuid := '{ROOT_ID}'; " + " ".join(f"{k} uuid;" for k in BOTS))
# Point de départ propre, dans la transaction annulée : CGU acceptées, aucun lien entre bots (groupes, événements,
# conversations, blocages, réglages, essais d'empreinte).
SETUP = "\n".join(f"select id into {k} from public.profiles where phone = '{p}';" for k, p in BOTS.items()) + f"""
insert into public.terms_acceptances (user_id, version)
  select x, (select terms_version from private.moderation_settings where id = 1) from unnest({IDS}) x on conflict do nothing;
delete from public.direct_chats where user_a = any ({IDS}) or user_b = any ({IDS});
delete from public.direct_blocks where user_id = any ({IDS}) or blocked_id = any ({IDS});
delete from public.chat_prefs where user_id = any ({IDS});
delete from public.chat_list_state where user_id = any ({IDS});
delete from private.contact_hash_fails where user_id = any ({IDS});
delete from public.member_groups where created_by = any ({IDS});
delete from public.member_group_members mm using public.member_groups gg
  where gg.id = mm.group_id and gg.system_key is null and mm.user_id = any ({IDS});
delete from public.events where created_by = any ({IDS});
delete from public.rsvps where user_id = any ({IDS});
delete from public.event_invites where user_id = any ({IDS});
delete from public.event_organizers where user_id = any ({IDS});
delete from public.notifications where user_id = any ({IDS});"""


def as_bot(name: str) -> str:
    return (f"execute 'reset role'; perform set_config('request.jwt.claims', "
            f"json_build_object('sub', {name}, 'role', 'authenticated')::text, true); execute 'set local role authenticated';")


def as_postgres() -> str:
    return "execute 'reset role'; perform set_config('request.jwt.claims', '', true);"


def note(label: str, statement: str) -> str:
    """Essaie un geste ; garde « ok » ou le message de refus de la base, sous son nom."""
    return f"""
      begin {statement}; msg := 'ok'; exception when others then msg := sqlerrm; end;
      out := out || ' | {label}=' || msg;"""


def keep(label: str, expr: str) -> str:
    return f"\n      out := out || ' | {label}=' || coalesce(({expr})::text, 'null');"


def run(body: str) -> dict:
    """Exécute le scénario dans une transaction annulée ; rend {étiquette: valeur}."""
    rows = sql_test(f"""
    begin;
    do $$ declare {DECLARE} begin
      {SETUP}
      {body}
      raise exception 'résultat:%', out;
    end $$;
    rollback;""")
    raw = rows[0].get("error", "") if rows and isinstance(rows[0], dict) else json.dumps(rows, ensure_ascii=False)
    if "HTTP" in raw and "{" in raw:
        raw = json.loads(raw[raw.index("{"):])["message"]
    assert "résultat:" in raw, raw
    text = raw.split("résultat:", 1)[1].split("\nCONTEXT:", 1)[0]
    return {k.strip(): v.strip() for k, v in (part.split("=", 1) for part in text.split(" | ") if "=" in part)}


def open_chat(target: str, var: str = "c", hash_: str = "null") -> str:
    return f"r := public.open_direct_chat({target}, {hash_}); {var} := (r ->> 'chat')::uuid;"


def say(chat: str, body: str, extra_cols: str = "", extra_vals: str = "") -> str:
    return (f"insert into public.direct_messages (chat_id, body{extra_cols}) values ({chat}, '{body}'{extra_vals}) "
            f"returning id into m")


def in_list(chat: str, field: str, archived: str = "false") -> str:
    return (f"(select x ->> '{field}' from jsonb_array_elements(public.chat_list({archived})) x "
            f"where x ->> 'id' = {chat}::text)")


PUBLIC_EVENT = """
      insert into public.events (title, status, visibility, public_link, notify_on_publish, starts_at, created_by)
        values ('[DV2] Soirée publique', 'published', 'all', true, false, now() + interval '2 days', olga) returning id into e;"""
INVITED_EVENT = """
      insert into public.events (title, status, visibility, notify_on_publish, starts_at, created_by, forum_enabled)
        values ('[DV2] Sur invitation', 'published', 'invited', false, now() + interval '2 days', olga, true) returning id into e2;"""
GROUP_VICTOR_VERA = """
      insert into public.member_groups (name, created_by) values ('[DV2] Bande', victor) returning id into g;
      insert into public.member_group_members (group_id, user_id) values (g, vera) on conflict do nothing;"""


def test_who_can_write_to_whom():
    out = run(as_postgres()
              + keep("guests", "private.dm_check(gus, gina)")
              + keep("soi", "private.dm_link(gus, gus)")
              + PUBLIC_EVENT + """
      insert into public.rsvps (event_id, user_id, status) values (e, gus, 'yes'), (e, gina, 'maybe');"""
              + keep("public", "private.dm_link(gus, gina)")
              + keep("orga_vers_reponse", "private.dm_link(olga, gus)") + keep("reponse_vers_orga", "private.dm_link(gus, olga)")
              + INVITED_EVENT + """
      insert into public.event_invites (event_id, user_id) values (e2, gus), (e2, gina);"""
              + keep("invitation", "private.dm_link(gus, gina)") + """
      -- Réservé au groupe Vendredi Party : comme un événement public.
      insert into public.event_groups (event_id, group_id) values (e2, private.vip_group_id());"""
              + keep("reserve_vp", "private.dm_link(gus, gina)")
              + keep("vp_seul", "private.dm_link(victor, vera)")
              + keep("basic_sans_lien", "private.dm_link(marc, mia)")
              + GROUP_VICTOR_VERA
              + keep("groupe", "private.dm_link(victor, vera)") + """
      insert into public.direct_blocks (user_id, blocked_id) values (vera, victor);"""
              + keep("bloque", "private.dm_check(victor, vera)") + keep("bloque_autre_sens", "private.dm_link(vera, victor)") + """
      delete from public.direct_blocks where user_id = vera;""" + as_bot("vera") + """
      perform public.chat_prefs_set('none');""" + keep("prefs", "public.chat_prefs_get()") + as_postgres()
              + keep("personne_mais_groupe", "private.dm_link(victor, vera)") + """
      delete from public.member_group_members where group_id = g and user_id = vera;"""
              + keep("personne", "private.dm_check(victor, vera)")
              + keep("incomplet", "private.dm_check(nobody, victor)") + """
      delete from public.terms_acceptances where user_id = gus;"""
              + keep("cgu", "private.dm_check(gus, olga)") + """
      update public.profiles set status = 'banned' where id = gina;"""
              + keep("banni", "private.dm_check(olga, gina)")
              + as_bot("victor") + keep("ecran", "public.chat_link(vera)")
              + keep("ouvrir_refuse", "public.open_direct_chat(vera)"))
    assert json.loads(out["guests"]) == {"link": "none", "reason": None}, out
    assert out["soi"] == "none", out
    assert out["public"] == "request" and out["orga_vers_reponse"] == "direct" and out["reponse_vers_orga"] == "direct", out
    assert out["invitation"] == "direct" and out["reserve_vp"] == "request", out
    assert out["vp_seul"] == "request" and out["basic_sans_lien"] == "none", out
    assert out["groupe"] == "direct", out
    assert json.loads(out["bloque"]) == {"link": "none", "reason": "blocked"} and out["bloque_autre_sens"] == "none", out
    assert json.loads(out["prefs"]) == {"message_requests": "none", "read_receipts": True}, out
    assert out["personne_mais_groupe"] == "direct", out  # « personne » ne coupe que les demandes
    assert json.loads(out["personne"]) == {"link": "none", "reason": "closed"}, out
    assert json.loads(out["incomplet"])["reason"] == "profile_required", out
    assert json.loads(out["cgu"])["reason"] == "terms_required", out
    assert json.loads(out["banni"])["reason"] == "inactive", out
    assert out["ecran"] == "none", out
    assert json.loads(out["ouvrir_refuse"]) == {"chat": None, "status": "none", "reason": "closed"}, out


def test_a_request_is_one_text_message_announced_once_without_its_content():
    out = run(PUBLIC_EVENT + as_bot("vera") + keep("pastille_avant", "public.chat_badge()")
              + as_bot("victor") + open_chat("vera") + keep("statut", "r ->> 'status'")
              + note("photo", say("c", "Coucou", ", photo_path", ", c || '/x.jpg'"))
              + note("lien", say("c", "Va voir https://exemple.ch"))
              + note("www", say("c", "Va voir www.exemple.ch"))
              + note("numero", say("c", "Appelle-moi au 079 123 45 67"))
              + note("carte", say("c", "Viens", ", event_id", ", e"))
              + note("texte", say("c", "Salut, on s''est croisés à la soirée"))
              + note("second", say("c", "Tu es là ?"))
              + as_bot("vera") + note("reponse_avant", say("c", "Coucou"))
              + keep("notif", "(select count(*) || '|' || max(title) || '|' || max(body) from public.notifications "
                              "where user_id = vera and kind = 'message_request' and data ->> 'chat_id' = c::text)")
              + keep("nouveau_message", "(select count(*) from public.notifications where user_id = vera and kind = 'direct_message')")
              + keep("liste_vera", in_list("c", "request"))
              + keep("ancienne_liste", "position(c::text in public.my_chats()::text)")
              + keep("pastille_apres", "public.chat_badge()")
              + as_bot("victor") + keep("liste_victor", in_list("c", "request")) + keep("vu", in_list("c", "seen_by_other"))
              + note("victor_accepte", "perform public.accept_message_request(c)")
              + as_bot("vera") + "perform public.accept_message_request(c);" + note("reponse", say("c", "Avec plaisir"))
              + as_bot("victor") + note("photo_apres", say("c", "", ", photo_path", ", c || '/x.jpg'"))
              + as_postgres() + keep("statut_apres", "(select status from public.direct_chats where id = c)")
              + keep("nouveau_message_apres", "(select count(*) from public.notifications where user_id = victor and kind = 'direct_message')"))
    assert out["statut"] == "request", out
    for refused in ("photo", "lien", "www", "numero", "carte", "second", "reponse_avant", "victor_accepte"):
        assert out[refused].startswith(("request_pending", "forbidden")), (refused, out)
    assert out["texte"] == "ok", out
    count, title, body = out["notif"].split("|")
    assert count == "1" and title == "💬 Bot Victor veut t'écrire" and "croisés" not in body, out
    assert out["nouveau_message"] == "0", out
    assert out["liste_vera"] == "incoming" and out["ancienne_liste"] == "0", out
    assert int(out["pastille_apres"]) == int(out["pastille_avant"]) + 1, out
    assert out["liste_victor"] == "outgoing" and out["vu"] == "null", out
    assert out["reponse"] == "ok" and out["photo_apres"] == "ok" and out["statut_apres"] == "active", out
    assert out["nouveau_message_apres"] == "1", out


def test_declining_hides_the_request_and_the_sender_is_never_told():
    out = run(as_bot("victor") + open_chat("vera") + say("c", "Hello") + ";"
              + as_bot("vera") + "perform public.decline_message_request(c);"
              + keep("liste_vera", "position(c::text in public.chat_list(true)::text)")
              + as_postgres() + keep("messages", "(select count(*) from public.direct_messages where chat_id = c)")
              + keep("notif", "(select count(*) from public.notifications where user_id = vera and kind = 'message_request')")
              + as_bot("victor") + keep("liste_victor", in_list("c", "request"))
              + note("encore", say("c", "Tu as vu ?"))
              + keep("rouvrir", "(public.open_direct_chat(vera)) ->> 'status'")
              + keep("meme", "(public.open_direct_chat(vera)) ->> 'chat' = c::text")
              # Ignorée : effacée au bout de 30 jours, comme la refusée.
              + open_chat("violette", "c2") + say("c2", "Coucou Violette") + ";"
              + as_postgres() + """
      update public.direct_chats set requested_at = now() - interval '31 days' where id in (c, c2);
      perform private.chat_requests_tick();"""
              + keep("purge", "(select count(*) from public.direct_chats where id in (c, c2))"))
    assert out["liste_vera"] == "0" and out["messages"] == "0" and out["notif"] == "0", out
    assert out["liste_victor"] == "outgoing", out
    assert out["encore"].startswith("request_pending"), out
    assert out["rouvrir"] == "request" and out["meme"] == "true", out
    assert out["purge"] == "0", out


# Paires de bots sans victor ni vera : demandes posées pour l'exemple au nom de victor.
FAKE_REQUESTS = """
      insert into public.direct_chats (user_a, user_b, created_by, status, requested_by, requested_at)
        select least(x, y), greatest(x, y), victor, 'request', victor, now() - ({age})
        from unnest({ids}) x, unnest({ids}) y
        where x < y and not exists (select 1 from public.direct_chats d where d.user_a = least(x, y) and d.user_b = greatest(x, y))
        limit {n};"""


def fake(n: int, age: str = "interval '0'") -> str:
    others = "array[ada, come, olga, oscar, valentin, violette, marc, mia, max, gus, gina, nobody, nobody2]"
    return FAKE_REQUESTS.format(n=n, age=age, ids=others)


def test_ten_new_requests_a_day_and_thirty_waiting():
    out = run(as_postgres() + fake(10) + as_bot("victor") + keep("dix", "public.open_direct_chat(vera)")
              + as_postgres() + "update public.direct_chats set requested_at = now() - interval '2 days' where requested_by = victor;"
              + as_bot("victor") + keep("lendemain", "(public.open_direct_chat(vera)) ->> 'status'")
              + as_postgres() + "delete from public.direct_chats where user_a = least(victor, vera) and user_b = greatest(victor, vera);"
              + fake(20, "interval '2 days'") + as_bot("victor") + keep("trente", "public.open_direct_chat(vera)")
              + note("ancienne", "perform public.start_direct_chat(vera)"))
    assert json.loads(out["dix"]) == {"chat": None, "status": "none", "reason": "limit"}, out
    assert out["lendemain"] == "request", out
    assert json.loads(out["trente"])["reason"] == "limit", out
    assert out["ancienne"].startswith("limit"), out


def test_chat_list_groups_directs_events_pins_archives_and_seen():
    pin = "perform public.set_chat_state('group', {0}, pinned => true);"
    out = run(as_postgres() + GROUP_VICTOR_VERA + INVITED_EVENT + """
      insert into public.event_invites (event_id, user_id) values (e2, vera);
      -- Discussion d'un événement réservée à Présent / Peut-être (19.11).
      insert into public.rsvps (event_id, user_id, status) values (e2, vera, 'maybe');
      insert into public.member_groups (name, created_by) values ('[DV2] Pas à Vera', olga) returning id into e;
      for i in 1..5 loop
        insert into public.member_groups (name, created_by) values ('[DV2] Groupe ' || i, victor) returning id into g2;
        insert into public.member_group_members (group_id, user_id) values (g2, vera);
      end loop;""" + as_bot("victor") + """
      insert into public.group_messages (group_id, user_id, body, mentions) values (g, victor, 'Salut @Vera', array[vera]);"""
              + open_chat("vera") + say("c", "Ça va ?") + ";"
              + keep("vu_avant", in_list("c", "seen_by_other"))
              + as_bot("olga") + "insert into public.messages (event_id, user_id, body) values (e2, olga, 'Bienvenue à tous');"
              + as_bot("vera") + keep("pastille", "public.chat_badge()")
              + keep("sortes", "(select string_agg(x ->> 'kind', ',' order by x ->> 'kind') from jsonb_array_elements(public.chat_list()) x "
                               "where x ->> 'id' in (g::text, c::text, e2::text))")
              + keep("groupe", in_list("g", "unread") + " || '/' || " + in_list("g", "mention"))
              + keep("soiree", in_list("e2", "unread") + " || '/' || " + in_list("e2", "title"))
              + keep("direct", "(select (x -> 'last' ->> 'text') || '/' || (x -> 'last' ->> 'from_me') from jsonb_array_elements(public.chat_list()) x where x ->> 'id' = c::text)")
              + "perform public.set_chat_state('event', e2, pinned => true);"
              + keep("premiere", "(public.chat_list() -> 0 ->> 'id') = e2::text")
              + "".join(pin.format(f"(select id from public.member_groups where name = '[DV2] Groupe {i}')") for i in range(1, 5))
              + note("sixieme", pin.format("(select id from public.member_groups where name = '[DV2] Groupe 5')").rstrip(";"))
              + "perform public.set_chat_state('direct', c, archived => true);"
              + keep("archivee_cachee", "position(c::text in public.chat_list()::text)")
              + keep("archivee", in_list("c", "archived", "true"))
              + "perform public.set_chat_state('group', g, unread => true);" + keep("non_lu", in_list("g", "marked_unread"))
              + "perform public.mark_group_read(g);" + keep("lu", in_list("g", "marked_unread") + " || '/' || " + in_list("g", "unread"))
              + "perform public.set_chat_state('group', g, unread => true);"
              + keep("pastille_non_lu", "public.chat_badge()")
              + "perform public.set_chat_state('group', g, muted_until => now() + interval '1 hour');"
              + keep("sourdine", in_list("g", "muted_until") + " is not null")
              + keep("pastille_sourdine", "public.chat_badge()")
              + "perform public.mark_event_chat_read(e2);" + keep("soiree_lue", in_list("e2", "unread"))
              + note("autre_sorte", "perform public.set_chat_state('chat', g)")
              + note("pas_a_moi", "perform public.set_chat_state('group', e)")
              + "perform public.mark_direct_read(c);"
              + as_bot("victor") + keep("vu", in_list("c", "seen_by_other")) + keep("vu_date", "public.direct_seen(c) is not null")
              + as_bot("vera") + "perform public.chat_prefs_set(read_receipts => false);"
              + as_bot("victor") + keep("vu_coupe", in_list("c", "seen_by_other")) + keep("vu_date_coupe", "public.direct_seen(c)")
              + as_postgres() + "update public.events set starts_at = now() - interval '10 days', ends_at = null where id = e2;"
              + as_bot("vera") + keep("soiree_passee", "position(e2::text in public.chat_list(true)::text)")
              + as_bot("root") + keep("root_groupe", "position(g::text in public.chat_list()::text) > 0"))
    assert out["vu_avant"] == "false", out
    assert out["sortes"] == "direct,event,group", out
    assert out["groupe"] == "1/true" and out["soiree"] == "1/[DV2] Sur invitation", out
    assert out["direct"] == "Ça va ?/false", out
    assert out["premiere"] == "true" and out["sixieme"].startswith("pin_limit"), out
    assert out["archivee_cachee"] == "0" and out["archivee"] == "true", out
    assert out["non_lu"] == "true" and out["lu"] == "false/0", out
    assert out["sourdine"] == "true", out
    # Pastille : le groupe marqué non lu compte 1 ; en sourdine, plus rien ; la discussion archivée ne compte pas.
    assert int(out["pastille_sourdine"]) == int(out["pastille_non_lu"]) - 1, out
    assert out["soiree_lue"] == "0", out
    assert out["autre_sorte"].startswith("invalid") and out["pas_a_moi"].startswith("forbidden"), out
    assert out["vu"] == "true" and out["vu_date"] == "true", out
    assert out["vu_coupe"] == "null" and out["vu_date_coupe"] == "null", out
    assert out["soiree_passee"] == "0" and out["root_groupe"] == "true", out


def person(fn: str, who: str, field: str = "id") -> str:
    return f"(select p ->> '{field}' from jsonb_array_elements({fn}) p where p ->> 'id' = {who}::text)"


def test_suggestions_and_search_follow_real_links_never_a_number_nor_a_blocked_person():
    out = run(as_postgres() + """
      insert into public.member_groups (name, created_by) values ('[DV2] Les potes', victor) returning id into g;
      insert into public.member_group_members (group_id, user_id) values (g, vera);
      insert into public.events (title, status, visibility, public_link, notify_on_publish, starts_at, created_by, show_participants)
        values ('[DV2] Soirée croisée', 'published', 'all', true, false, now() - interval '5 days', olga, true) returning id into e;
      insert into public.rsvps (event_id, user_id, status) values (e, victor, 'yes'), (e, violette, 'yes');"""
              + as_bot("victor") + "r := public.chat_people_suggestions();"
              + keep("groupes", person("r -> 'groups'", "vera", "sub"))
              + keep("croises", person("r -> 'crossed'", "violette", "sub") + " || '/' || " + person("r -> 'crossed'", "violette", "link"))
              + keep("organisatrice", person("r -> 'crossed'", "olga", "link"))
              + keep("accents", person("public.chat_people_search('véra')", "vera", "link"))
              + keep("court", "public.chat_people_search('v')")
              + keep("numero", "public.chat_people_search('41790000106')")
              + keep("guest", person("public.chat_people_search('Bot Gus')", "gus"))
              + keep("membre", person("public.chat_people_search('bot violette')", "violette", "link"))
              + as_bot("gus") + keep("guest_cherche", "public.chat_people_search('Bot Vi')")
              + as_postgres() + "insert into public.direct_blocks (user_id, blocked_id) values (vera, victor);"
              + as_bot("victor") + keep("bloque_recherche", person("public.chat_people_search('vera')", "vera"))
              + keep("bloque_suggestion", person("(public.chat_people_suggestions()) -> 'groups'", "vera")))
    assert out["groupes"] == "[DV2] Les potes", out
    assert out["croises"] == "[DV2] Soirée croisée/request" and out["organisatrice"] == "direct", out
    assert out["accents"] == "direct", out
    assert out["court"] == "[]" and out["numero"] == "[]", out
    assert out["guest"] == "null" and out["membre"] == "request", out
    assert out["guest_cherche"] == "[]", out  # un Guest sans lien ne trouve personne
    assert out["bloque_recherche"] == "null" and out["bloque_suggestion"] == "null", out


PAST = """
      insert into public.events (title, status, visibility, public_link, notify_on_publish, starts_at, created_by, show_participants)
        values ('{title}', 'published', 'all', true, false, now() - interval '{days} days', olga, {shown}) returning id into e;
      insert into public.rsvps (event_id, user_id, status) values (e, victor, 'yes'), (e, vera, '{vera}');"""


def test_member_mini_already_met_and_upcoming_together():
    out = run(as_postgres()
              + PAST.format(title="[DV2] -10", days=10, shown="true", vera="yes")
              + PAST.format(title="[DV2] -15 absente", days=15, shown="true", vera="no")
              + PAST.format(title="[DV2] -20", days=20, shown="true", vera="yes")
              + PAST.format(title="[DV2] -30", days=30, shown="true", vera="yes")
              + PAST.format(title="[DV2] -40", days=40, shown="true", vera="yes")
              + PAST.format(title="[DV2] -45 liste cachée", days=45, shown="false", vera="yes")
              + """
      -- Vera organise : présente d'office.
      insert into public.events (title, status, visibility, public_link, notify_on_publish, starts_at, created_by)
        values ('[DV2] -50 chez Vera', 'published', 'all', true, false, now() - interval '50 days', vera) returning id into e;
      insert into public.rsvps (event_id, user_id, status) values (e, victor, 'yes');"""
              + INVITED_EVENT + """
      insert into public.event_invites (event_id, user_id) values (e2, victor), (e2, vera);
      insert into public.rsvps (event_id, user_id, status) values (e2, victor, 'maybe'), (e2, vera, 'yes');"""
              + as_bot("victor") + "r := public.member_mini(vera);"
              + keep("deja_vu", "r ->> 'met_count'")
              + keep("dernieres", "(select string_agg(x ->> 'title', ',' order by o) from jsonb_array_elements(r -> 'met') with ordinality x(x, o))")
              + keep("a_venir", "(r -> 'events' -> 0 ->> 'mine') || '/' || (r -> 'events' -> 0 ->> 'theirs') || '/' || (r ->> 'events_count')")
              + keep("lien", "r ->> 'link'") + keep("nom", "r ->> 'name'")
              + keep("p_deja_vu", person("public.chat_people_search('Bot Vera')", "vera", "met_count"))
              + as_postgres() + "insert into public.direct_blocks (user_id, blocked_id) values (vera, victor);"
              + as_bot("victor") + "r := public.member_mini(vera);"
              + keep("bloque", "(r ->> 'blocked_me') || '/' || (r ->> 'link') || '/' || (r ->> 'met_count')"))
    assert out["deja_vu"] == "5", out  # -10, -20, -30, -40, -50 (absente et liste cachée : non)
    assert out["dernieres"] == "[DV2] -10,[DV2] -20,[DV2] -30", out
    assert out["a_venir"] == "maybe/yes/1", out
    assert out["lien"] == "direct" and out["nom"] in ("Bot Vera", "Vera Vip"), out  # direct : réponse à l'événement qu'elle organise
    assert out["p_deja_vu"] == "5", out
    assert out["bloque"] == "true/none/0", out


def test_private_group_is_not_read_by_root_and_request_links_are_refused():
    out = run(as_postgres() + GROUP_VICTOR_VERA + as_bot("victor")
              + "r := public.create_chat_group('[DV2] Privé', '🎲', 'mint', array[vera, violette, gus]); g2 := (r ->> 'group')::uuid;"
              + keep("invites", "r ->> 'invited'")
              + keep("refuses", "(select string_agg(x, ',' order by x) from jsonb_array_elements_text(r -> 'refused') x) = "
                                "(select string_agg(x::text, ',' order by x::text) from unnest(array[violette, gus]) x)")
              + keep("avec_vera", "public.chat_group_with(array[vera]) = g2")
              + keep("avec_violette", "public.chat_group_with(array[vera, violette])")
              + note("un_seul", "perform public.create_chat_group('x', '🎲', 'mint', array[vera])")
              + note("emoji", "perform public.create_chat_group('[DV2] Serpents', '🐍', 'mint', array[vera, valentin])")
              + "insert into public.group_messages (group_id, user_id, body) values (g2, victor, 'Entre nous');"
              + "update public.member_groups set private_chat = false where id = g2;"
              + "insert into public.member_groups (name, created_by, private_chat) values ('[DV2] Normal', victor, true) returning id into g;"
              + as_postgres() + keep("prive", "(select private_chat from public.member_groups where id = g2)")
              + keep("normal", "(select private_chat from public.member_groups where id = g)")
              + keep("root_admin", "private.group_admin(g2, root)")
              + keep("invitation", "(select count(*) from private.group_invitations where group_id = g2 and user_id = vera and status = 'pending')")
              + as_bot("root") + keep("root_lit", "(select count(*) from public.group_messages where group_id = g2)")
              + keep("root_liste", "position(g2::text in public.chat_list()::text)")
              + keep("root_ancienne", "position(g2::text in public.my_chats()::text)")
              + keep("root_normal", "position(g::text in public.chat_list()::text) > 0")
              + as_bot("ada") + keep("admin_voit", "(select count(*) from public.member_groups where id = g2)")
              + keep("admin_membres", "(select count(*) from public.member_group_members where group_id = g2)")
              + as_bot("victor") + keep("createur", in_list("g2", "title")))
    assert out["invites"] == "1" and out["refuses"] == "true", out
    assert out["avec_vera"] == "true" and out["avec_violette"] == "null", out
    assert out["un_seul"].startswith("invalid") and out["emoji"].startswith("invalid"), out
    assert out["prive"] == "true" and out["normal"] == "false" and out["root_admin"] == "false", out
    assert out["invitation"] == "1", out
    assert out["root_lit"] == "0" and out["root_liste"] == "0" and out["root_ancienne"] == "0", out
    assert out["root_normal"] == "true", out
    # Groupes libres (22.11) : l'admin du site voit le groupe privé et ses membres, jamais ses messages (root_lit = 0).
    assert out["admin_voit"] == "1" and int(out["admin_membres"]) >= 1, out
    assert out["createur"] == "[DV2] Privé", out


def test_editing_is_refused_after_fifteen_minutes():
    out = run(as_postgres() + GROUP_VICTOR_VERA + as_bot("victor") + open_chat("vera") + say("c", "Rendez-vous à 20 h") + ";"
              + note("tout_de_suite", "perform public.edit_direct_message(m, 'Rendez-vous à 21 h')")
              + keep("modifie", "(select body from public.direct_messages where id = m)")
              + "insert into public.group_messages (group_id, user_id, body) values (g, victor, 'On amène quoi ?') returning id into e;"
              + note("groupe_tout_de_suite", "perform public.edit_group_message(e, 'On amène quoi samedi ?')")
              + as_postgres() + """
      update public.direct_messages set created_at = now() - interval '16 minutes' where id = m;
      update public.group_messages set created_at = now() - interval '16 minutes' where id = e;"""
              + as_bot("victor")
              + note("trop_tard", "perform public.edit_direct_message(m, 'Finalement 22 h')")
              + note("groupe_trop_tard", "perform public.edit_group_message(e, 'Trop tard')")
              + as_bot("vera") + note("pas_l_auteur", "perform public.edit_group_message(e, 'Pirate')"))
    assert out["tout_de_suite"] == "ok" and out["modifie"] == "Rendez-vous à 21 h" and out["groupe_tout_de_suite"] == "ok", out
    assert out["trop_tard"].startswith("edit_window") and out["groupe_trop_tard"].startswith("edit_window"), out
    assert out["pas_l_auteur"].startswith("forbidden"), out


def test_event_cards_only_for_who_can_see_the_event_and_quotes_are_cleaned():
    long = "x" * 200
    quote = ('{"from": "group", "title": "[DV2] Bande", "author": "Bot Victor", "excerpt": "' + long + '", "pirate": 1}')
    out = run(as_postgres() + GROUP_VICTOR_VERA + INVITED_EVENT + """
      insert into public.event_invites (event_id, user_id) values (e2, victor);"""
              + as_bot("victor") + open_chat("vera") + say("c", "", ", event_id", ", e2") + ";"
              + keep("carte", "(select event_card || '/' || (event_id = e2) from public.direct_messages where id = m)")
              + keep("cartes_victor", "(public.chat_event_cards(array[e2]) -> 0 ->> 'mine') || '/' || jsonb_array_length(public.chat_event_cards(array[e2]))")
              + keep("liste_type", "(select x -> 'last' ->> 'type' from jsonb_array_elements(public.chat_list()) x where x ->> 'id' = c::text)")
              + "insert into public.group_messages (group_id, user_id, body, event_id) values (g, victor, 'Qui vient ?', e2) returning id into m;"
              + keep("carte_groupe", "(select event_card from public.group_messages where id = m)")
              + as_bot("vera") + keep("cartes_vera", "public.chat_event_cards(array[e2])")
              + say("c", "Regarde", ", event_id", ", e2") + ";"
              + keep("carte_invisible", "(select event_card || '/' || coalesce(event_id::text, 'null') from public.direct_messages where id = m)")
              + say("c", "Je te réponds ici", ", quote", f", '{quote}'::jsonb") + ";"
              + keep("citation", "(select (select string_agg(k, ',' order by k) from jsonb_object_keys(quote) k) || '/' || "
                                 "char_length(quote ->> 'excerpt') from public.direct_messages where id = m)")
              + say("c", "Mauvaise citation", ", quote", ", '{\"from\": \"dm\", \"excerpt\": \"x\"}'::jsonb") + ";"
              + keep("citation_refusee", "(select coalesce(quote::text, 'null') from public.direct_messages where id = m)")
              + as_postgres() + "delete from public.events where id = e2;"
              + keep("apres_suppression", "(select count(*) || '/' || bool_and(event_card) || '/' || count(event_id) from public.direct_messages "
                                          "where chat_id = c and event_card)"))
    assert out["carte"] == "true/true" and out["cartes_victor"] == "invited/1", out
    assert out["liste_type"] == "event" and out["carte_groupe"] == "true", out
    assert out["cartes_vera"] == "[]", out
    assert out["carte_invisible"] == "false/null", out
    assert out["citation"] == "author,excerpt,from,title/140", out
    assert out["citation_refusee"] == "null", out
    assert out["apres_suppression"] == "1/true/0", out  # la carte reste, l'événement n'est plus désigné


def test_phone_number_guessing_stops_after_twenty_misses():
    wrong = "repeat('0', 64)"
    out = run(as_postgres() + """
      h := encode(extensions.hmac('+' || (select phone from public.profiles where id = gina),
                                  (select k.key from private.contact_key k where k.id = 1), 'sha256'), 'hex');"""
              + as_bot("gus") + keep("sans", "(public.open_direct_chat(gina)) ->> 'status'")
              + keep("bon", "(public.open_direct_chat(gina, h)) ->> 'status'")
              + as_postgres() + "delete from public.direct_chats where user_a = least(gus, gina) and user_b = greatest(gus, gina);"
              + as_bot("gus") + f"for i in 1..25 loop r := public.open_direct_chat(gina, {wrong}); end loop;"
              + keep("rate", "r ->> 'status'")
              + keep("bloque", "(public.open_direct_chat(gina, h)) ->> 'status'")
              + as_postgres() + keep("essais", "(select count(*) from private.contact_hash_fails where user_id = gus)")
              + "delete from private.contact_hash_fails where user_id = gus;"
              + as_bot("gus") + keep("ancienne_null", f"coalesce(public.start_direct_chat(gina, {wrong})::text, 'null')")
              + note("ancienne_sans_empreinte", "perform public.start_direct_chat(gina)")
              + as_postgres() + keep("compte", "(select count(*) from private.contact_hash_fails where user_id = gus)"))
    assert out["sans"] == "none" and out["bon"] == "request", out
    assert out["rate"] == "none" and out["bloque"] == "none", out
    assert out["essais"] == "20", out
    assert out["ancienne_null"] == "null" and out["ancienne_sans_empreinte"].startswith("forbidden"), out
    assert out["compte"] == "1", out
