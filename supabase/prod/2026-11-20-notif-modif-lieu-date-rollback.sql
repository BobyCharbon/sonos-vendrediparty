-- Retour arrière de 20261120200000 : notify_event_change revient à « les informations ont changé » pour la date, le lieu,
-- l'heure de fin, le lien du lieu, le titre, la description et le prix (texte d'avant, mot pour mot).
begin;
do $$
declare
  src text := pg_get_functiondef('public.notify_event_change()'::regprocedure);
  a int := position(E'    else\n      -- Avis 27b5eea5121c' in src);
  b int;
  old_text text := $old$    elsif new.starts_at is distinct from old.starts_at or new.location_name is distinct from old.location_name
       or new.location_address is distinct from old.location_address
       or new.ends_at is distinct from old.ends_at or new.location_url is distinct from old.location_url
       or new.title is distinct from old.title or new.description is distinct from old.description
       or new.price_chf is distinct from old.price_chf then
      for u in select a from event_audience(new.id) a join notification_prefs np on np.user_id = a where np.event_changed loop
        perform queue_notification(u, 'event_changed', new.id, 'Événement modifié',
          '« ' || new.title || ' » : les informations ont changé.');
      end loop;$old$;
begin
  if a = 0 then raise exception 'notify_event_change : version de l''avis introuvable, rien changé'; end if;
  b := position(E'        end loop;\n      end if;' in substr(src, a));
  if b = 0 then raise exception 'notify_event_change : fin du bloc introuvable, rien changé'; end if;
  src := substr(src, 1, a - 1) || old_text || substr(src, a + b - 1 + length(E'        end loop;\n      end if;'));
  src := replace(src, E'declare u uuid; changes text[];\nbegin', E'declare u uuid;\nbegin');
  execute src;
end $$;
delete from supabase_migrations.schema_migrations where version = '20261120200000';
commit;
