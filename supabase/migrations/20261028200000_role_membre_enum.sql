-- Nouveau rôle « Membre » (valeur basic), entre Guest et Membre VIP (retour de l'admin du 28 octobre 2026).
-- À part : une nouvelle valeur d'énumération doit être enregistrée avant d'être utilisée (20261028200100).
alter type public.member_role add value if not exists 'basic' before 'member';
