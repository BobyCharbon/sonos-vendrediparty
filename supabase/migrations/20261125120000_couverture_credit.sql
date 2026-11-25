-- Couverture d'un événement changée après coup (demande de l'admin du 25.11.2026) : crédit de la photo libre de droits
-- (« Photo : Nom / Pexels », « Photo : auteur · CC BY 4.0 · Openverse ») ou de l'image officielle (« Visuel : domaine »),
-- affiché discrètement sous la couverture, avec le lien de la source. Écrit par le serveur (app/event_covers.py) avec le
-- jeton de la personne : RLS et garde de statut des événements inchangées (mêmes droits que « Modifier »).
-- Purement additive et rejouable.

alter table public.events add column if not exists cover_credit text;
alter table public.events add column if not exists cover_credit_url text;

alter table public.events drop constraint if exists events_cover_credit_check;
alter table public.events add constraint events_cover_credit_check
  check (cover_credit is null or char_length(cover_credit) <= 200);
alter table public.events drop constraint if exists events_cover_credit_url_check;
alter table public.events add constraint events_cover_credit_url_check
  check (cover_credit_url is null or (cover_credit_url like 'https://%' and char_length(cover_credit_url) <= 500));

comment on column public.events.cover_credit is 'Crédit de la couverture (photo libre de droits ou visuel officiel), affiché sous elle.';
comment on column public.events.cover_credit_url is 'Page source du crédit (Pexels, Openverse, page officielle), https seulement.';
