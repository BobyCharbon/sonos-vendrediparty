"""Options du bar (demande de l'admin du 10.11.2026 : « vraiment modulable », migration 20261110160000_bar_options), sur la
VRAIE base de TEST (jamais la prod), avec les comptes des BOTS seulement :
- organisatrice Bot Olga ; barman Bot Valentin ; invités Bot Ada, Bot Côme ; Bot Victor invité mais pas barman ;
- options de l'organisateur : commandes dans l'app, service au comptoir, stock montré, bar offert, limites par personne,
  droits des barmans ; articles : catégorie, précision, maximum par personne, « Indisponible pour l'instant » ;
- gestes du barman : « Il en reste… », « + Réassort », « Indisponible » / « De nouveau dispo », notés au journal, droits
  vérifiés par la base.
Tout se passe dans des transactions ANNULÉES (rien ne reste) ; l'événement est sur invitation, sans notification.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_bar_options_live.py -q"""
import json

from tests.supabase_live.test_groups_members_only_live import sql_test
from tests.supabase_live.test_member_admin_live import pytestmark  # noqa: F401

BOTS = {"olga": "41790000103", "ada": "41790000101", "come": "41790000102", "victor": "41790000105", "valentin": "41790000107"}
DECLARE = ("e uuid; vrb uuid; coca uuid; r jsonb; n int; out text := ''; msg text; pv int; pt text; srv uuid; "
           + " ".join(f"{k} uuid;" for k in BOTS))
SETUP = "\n".join(f"select id into {k} from public.profiles where phone = '{p}';" for k, p in BOTS.items()) + """
insert into public.terms_acceptances (user_id, version)
  select p.id, (select terms_version from private.moderation_settings where id = 1) from public.profiles p
  where p.phone in (""" + ", ".join(f"'{p}'" for p in BOTS.values()) + """) on conflict do nothing;"""


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


# Événement sur invitation, sans notification ; tout le monde « Présent » ; bar ouvert : Vodka Red Bull 4.50 (stock 10),
# Coca 2.00 (illimité) ; Valentin barman.
BAR = as_postgres() + """
      insert into public.events (title, status, visibility, notify_on_publish, starts_at, created_by)
        values ('[Recette] Options du bar', 'published', 'invited', false, now() + interval '2 days', olga) returning id into e;
      insert into public.event_invites (event_id, user_id) select e, x from unnest(array[ada, come, victor, valentin]) x;
      insert into public.rsvps (event_id, user_id, status) select e, x, 'yes' from unnest(array[olga, ada, come, victor, valentin]) x
        on conflict do nothing;""" + as_bot("olga") + """
      perform public.bar_create(e);
      vrb := (public.bar_save_item(e, '{"name": "Vodka Red Bull", "emoji": "🍸", "price_chf": 4.5, "stock": 10}'::jsonb))->>'id';
      coca := (public.bar_save_item(e, '{"name": "Coca", "price_chf": 2}'::jsonb))->>'id';
      perform public.bar_save_settings(e, '{"orders_open": true}'::jsonb);
      perform public.bar_set_staff(e, valentin, true);"""


def lines(item: str, qty: int, extra: int = 0) -> str:
    extra_part = f", 'extra', {extra}" if extra else ""
    return f"jsonb_build_array(jsonb_build_object('item', {item}, 'qty', {qty}{extra_part}))"


def pledge_of(who: str) -> str:
    """Se met dans la peau de `who` et lit l'engagement courant (texte exact de my_bar)."""
    return as_bot(who) + """
      r := public.my_bar(e); pt := r->>'pledge_text'; pv := (r->>'pledge_version')::int;"""


def run(body: str) -> str:
    rows = sql_test(f"""
    begin;
    do $$ declare {DECLARE} begin
      {SETUP}
      {body}
      raise exception 'résultat:%', out;
    end $$;
    rollback;""")
    text = json.dumps(rows, ensure_ascii=False)
    raw = rows[0].get("error", "") if rows and isinstance(rows[0], dict) else ""
    if "HTTP" in raw and "{" in raw:  # « HTTP 400: {"message": "… résultat: …"} » : le message en clair
        try:
            return json.loads(raw[raw.index("{"):])["message"]
        except (ValueError, KeyError):
            return text
    return text


def test_options_have_safe_defaults_and_the_organizer_saves_them():
    out = run(BAR + keep("defaut", "(public.bar_overview(e))->'options'") + """
      r := public.bar_save_settings(e, '{"show_stock": false, "free_bar": false, "limit_glasses": 6, "limit_chf": 30,
        "staff_prices": true, "staff_correct": false}'::jsonb);""" + keep("apres", "r->'options'")
        + note("les_deux_eteints", "perform public.bar_save_settings(e, '{\"guest_orders\": false, \"counter_serve\": false}'::jsonb)")
        + note("limite_folle", "perform public.bar_save_settings(e, '{\"limit_glasses\": 0}'::jsonb)")
        + as_bot("valentin") + note("barman_regle", "perform public.bar_save_settings(e, '{\"free_bar\": true}'::jsonb)"))
    assert ('defaut={"free_bar": false, "limit_chf": null, "show_stock": true, "staff_items": false, "guest_orders": true, '
            '"staff_prices": false, "counter_serve": false, "limit_glasses": null, "staff_correct": true, '
            '"staff_unavailable": true, "staff_adjust_stock": true}') in out, out
    assert '"limit_chf": 30' in out and '"show_stock": false' in out and '"limit_glasses": 6' in out, out
    assert 'les_deux_eteints=Sans commande dans l’app, le service au comptoir doit rester allumé' in out.replace("'", '’'), out
    assert 'limite_folle=Limite de verres' in out, out
    assert 'barman_regle=forbidden' in out, out


def test_without_app_orders_the_barman_serves_at_the_counter_once_the_pledge_is_accepted():
    out = run(BAR + as_bot("olga") + """
      perform public.bar_save_settings(e, '{"guest_orders": false, "counter_serve": true}'::jsonb);""" + pledge_of("ada")
        + note("commande_app", f"perform public.bar_order(e, {lines('vrb', 1)}, pt, pv)")
        + keep("carte_options", "r->'options'->>'guest_orders'") + keep("engage_avant", "r->>'pledged_current'")
        + as_bot("valentin")
        + note("sans_engagement", f"perform public.bar_serve(e, ada, {lines('vrb', 0, 1)}, gen_random_uuid()::text)")
        + as_bot("ada") + """
      perform public.bar_pledge(e, pt, pv);"""
        + keep("engage_apres", "(public.my_bar(e))->>'pledged_current'") + """
      pt := (public.my_bar(e))->'qr'->>'token';""" + as_bot("valentin") + """
      r := public.bar_scan(e, pt);"""
        + keep("scan_comptoir", "r->>'counter'") + keep("scan_carte", "jsonb_array_length(r->'menu')") + f"""
      r := public.bar_serve(e, ada, {lines('vrb', 0, 2)}, gen_random_uuid()::text);"""
        + keep("debite", "r->>'balance'") + as_postgres()
        + keep("verres", "(select count(*) from public.event_bar_units where event_id = e and user_id = ada and status = 'served' and pledge_id is not null)"))
    assert "commande_app=counter_only" in out, out
    assert "sans_engagement=pledge_required" in out, out
    assert "carte_options=false" in out and "engage_avant=false" in out and "engage_apres=true" in out, out
    assert "scan_comptoir=true" in out and "scan_carte=2" in out, out
    assert "debite=9.00" in out and "verres=2" in out, out


def test_counter_service_is_refused_when_the_organizer_keeps_it_off():
    out = run(BAR + pledge_of("ada") + """
      perform public.bar_pledge(e, pt, pv);""" + as_bot("valentin")
        + note("comptoir", f"perform public.bar_serve(e, ada, {lines('coca', 0, 1)}, gen_random_uuid()::text)"))
    assert "comptoir=counter_off" in out, out


def test_stock_shown_or_hidden_and_sold_out_still_said():
    out = run(BAR + as_bot("olga") + """
      perform public.bar_save_item(e, jsonb_build_object('id', vrb, 'name', 'Vodka Red Bull', 'stock', 1));""" + as_bot("ada") + """
      r := public.my_bar(e);""" + keep("montre", "(select x->>'available' from jsonb_array_elements(r->'items') x where x->>'id' = vrb::text)")
        + pledge_of("come") + f"""
      perform public.bar_order(e, {lines('vrb', 1)}, pt, pv);""" + as_bot("olga") + """
      perform public.bar_save_settings(e, '{"show_stock": false}'::jsonb);""" + as_bot("ada") + """
      r := public.my_bar(e);"""
        + keep("cache", "(select coalesce(x->>'available', 'null') || '/' || (x->>'sold_out') from jsonb_array_elements(r->'items') x where x->>'id' = vrb::text)")
        + keep("coca", "(select coalesce(x->>'available', 'null') || '/' || (x->>'sold_out') from jsonb_array_elements(r->'items') x where x->>'id' = coca::text)"))
    assert "montre=1" in out and "cache=null/true" in out and "coca=null/false" in out, out


def test_free_bar_needs_no_pledge_costs_nothing_and_still_counts_the_glasses():
    out = run(BAR + as_bot("olga") + """
      perform public.bar_save_settings(e, '{"free_bar": true}'::jsonb);""" + as_bot("ada") + """
      r := public.my_bar(e);"""
        + keep("prix_vus", "(select string_agg(x->>'price_chf', ',') from jsonb_array_elements(r->'items') x)")
        + keep("paiement", "r->'payee'->>'link'") + f"""
      perform public.bar_order(e, {lines('vrb', 2)}, null, null);""" + as_bot("valentin") + f"""
      r := public.bar_serve(e, ada, {lines('vrb', 2)}, gen_random_uuid()::text);"""
        + keep("solde", "r->>'balance'") + as_postgres()
        + keep("engagements", "(select count(*) from public.event_bar_pledges where event_id = e)")
        + keep("note", "(select body from public.notifications where user_id = ada and kind = 'bar_served' and event_id = e)")
        + as_bot("olga") + keep("servis", "(public.bar_overview(e))->'totals'->>'served'") + """
      perform public.bar_save_settings(e, '{"free_bar": false}'::jsonb);""" + pledge_of("come")
        + note("payant_sans_engagement", f"perform public.bar_order(e, {lines('coca', 1)}, null, null)") + f"""
      perform public.bar_order(e, {lines('coca', 1)}, pt, pv);""" + as_bot("valentin") + f"""
      perform public.bar_serve(e, come, {lines('coca', 1)}, gen_random_uuid()::text);"""
        + as_bot("olga") + note("offert_apres_payant", "perform public.bar_save_settings(e, '{\"free_bar\": true}'::jsonb)"))
    assert "prix_vus=0,0" in out and "paiement=null" in out, out
    assert "solde=0" in out and "engagements=0" in out, out
    served_note = out.split("note=")[1].split(" | ")[0]
    assert "Bar offert" in served_note and "rembourser" not in served_note, out
    assert "servis=2" in out, out
    assert "payant_sans_engagement=terms_changed" in out, out
    assert "offert_apres_payant=Des verres payants" in out, out


def test_limits_per_person_for_the_evening_count_served_and_pending():
    out = run(BAR + as_bot("olga") + """
      perform public.bar_save_settings(e, '{"limit_glasses": 3}'::jsonb);""" + as_bot("ada") + """
      r := public.my_bar(e); pt := r->>'pledge_text'; pv := (r->>'pledge_version')::int;
      perform public.bar_order(e, """ + lines("coca", 2) + """, pt, pv);""" + as_bot("valentin") + """
      perform public.bar_serve(e, ada, """ + lines("coca", 1) + """, gen_random_uuid()::text);""" + as_bot("ada")
        + note("trois_plus_un", f"perform public.bar_order(e, {lines('vrb', 2)}, pt, pv)")
        + note("trois", f"perform public.bar_order(e, {lines('vrb', 1)}, pt, pv)")
        + keep("mes_verres", "(public.my_bar(e))->'mine'->>'glasses'") + as_bot("olga") + """
      perform public.bar_save_settings(e, '{"limit_glasses": null, "limit_chf": 10}'::jsonb);
      perform public.bar_save_item(e, jsonb_build_object('id', coca, 'name', 'Coca', 'max_per_person', 3));""" + as_bot("come") + """
      r := public.my_bar(e); pt := r->>'pledge_text'; pv := (r->>'pledge_version')::int;
      perform public.bar_order(e, """ + lines("vrb", 2) + """, pt, pv);"""
        + note("chf_depasse", f"perform public.bar_order(e, {lines('coca', 1)}, pt, pv)")
        + as_bot("ada") + note("max_article", f"perform public.bar_order(e, {lines('coca', 2)}, pt, pv)"))
    assert "trois_plus_un=limit_glasses" in out and "trois=ok" in out and "mes_verres=3" in out, out
    assert "chf_depasse=limit_chf" in out, out
    assert "max_article=limit_glasses" not in out and "max_article=max_person" in out, out


def test_unavailable_item_refuses_new_orders_but_waiting_glasses_stay_with_the_barman():
    out = run(BAR + as_bot("ada") + """
      r := public.my_bar(e); pt := r->>'pledge_text'; pv := (r->>'pledge_version')::int;
      perform public.bar_order(e, """ + lines("vrb", 2) + """, pt, pv);""" + as_bot("valentin") + """
      r := public.bar_item_action(e, vrb, 'unavailable', null);""" + keep("etat", "r->>'unavailable'") + as_bot("come") + """
      r := public.my_bar(e);"""
        + keep("vu_grise", "(select x->>'unavailable' from jsonb_array_elements(r->'items') x where x->>'id' = vrb::text)")
        + note("nouvelle", f"perform public.bar_order(e, {lines('vrb', 1)}, r->>'pledge_text', (r->>'pledge_version')::int)")
        + as_bot("valentin") + note("servir_attente", f"perform public.bar_serve(e, ada, {lines('vrb', 1)}, gen_random_uuid()::text)")
        + note("annuler_attente", "perform public.bar_cancel_units(e, ada, vrb, 1)") + """
      perform public.bar_item_action(e, vrb, 'available', null);""" + as_bot("come")
        + note("de_nouveau", f"perform public.bar_order(e, {lines('vrb', 1)}, r->>'pledge_text', (r->>'pledge_version')::int)")
        + as_postgres() + keep("journal", "(select string_agg(kind || ':' || (actor = valentin)::text, ',' order by id) from public.event_bar_log where event_id = e and kind in ('unavailable', 'available'))"))
    assert "etat=true" in out and "vu_grise=true" in out and "nouvelle=unavailable" in out, out
    assert "servir_attente=ok" in out and "annuler_attente=ok" in out and "de_nouveau=ok" in out, out
    assert "journal=unavailable:true,available:true" in out, out


def test_the_barman_sets_what_is_left_and_restocks_and_each_gesture_is_logged():
    out = run(BAR + as_bot("ada") + """
      r := public.my_bar(e);
      perform public.bar_order(e, """ + lines("vrb", 3) + """, r->>'pledge_text', (r->>'pledge_version')::int);""" + as_bot("valentin") + """
      perform public.bar_serve(e, ada, """ + lines("vrb", 2) + """, gen_random_uuid()::text);
      r := public.bar_item_action(e, vrb, 'remaining', 5);""" + keep("reste", "(r->>'stock') || '/' || (r->>'available') || '/' || (r->>'left')") + """
      r := public.bar_item_action(e, vrb, 'restock', 4);""" + keep("reassort", "(r->>'stock') || '/' || (r->>'left')")
        + note("reassort_illimite", "perform public.bar_item_action(e, coca, 'restock', 4)")
        + note("prix_barman", "perform public.bar_item_action(e, vrb, 'price', 6)")
        + note("article_barman", "perform public.bar_save_item(e, '{\"name\": \"Bière\", \"price_chf\": 3}'::jsonb)")
        + as_bot("victor") + note("invite_reste", "perform public.bar_item_action(e, vrb, 'remaining', 1)")
        + as_bot("olga") + """
      perform public.bar_save_settings(e, '{"staff_adjust_stock": false, "staff_unavailable": false, "staff_prices": true, "staff_items": true}'::jsonb);"""
        + as_bot("valentin")
        + note("reste_interdit", "perform public.bar_item_action(e, vrb, 'remaining', 1)")
        + note("indispo_interdit", "perform public.bar_item_action(e, vrb, 'unavailable', null)")
        + note("prix_permis", "perform public.bar_item_action(e, vrb, 'price', 6)")
        + note("article_permis", "perform public.bar_save_item(e, '{\"name\": \"Bière\", \"price_chf\": 3}'::jsonb)")
        + as_bot("olga") + note("orga_toujours", "perform public.bar_item_action(e, vrb, 'remaining', 3)")
        + as_postgres() + keep("journal", "(select string_agg(kind || ':' || coalesce(qty::text, '-'), ',' order by id) from public.event_bar_log "
                                          "where event_id = e and kind in ('stock_set', 'restock', 'price_set'))"))
    assert "reste=7/4/5" in out and "reassort=11/9" in out, out  # stock = servis (2) + reste ; dispo = reste − en attente (1)
    assert "reassort_illimite=" in out and "reassort_illimite=ok" not in out, out
    assert "prix_barman=forbidden" in out and "article_barman=forbidden" in out and "invite_reste=forbidden" in out, out
    assert "reste_interdit=forbidden" in out and "indispo_interdit=forbidden" in out, out
    assert "prix_permis=ok" in out and "article_permis=ok" in out and "orga_toujours=ok" in out, out
    assert "journal=stock_set:5,restock:4,price_set:-,stock_set:3" in out, out


def test_the_organizer_can_take_back_the_barman_undo():
    out = run(BAR + as_bot("ada") + """
      r := public.my_bar(e);
      perform public.bar_order(e, """ + lines("coca", 3) + """, r->>'pledge_text', (r->>'pledge_version')::int);""" + as_bot("valentin") + """
      srv := (public.bar_serve(e, ada, """ + lines("coca", 1) + """, gen_random_uuid()::text))->>'serve_id';"""
        + note("annuler_permis", "perform public.bar_undo_serve(e, srv)") + as_bot("olga") + """
      perform public.bar_save_settings(e, '{"staff_correct": false}'::jsonb);""" + as_bot("valentin") + """
      srv := (public.bar_serve(e, ada, """ + lines("coca", 1) + """, gen_random_uuid()::text))->>'serve_id';"""
        + note("annuler_retire", "perform public.bar_undo_serve(e, srv)")
        + note("annuler_attente_retire", "perform public.bar_cancel_units(e, ada, coca, 1)"))
    assert "annuler_permis=ok" in out and "annuler_retire=forbidden" in out and "annuler_attente_retire=forbidden" in out, out


def test_items_carry_a_category_a_short_detail_and_a_per_person_maximum():
    out = run(BAR + as_bot("olga") + """
      perform public.bar_save_item(e, jsonb_build_object('id', vrb, 'name', 'Vodka Red Bull', 'category', 'cocktails',
        'detail', '25 cl', 'max_per_person', 2));"""
        + note("categorie_inconnue", "perform public.bar_save_item(e, jsonb_build_object('id', vrb, 'name', 'Vodka Red Bull', 'category', 'jus'))")
        + note("precision_longue", "perform public.bar_save_item(e, jsonb_build_object('id', vrb, 'name', 'Vodka Red Bull', 'detail', repeat('x', 31)))")
        + as_bot("ada") + """
      r := public.my_bar(e);"""
        + keep("carte", "(select (x->>'category') || '/' || (x->>'detail') || '/' || (x->>'max_per_person') from jsonb_array_elements(r->'items') x where x->>'id' = vrb::text)")
        + keep("defaut", "(select x->>'category' from jsonb_array_elements(r->'items') x where x->>'id' = coca::text)"))
    assert "carte=cocktails/25 cl/2" in out and "defaut=autre" in out, out
    assert "categorie_inconnue=Catégorie" in out and "precision_longue=Précision" in out, out


def test_undoing_a_counter_service_cancels_the_glasses_instead_of_leaving_them_waiting():
    out = run(BAR + as_bot("olga") + """
      perform public.bar_save_settings(e, '{"counter_serve": true}'::jsonb);""" + pledge_of("ada") + f"""
      perform public.bar_pledge(e, pt, pv);
      perform public.bar_order(e, {lines('coca', 1)}, pt, pv);""" + as_bot("valentin") + f"""
      srv := (public.bar_serve(e, ada, {lines('coca', 1, 2)}, gen_random_uuid()::text))->>'serve_id';
      r := public.bar_undo_serve(e, srv);""" + keep("annule", "r->>'undone'") + keep("solde", "r->>'balance'") + as_postgres()
        + keep("etats", "(select string_agg(status || ':' || coalesce(cancel_reason, '-'), ',' order by status) from public.event_bar_units where event_id = e and user_id = ada)"))
    assert "annule=3" in out and "solde=0" in out, out
    assert "etats=cancelled:undone,cancelled:undone,pending:-" in out, out
