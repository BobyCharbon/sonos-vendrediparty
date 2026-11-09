# Maquettes « Bar de la soirée » (10.11.2026)

Proposition à valider, pas encore de code. Le bar se crée depuis un événement, dans la zone organisateur.
L'organisateur fixe les articles, les prix et le stock. Chaque invité remplit son panier et reçoit un QR.
À chaque scan au bar, un article est servi : le stock baisse et le prix s'ajoute à l'ardoise de l'invité.

![Les 6 écrans](bar-soiree.png)

- `bar-soiree.html` : page autonome (police et QR intégrés), qui s'adapte au téléphone.
- `template.html` + `build.py` : source. `python build.py app/fonts/BricolageGrotesque.ttf` (paquets `qrcode` et `fonttools[woff]`).
