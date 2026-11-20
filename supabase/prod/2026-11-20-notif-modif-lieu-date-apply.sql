-- Prod : 20261120200000_notif_modif_lieu_date (avis 27b5eea5121c) : la modification d'un événement ne prévient que pour le lieu, la date ou le retour au sondage.
begin;
do $$
declare
  src text := pg_get_functiondef('public.notify_event_change()'::regprocedure);
  old_text text := $old$    elsif new.starts_at is distinct from old.starts_at or new.location_name is distinct from old.location_name
       or new.location_address is distinct from old.location_address
       or new.ends_at is distinct from old.ends_at or new.location_url is distinct from old.location_url
       or new.title is distinct from old.title or new.description is distinct from old.description
       or new.price_chf is distinct from old.price_chf then
      for u in select a from event_audience(new.id) a join notification_prefs np on np.user_id = a where np.event_changed loop
        perform queue_notification(u, 'event_changed', new.id, 'Événement modifié',
          '« ' || new.title || ' » : les informations ont changé.');
      end loop;$old$;
  new_text text := $new$    else
      -- Avis 27b5eea5121c : seulement le lieu, la date de début (date fixe) ou le retour au sondage de dates.
      changes := array_remove(array[
        case when new.location_name is distinct from old.location_name
             then 'nouveau lieu : ' || coalesce(nullif(btrim(new.location_name), ''), nullif(btrim(new.location_address), ''), 'à définir')
             when new.location_address is distinct from old.location_address
             then 'nouvelle adresse : ' || coalesce(nullif(btrim(new.location_address), ''), 'à définir') end,
        case when new.date_mode is distinct from 'poll' and new.starts_at is not null and new.starts_at is distinct from old.starts_at
             then 'nouvelle date : ' || to_char(new.starts_at at time zone 'Europe/Zurich', 'DD.MM à HH24:MI') end,
        case when new.date_mode = 'poll' and old.date_mode is distinct from 'poll'
             then 'date à revoter' end], null);
      if cardinality(changes) > 0 then
        for u in select a from event_audience(new.id) a join notification_prefs np on np.user_id = a where np.event_changed loop
          perform queue_notification(u, 'event_changed', new.id, 'Événement modifié',
            '« ' || new.title || ' » : ' || array_to_string(changes, ' · ') || '.');
        end loop;
      end if;$new$;
begin
  if position('Avis 27b5eea5121c' in src) > 0 then return; end if;
  if position(old_text in src) = 0 then raise exception 'notify_event_change : repère introuvable, rien changé'; end if;
  src := replace(src, old_text, new_text);
  src := replace(src, E'declare u uuid;\nbegin', E'declare u uuid; changes text[];\nbegin');
  if position('changes text[]' in src) = 0 then raise exception 'notify_event_change : déclaration introuvable, rien changé'; end if;
  execute src;
end $$;
insert into supabase_migrations.schema_migrations (version, name) values ('20261120200000', 'notif_modif_lieu_date') on conflict do nothing;
commit;
