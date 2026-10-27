# App Android « Party ! »

L'app ouvre la webapp dans Chrome en plein écran (Trusted Web Activity) : c'est le site lui-même, notifications
Web Push comprises. Une évolution du site arrive dans l'app sans nouvelle version sur le Play Store.

| Variante Gradle | App | Identifiant | Site |
|---|---|---|---|
| `beta` | Party BETA | `ch.bobycharbon.party.beta` | partytest.bobycharbon.ch (`develop`) |
| `prod` | Party ! | `ch.bobycharbon.party` | party.bobycharbon.ch (`main`) |

## Compilation et envoi
`.github/workflows/android-play.yml` (GitHub Actions, Ubuntu) : à chaque push touchant `android/` sur `develop`
(→ beta) ou `main` (→ prod), il compile le paquet `.aab`, le signe avec la clé d'envoi et l'envoie au Play Store,
piste **test interne**. Le paquet est aussi dans l'artefact de l'exécution. Rien à installer sur le Mac.

Secrets GitHub :
- `ANDROID_KEYSTORE_B64`, `ANDROID_KEYSTORE_PASSWORD` : clé d'envoi, créée le 27 octobre 2026 dans
  `~/.android-keys/` du Mac mini (alias `upload`, PKCS12). **À sauvegarder** : la perdre oblige à demander à Google
  une réinitialisation de la clé d'envoi.
- `PLAY_SERVICE_ACCOUNT_JSON` : compte de service Google Cloud invité dans la Play Console (droit de publier).

Variable GitHub `PLAY_RELEASE_STATUS` : `draft` tant que l'app n'a jamais été publiée sur une piste
(Google refuse sinon les versions « completed »), puis à supprimer.

## Barre d'adresse et liens
Chrome n'affiche l'app sans barre d'adresse que si le site la déclare : `/.well-known/assetlinks.json`
(`app/main.py`, `ANDROID_UPLOAD_KEY_SHA256` + `ANDROID_PLAY_SIGNING_SHA256`). Ajouter l'empreinte SHA-256 de la
**clé de signature d'application** donnée par Play Console (Configuration › Intégrité de l'app).

## Play Console (une fois)
1. Compte développeur Google Play (25 $, vérification d'identité).
2. Créer l'app « VendrediPartyBETA » (gratuite, app), puis « VendrediParty ».
3. Premier `.aab` envoyé à la main (artefact du workflow) dans Tests › Test interne.
4. Compte de service : Google Cloud › IAM › Comptes de service › clé JSON ; l'inviter dans Play Console
   (Utilisateurs et autorisations) avec le droit de publier ; JSON dans le secret `PLAY_SERVICE_ACCOUNT_JSON`.
5. Testeurs : Test interne › Testeurs (adresses Gmail ou Google Group), puis partager le lien d'inscription.

Compte personnel récent : avant la publication publique, Google exige un test fermé de 12 testeurs pendant 14 jours.
