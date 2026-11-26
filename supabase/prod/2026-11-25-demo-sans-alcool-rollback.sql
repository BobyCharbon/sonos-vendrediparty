-- Retour arrière de 2026-11-25-demo-sans-alcool-apply.sql : remet la Bière à la carte, l'ancienne description et les
-- deux anciens messages (valeurs lues en prod le 25.11.2026).
begin;
update public.event_bar_items set active = true
 where id = '6d2d51c6-9c0d-47aa-9bbd-5c3435a04e45' and event_id = '82ea0ad6-ac8b-43c2-b4ee-548afd21b243';
update public.events
   set description = 'Événement de démonstration pour la revue Apple. Réponds « Présent » pour commander au bar de la soirée ; en co-organisateur, ouvre « Gérer le bar » pour voir les articles, le direct et le récapitulatif.'
 where id = '82ea0ad6-ac8b-43c2-b4ee-548afd21b243';
update public.messages set body = 'Pensez à répondre « Présent » pour commander au bar.'
 where id = '1204f0e4-bb62-43ca-97c2-5ffb5453a389';
update public.group_messages set body = 'Le bar est ouvert : réponds « Présent » sur l''événement puis commande depuis ton téléphone.'
 where id = 'ddf88011-452f-4cba-a604-8307b9b0d398';
delete from supabase_migrations.schema_migrations where version = '20261125090000';
commit;
