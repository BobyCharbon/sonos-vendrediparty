import { storeApp } from './features';

/** Texte des conditions d'utilisation (version 2026-11-18, = private.moderation_settings.terms_version).
 * Le même texte est repris dans l'app iPhone (ios/Party/Settings/Moderation/TermsView.swift) : changer les deux,
 * puis la version dans la base (les comptes acceptent alors la nouvelle version avant leur prochain contenu). */
export const TERMS_UPDATED = '18 novembre 2026';

const ALL_SECTIONS: { title: string; paragraphs: string[] }[] = [
  {
    title: 'Party, entre amis',
    paragraphs: [
      'Party sert à organiser des soirées et des événements, à jouer et à discuter entre amis. En créant un compte et en publiant quoi que ce soit (message, surnom, nom de groupe, photo, réponse de jeu), tu acceptes ces conditions.',
    ],
  },
  {
    title: 'Réservé aux adultes',
    paragraphs: [
      'Party est réservée aux personnes de 18 ans ou plus. En acceptant ces conditions, tu confirmes avoir 18 ans ou plus.',
    ],
  },
  {
    title: 'Le respect avant tout',
    paragraphs: [
      'Pas de harcèlement : ni insultes répétées, ni menaces, ni moqueries visant une personne, ni messages insistants à quelqu’un qui ne veut pas te répondre.',
      'Interdits : propos haineux (origine, religion, genre, orientation, handicap…), contenu sexuel ou violent, contenu illégal, photos d’autres personnes sans leur accord, usurpation d’identité, spam et publicité.',
      'Un filtre retire automatiquement certains mots ; il ne remplace pas le bon sens.',
      'Aucune tolérance pour les contenus choquants ou les utilisateurs abusifs : le contenu est retiré et le compte peut être suspendu ou banni.',
    ],
  },
  {
    title: 'Messages directs et demandes',
    paragraphs: [
      'Tu écris directement aux personnes avec qui tu as un vrai lien dans Party : un groupe en commun (hors Membres Vendredi Party), un événement non public en commun, ou l’organisateur d’un événement auquel tu as répondu (et l’organisateur à toi). À tout autre membre, tu envoies une demande de message : un seul message texte, sans photo, vocal, lien ni numéro de téléphone. Tant que la personne ne l’a pas acceptée, tu ne peux rien envoyer d’autre ; si elle la supprime, tu n’en es pas prévenu.',
      'Au plus 10 nouvelles demandes par jour et 30 en attente. Relancer quelqu’un qui ne répond pas ou a supprimé ta demande, ou créer un groupe pour l’obliger à te lire, c’est du harcèlement. Dans Réglages › Confidentialité, « Demandes de message » te permet de n’en recevoir de personne.',
      'Le filtre automatique et ces conditions valent pour tous les messages, messages directs et demandes compris.',
      'Les messages directs, les demandes de message et les groupes privés créés depuis « Nouveau message » ne sont jamais lus par l’administration de Party : un modérateur ne voit que ce qu’on lui signale. Les autres groupes peuvent être lus par l’administrateur principal de Party (Root) pour la modération.',
    ],
  },
  {
    title: 'Le jeu n’a aucune valeur en argent',
    paragraphs: [
      'Les pièces, objets, cartes et récompenses des jeux de Party n’ont aucune valeur monétaire. Ils ne s’achètent pas, ne se vendent pas et ne s’échangent pas contre de l’argent ou un service, ni dans Party ni ailleurs.',
      'Toute vente, achat ou proposition de vente d’un objet ou d’un compte est interdite. Le paiement entre amis et les billets d’événement ne concernent jamais un objet du jeu.',
    ],
  },
  {
    title: 'Pronos et confettis',
    paragraphs: [
      'Les Pronos se jouent entre amis, pour l’honneur : on devine, on marque des points et, dans un groupe ou un événement, on lance des confettis pour rire. Apple et Google ne sont ni organisateurs ni sponsors des Pronos.',
      'Les confettis sont gratuits et n’ont aucune valeur. Ils ne s’achètent pas, ne se vendent pas, ne s’échangent pas et ne se transfèrent pas d’une personne à une autre. Ils ne se convertissent en rien (ni argent, ni boisson, ni objet du jeu) et aucun lot ne récompense le classement.',
      'Il est interdit de régler un prono ou des confettis en argent, en boissons, en objets ou en services, dans Party ou ailleurs, et de proposer d’acheter ou de vendre des confettis. Jamais de prono sur l’alcool ni sur ce que boit quelqu’un.',
      'Un compte qui détourne les Pronos ou les confettis (argent, boissons, vente, triche) peut être suspendu, et ses confettis retirés. Un résultat qui te semble injuste se conteste ou se signale.',
    ],
  },
  {
    title: 'Événements publics et groupes',
    paragraphs: [
      'Un événement public (visible par tous les comptes et par son lien), créé par un membre qui ne publie pas directement, attend l’accord d’un organisateur, d’un co-admin ou d’un admin de Vendredi Party avant d’être visible ; ils peuvent le refuser. Les admins et co-admins de Vendredi Party peuvent aussi, à tout moment, modifier ses informations ou le retirer, même après sa publication.',
      'Dans tes groupes, tu es libre : un événement réservé à tes groupes est publié sans validation de Vendredi Party ; seul un groupe qui le demande fait valider les événements de ses membres par qui le gère. Les administrateurs de Party voient la liste de tous les groupes et de leurs membres, jamais les messages, photos ni vocaux des groupes privés créés depuis « Nouveau message ».',
    ],
  },
  {
    title: 'Paiements, billets et bar',
    paragraphs: [
      'Party ne vend rien et ne touche jamais d’argent : ni paiement, ni portefeuille, ni commission. Un organisateur peut indiquer un prix et un moyen de payer qui est le sien (Revolut, billetterie, sur place) ; le paiement se fait en dehors de Party, entre personnes. Un « J’ai payé » n’est confirmé que par l’organisateur.',
      'Le bar de la soirée est une option de l’organisateur pour une soirée privée entre amis, offerte ou à prix coûtant. Party note seulement qui a pris quoi et qui doit combien ; l’engagement à rembourser est une promesse entre personnes. L’organisateur est seul responsable de ses prix, de ce qu’il sert et du respect de la loi, en particulier sur l’alcool (âge minimum, pas d’alcool à une personne ivre). Tabac et drogues sont interdits.',
      'Boire n’est jamais obligatoire ni récompensé, et personne n’est classé selon ce qu’il boit.',
    ],
  },
  {
    title: 'Signaler et bloquer',
    paragraphs: [
      '« Signaler » existe sur chaque message, demande de message, profil, groupe et photo, et sur les réponses écrites montrées à la table dans les jeux (Le Masque, Tu me connais ?, dilemmes proposés de Pour ou contre) ; dans tous les jeux, l’animateur peut retirer ou exclure un joueur. Un modérateur reçoit le signalement avec une copie du contenu concerné : pour un message, ce seul message avec sa photo ou son vocal, et les 10 messages précédents seulement si tu coches « Joindre les 10 messages précédents » ; la personne signalée ne sait pas qui l’a signalée. Les signalements sont traités sous 24 heures.',
      'Tu peux bloquer quelqu’un depuis sa fiche ou une conversation : il ne peut plus t’écrire, t’envoyer de demande de message, te citer, t’inviter ni voir ta fiche. La liste « Personnes bloquées » est dans Réglages › Confidentialité.',
    ],
  },
  {
    title: 'Sanctions',
    paragraphs: [
      'Selon la gravité, un modérateur peut masquer un contenu, avertir, suspendre un compte pour une durée choisie ou le bannir. Les sanctions visent le compte, jamais un appareil ou une connexion partagée. Quand un modérateur masque ton contenu, tu en es prévenu avec le motif et l’adresse pour le contester.',
      'Les signalements traités sont gardés un an, puis effacés. Supprimer ton compte efface aussi tes contenus et les signalements qui te visent.',
    ],
  },
];

/**
 * App App Store (refus Apple 1.4.3, 25.11) : ni la section des Pronos (éteints dans cette version), ni les paragraphes du bar
 * (caché dans l'app) ; « Paiements et billets » garde son premier paragraphe. Le site garde le texte complet (même version).
 * Même filtre dans l'app iPhone (TermsView.swift, prochain build).
 */
export const TERMS_SECTIONS = storeApp
  ? ALL_SECTIONS.filter((s) => s.title !== 'Pronos et confettis')
      .map((s) => (s.title === 'Paiements, billets et bar' ? { title: 'Paiements et billets', paragraphs: s.paragraphs.slice(0, 1) } : s))
  : ALL_SECTIONS;
