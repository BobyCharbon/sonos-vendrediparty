-- PROD, groupes_membres_seulement (20261106090000). À appliquer SEULEMENT après un « Ok prod » donné pour CETTE migration.
-- Un organisateur ne réserve un événement qu'aux groupes dont il fait partie (Vendredi Party compris) ; admin inchangé.
-- Prérequis : 20261025160000_vip_group_and_audiences (vip_group_id), déjà en prod. Rejouable. Tout ou rien.
begin;
-- Un organisateur ne réserve un événement qu'aux groupes dont il FAIT PARTIE (question de l'admin, 06.11.2026) :
--   - event_groups : un groupe n'est ajouté que par l'un de ses membres (avant : tout organisateur, n'importe quel
--     groupe, par l'API) ; invite_people (invitations v2) passe aussi par ici ;
--   - « Membres Vendredi Party » (visibility 'all' sans lien public) : seulement par un membre du groupe Vendredi Party.
-- Un admin (droit events.manage_all, public.is_admin) garde la main sur tous les groupes, comme avant. Les appels
-- sans compte (service, fonctions internes : auth.uid() vide) ne sont pas concernés. Seuls un AJOUT de groupe ou un
-- CHANGEMENT de visibilité sont vérifiés : les événements existants et leurs autres modifications ne changent pas.
-- Purement additive et rejouable.

create or replace function private.may_use_group(g uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select (select auth.uid()) is null or public.is_admin()
    or exists (select 1 from public.member_group_members m where m.group_id = g and m.user_id = (select auth.uid()));
$$;
revoke all on function private.may_use_group(uuid) from public, anon, authenticated;

create or replace function private.guard_event_group() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if not private.may_use_group(new.group_id) then
    raise exception 'forbidden: tu ne peux inviter que les groupes dont tu fais partie' using errcode = '42501';
  end if;
  return new;
end $$;
revoke all on function private.guard_event_group() from public, anon, authenticated;
drop trigger if exists guard_event_group on public.event_groups;
create trigger guard_event_group before insert or update of group_id on public.event_groups
  for each row execute function private.guard_event_group();

create or replace function private.guard_event_vip_visibility() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if new.visibility = 'all' and not coalesce(new.public_link, false)
     and (tg_op = 'INSERT' or old.visibility is distinct from new.visibility or old.public_link is distinct from new.public_link)
     and not private.may_use_group(private.vip_group_id()) then
    raise exception 'forbidden: seuls les membres de Vendredi Party peuvent lui réserver un événement. Choisis « Public » ou « Sur invitation ».'
      using errcode = '42501';
  end if;
  return new;
end $$;
revoke all on function private.guard_event_vip_visibility() from public, anon, authenticated;
drop trigger if exists guard_event_vip_visibility on public.events;
create trigger guard_event_vip_visibility before insert or update of visibility, public_link on public.events
  for each row execute function private.guard_event_vip_visibility();

insert into supabase_migrations.schema_migrations (version, name) values ('20261106090000', 'groupes_membres_seulement')
  on conflict (version) do nothing;
commit;

notify pgrst, 'reload schema';
