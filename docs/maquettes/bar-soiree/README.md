# Maquettes « Bar de la soirée » (v2, 10.11.2026)

Proposition à valider, pas encore de code. Le bar se crée depuis un événement, dans la zone organisateur ;
les co-organisateurs gèrent tout comme l'organisateur. L'organisateur fixe les articles, les prix et le stock,
puis les conditions de remboursement (moyen, date limite). L'invité commande et coche à chaque commande
l'engagement à rembourser. Rien n'est dû avant le scan au bar ; chaque scan ajoute le prix à son solde,
toujours affiché en grand. Il rembourse après la soirée (Stripe plus tard).

![Les 8 écrans](bar-soiree.png)

- `bar-soiree.html` : page autonome (police et QR intégrés), qui s'adapte au téléphone.
- `template.html` + `build.py` : source. `python build.py app/fonts/BricolageGrotesque.ttf` (paquets `qrcode` et `fonttools[woff]`).
