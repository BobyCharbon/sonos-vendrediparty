-- Demande de l'admin du 21.11.2026 : les heures de silence (23 h – 8 h) ne sont plus allumées par défaut ; les membres
-- n'avaient pas compris le principe (notifications de la nuit jamais sonnées). Éteintes pour tout le monde (en prod, les
-- 37 comptes avaient tous la valeur par défaut, personne ne l'avait réglée lui-même) ; chacun peut les rallumer dans
-- Réglages › Notifications › « Heures de silence » (23:00 – 08:00 proposés). Rejouable.
alter table public.notification_prefs alter column quiet_start drop default;
alter table public.notification_prefs alter column quiet_end drop default;
update public.notification_prefs set quiet_start = null, quiet_end = null
 where quiet_start = '23:00' and quiet_end = '08:00';
