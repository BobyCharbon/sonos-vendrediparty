-- Nouveau rôle « Guest+ » (valeur guestplus), entre Guest et Membre (demande de l'admin du 29 octobre 2026).
-- À part : une nouvelle valeur d'énumération doit être enregistrée avant d'être utilisée (20261029120100).
alter type public.member_role add value if not exists 'guestplus' after 'guest';
