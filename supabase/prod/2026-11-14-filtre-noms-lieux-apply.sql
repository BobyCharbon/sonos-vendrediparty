-- PROD, filtre_noms_lieux (20261114123000). À appliquer SEULEMENT après un « Ok prod » donné pour CETTE migration.
-- Rejouable. Tout ou rien. Aucune donnée modifiée : trois déclencheurs qui filtrent les textes nouveaux ou modifiés
-- (prénom et nom du profil, nom d'un lien d'invitation, nom du lieu d'un événement). Prérequis : 2026-11-04-moderation.
begin;
-- Exigence Apple 1.2 (campagne de tests du 14.11.2026) : trois textes libres montrés aux autres passaient encore sans le
-- filtre commun (private.moderation_verdict, migration 20261104200000_moderation.sql) :
--   · le prénom et le nom du profil (fiche d'un membre, listes de l'admin, « Nouveau compte ») : comme le surnom, refusés
--     s'ils contiennent une insulte, un propos haineux ou sexuel, un lien ou un numéro ;
--   · le nom d'un lien d'invitation (« Plusieurs », « Pour Julie »… vu par l'organisateur dans la carte Invités, partage
--     commun du 11.11) : même règle qu'un nom ;
--   · le nom du lieu d'un événement : même règle que le titre (insulte d'un mot masquée, le reste refusé).
-- Seul un texte nouveau ou modifié est contrôlé : rien de ce qui existe n'est réécrit. Le système (cron, service, sans
-- session) n'y passe pas. Purement additive et rejouable (create or replace, drop trigger if exists).

create or replace function private.moderate_profile_identity() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null then return new; end if;
  if btrim(coalesce(new.first_name, '')) <> '' and (tg_op = 'INSERT' or new.first_name is distinct from old.first_name) then
    new.first_name := private.moderate_text(new.first_name, 'name');
  end if;
  if btrim(coalesce(new.last_name, '')) <> '' and (tg_op = 'INSERT' or new.last_name is distinct from old.last_name) then
    new.last_name := private.moderate_text(new.last_name, 'name');
  end if;
  return new;
end $$;
revoke all on function private.moderate_profile_identity() from public, anon, authenticated;
drop trigger if exists profiles_identity_moderation on public.profiles;
create trigger profiles_identity_moderation before insert or update of first_name, last_name on public.profiles
  for each row execute function private.moderate_profile_identity();

create or replace function private.moderate_invite_label() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null then return new; end if;
  if btrim(coalesce(new.label, '')) <> '' and (tg_op = 'INSERT' or new.label is distinct from old.label) then
    new.label := private.moderate_text(new.label, 'name');
  end if;
  return new;
end $$;
revoke all on function private.moderate_invite_label() from public, anon, authenticated;
drop trigger if exists invite_links_label_moderation on private.invite_links;
create trigger invite_links_label_moderation before insert or update of label on private.invite_links
  for each row execute function private.moderate_invite_label();

create or replace function private.moderate_event_place() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null then return new; end if;
  if btrim(coalesce(new.location_name, '')) <> ''
     and (tg_op = 'INSERT' or new.location_name is distinct from old.location_name) then
    new.location_name := private.event_text_verdict(new.location_name, 'le nom du lieu');
  end if;
  return new;
end $$;
revoke all on function private.moderate_event_place() from public, anon, authenticated;
drop trigger if exists events_place_moderation on public.events;
create trigger events_place_moderation before insert or update of location_name on public.events
  for each row execute function private.moderate_event_place();

insert into supabase_migrations.schema_migrations (version, name) values ('20261114123000', 'filtre_noms_lieux') on conflict do nothing;
commit;
