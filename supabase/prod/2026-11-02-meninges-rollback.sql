-- PROD, retour arrière de Méninges (20261102210000 + analyse 20261102220000 + percentile par jeu 20261102240000) : supprime l'entraînement cérébral (ATTENTION : efface les parties).
begin;
drop function if exists public.brain_game_percentile(text), private.brain_party_domains(uuid), public.brain_compare(uuid), public.brain_my_stats(),
  public.brain_record(text, integer, real, integer, integer, integer), private.brain_percentile(integer),
  private.brain_players(), private.brain_profile(uuid), private.brain_index(text, integer);
drop table if exists public.brain_sessions, public.brain_games;
delete from supabase_migrations.schema_migrations where version = '20261102240000';
delete from supabase_migrations.schema_migrations where version = '20261102220000';
delete from supabase_migrations.schema_migrations where version = '20261102210000';
commit;
