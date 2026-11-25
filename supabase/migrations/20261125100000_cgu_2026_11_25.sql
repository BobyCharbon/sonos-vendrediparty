-- Conditions d'utilisation version 2026-11-25 (refus Apple 1.4.3, revue du 25.11.2026) : texte affiché depuis le 25.11
-- (paragraphe « Signaler », éditeur établi en France ; l'app App Store n'en montre que les sections de ses fonctions).
-- Le consentement porte ainsi sur le texte réellement affiché. Chaque compte les accepte à nouveau avant son prochain
-- contenu (web lib/terms.ts, iPhone TermsView.swift). Purement additive et rejouable.
update private.moderation_settings set terms_version = '2026-11-25' where terms_version < '2026-11-25';
alter table private.moderation_settings alter column terms_version set default '2026-11-25';
