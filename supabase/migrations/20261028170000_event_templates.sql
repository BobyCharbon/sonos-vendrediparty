-- Modèles d'événement (demande de l'admin du 28 octobre 2026) : les organisateurs et admins (droit
-- events.publish_direct) enregistrent un événement type et repartent de lui. Un modèle est perso (visible par son
-- auteur seulement) ou d'équipe (visible par tous les organisateurs et admins).
-- Suppression : chacun ses propres modèles ; un admin ou co-admin (events.manage_all) peut supprimer n'importe lequel.
-- Contenu (data) : les réglages du formulaire sans dates ni personnes (web/events/src/lib/templates.ts).
-- Purement additif et rejouable.

create table if not exists public.event_templates (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null default auth.uid() references public.profiles (id) on delete cascade,
  name text not null check (char_length(btrim(name)) between 1 and 60),
  shared boolean not null default false,
  data jsonb not null default '{}'::jsonb check (jsonb_typeof(data) = 'object' and pg_column_size(data) < 65536),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists event_templates_owner_idx on public.event_templates (owner_id);

alter table public.event_templates enable row level security;

drop policy if exists event_templates_select on public.event_templates;
create policy event_templates_select on public.event_templates for select to authenticated
  using (public.has_perm('events.publish_direct') and (owner_id = auth.uid() or shared));

drop policy if exists event_templates_insert on public.event_templates;
create policy event_templates_insert on public.event_templates for insert to authenticated
  with check (public.has_perm('events.publish_direct') and owner_id = auth.uid());

drop policy if exists event_templates_update on public.event_templates;
create policy event_templates_update on public.event_templates for update to authenticated
  using (public.has_perm('events.publish_direct') and owner_id = auth.uid())
  with check (owner_id = auth.uid());

drop policy if exists event_templates_delete on public.event_templates;
create policy event_templates_delete on public.event_templates for delete to authenticated
  using (owner_id = auth.uid() or public.has_perm('events.manage_all'));

-- Une mise à jour ne change jamais l'auteur ni la date de création ; updated_at suit.
create or replace function private.guard_event_template() returns trigger
language plpgsql set search_path = '' as $$
begin
  new.owner_id := old.owner_id;
  new.created_at := old.created_at;
  new.updated_at := now();
  new.name := btrim(new.name);
  return new;
end $$;
drop trigger if exists guard_event_template on public.event_templates;
create trigger guard_event_template before update on public.event_templates
  for each row execute function private.guard_event_template();

revoke all on public.event_templates from anon;
grant select, insert, update, delete on public.event_templates to authenticated;
