"""« Chacun est libre de faire ce qu'il veut avec son groupe » (décision de l'admin du 22.11.2026, migration
20261122150000), sur la VRAIE base de TEST (jamais la prod), avec les comptes des BOTS, validation du site allumée
(group_settings.require_approval, comme en prod) :
- un Guest crée son groupe puis un événement réservé à ce groupe : publié, sans validation du site (formulaire : brouillon
  puis statut ; insertion directe « en attente » puis groupe ajouté : publié aussi) ;
- un simple membre dans un groupe « Événements à valider » : l'événement est en ligne, le groupe en attente
  (event_groups.status), validé par le créateur du groupe, jamais par le site ;
- l'événement public d'un Guest attend toujours ; un événement de groupe publié qui devient public repasse « en attente » ;
- un Organisateur (rôle du site) voit la proposition, la refuse (raison gardée) ou l'accepte ;
- un admin du site voit un groupe privé de Discussions et ses membres, jamais ses messages.
Tout se passe dans des transactions ANNULÉES : rien ne reste."""
import json

from tests.supabase_live.test_groups_members_only_live import sql_test
from tests.supabase_live.test_member_admin_live import pytestmark  # noqa: F401

BOTS = {"ada": "41790000101", "olga": "41790000103", "victor": "41790000105", "gus": "41790000112", "gina": "41790000113"}

DECLARE = "e uuid; e2 uuid; g uuid; r jsonb; n int; m int; st text; " + " ".join(f"{k} uuid;" for k in BOTS)
SETUP = "\n".join(f"select id into {k} from public.profiles where phone = '{p}';" for k, p in BOTS.items()) + """
update public.group_settings set require_approval = true;
update public.profiles set role = 'guest' where id in (gus, gina);
-- Droits de la prod (22.11) : un Guest crée des événements ; un Organisateur ne valide que par cette migration.
insert into public.role_permissions (role, perm) values ('guest', 'events.create') on conflict do nothing;
-- CGU exigées (comme en prod) : les bots les ont acceptées (annulé avec le reste de la transaction).
insert into public.terms_acceptances (user_id, version)
  select p.id, (select terms_version from private.moderation_settings where id = 1) from public.profiles p
  where p.phone in (""" + ", ".join(f"'{p}'" for p in BOTS.values()) + """) on conflict do nothing;"""


def as_bot(name: str) -> str:
    return (f"execute 'reset role'; perform set_config('request.jwt.claims', "
            f"json_build_object('sub', {name}, 'role', 'authenticated')::text, true); execute 'set local role authenticated';")


def as_postgres() -> str:
    return "execute 'reset role'; perform set_config('request.jwt.claims', '', true);"


def run(body: str) -> str:
    rows = sql_test(f"""
    begin;
    do $$ declare {DECLARE} begin
      {SETUP}
      {body}
    end $$;
    rollback;""")
    return json.dumps(rows, ensure_ascii=False)


def gus_group(need_approval: bool = False) -> str:
    """Gus (Guest) crée son groupe ; Gina (Guest) en est simple membre."""
    return as_bot("gus") + f"""
      insert into public.member_groups (name, emoji, color, created_by) values ('Test groupes libres', '⚽', 'mint', gus)
        returning id into g;
      update public.member_groups set events_need_approval = {str(need_approval).lower()} where id = g;""" + as_postgres() + """
      insert into public.member_group_members (group_id, user_id) values (g, gus), (g, gina) on conflict do nothing;"""


def event_by(who: str, public: bool = False, group: bool = True, var: str = "e") -> str:
    """Comme le formulaire : brouillon, groupe, puis « Publier »."""
    return as_bot(who) + f"""
      insert into public.events (title, status, visibility, public_link, notify_on_publish, starts_at)
        values ('Test groupes libres', 'draft', '{'all' if public else 'invited'}', {str(public).lower()}, false,
                now() + interval '30 days') returning id into {var};
      {f"insert into public.event_groups (event_id, group_id) values ({var}, g);" if group else ''}
      update public.events set status = 'published' where id = {var};"""


def test_a_new_guest_publishes_in_his_own_group_without_the_site():
    out = run(gus_group() + event_by("gus") + as_postgres() + """
      -- Insertion directe « en attente » (API, anciennes apps), puis le groupe : publiée aussi.
      """ + as_bot("gus") + """
      insert into public.events (title, status, visibility, public_link, notify_on_publish, starts_at)
        values ('Test groupes libres 2', 'pending', 'invited', false, false, now() + interval '30 days') returning id into e2;
      insert into public.event_groups (event_id, group_id) values (e2, g);""" + as_bot("gina") + """
      select count(*) into n from public.events where id = e;""" + as_postgres() + """
      raise exception 'résultat: statut=% direct=% groupe=% vu_par_gina=% propositions=%',
        (select status from public.events where id = e), (select status from public.events where id = e2),
        (select status from public.event_groups where event_id = e), n,
        (select count(*) from public.notifications where kind = 'proposal' and event_id in (e, e2));""")
    assert "résultat: statut=published direct=published groupe=approved vu_par_gina=1 propositions=0" in out, out


def test_the_group_rule_decides_for_a_simple_member_never_the_site():
    out = run(gus_group(need_approval=True) + event_by("gina") + as_bot("victor") + """
      select count(*) into n from public.events where id = e;""" + as_postgres() + """
      st := (select status::text || '/' || (select status from public.event_groups where event_id = e) from public.events where id = e);
      """ + as_bot("gus") + """
      r := public.answer_group_event(e, g, true);""" + as_postgres() + """
      raise exception 'résultat: avant=% apres=% demande_gus=% propositions=%', st,
        (select status from public.event_groups where event_id = e),
        (select count(*) from public.notifications where kind = 'group_event_request' and user_id = gus),
        (select count(*) from public.notifications where kind = 'proposal' and event_id = e);""")
    assert "résultat: avant=published/pending apres=approved demande_gus=1 propositions=0" in out, out


def test_a_guest_public_event_still_waits_and_a_group_event_turned_public_waits_again():
    """Pas de faille : publié dans son groupe puis rendu public = validation du site (Membre : peut modifier un publié,
    mais ne publie pas sans validation). Un Guest (sans « modifier un événement publié ») ne le modifie pas du tout."""
    out = run(gus_group() + as_postgres() + """
      insert into public.member_group_members (group_id, user_id) values (g, victor) on conflict do nothing;"""
              + event_by("gus", public=True, group=False) + event_by("victor", var="e2") + """
      st := (select status::text from public.events where id = e2);""" + as_bot("victor") + """
      update public.events set visibility = 'all', public_link = true where id = e2;""" + event_by("gus", var="e2") + """
      begin update public.events set visibility = 'all', public_link = true where id = e2; r := '{"guest": "changé"}';
        exception when others then r := '{"guest": "refusé"}'; end;""" + as_postgres() + """
      raise exception 'résultat: public=% groupe=% devenu_public=% guest=%',
        (select status from public.events where id = e), st,
        (select status from public.events e3 where e3.created_by = victor and e3.title = 'Test groupes libres'), r->>'guest';""")
    assert "résultat: public=pending groupe=published devenu_public=pending guest=refusé" in out, out


def test_membres_vendredi_party_and_invitation_only_are_unchanged():
    out = run(gus_group() + event_by("gus", group=False) + as_postgres() + """
      raise exception 'résultat: sur_invitation=%', (select status from public.events where id = e);""")
    assert "résultat: sur_invitation=pending" in out, out


def test_a_site_organizer_sees_rejects_and_approves_proposals():
    out = run(gus_group() + event_by("gus", public=True, group=False) + event_by("gus", public=True, group=False, var="e2")
              + as_bot("olga") + """
      select count(*) into n from public.events where id in (e, e2);
      perform public.reject_event(e, 'Pas cette fois');
      perform public.approve_event(e2);""" + as_postgres() + """
      raise exception 'résultat: vus=% refus=%/% accord=%/%', n,
        (select status from public.events where id = e), (select rejection_reason from public.events where id = e),
        (select status from public.events where id = e2), (select approved_by = olga from public.events where id = e2);""")
    assert "résultat: vus=2 refus=rejected/Pas cette fois accord=published/t" in out, out


def test_a_site_admin_sees_a_private_group_and_its_members_never_its_messages():
    out = run(as_bot("gus") + """
      r := public.create_chat_group('Test groupe privé', '⚽', 'mint', array[gina, victor]);
      g := (r->>'group')::uuid;""" + as_postgres() + """
      insert into public.member_group_members (group_id, user_id) values (g, gus), (g, gina), (g, victor) on conflict do nothing;""" + as_bot("gus") + """
      insert into public.group_messages (group_id, user_id, body) values (g, gus, 'Secret entre nous');""" + as_bot("ada") + """
      select count(*) into n from public.member_groups where id = g and private_chat;
      select count(*) into m from public.member_group_members where group_id = g;
      raise exception 'résultat: groupe=% membres=% messages=% lit=%', n, m,
        (select count(*) from public.group_messages where group_id = g), private.reads_group(g);""")
    assert "résultat: groupe=1 membres=3 messages=0 lit=f" in out, out
