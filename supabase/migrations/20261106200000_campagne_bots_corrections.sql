-- Corrections de la campagne des bots (06.11.2026, base TEST réglée comme la prod) et décision de l'admin du même jour.
-- 1. Événement PUBLIC (lien public) : JAMAIS d'annonce de publication (« Nouvel événement », invitations du groupe),
--    sinon c'est du spam. notify_on_publish est forcé à false dès qu'un événement public est (ou devient) publié,
--    quel que soit le chemin (formulaire, assistant IA, API) ; un événement de groupe passé public après coup aussi.
--    Un BROUILLON public garde son réglage : passé à un groupe avant publication (étape 2 de l'assistant IA), il
--    prévient bien son groupe. Les autres notifications (changement de date, annulation, rappels, invitation ajoutée
--    une à une) ne changent pas.
-- 2. Le créateur d'un événement ANNULÉ peut le supprimer (avant : brouillon, proposition, refusé seulement). Le rouvrir
--    reste réservé à events.manage_all (guard_event, 20261105131500).
-- 3. Carte d'invitation sans compte et relance : le surnom COMPLET de qui invite (« Bot Olga », plus « Bot »).
--    Les prénoms de « qui vient déjà » restent réduits au premier mot (lus sans compte).
-- Purement additive et rejouable : create or replace, drop … if exists, fonctions complétées en place une seule fois.

-- 1. -----------------------------------------------------------------------------------------------------------------
create or replace function private.public_event_is_silent() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if new.public_link and new.status = 'published' then
    new.notify_on_publish := false;
  end if;
  return new;
end $$;
revoke all on function private.public_event_is_silent() from public, anon, authenticated;
-- Nommé après events_guard (qui fixe le statut) : PostgreSQL lance les déclencheurs BEFORE par ordre alphabétique.
drop trigger if exists events_public_silent on public.events;
create trigger events_public_silent before insert or update on public.events
  for each row execute function private.public_event_is_silent();

-- 2. -----------------------------------------------------------------------------------------------------------------
drop policy if exists "supprimer événement" on public.events;
create policy "supprimer événement" on public.events for delete
  using (public.is_admin() or (created_by = (select auth.uid()) and status in ('draft', 'pending', 'rejected', 'cancelled')));

-- 3. -----------------------------------------------------------------------------------------------------------------
do $$
declare
  def text := pg_get_functiondef('public.invite_preview(uuid, boolean)'::regprocedure);
  anchor text := '''inviter'', private.first_word(who)';
begin
  if position(anchor in def) > 0 then
    execute replace(def, anchor, '''inviter'', nullif(btrim(coalesce(who, '''')), '''')');
  end if;
end $$;

do $$
declare
  def text := pg_get_functiondef('public.nudge_invitees(uuid, uuid[])'::regprocedure);
  anchor text := 'coalesce(private.first_word(host), ''L''''organisateur'')';
begin
  if position(anchor in def) > 0 then
    execute replace(def, anchor, 'coalesce(nullif(btrim(coalesce(host, '''')), ''''), ''L''''organisateur'')');
  end if;
end $$;

notify pgrst, 'reload schema';
