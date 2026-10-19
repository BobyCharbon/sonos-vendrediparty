// Ces deux valeurs sont publiques. Aucune clé serveur n’est incluse dans le site.
process.env.EXPO_PUBLIC_SUPABASE_URL ||= 'https://gsuetixzobooggeaubvb.supabase.co';
process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY ||= 'sb_publishable_DJJSW8NYvEfA7DUDoXSwkw_wTF1fnoK';
module.exports = ({ config }) => config;
