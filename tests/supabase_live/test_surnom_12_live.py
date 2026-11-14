"""Surnom de 12 caractères au plus (avis bda77087d7dc de l'admin, 14.11.2026), sur la base de TEST, tout annulé :
la base refuse un surnom nouveau ou modifié plus long ; un surnom plus long d'avant reste, et la personne peut encore
changer sa photo ou son nom sans y toucher."""
from tests.supabase_live.test_annonces_groupe_live import as_postgres, run
from tests.supabase_live.test_member_admin_live import pytestmark  # noqa: F401

NEW_ACCOUNT = as_postgres() + """
  a := gen_random_uuid();
  insert into auth.users (id, phone, aud, role) values (a, '41799991' || lpad((random() * 999)::int::text, 3, '0'), 'authenticated', 'authenticated');"""


def test_a_nickname_of_more_than_twelve_characters_is_refused():
    out = run(NEW_ACCOUNT + """
      update public.profiles set first_name = 'Nina', last_name = 'Test', display_name = 'Nina recette' where id = a;  -- 12
      begin
        update public.profiles set display_name = 'Nina recettes' where id = a;  -- 13
        raise exception 'résultat: treize accepté';
      exception when check_violation then
        raise exception 'résultat: douze=% treize=refusé message=%',
          (select display_name from public.profiles where id = a), sqlerrm;
      end;""")
    assert "résultat: douze=Nina recette treize=refusé message=nickname_too_long: le surnom est limité à 12 caractères" in out, out


def test_an_older_long_nickname_stays_until_it_is_changed():
    out = run(NEW_ACCOUNT + """
      alter table public.profiles disable trigger profiles_guard;  -- un surnom d'avant la règle (16 caractères)
      update public.profiles set first_name = 'Nina', last_name = 'Test', display_name = 'Nina la recette!' where id = a;
      alter table public.profiles enable trigger profiles_guard;
      update public.profiles set last_name = 'Testeuse' where id = a;  -- nom changé, surnom intact : accepté
      begin
        update public.profiles set display_name = 'Nina la recette!!' where id = a;
        raise exception 'résultat: modifié accepté';
      exception when check_violation then
        raise exception 'résultat: garde=% nom=% modifie=refusé',
          (select display_name from public.profiles where id = a), (select last_name from public.profiles where id = a);
      end;""")
    assert "résultat: garde=Nina la recette! nom=Testeuse modifie=refusé" in out, out
