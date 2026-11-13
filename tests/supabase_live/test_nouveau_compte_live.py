"""« Nouveau compte » (avis 662065a54b22 de l'admin, 12.11.2026), sur la base de TEST, tout annulé : quand un profil devient
complet (prénom, nom, surnom), ceux qui valident les membres (members.approve) sont prévenus, une seule fois ; leur
interrupteur « member_signups » coupe la notification sur tous les canaux."""
from tests.supabase_live.test_annonces_groupe_live import as_postgres, run
from tests.supabase_live.test_member_admin_live import pytestmark  # noqa: F401

SIGNUP = as_postgres() + """
  a := gen_random_uuid();  -- une vraie inscription : compte créé (profil vide), puis « Faisons connaissance »
  insert into auth.users (id, phone, aud, role) values (a, '41799990' || lpad((random() * 999)::int::text, 3, '0'), 'authenticated', 'authenticated');
  delete from public.notifications where kind = 'member_signup';
  m := (select count(*) from public.notifications where kind = 'member_signup');
  update public.profiles set first_name = 'Nina', last_name = 'Test', display_name = 'Nina recette' where id = a;"""


def test_approvers_are_told_once_when_a_profile_becomes_complete():
    out = run(SIGNUP + """
      n := m;  -- avant : aucune
      m := (select count(*) from public.notifications where kind = 'member_signup');
      update public.profiles set display_name = 'Nina R' where id = a;  -- déjà complet : rien de plus
      raise exception 'résultat: avant=% prevenus=% tous_valideurs=% elle=% apres=% texte=%', n, case when m > 0 then 'oui' else 'non' end,
        not exists (select 1 from public.notifications x where x.kind = 'member_signup' and not private.user_has(x.user_id, 'members.approve')),
        (select count(*) from public.notifications where kind = 'member_signup' and user_id = a),
        (select count(*) from public.notifications where kind = 'member_signup') = m,
        (select body like '%vient de créer son compte.' from public.notifications where kind = 'member_signup' limit 1);""")
    assert "résultat: avant=0 prevenus=oui tous_valideurs=t elle=0 apres=t texte=t" in out, out


def test_the_switch_turns_it_off_everywhere():
    out = run(SIGNUP + """
      select x.user_id into e from public.notifications x where x.kind = 'member_signup' limit 1;
      insert into public.notification_prefs (user_id, member_signups) values (e, false)
        on conflict (user_id) do update set member_signups = false;
      raise exception 'résultat: coupe=% allume_ailleurs=%',
        (select private.web_push_allowed(x) from public.notifications x where x.kind = 'member_signup' and x.user_id = e limit 1),
        coalesce((select bool_and(private.web_push_allowed(x)) from public.notifications x
                  where x.kind = 'member_signup' and x.user_id <> e and not exists (
                    select 1 from public.notification_prefs p where p.user_id = x.user_id and p.member_signups = false)), true);""")
    assert "résultat: coupe=f allume_ailleurs=t" in out, out
