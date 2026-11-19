-- PROD, retour arrière de paiement_ouvert_notification (20261117135000) : les fonctions remplacées retrouvent leur texte de prod du 19.11 (lu
-- avant la mise en prod), les nouveaux déclencheurs sont retirés. Tables, colonnes et fonctions nouvelles restent
-- (sans effet). Tout ou rien.
begin;
drop trigger if exists events_payment_open_notify on public.events;

delete from supabase_migrations.schema_migrations where version = '20261117135000';
commit;
