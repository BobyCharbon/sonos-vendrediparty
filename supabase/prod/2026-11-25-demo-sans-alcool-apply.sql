-- PROD, refus Apple 1.4.3 du 25.11.2026 : la démo de la revue (« Soirée démo Vendredi Party », compte Apple-test) ne
-- montre plus aucune boisson alcoolisée ni « commander au bar ». Le bar est caché dans l'app App Store (app/store_app.py) ;
-- ici les DONNÉES : la « Bière 🍺 33 cl 18+ » est retirée de la carte (désactivée, rien n'a été commandé), la description
-- de l'événement et les deux messages qui disaient « commander au bar » sont neutres. Aucune notification ne part
-- (description et messages modifiés sans passer par l'app ; notify_event_change ne réagit qu'au lieu, à la date, au statut).
-- Valeurs d'avant lues en prod le 25.11 (lecture seule) ; retour arrière : 2026-11-25-demo-sans-alcool-rollback.sql.
begin;
update public.event_bar_items set active = false
 where id = '6d2d51c6-9c0d-47aa-9bbd-5c3435a04e45' and event_id = '82ea0ad6-ac8b-43c2-b4ee-548afd21b243' and name = 'Bière';
update public.events
   set description = 'Événement de démonstration pour la revue Apple. Réponds « Présent », regarde qui vient et écris dans la discussion de la soirée. En co-organisateur, tu vois les invités et leurs réponses.'
 where id = '82ea0ad6-ac8b-43c2-b4ee-548afd21b243';
update public.messages set body = 'Pensez à répondre « Présent » ou « Absent » !'
 where id = '1204f0e4-bb62-43ca-97c2-5ffb5453a389' and event_id = '82ea0ad6-ac8b-43c2-b4ee-548afd21b243';
update public.group_messages set body = 'Réponds « Présent » sur l''événement, puis regarde qui vient et écris dans sa discussion.'
 where id = 'ddf88011-452f-4cba-a604-8307b9b0d398' and group_id = 'ab637a9d-1b7f-4110-bbc3-f24d591a4e79';
-- Contrôle : plus aucun article alcoolisé actif ni « bar » dans les textes de la démo (sinon tout est annulé).
do $$
begin
  if exists (select 1 from public.event_bar_items where event_id = '82ea0ad6-ac8b-43c2-b4ee-548afd21b243' and active
             and (category in ('bieres', 'vins', 'cocktails', 'shots') or age_min > 0))
     or exists (select 1 from public.events where id = '82ea0ad6-ac8b-43c2-b4ee-548afd21b243' and description ~* 'bar')
     or exists (select 1 from public.messages where event_id = '82ea0ad6-ac8b-43c2-b4ee-548afd21b243' and deleted_at is null and body ~* '\mbar\M')
     or exists (select 1 from public.group_messages where group_id = 'ab637a9d-1b7f-4110-bbc3-f24d591a4e79' and body ~* '\mbar\M') then
    raise exception 'Démo : il reste un article alcoolisé ou un texte sur le bar.';
  end if;
end $$;
insert into supabase_migrations.schema_migrations (version, name) values ('20261125090000', 'demo_sans_alcool')
  on conflict do nothing;
commit;
