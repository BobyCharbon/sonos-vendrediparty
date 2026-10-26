# App iOS « Party ! »

L'app native affiche la webapp (party.bobycharbon.ch) en plein écran dans un `WKWebView`, réglée pour se
comporter **exactement** comme l'app ajoutée à l'écran d'accueil : même code, mêmes écrans. Une évolution du
site arrive donc dans l'app sans nouvelle version sur l'App Store.

| Build Xcode | Site chargé |
|---|---|
| Debug | https://partytest.bobycharbon.ch (site de test, branche `develop`) |
| Release | https://party.bobycharbon.ch (site principal, branche `main`) |

## Ce que fait l'app en plus d'un simple navigateur

- `navigator.standalone === true` : pas d'invitation « Ajouter à l'écran d'accueil », et `ios-app.js` reste actif
  (règle de la barre d'onglets, voir CLAUDE.md).
- Zones sûres gérées par la page (`viewport-fit=cover`), fond `#0e0b16` dès le lancement : pas de flash blanc.
- Cookies et localStorage conservés (session, prénom, compte).
- `alert()` / `confirm()` / `prompt()` affichés en boîtes iOS natives (sinon un WKWebView ne montre rien).
- Liens vers d'autres sites (open.spotify.com, Google Agenda, `tel:`, `sms:`, `mailto:`…) : ouverts dans Safari
  ou l'app concernée ; la connexion Spotify et Supabase reste dans l'app.
- Fichier `.ics` (« Ajouter à mon agenda ») : feuille Safari avec le bouton « Ajouter ».
- `navigator.vibrate()` des jeux : rendu en vrai retour haptique.
- Liens universels : un QR code ou un lien Party ouvre directement l'app.
- Écran « Party ! est injoignable » avec bouton Réessayer si le réseau tombe.
- Notifications natives (APNs) via `window.PartyNative.push.register()` : voir l'étape 5.

## Étapes

### 1. Prérequis (une fois)
- Installer **Xcode** depuis le Mac App Store (le Mac n'a pour l'instant que les outils en ligne de commande), puis
  `sudo xcode-select -s /Applications/Xcode.app`.
- `brew install xcodegen`.
- S'inscrire au **Apple Developer Program** (99 $/an), indispensable pour TestFlight, l'App Store, les notifications
  et les liens universels. Un compte gratuit suffit pour installer l'app sur son propre iPhone (valable 7 jours).

### 2. Générer et lancer le projet
```sh
cd ios
xcodegen                 # crée Party.xcodeproj depuis project.yml
open Party.xcodeproj
```
Dans Xcode : cible **Party** › *Signing & Capabilities* › choisir son équipe (ou mettre l'identifiant d'équipe dans
`DEVELOPMENT_TEAM` de `project.yml`). Choisir un simulateur ou l'iPhone branché, puis ▶︎.
L'inspecteur web est actif en Debug : Safari › Développement › (iPhone) › Party.

### 3. Liens universels (QR codes → app)
Servi par FastAPI (`app/main.py`, `IOS_APP_ID`) : `https://party.bobycharbon.ch/.well-known/apple-app-site-association` (et sur le site de
test), en JSON, sans redirection. À vérifier après déploiement avec `curl -i <site>/.well-known/apple-app-site-association` :
```json
{ "applinks": { "details": [ { "appIDs": ["GS2B6GA9JA.ch.bobycharbon.party"], "components": [ { "/": "/*" } ] } ] } }
```

### 4. Icône et écran de lancement
L'icône 1024 px est agrandie depuis `app/static/icon-512.png` : la remplacer par un original en 1024 × 1024, sans
transparence, dans `Party/Assets.xcassets/AppIcon.appiconset/icon-1024.png`.

### 5. Notifications natives
Web Push (`PushManager`) n'existe pas dans un WKWebView : l'app passe par APNs.
1. developer.apple.com › Keys : créer une clé **APNs** (.p8) ; noter Key ID et Team ID. La garder en secret
   (variable d'environnement du conteneur, jamais dans le dépôt).
2. Site : dans `push.js` et `web/events/src/lib/push.ts`, si `window.PartyNative` existe, appeler
   `PartyNative.push.register()` → `{ token, environment, bundleId }` et l'envoyer au serveur à la place de
   l'abonnement Web Push.
3. Serveur (`app/push.py`) : enregistrer ces jetons à côté des abonnements Web Push et les envoyer en HTTP/2 à
   `api.push.apple.com` (`api.sandbox.push.apple.com` quand `environment == "sandbox"`), charge utile
   `{"aps": {"alert": {"title": …, "body": …}, "sound": "default"}, "url": "/…"}`. Un jeton refusé (410) est supprimé,
   comme un abonnement Web Push disparu.

### 6. TestFlight puis App Store
1. Dans `project.yml`, passer `aps-environment` à `production` pour l'archive App Store.
2. Xcode › Product › **Archive** (schéma Release) › Distribute App › App Store Connect.
3. App Store Connect : fiche de l'app (captures 6,9″ et 6,5″, description, URL de confidentialité, classement
   d'âge), puis **TestFlight** pour faire tester les invités.
4. Soumission à la revue. Apple refuse les apps « simple site web emballé » (règle 4.2) : mettre en avant ce que
   l'app apporte (notifications, haptique, liens universels, agenda) et fournir un compte de démonstration.

## Fichiers
- `project.yml` : projet XcodeGen (cible, Info.plist, droits, URL par configuration).
- `Party/PartyApp.swift` : point d'entrée, liens universels et notifications.
- `Party/PartyWebView.swift` : WKWebView, navigation interne / externe, boîtes de dialogue, `.ics`.
- `Party/NativeBridge.swift` : scripts injectés (`navigator.standalone`, `vibrate`, `PartyNative`).
- `Party/PushRegistrar.swift` : permission et jeton APNs, toucher d'une notification.
- `Party/WebModel.swift`, `Party/OfflineView.swift`, `Party/AppConfig.swift`.
