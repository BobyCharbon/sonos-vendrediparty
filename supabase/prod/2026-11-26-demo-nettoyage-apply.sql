-- PROD, nettoyage de la démo avant le renvoi à Apple (contrôle du 26.11.2026, rapport controle-prod-26-11 : R2 et mineurs).
-- 1. « Soirée démo Vendredi Party » n'a plus de bar : event_bars et, en cascade, ses 3 articles (Bière désactivée, Limonade,
--    Thé froid) et ses 5 lignes de journal ; aucune commande, aucun engagement, aucun remboursement, aucun barman, aucun
--    pass Wallet (lu en prod le 26.11). Le billet Wallet ne montre de toute façon plus le bar (app/wallet_tickets.py).
-- 2. Apple-test quitte le vrai Pot commun « Cobalt Project Paintball » (12 vraies personnes) comme « Quitter » de l'app
--    (tc_leave : left_at), sans toucher à sa réponse : il y est déjà « Absent » (status no depuis le 19.11), et le pot
--    n'ajoute que les « Présent » qui n'y sont pas encore (private.tc_event_sync) : sa ligne gardée l'en empêche. Aucune
--    dépense ni part à son nom. Le pot ne lui est plus listé (tc_list), les autres le voient « parti ».
-- 3. La cloche d'Apple-test : les 2 « Événement annulé » et le « Événement rétabli » de la démo sont effacés (jamais
--    envoyés : skipped, aucune livraison).
-- Rien n'est notifié. Retour arrière : 2026-11-26-demo-nettoyage-rollback.sql (lignes d'avant recopiées).
begin;
do $$
begin
  if (select count(*) from public.event_bar_units where event_id = '82ea0ad6-ac8b-43c2-b4ee-548afd21b243') + (select count(*) from public.event_bar_pledges where event_id = '82ea0ad6-ac8b-43c2-b4ee-548afd21b243')
     + (select count(*) from public.event_bar_refunds where event_id = '82ea0ad6-ac8b-43c2-b4ee-548afd21b243') + (select count(*) from public.event_bar_serves where event_id = '82ea0ad6-ac8b-43c2-b4ee-548afd21b243')
     + (select count(*) from public.event_bar_staff where event_id = '82ea0ad6-ac8b-43c2-b4ee-548afd21b243') > 0
     or (select count(*) from public.event_bar_items where event_id = '82ea0ad6-ac8b-43c2-b4ee-548afd21b243') <> 3
     or (select count(*) from public.event_bar_log where event_id = '82ea0ad6-ac8b-43c2-b4ee-548afd21b243') <> 5 then
    raise exception 'Démo : le bar a changé depuis la lecture du 26.11, rien n''est fait (relire et refaire ce fichier).';
  end if;
  if exists (select 1 from public.tc_expenses where paid_by = '17277a87-6f00-42cb-9ad1-0c39a546ff41') or exists (select 1 from public.tc_shares where member_id = '17277a87-6f00-42cb-9ad1-0c39a546ff41')
     or exists (select 1 from public.rsvps where event_id = '81ea6cbd-4c95-4af0-98d3-68fc25c8b27d' and user_id = '49d9777e-82a5-49d2-b9c3-6f07f0d91fdd' and status = 'yes') then
    raise exception 'Pot du Paintball : Apple-test a une dépense, une part ou est « Présent » depuis le 26.11, rien n''est fait.';
  end if;
end $$;
delete from public.event_bars where event_id = '82ea0ad6-ac8b-43c2-b4ee-548afd21b243';
update public.tc_members set left_at = now()
 where id = '17277a87-6f00-42cb-9ad1-0c39a546ff41' and group_id = '5cc8878c-b69d-46ec-9dcd-2d06df559c33' and user_id = '49d9777e-82a5-49d2-b9c3-6f07f0d91fdd' and left_at is null;
delete from public.notifications where user_id = '49d9777e-82a5-49d2-b9c3-6f07f0d91fdd' and id in ('e8e3bdde-d74b-47f4-a0e8-2529710cf44e', '218365ab-e710-4287-89a6-cd5897ec8d56', '2f38b100-4b64-4bed-aa89-a4904dd5e99e');
do $$
begin
  if exists (select 1 from public.event_bars where event_id = '82ea0ad6-ac8b-43c2-b4ee-548afd21b243')
     or exists (select 1 from public.tc_members where group_id = '5cc8878c-b69d-46ec-9dcd-2d06df559c33' and user_id = '49d9777e-82a5-49d2-b9c3-6f07f0d91fdd' and left_at is null)
     or exists (select 1 from public.notifications where user_id = '49d9777e-82a5-49d2-b9c3-6f07f0d91fdd' and kind = 'event_changed'
                and title in ('Événement annulé', 'Événement rétabli') and body like '%Soirée démo Vendredi Party%') then
    raise exception 'Démo : le nettoyage n''est pas complet, tout est annulé.';
  end if;
end $$;
insert into supabase_migrations.schema_migrations (version, name) values ('20261126110000', 'demo_nettoyage') on conflict do nothing;
commit;
