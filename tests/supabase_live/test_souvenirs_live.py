"""Souvenirs (avis 74d36b93e7bd, 24.11.2026, migration 20261124090000), sur la VRAIE base de TEST, bots seulement, tout
dans des transactions ANNULÉES (rien ne reste). Événement public de Bot Olga (organisatrice), Souvenirs allumés ;
Victor (Présent) et Valentin (Peut-être) prennent des photos ; Violette ne répond pas ; Ada (admin, events.manage_all)
fait partie de l'organisation pour la relecture. Le temps se déplace en déplaçant l'événement (now() est fixe dans la
transaction) : début / fin dans le passé = fermé, story (dévoilement = fin + 24 h, story 24 h), après la story."""
import json
import re
from pathlib import Path

from tests.supabase_live.test_annonces_groupe_live import BOTS, SETUP, as_bot, as_postgres
from tests.supabase_live.test_groups_members_only_live import sql_test
from tests.supabase_live.test_member_admin_live import pytestmark  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
DECLARE = ("e uuid; a uuid; b uuid; c uuid; d uuid; n int; m int; r jsonb; s text; t text; bots uuid; bots2 uuid; "
           + " ".join(f"{k} uuid;" for k in BOTS))

# Phases (par rapport à now()) : ouvert, fermé avant le dévoilement, story, après la story.
OPEN = "now() - interval '1 hour', now() + interval '1 hour'"
WAITING = "now() - interval '5 hours', now() - interval '3 hours'"
STORY = "now() - interval '30 hours', now() - interval '26 hours'"
AFTER = "now() - interval '60 hours', now() - interval '50 hours'"


def run(body: str) -> str:
    rows = sql_test(f"""
    begin;
    do $$ declare {DECLARE} begin
      {SETUP}
      {body}
    end $$;
    rollback;""")
    return json.dumps(rows, ensure_ascii=False) if not isinstance(rows, str) else rows


def event(keep: bool = True) -> str:
    """Événement public d'Olga, Souvenirs allumés ; Victor Présent, Valentin Peut-être."""
    return as_bot("olga") + f"""
      insert into public.events (title, status, visibility, public_link, notify_on_publish, starts_at, ends_at,
                                 souvenirs_enabled, souvenirs_keep)
        values ('Test souvenirs bots', 'draft', 'all', true, false, now() - interval '1 hour', now() + interval '1 hour',
                true, {str(keep).lower()}) returning id into e;
      update public.events set status = 'published' where id = e;""" + as_postgres() + """
      insert into public.rsvps (event_id, user_id, status) values (e, victor, 'yes'), (e, valentin, 'maybe');"""


def move(span: str) -> str:
    return as_postgres() + f"update public.events set (starts_at, ends_at) = ({span}) where id = e;"


def take(bot: str, into: str = "a") -> str:
    """Le serveur dépose le fichier (ici : la ligne de storage.objects), puis souvenir_take avec la session du bot."""
    return as_postgres() + f"""
      {into} := gen_random_uuid();
      insert into storage.objects (bucket_id, name, owner_id) values ('souvenirs', e || '/' || {bot} || '/' || {into} || '.jpg', {bot}::text);
      """ + as_bot(bot) + f"perform public.souvenir_take(e, {into});"


def attempt(stmt: str, label: str) -> str:
    """Essaie stmt : ajoute « label=ok » ou « label=<code> » (code de la phrase de la base) à s."""
    return f"""
      begin {stmt} s := s || ' {label}=ok';
      exception when others then s := s || ' {label}=' || split_part(sqlerrm, ':', 1); end;"""


def result(out: str) -> str:
    found = re.search(r"résultat:([^\"\\]*)", out)
    assert found, out
    return found.group(1).strip()


def test_three_photos_at_most_and_the_counter_gives_the_number_only():
    out = run(event() + "s := '';" + take("victor") + take("victor", "b") + take("victor", "c") + as_postgres() + """
      d := gen_random_uuid();
      insert into storage.objects (bucket_id, name, owner_id) values ('souvenirs', e || '/' || victor || '/' || d || '.jpg', victor::text);
      """ + as_bot("victor") + attempt("perform public.souvenir_take(e, d);", "quatrieme") + """
      r := public.souvenir_counter(e);""" + as_bot("violette") + """
      raise exception 'résultat:% compte=% reste=% peut=% violette=% qui=%', s, r->>'count', r->>'left', r->>'can_take',
        public.souvenir_counter(e)->>'count', coalesce(public.souvenir_counter(e)->>'photos', 'aucun');""")
    assert result(out) == "quatrieme=full compte=3 reste=0 peut=false violette=3 qui=aucun", out


def test_the_window_the_circle_the_profile_and_the_file():
    out = run(event() + "s := '';" + as_postgres() + """
      a := gen_random_uuid();
      insert into storage.objects (bucket_id, name, owner_id) values ('souvenirs', e || '/' || violette || '/' || a || '.jpg', violette::text);
      """ + as_bot("violette") + attempt("perform public.souvenir_take(e, a);", "sans_reponse") + as_postgres() + """
      insert into public.rsvps (event_id, user_id, status) values (e, violette, 'no');""" + as_bot("violette")
        + attempt("perform public.souvenir_take(e, a);", "pas_present") + as_bot("victor")
        + attempt("perform public.souvenir_take(e, gen_random_uuid());", "sans_fichier") + move(WAITING)
        + take("victor").replace("perform public.souvenir_take(e, a);", "") + as_bot("victor")
        + attempt("perform public.souvenir_take(e, a);", "apres_fin") + move("now() + interval '1 hour', now() + interval '3 hours'")
        + as_bot("victor") + attempt("perform public.souvenir_take(e, a);", "avant_debut") + move(OPEN) + as_postgres() + """
      delete from public.terms_acceptances where user_id = victor;""" + as_bot("victor")
        + attempt("perform public.souvenir_take(e, a);", "cgu") + """
      raise exception 'résultat:%', s;""")
    assert result(out) == ("sans_reponse=forbidden pas_present=forbidden sans_fichier=invalid apres_fin=closed "
                           "avant_debut=closed cgu=terms_required"), out


def test_cancel_within_five_seconds_only_and_the_upload_rule_of_the_bucket():
    out = run(event() + "s := '';" + take("victor") + as_bot("victor") + attempt("perform public.souvenir_cancel(a);", "tout_de_suite")
              + take("victor", "b") + as_postgres() + """
      update public.souvenir_photos set taken_at = now() - interval '10 seconds' where id = b;""" + as_bot("victor")
              + attempt("perform public.souvenir_cancel(b);", "dix_secondes") + """
      raise exception 'résultat:% photos=% depot_soi=% depot_autre=%', s,
        (select count(*) from public.souvenir_counter(e) x), private.souvenir_may_upload(e || '/' || victor || '/' || gen_random_uuid() || '.jpg'),
        private.souvenir_may_upload(e || '/' || valentin || '/' || gen_random_uuid() || '.jpg');""")
    assert result(out) == "tout_de_suite=ok dix_secondes=closed photos=1 depot_soi=t depot_autre=f", out


def test_before_the_reveal_only_the_organization_sees_the_photos():
    out = run(event() + "s := '';" + take("victor") + take("valentin", "b") + move(WAITING) + as_bot("valentin")
              + attempt("perform public.souvenir_story(e);", "story_valentin") + """
      n := jsonb_array_length(public.souvenir_mine(e)->'photos');""" + as_bot("olga") + """
      m := jsonb_array_length(public.souvenir_review(e)->'photos');""" + as_bot("ada") + """
      r := public.souvenir_review(e);""" + as_bot("victor") + attempt("perform public.souvenir_review(e);", "relecture_victor") + """
      raise exception 'résultat:% mine_valentin=% olga=% ada=%', s, n, m, jsonb_array_length(r->'photos');""")
    assert result(out) == "story_valentin=closed relecture_victor=forbidden mine_valentin=0 olga=2 ada=2", out


def test_the_organization_removes_a_photo_during_the_review():
    out = run(event() + take("victor") + take("valentin", "b") + move(WAITING) + as_bot("olga") + """
      perform public.souvenir_remove(a);
      n := jsonb_array_length(public.souvenir_review(e)->'photos');""" + as_postgres() + """
      raise exception 'résultat: restent=% corbeille=%', n,
        (select count(*) from private.souvenir_trash where path like e || '/%');""")
    assert "résultat: restent=1 corbeille=1" in out, out


def test_the_story_shows_every_photo_to_the_circle_for_24_hours():
    out = run(event() + "s := '';" + take("victor") + take("valentin", "b") + take("olga", "c") + as_postgres() + """
      update public.souvenir_photos set taken_at = now() - interval '3 minutes' where id = a;
      update public.souvenir_photos set taken_at = now() - interval '2 minutes' where id = b;""" + move(STORY) + as_bot("victor") + """
      r := public.souvenir_story(e);""" + as_bot("violette") + attempt("perform public.souvenir_story(e);", "violette") + """
      raise exception 'résultat:% photos=% auteurs=% gardable=% jusqua=%', s, jsonb_array_length(r->'photos'),
        (select string_agg(x->'author'->>'name', ',') from jsonb_array_elements(r->'photos') x),
        r->'photos'->0->>'can_keep', (r->>'until')::timestamptz > now() + interval '21 hours';""")
    assert result(out) == "violette=forbidden photos=3 auteurs=Bot Victor,Bot Valentin,Bot Olga gardable=false jusqua=t", out


def test_after_the_story_there_is_no_story_anymore():
    out = run(event() + "s := '';" + take("victor") + move(AFTER) + as_bot("valentin")
              + attempt("perform public.souvenir_story(e);", "story") + """
      raise exception 'résultat:%', s;""")
    assert result(out) == "story=closed", out


def test_blocking_hides_photos_both_ways_everywhere():
    out = run(event() + take("victor") + take("valentin", "b") + as_postgres() + """
      insert into public.direct_blocks (user_id, blocked_id) values (victor, valentin);""" + move(STORY) + as_bot("victor") + """
      r := public.souvenir_story(e);
      n := (public.souvenir_counter(e)->>'count')::int;""" + as_bot("valentin") + """
      raise exception 'résultat: victor_voit=% victor_compte=% valentin_voit=% valentin_compte=%',
        (select string_agg(x->'author'->>'name', ',') from jsonb_array_elements(r->'photos') x), n,
        (select string_agg(x->'author'->>'name', ',') from jsonb_array_elements(public.souvenir_story(e)->'photos') x),
        public.souvenir_counter(e)->>'count';""")
    assert "résultat: victor_voit=Bot Victor victor_compte=1 valentin_voit=Bot Valentin valentin_compte=1" in out, out


def test_keep_during_the_story_then_my_souvenirs_hold_mine_and_kept_ones():
    out = run(event() + "s := '';" + take("victor") + take("valentin", "b") + take("olga", "c") + as_postgres() + """
      update public.souvenir_photos set taken_at = now() - interval '3 minutes' where id = a;""" + move(STORY) + as_bot("valentin") + """
      perform public.souvenir_keep(a);
      r := public.souvenir_story(e);""" + move(AFTER) + as_bot("valentin")
              + attempt("perform public.souvenir_keep(c);", "garder_apres") + """
      r := r || jsonb_build_object('mine', public.souvenir_mine(e));""" + as_bot("victor") + """
      perform public.souvenir_delete(a);""" + as_bot("valentin") + """
      raise exception 'résultat:% garde=% mes=% apres_suppression=%', s, (select x->>'kept' from jsonb_array_elements(r->'photos') x where x->>'id' = a::text),
        (select string_agg((x->'author'->>'name') || '/' || (x->>'origin'), ',') from jsonb_array_elements(r->'mine'->'photos') x),
        (select string_agg(x->>'origin', ',') from jsonb_array_elements(public.souvenir_mine(e)->'photos') x);""")
    assert result(out) == "garder_apres=not_found garde=true mes=Bot Victor/kept,Bot Valentin/taken apres_suppression=taken", out


def test_without_keep_nothing_stays_and_the_files_are_erased_after_the_story():
    out = run(event(keep=False) + "s := '';" + take("victor") + take("valentin", "b") + move(STORY) + as_bot("valentin")
              + attempt("perform public.souvenir_keep(a);", "garder") + """
      n := jsonb_array_length(public.souvenir_mine(e)->'photos');""" + move(AFTER) + """
      perform private.souvenir_tick();""" + as_bot("victor") + """
      m := jsonb_array_length(public.souvenir_mine(e)->'photos');""" + as_postgres() + """
      raise exception 'résultat:% mine_story=% mine_apres=% lignes=% corbeille=%', s, n, m, (select count(*) from public.souvenir_photos where event_id = e),
        (select count(*) from private.souvenir_trash where path like e || '/%');""")
    # La tâche a aussi vidé la corbeille (demandes d'effacement à l'API Storage, envoyées par pg_net après validation).
    assert result(out) == "garder=forbidden mine_story=0 mine_apres=0 lignes=0 corbeille=0", out


def test_settings_are_frozen_by_the_first_photo_and_only_the_organization_sets_them():
    out = run(event() + "s := '';" + as_bot("victor")
              + attempt("update public.events set souvenirs_keep = false where id = e;", "victor_regle") + as_bot("olga")
              + attempt("perform public.souvenir_settings(e, '{\"keep\": false}');", "avant") + attempt(
                  "perform public.souvenir_settings(e, '{\"keep\": true}');", "remis") + take("victor") + as_bot("olga")
              + attempt("perform public.souvenir_settings(e, '{\"keep\": false}');", "apres")
              + attempt("update public.events set souvenirs_keep = false where id = e;", "direct")
              + attempt("update public.events set souvenirs_reveal_at = now() where id = e;", "date_directe") + """
      raise exception 'résultat:% verrou=%', s, (select souvenirs_locked from public.events where id = e);""")
    # Victor (membre) : la règle de la base ne lui laisse modifier aucune ligne de l'événement d'Olga (0 ligne, pas
    # d'erreur) ; la garde refuse aussi s'il passe.
    assert result(out) == ("victor_regle=ok avant=ok remis=ok apres=locked direct=locked date_directe=forbidden verrou=t"), out


def test_reveal_now_never_before_the_end_then_the_circle_is_told_once():
    out = run(event() + "s := '';" + take("victor") + as_postgres() + """
      insert into public.notification_prefs (user_id, souvenirs) values (valentin, false)
      on conflict (user_id) do update set souvenirs = false;""" + as_bot("olga")
              + attempt("perform public.souvenir_reveal_now(e);", "avant_fin") + move(WAITING) + as_bot("victor")
              + attempt("perform public.souvenir_reveal_now(e);", "victor") + as_bot("olga") + """
      r := public.souvenir_reveal_now(e);""" + as_postgres() + """
      perform private.souvenir_tick();
      raise exception 'résultat:% phase=% victor=% valentin=% olga=% violette=%', s, r->>'phase',
        (select count(*) from public.notifications where kind = 'souvenirs_revealed' and event_id = e and user_id = victor),
        (select count(*) from public.notifications where kind = 'souvenirs_revealed' and event_id = e and user_id = valentin),
        (select count(*) from public.notifications where kind = 'souvenirs_revealed' and event_id = e and user_id = olga),
        (select count(*) from public.notifications where kind = 'souvenirs_revealed' and event_id = e and user_id = violette);""")
    # Olga a dévoilé elle-même : pas de notification pour sa propre action.
    assert result(out) == "avant_fin=too_early victor=forbidden phase=story victor=1 valentin=0 olga=0 violette=0", out


def test_the_tick_reveals_at_end_plus_24_hours():
    out = run(event() + take("victor") + move(STORY) + as_postgres() + """
      perform private.souvenir_tick();
      perform private.souvenir_tick();
      raise exception 'résultat: olga=% victor=%',
        (select count(*) from public.notifications where kind = 'souvenirs_revealed' and event_id = e and user_id = olga),
        (select count(*) from public.notifications where kind = 'souvenirs_revealed' and event_id = e and user_id = victor);""")
    assert "résultat: olga=1 victor=1" in out, out


def test_a_reported_photo_is_hidden_at_once_the_organization_is_told_and_decides():
    out = run(event() + take("victor") + take("olga", "b") + move(STORY) + as_bot("valentin") + """
      perform public.souvenir_keep(a);
      perform public.report_content('souvenir', a::text, 'my_image', null);""" + as_bot("violette") + """
      """ + as_postgres() + """
      insert into public.rsvps (event_id, user_id, status) values (e, violette, 'yes');""" + as_bot("violette") + """
      n := jsonb_array_length(public.souvenir_story(e)->'photos');""" + as_bot("valentin") + """
      m := (select count(*) from jsonb_array_elements(public.souvenir_mine(e)->'photos') x where x->>'id' = a::text);""" + as_bot("olga") + """
      r := public.souvenir_review(e);
      perform public.souvenir_restore(a);""" + as_postgres() + """
      s := (select count(*) from public.notifications where kind = 'souvenir_reported' and user_id = olga and event_id = e)::text
        || ' moderateurs=' || (select count(*) from public.notifications where kind = 'report_new'
                               and body like 'Droit à l''image · une photo Souvenirs%');""" + as_bot("violette") + """
      raise exception 'résultat: masquee_story=% masquee_gardee=% orga_prevenue=% signalee=% remise=%', n, m, s,
        jsonb_array_length(r->'reported'), jsonb_array_length(public.souvenir_story(e)->'photos');""")
    # Les modérateurs de Party (droit moderation.reports) reçoivent « Droit à l'image · une photo Souvenirs » (au moins un).
    assert re.search(r"résultat: masquee_story=1 masquee_gardee=0 orga_prevenue=1 moderateurs=[1-9]\d* signalee=1 remise=2", out), out


def test_party_moderation_has_the_last_word():
    out = run(event() + take("victor") + take("valentin", "b") + move(STORY) + as_bot("olga") + """
      perform public.report_content('souvenir', a::text, 'shocking', null);
      perform public.report_content('souvenir', b::text, 'other', null);""" + as_postgres() + """
      perform private.moderation_hide(x) from public.content_reports x where target_kind = 'souvenir' and target_id = a::text;
      update public.content_reports set status = 'dismissed' where target_kind = 'souvenir' and target_id = b::text;
      n := (select count(*) from public.souvenir_photos where id = a);
      m := (select count(*) from private.souvenir_trash where path like e || '/%');""" + as_bot("olga") + """
      raise exception 'résultat: lignes_a=% story=% corbeille=%', n, jsonb_array_length(public.souvenir_story(e)->'photos'), m;""")
    # « Masquer » (modération de Party) efface la photo a ; « Classer » remet la photo b.
    assert "résultat: lignes_a=0 story=1 corbeille=1" in out, out


def test_the_organization_is_never_told_by_a_blocked_reporter():
    out = run(event() + take("victor") + move(STORY) + as_postgres() + """
      insert into public.direct_blocks (user_id, blocked_id) values (olga, valentin);""" + as_bot("valentin") + """
      perform public.report_content('souvenir', a::text, 'my_image', null);""" + as_postgres() + """
      raise exception 'résultat: olga=% masquee=%',
        (select count(*) from public.notifications where kind = 'souvenir_reported' and user_id = olga and event_id = e),
        (select hidden_at is not null from public.souvenir_photos where id = a);""")
    assert "résultat: olga=0 masquee=t" in out, out


def test_tables_are_never_read_directly_and_the_event_cascade_empties_everything():
    out = run(event() + "s := '';" + take("victor") + as_bot("victor")
              + attempt("select count(*) into n from public.souvenir_photos;", "photos").replace("split_part(sqlerrm, ':', 1)", "sqlstate")
              + attempt("select count(*) into n from public.souvenir_keeps;", "gardees").replace("split_part(sqlerrm, ':', 1)", "sqlstate") + as_postgres() + """
      delete from public.events where id = e;
      raise exception 'résultat:% lignes=% corbeille=%', s, (select count(*) from public.souvenir_photos where event_id = e),
        (select count(*) from private.souvenir_trash where path like e || '/%');""")
    assert result(out) == "photos=42501 gardees=42501 lignes=0 corbeille=1", out


def test_the_ai_never_turns_souvenirs_on():
    from app import ai_events as ev
    schema = ev.schema({"categories": [], "tags": [], "audiences": ["Vendredi Party"], "people": []})
    assert not any("souvenir" in k for k in json.dumps(schema).split('"'))


def test_the_migration_replays_without_change():
    sql = (ROOT / "supabase/migrations/20261124090000_souvenirs.sql").read_text()
    out = sql_test("begin;\n" + sql + "\nrollback;")
    assert "HTTP" not in str(out) and "ERROR" not in str(out), out
    check = sql_test("""select (select count(*) from cron.job where jobname = 'souvenirs-tick') jobs,
      (length(pg_get_functiondef('private.may_receive_push(uuid,text)'::regprocedure))
       - length(replace(pg_get_functiondef('private.may_receive_push(uuid,text)'::regprocedure), 'souvenirs_revealed', ''))) / 18 fois,
      pg_get_constraintdef((select oid from pg_constraint where conname = 'content_reports_target_kind_check')) like '%prono_answer%souvenir%' kinds;""")
    assert check == [{"jobs": 1, "fois": 1, "kinds": True}], check
