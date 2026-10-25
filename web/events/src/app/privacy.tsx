import { router } from 'expo-router';

import { Button, Screen, Section, T, Title } from '@/components/ui';

export default function Privacy() {
  return (
    <Screen edges={[]}>
      <Title>Confidentialité</Title>
      <T muted>Vendredi Party · Mise à jour du 19 octobre 2026</T>
      <Section title="Un espace pour le groupe">
        <T>Vendredi Party organise les événements d’un groupe privé. Un administrateur valide l’accès des nouveaux membres.</T>
      </Section>
      <Section title="Données utilisées">
        <T>Ton numéro de téléphone sert à recevoir un code de connexion. Ton prénom, tes événements, tes réponses, tes votes et tes messages permettent au groupe d’organiser les événements.</T>
        <T>Les catégories et tags auxquels tu t’abonnes servent à filtrer les événements et les notifications. L’application enregistre tes préférences pour les notifications des événements.</T>
      </Section>
      <Section title="Qui peut voir quoi ?">
        <T>Les membres autorisés voient les événements et les contributions selon leur visibilité. Ton numéro de téléphone est visible par toi et par les administrateurs qui gèrent les accès au groupe.</T>
        <T>Un sondage anonyme affiche les totaux. Un sondage nominatif peut afficher les votants. Les messages d’une discussion sont visibles aux membres autorisés à consulter l’événement.</T>
      </Section>
      <Section title="Services techniques">
        <T>Supabase héberge la base du projet en région Zurich et gère la connexion. Twilio reçoit le numéro nécessaire à l’envoi du code SMS. Le module événements est hébergé sur le même site que Party.</T>
        <T>Les notifications des événements sont consultables dans Activité. Si tu actives leur réception sur un appareil, son adresse de notification et ses clés de chiffrement sont enregistrées avec ton compte et ta session. Les services push du navigateur transmettent les messages chiffrés.</T>
        <T>Les préférences des événements et de la musique sont distinctes. L’autorisation système de notification peut être commune au site. Les annonces admin restent lisibles et ne peuvent pas être désactivées dans les préférences.</T>
      </Section>
      <Section title="Tes choix et la conservation">
        <T>Tu peux modifier ton prénom, tes abonnements et tes préférences de notifications depuis ton profil. Les notifications de l’historique sont purgées après 90 jours ; les annonces admin sont conservées dans leur historique. Une déconnexion retire l’abonnement aux événements de cet appareil.</T>
        <T>Tu peux supprimer ton compte depuis Profil → Gérer mon compte. Cette action supprime tes contributions et les événements que tu as créés. Les textes rédigés par d’autres membres peuvent encore contenir des références à ton prénom.</T>
        <T>Pour toute question sur les données du groupe, contacte son administrateur par le canal habituel du groupe.</T>
      </Section>
      <Button label="Revenir à l’application" onPress={() => router.canGoBack() ? router.back() : router.replace('/')} />
    </Screen>
  );
}
