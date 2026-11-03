-- PROD, retour arrière de wallet_passes (20261103160000) : les billets déjà dans Cartes ne se mettent plus à jour
-- (le serveur répond « inconnu » à l'iPhone) ; ajouter un billet à Cartes échoue tant que le serveur garde la route
-- (à revenir en même temps que le code). Les jetons des pass et les appareils inscrits sont supprimés. Tout ou rien.
begin;

drop trigger if exists wallet_touch on public.event_tickets;
drop trigger if exists wallet_touch on public.rsvps;
drop trigger if exists wallet_touch_delete on public.rsvps;
drop trigger if exists wallet_touch on public.events;
drop trigger if exists wallet_touch on public.profiles;

drop function if exists public.wallet_pass_issue(uuid);
drop function if exists public.wallet_pass_by_token(text, text);
drop function if exists public.wallet_register(text, text, text, text);
drop function if exists public.wallet_unregister(text, text, text);
drop function if exists public.wallet_updated_serials(text, timestamptz);
drop function if exists public.wallet_push_targets(uuid, uuid);
drop function if exists private.wallet_payload(uuid, uuid);
drop function if exists private.wallet_pass_of(text, text);
drop function if exists private.wallet_touch_member();
drop function if exists private.wallet_touch_event();
drop function if exists private.wallet_touch_profile();

drop table if exists public.wallet_devices;
drop table if exists public.wallet_passes;

delete from supabase_migrations.schema_migrations where version = '20261103160000';
commit;

notify pgrst, 'reload schema';
