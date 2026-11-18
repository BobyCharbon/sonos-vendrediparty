-- Conditions d'utilisation version 2026-11-18 (Pronos v2, revue de conformité des confettis, ex-patates, du 18.11.2026) : nouvelle
-- section « Pronos et confettis » (pour l'honneur, confettis gratuits sans valeur, ni achat ni vente ni échange ni transfert,
-- jamais réglés en argent / boissons / objets, jamais de prono sur l'alcool, suspension, Apple et Google ni organisateurs
-- ni sponsors). Chaque compte les accepte à nouveau avant son prochain contenu (web lib/terms.ts, iPhone TermsView.swift).
-- Purement additive et rejouable.
update private.moderation_settings set terms_version = '2026-11-18' where terms_version < '2026-11-18';
alter table private.moderation_settings alter column terms_version set default '2026-11-18';
