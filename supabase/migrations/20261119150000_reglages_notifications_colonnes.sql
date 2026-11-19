-- Notifications de la PRODUCTION en panne (trouvé le 19.11) : private.may_receive_push et private.web_push_allowed lisent
-- des interrupteurs de notification_prefs (pet_* de Zicou) dont les migrations ne sont pas en prod ; chaque passage de
-- send-push / send-web-push échouait (42703 record "prefs" has no field "pet_daily") : aucune notification iPhone ni web.
-- Toutes les colonnes d'interrupteurs, mêmes défauts que sur TEST, y compris celles des fonctions gardées en test
-- (Agenda, Pronos) : une fonction partagée qui les cite ne peut plus casser la prod. Purement additive et rejouable.
alter table public.notification_prefs add column if not exists pet_daily boolean not null default true;
alter table public.notification_prefs add column if not exists pet_alerts boolean not null default true;
alter table public.notification_prefs add column if not exists pet_gifts boolean not null default true;
alter table public.notification_prefs add column if not exists pet_streaks boolean not null default true;
alter table public.notification_prefs add column if not exists pet_bar boolean not null default true;
alter table public.notification_prefs add column if not exists group_added boolean not null default true;
alter table public.notification_prefs add column if not exists booking_requests boolean not null default true;
alter table public.notification_prefs add column if not exists pronos boolean not null default true;
alter table public.notification_prefs add column if not exists message_requests boolean not null default true;
