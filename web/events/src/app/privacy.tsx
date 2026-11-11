import { router } from 'expo-router';
import { Linking } from 'react-native';

import { Button, Screen, Section, T, Title } from '@/components/ui';
import { RESPONSIBLE, SUPPORT_EMAIL } from '@/lib/contact';

/** Politique de confidentialité (Apple 5.1.1(i), nLPD art. 19) : lisible par tous, sans compte. Chaque donnée, son but,
 * qui la reçoit (sous-traitants) et combien de temps elle est gardée. À tenir à jour avec App Privacy (App Store
 * Connect) et Data safety (Play Console) à chaque nouvelle donnée. */
const UPDATED = '9 novembre 2026';

type Block = { title: string; paragraphs: string[] };

const BLOCKS: Block[] = [
  {
    title: 'Qui est responsable ?',
    paragraphs: [
      `Party (Vendredi Party : l’app iPhone, l’app Apple TV et le site) est édité par ${RESPONSIBLE}, en Suisse, responsable du traitement de tes données au sens de la loi fédérale sur la protection des données (nLPD).`,
      `Pour toute question ou demande sur tes données : ${SUPPORT_EMAIL}. Réponse en principe sous 30 jours.`,
      'Party est réservé aux personnes de 18 ans et plus. Party ne fait aucune publicité, ne revend aucune donnée et n’utilise aucun outil tiers de mesure d’audience ni de suivi (« tracking »).',
    ],
  },
  {
    title: 'Ton compte',
    paragraphs: [
      'Numéro de téléphone : il sert à te connecter avec un code reçu par SMS et à te reconnaître. Il est visible par toi, par les administrateurs qui gèrent les accès et, si tu le choisis dans tes réglages, par les membres de tes groupes.',
      'Surnom, prénom, nom et, si tu veux, photo de profil : ils te présentent aux autres dans les jeux, les événements et les groupes. Tu les modifies à tout moment dans Réglages › Mon profil.',
      'Rôle, groupes, amis et invitations : ils décident de ce que tu vois et de ce que tu peux faire.',
    ],
  },
  {
    title: 'Événements, groupes et messages',
    paragraphs: [
      'Tes événements, réponses (présent, absent…), votes, sondages, ce que tu amènes et tes messages servent à organiser les événements avec les personnes concernées. Ils sont visibles selon la visibilité de chaque événement ou groupe.',
      'Messages, photos et messages vocaux : envoyés seulement quand tu le décides. Le micro n’est utilisé que pendant que tu enregistres un vocal ou que tu dictes un texte ; ta voix dictée est transcrite en texte par le service vocal de ton système, pas par Party : Apple (Dictée) sur iPhone, Google ou Apple selon ton navigateur sur le web. Party et l’IA ne reçoivent que le texte. Les photos ne sont lues que celles que tu choisis.',
      'Organisateurs d’événements payants : les coordonnées de paiement que tu enregistres (IBAN, titulaire, liens de paiement comme Twint, note) sont montrées aux participants de tes événements payants pour qu’ils te paient. Party ne traite jamais l’argent lui-même.',
      'Billets : un billet QR personnel est créé pour tes événements à billets ; son passage à l’entrée est noté.',
      'Invitation par lien : la page de l’invitation se lit sans compte et ne montre que le titre, la date, le nom du lieu, le prénom de la personne qui invite et au plus trois prénoms de ceux qui viennent (aucun si l’organisateur cache la liste). Pour répondre, tu donnes ton prénom et ton numéro (code par SMS) : l’organisateur voit ton prénom, ta réponse, par quel lien tu es venu et quand le lien a été ouvert, jamais ton numéro. Les relances de l’organisateur passent par une notification (si tu as l’app, avec son interrupteur « Invitations ») ou par un message qu’il t’envoie lui-même.',
    ],
  },
  {
    title: 'Contacts de ton iPhone',
    paragraphs: [
      'Seulement si tu l’autorises : l’app transforme chaque numéro de tes contacts en une empreinte (un code chiffré dont on ne peut pas retrouver le numéro), sur ton iPhone, et l’envoie pour reconnaître les personnes déjà inscrites. Les noms de tes contacts ne quittent jamais ton iPhone et le serveur ne garde pas ces empreintes.',
    ],
  },
  {
    title: 'Ton agenda',
    paragraphs: [
      'Quand tu ajoutes un événement à ton agenda, ton agenda s’abonne à ton calendrier « Vendredi Party », un lien secret propre à toi : il n’y lit que les événements que tu y as ajoutés et, une fois l’agenda activé, ceux où tu réponds Présent ou Peut-être (ou votes Oui / Si besoin pour une date), jamais un événement que tu ne vois plus dans Party (titre, description, lieu, date, ou tes dates votées tant que la date n’est pas fixée) et suit leurs changements. Party note seulement quand ton agenda l’a relu pour la dernière fois, pour savoir qu’il est abonné. Tout disparaît avec ton compte.',
      'App iPhone, seulement si tu l’autorises, si l’agenda abonné n’est pas disponible : l’app met elle-même les dates d’un sondage dans ton calendrier, puis, une fois la date fixée, garde la bonne et retire les autres. Elle ne lit que les entrées qu’elle a ajoutées ; rien de ton calendrier ne quitte ton iPhone.',
    ],
  },
  {
    title: 'Jeux, musique et stats',
    paragraphs: [
      'Pendant une soirée, ton prénom et tes réponses de jeu sont visibles par les joueurs de la partie (et sur l’écran de la soirée). Les titres que tu proposes sont envoyés à Spotify pour être recherchés et joués sur le compte de l’hôte, avec ton prénom visible dans la file.',
      'Stats de jeux (Quiz, Méninges, Purify Test) : gardées avec ton compte pour te montrer tes progrès et les classements.',
      'Purify Test : tes réponses aux questions ne sont jamais enregistrées. Seul ton score global l’est ; ton profil par catégorie se voit à la fin du test, puis disparaît. Tu n’apparais dans le classement général que si tu l’actives (Réglages › Mes stats de jeu).',
      'Invités sans compte : un compteur de parties jouées est gardé avec l’identifiant de ton appareil (jamais ton adresse IP), effacé après 6 mois sans visite.',
    ],
  },
  {
    title: 'L’IA (Anthropic, Claude)',
    paragraphs: [
      'Seulement après ton accord exprès (une feuille te le demande avant la première fois), Party envoie à Anthropic ce que tu confies à l’IA : le texte de ton avis (et la transcription de ta voix) pour le mettre au propre ; avec l’assistant des événements, ta description, tes captures d’écran, tes photos, les liens que tu donnes et les noms utiles à l’événement ; pour un ticket du pot commun, sa photo.',
      'Ton numéro n’est jamais envoyé. Anthropic traite ces données pour répondre et ne les utilise pas pour entraîner ses modèles. Tu vois, retires ou redonnes ton accord à tout moment dans Réglages › Confidentialité ; sans accord, tout marche sans l’IA.',
      'Chaque appel est noté (date, coût, ce que tu as demandé) pour les plafonds mensuels et le contrôle des coûts ; les plus anciens partent automatiquement et tout part avec ton compte.',
    ],
  },
  {
    title: 'Tes avis sur l’app (« Ton avis »)',
    paragraphs: [
      'Quand tu écris un avis (idée, bug), l’administrateur reçoit ton texte, ton prénom, l’écran où tu étais et ton appareil (modèle, version du système et de l’app). Il peut te répondre dans l’app.',
      'Si tu modifies ton avis, les versions précédentes sont gardées avec leur date (au plus les 20 dernières) pour que l’administrateur voie ce qui a changé. Elles partent avec l’avis.',
      'Pour corriger l’app, l’administrateur peut confier un avis à une IA de développement : l’avis est alors copié sur GitHub (où le code de Party est gardé), puis lu par Claude (Anthropic). Cela n’arrive que si tu as donné ton accord pour l’IA, et toujours sans ton prénom ni ton numéro. Sans accord, ton avis reste chez l’administrateur.',
    ],
  },
  {
    title: 'Notifications, Apple Wallet et appareils',
    paragraphs: [
      'Notifications : l’adresse de notification de ton appareil (Apple Push Notification service pour l’iPhone, service push de ton navigateur sur le web) est enregistrée avec ton compte. Chaque type de notification a son interrupteur dans Réglages › Notifications. L’historique des notifications est effacé après 90 jours.',
      'Apple Wallet : si tu ajoutes un billet, le pass contient ton surnom, l’événement et ton QR ; ton iPhone s’inscrit auprès de Party pour recevoir ses mises à jour.',
      'Identifiant de l’appareil : Party enregistre un identifiant d’invité tiré au hasard (pour te reconnaître à la soirée sans compte), le jeton de notifications de ton appareil et, si tu ajoutes un billet à Wallet, l’identifiant d’inscription de ton iPhone. Ils servent seulement à faire marcher l’app, jamais à te suivre ni à faire de la publicité.',
      'Journaux techniques : le serveur garde les connexions et les actions d’administration (date, compte, adresse IP) pour la sécurité, et des journaux d’erreurs sans contenu de message.',
    ],
  },
  {
    title: 'Qui reçoit tes données (sous-traitants)',
    paragraphs: [
      'Supabase : base de données et connexion, hébergées en Suisse (Zurich).',
      'Twilio : envoi du code de connexion par SMS (ton numéro).',
      'Anthropic : l’IA, seulement avec ton accord (voir plus haut).',
      'GitHub : garde le code de Party ; y sont copiés, sans ton prénom, les avis confiés à l’IA de développement, seulement avec ton accord pour l’IA.',
      'Spotify : recherche et lecture des titres de la soirée.',
      'Apple : notifications de l’iPhone (APNs), billets Apple Wallet, app Apple TV, et la dictée vocale sur iPhone (transcription de ta voix, seulement quand tu dictes).',
      'Google : la recherche d’un lieu dans l’assistant des événements (le texte du lieu), et la dictée vocale dans Chrome (transcription de ta voix, seulement quand tu dictes).',
      'Infomaniak (Suisse) : messagerie de l’adresse de contact, quand tu nous écris.',
      'Le serveur de Party est hébergé en Suisse. Twilio, Anthropic, GitHub, Spotify, Apple et Google peuvent traiter des données hors de Suisse, notamment aux États-Unis, avec les garanties prévues par la nLPD (Swiss-U.S. Data Privacy Framework ou clauses contractuelles types).',
    ],
  },
  {
    title: 'Combien de temps',
    paragraphs: [
      'Ton compte et ce qui s’y rattache : jusqu’à ce que tu le supprimes. Notifications : 90 jours. Signalements traités : un an. Compteur des invités : 6 mois sans visite. Compte créé seulement pour répondre à une invitation (prénom et numéro, sans l’app ni profil complété) : effacé avec ses réponses 7 jours après le dernier événement auquel il était invité. Activité de la soirée : le temps de la soirée et au plus 3 jours.',
      'Les textes écrits par d’autres membres peuvent encore citer ton surnom après la suppression de ton compte.',
    ],
  },
  {
    title: 'Tes droits',
    paragraphs: [
      'Tu peux à tout moment : voir et corriger tes données dans l’app ; retirer un accord (IA, contacts, notifications) ; supprimer ton compte dans Réglages › Gérer mon compte. La suppression efface ton compte, tes contenus, les événements que tu as créés, tes stats de jeux, tes accords pour l’IA et le journal de tes appels à l’IA ; tes avis sur l’app restent, sans ton nom.',
      `Pour obtenir une copie de tes données ou toute autre demande : ${SUPPORT_EMAIL}. Tu peux aussi t’adresser au Préposé fédéral à la protection des données et à la transparence (PFPDT).`,
    ],
  },
  {
    title: 'Signalements et blocages',
    paragraphs: [
      'Quand tu signales un contenu, les modérateurs reçoivent ta raison, ton commentaire et une copie de ce contenu (pour un message direct : ce seul message). La personne signalée ne sait pas qui l’a signalée. Les blocages restent jusqu’à ce que tu débloques.',
    ],
  },
];

export default function Privacy() {
  return (
    <Screen edges={[]}>
      <Title>Confidentialité</Title>
      <T muted>Party · Mise à jour du {UPDATED}</T>
      {BLOCKS.map((block) => (
        <Section key={block.title} title={block.title}>
          {block.paragraphs.map((p) => <T key={p}>{p}</T>)}
        </Section>
      ))}
      <Button small variant="secondary" label={`Écrire à ${SUPPORT_EMAIL}`} onPress={() => void Linking.openURL(`mailto:${SUPPORT_EMAIL}`)} />
      <Button small variant="secondary" label="Conditions d’utilisation" onPress={() => router.push('/terms')} />
      <Button label="Revenir à l’application" onPress={() => router.canGoBack() ? router.back() : router.replace('/')} />
    </Screen>
  );
}
