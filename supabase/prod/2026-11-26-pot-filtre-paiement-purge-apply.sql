-- PROD, contrôle Apple du 26.11.2026, tour 3 (20261126160000) : profil de paiement du Pot commun filtré (titulaire, note),
-- moyens de paiement de l'organisateur dans event_pay_info seulement en « On me paie », photos et vocaux de la discussion
-- d'un événement effacés à 90 jours. Préparé le 26.11, PAS appliqué. Appliqué deux fois et testé sur la base de TEST le
-- 26.11 (tests/supabase_live/test_pot_filtre_paiement_purge_live.py, test_paiement_mode_live.py,
-- test_pot_paiement_geste_live.py). Ancres vérifiées en prod (lecture seule, 26.11) : moderate_tc_text (branche
-- tc_expenses), event_pay_info (ligne iban / holder / links / note), expire_chat_photos (total gone + gone_direct) ;
-- aucun déclencheur sur public.tc_payment en prod.
-- À appliquer APRÈS 2026-11-26-pot-paiement-geste-apply.sql (20261126140000) et après le fichier de 20261126150000 s'il
-- existe ; n'en dépend pas (seulement de 20261125110000, déjà en prod). Rejouable, tout ou rien.
-- Retour arrière : 2026-11-26-pot-filtre-paiement-purge-rollback.sql.
begin;
-- Contrôle Apple du 26.11.2026, tour 3 (côté base). Purement additive et rejouable ; tout est ÉTENDU par ancre sur la
-- définition en place (jamais réécrit), valable sur la prod (ancres vérifiées en lecture seule le 26.11) comme sur TEST.
-- Passe APRÈS 20261126140000_pot_paiement_geste_signalements.sql.
--
-- a. Pot commun : le profil de paiement (public.tc_payment : titulaire `holder`, `note`), montré aux autres membres du pot
--    et aux participants d'un événement, passe le même filtre que le pot (private.moderate_tc_text, 20261125110000) :
--    titulaire = 'Nom', note = 'Note'. Seul un texte NOUVEAU ou CHANGÉ est contrôlé ; écritures du serveur non filtrées.
-- b. event_pay_info ne renvoie l'IBAN, le titulaire, les liens et la note du profil de paiement de l'organisateur QUE pour
--    « On me paie » (payment_mode = 'organizer') ; jamais en ligne (billetterie) ni sur place.
-- c. private.expire_chat_photos() : photos et vocaux de la discussion d'un événement (public.messages) effacés à 90 jours,
--    comme groupes et messages directs (dit dans la politique de confidentialité).

-- a. Filtre du profil de paiement -----------------------------------------------------------------------------------------
do $$ declare def text;
begin
  def := pg_get_functiondef('private.moderate_tc_text()'::regprocedure);
  if position('tc_payment' in def) = 0 then
    if position($a$  elsif tg_table_name = 'tc_expenses' then$a$ in def) = 0 then
      raise exception 'moderate_tc_text : ancre tc_expenses introuvable';
    end if;
    execute replace(def, $a$  elsif tg_table_name = 'tc_expenses' then$a$, $a$  elsif tg_table_name = 'tc_payment' then
    if coalesce(new.holder, '') <> '' and (tg_op = 'INSERT' or new.holder is distinct from old.holder) then
      new.holder := private.item_text_verdict(new.holder, 'Nom');
    end if;
    if coalesce(new.note, '') <> '' and (tg_op = 'INSERT' or new.note is distinct from old.note) then
      new.note := private.item_text_verdict(new.note, 'Note');
    end if;
  elsif tg_table_name = 'tc_expenses' then$a$);
  end if;
end $$;
revoke all on function private.moderate_tc_text() from public, anon, authenticated;

drop trigger if exists tc_payment_moderation on public.tc_payment;
create trigger tc_payment_moderation before insert or update of holder, note on public.tc_payment
  for each row execute function private.moderate_tc_text();

-- b. Moyens de paiement de l'organisateur : « On me paie » seulement -------------------------------------------------------
do $$ declare def text;
begin
  def := pg_get_functiondef('public.event_pay_info(uuid)'::regprocedure);
  if position('pay_shown' in def) = 0 then
    if position($a$'iban', pay.iban, 'holder', pay.holder, 'links', coalesce(pay.links, '{}'::jsonb), 'note', pay.note,$a$ in def) = 0 then
      raise exception 'event_pay_info : ancre iban / holder / links / note introuvable';
    end if;
    -- pay_shown : vrai seulement en « On me paie » (sinon les 4 champs sont vides, comme sans profil de paiement).
    execute replace(def,
      $a$'iban', pay.iban, 'holder', pay.holder, 'links', coalesce(pay.links, '{}'::jsonb), 'note', pay.note,$a$,
      $a$'iban', case when ev.payment_mode = 'organizer' /* pay_shown */ then pay.iban end,
    'holder', case when ev.payment_mode = 'organizer' then pay.holder end,
    'links', case when ev.payment_mode = 'organizer' then coalesce(pay.links, '{}'::jsonb) else '{}'::jsonb end,
    'note', case when ev.payment_mode = 'organizer' then pay.note end,$a$);
  end if;
end $$;
revoke all on function public.event_pay_info(uuid) from public, anon;
grant execute on function public.event_pay_info(uuid) to authenticated;

-- c. Photos et vocaux de la discussion d'un événement : 90 jours --------------------------------------------------------
do $$ declare def text;
begin
  def := pg_get_functiondef('private.expire_chat_photos()'::regprocedure);
  if position('gone_event' in def) = 0 then
    if position($a$  select ((select count(*) from gone) + (select count(*) from gone_direct))::int;$a$ in def) = 0 then
      raise exception 'expire_chat_photos : ancre du total introuvable';
    end if;
    execute replace(def, $a$  select ((select count(*) from gone) + (select count(*) from gone_direct))::int;$a$,
      $a$, gone_event as (update public.messages
                set body = case when btrim(body) <> '' then body when audio_path is not null then '🎤 Message vocal expiré'
                                else '📷 Photo expirée' end,
                    photo_path = null, audio_path = null, audio_seconds = null
                where (photo_path is not null or audio_path is not null) and created_at < now() - interval '90 days' returning 1)
  select ((select count(*) from gone) + (select count(*) from gone_direct) + (select count(*) from gone_event))::int;$a$);
  end if;
end $$;
insert into supabase_migrations.schema_migrations (version, name) values ('20261126160000', 'pot_filtre_paiement_purge') on conflict do nothing;
commit;
