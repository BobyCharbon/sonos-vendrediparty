"""Origine des inscriptions (avis 01da90202166, 22.11.2026, migration 20261122133000), sur la base de TEST, bots et comptes
neufs créés dans des transactions ANNULÉES (rien ne reste) :
- une inscription par le lien d'invitation d'un événement note l'événement et la personne dont c'est le lien ; la
  plateforme dite à la connexion reste ; un lien l'emporte sur « direct » ;
- « Partager » (événement public) note l'événement ; un compte ancien ne gagne jamais de ligne (« Inconnu ») ;
- le lien personnel Party note qui ;
- sans le droit members.signup_source : refusé ; avec : la phrase de la fiche et la métrique."""
from tests.supabase_live.test_annonces_groupe_live import as_bot, as_postgres, olga_event, run
from tests.supabase_live.test_member_admin_live import pytestmark  # noqa: F401


def new_account(var: str, name: str) -> str:
    """Un vrai compte neuf (profil créé par la base), profil complet, CGU acceptées."""
    return as_postgres() + f"""
      {var} := gen_random_uuid();
      insert into auth.users (id, phone, aud, role)
        values ({var}, '41799991' || lpad((random() * 999)::int::text, 3, '0'), 'authenticated', 'authenticated');
      update public.profiles set first_name = '{name}', last_name = 'Recette', display_name = '{name} origine' where id = {var};
      insert into public.terms_acceptances (user_id, version)
        values ({var}, (select terms_version from private.moderation_settings where id = 1)) on conflict do nothing;"""


def as_user(var: str) -> str:
    return (f"execute 'reset role'; perform set_config('request.jwt.claims', "
            f"json_build_object('sub', {var}, 'role', 'authenticated')::text, true); execute 'set local role authenticated';")


def source_of(var: str) -> str:
    return f"(select source || '/' || coalesce(platform, '-') from private.signup_sources where user_id = {var})"


def test_an_event_invite_link_is_noted_with_its_event_and_inviter():
    out = run(olga_event(announce=False) + as_bot("olga") + """
      r := public.create_event_invite(e, 0);""" + new_account("a", "Nina") + as_user("a") + """
      perform public.note_signup('web', null);""" + as_postgres() + f"""
      n := (select count(*) from private.signup_sources where user_id = a and source = 'direct');""" + as_user("a") + """
      perform public.accept_invite((r->>'token')::uuid, 'yes');""" + as_postgres() + f"""
      raise exception 'résultat: avant=% apres=% bon_evenement=% inviteur=%', n, {source_of('a')},
        (select event_id = e from private.signup_sources where user_id = a),
        (select inviter = olga from private.signup_sources where user_id = a);""")
    assert "résultat: avant=1 apres=event_link/web bon_evenement=t inviteur=t" in out, out


def test_public_share_then_an_old_account_never_gets_a_line():
    out = run(olga_event(announce=False, public=True) + new_account("a", "Lou") + as_user("a") + """
      perform public.note_signup('ios', e);
      perform public.note_signup('web', null);""" + as_bot("olga") + """
      perform public.note_signup('web', null);""" + as_postgres() + f"""
      raise exception 'résultat: partage=% ancien=%', {source_of('a')},
        (select count(*) from private.signup_sources where user_id = olga);""")
    assert "résultat: partage=event_share/ios ancien=0" in out, out


def test_the_personal_party_link_notes_who():
    out = run(as_bot("ada") + """
      r := public.my_app_invite(false);""" + new_account("a", "Zoé") + as_user("a") + """
      perform public.claim_app_invite((r->>'token')::uuid);""" + as_postgres() + f"""
      raise exception 'résultat: %/%', {source_of('a')},
        (select inviter = ada from private.signup_sources where user_id = a);""")
    assert "résultat: app_invite/-/t" in out, out


def test_without_the_right_it_is_refused_with_it_the_line_and_the_metric():
    out = run(olga_event(announce=False) + as_bot("olga") + """
      r := public.create_event_invite(e, 0);""" + new_account("a", "Max") + as_user("a") + """
      perform public.note_signup('ios', null);
      perform public.accept_invite((r->>'token')::uuid, 'yes');""" + as_postgres() + """
      delete from public.role_permissions where perm = 'members.signup_source'
        and role = (select role from public.profiles where id = victor);""" + as_bot("victor") + """
      begin
        perform public.admin_signup_sources(a);
        n := 0;
      exception when insufficient_privilege then n := 1;
      end;
      begin
        perform public.admin_signup_stats();
        m := 0;
      exception when insufficient_privilege then m := 1;
      end;""" + as_postgres() + """
      insert into public.role_permissions (role, perm)
        values ((select role from public.profiles where id = victor), 'members.signup_source') on conflict do nothing;""" + as_bot("victor") + """
      raise exception 'résultat: refus=%/% ligne=% metrique=% inconnu=%', n, m,
        (select x->>'line' from jsonb_array_elements(public.admin_signup_sources(a)) x),
        (select (x->>'total')::int >= 1 and (x->>'last30')::int >= 1
           from jsonb_array_elements(public.admin_signup_stats()->'sources') x where x->>'source' = 'event_link'),
        (select x->>'source' from jsonb_array_elements(public.admin_signup_sources(olga)) x);""")
    assert "résultat: refus=1/1 ligne=Inscrit via le lien d'invitation de « Test annonce bots » (lien de " in out, out
    assert " · app iPhone · " in out and "metrique=t inconnu=unknown" in out, out
