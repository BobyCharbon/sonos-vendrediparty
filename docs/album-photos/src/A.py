NAME = 'A-boite.html'
TITLE = 'Album A · La boîte'

CSS = '''
.g3{display:grid;grid-template-columns:repeat(3,1fr);gap:2px;margin:0 -16px}
.g3 .ph{aspect-ratio:1;border-radius:0;font-size:30px}
.g4{display:grid;grid-template-columns:repeat(4,1fr);gap:4px}
.g4 .ph{aspect-ratio:1;border-radius:10px;font-size:22px}
.drop{border:2px dashed rgba(255,79,154,.6);border-radius:20px;padding:16px;display:flex;gap:14px;align-items:center;background:rgba(255,79,154,.07);width:100%;min-height:88px;transition:background .2s}
.drop:active{background:rgba(255,79,154,.16)}
.drop .bx{width:56px;height:56px;border-radius:16px;background:var(--neon);display:grid;place-items:center;font-size:28px;flex:0 0 auto;box-shadow:0 8px 24px -8px rgba(255,79,154,.9);animation:bob 2.6s ease-in-out infinite}
@keyframes bob{50%{transform:translateY(-4px)}}
.drop b{font-size:16px;display:block}
.drop small{color:var(--muted);font-size:13px;line-height:1.35;display:block;margin-top:2px}
.ahead{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:2px 0 12px}
.gsec{display:flex;justify-content:space-between;align-items:center;margin:18px 0 8px;min-height:44px}
.gsec b{font-size:16px}
.gsec small{display:block;color:var(--muted);font-size:12.5px;font-weight:400}
.gsec button{min-height:44px;padding:0 6px;color:var(--neon);font-weight:600;font-size:14px}
.illgrid{display:grid;grid-template-columns:repeat(3,48px);gap:5px}
.illgrid i{width:48px;height:48px;border-radius:8px;animation:pop .5s backwards}
.illbox{position:relative;width:150px;height:110px}
.illbox .lid{position:absolute;left:0;right:0;bottom:0;height:62px;border-radius:12px;background:linear-gradient(180deg,#FF4F9A,#c2337a);box-shadow:0 10px 30px -10px #FF4F9A}
.illbox .pic{position:absolute;width:52px;height:52px;border-radius:9px;border:3px solid #fff;animation:fall 2.8s ease-in infinite}
@keyframes fall{0%{transform:translateY(-60px) rotate(-12deg);opacity:0}25%{opacity:1}70%,100%{transform:translateY(40px) rotate(6deg);opacity:0}}
'''

def fake(n, seed):
    out = []
    em = ['🎯🟢', '🔫🎨', '😂🎯', '🏆🎉', '🍻🌭', '🌲🏃', '🎳🎳', '☀️🏖️', '🚗💨', '🎂🎈', '🐶🌳', '🌅🏔️']
    cols = ['#FFB547', '#FF4F9A', '#9B6BFF', '#2BD4A4', '#3d7bff', '#ff8a3d', '#ff6b7a', '#5B2E8C']
    for k in range(n):
        i = seed + k
        c1, c2 = cols[(i * 3) % 8], cols[(i * 5 + 2) % 8]
        out.append(f'<span class="ph fake" style="background:radial-gradient(circle at 28% 24%,{c1}d0,transparent 56%),radial-gradient(circle at 76% 78%,{c2}d0,transparent 56%),#140b26"><span class="em">{em[i % len(em)]}</span></span>')
    return ''.join(out)

TAB = '<div class="tabbar"><div><b>🎵</b>Musique</div><div class="on"><b>🎉</b>Événements</div><div><b>🎮</b>Jeux</div><div><b>💬</b>Discussions</div><div><b>⚙️</b>Réglages</div></div>'

ALBUM_SCREEN = f'''{status('23:26')}<div class="scr">
  <div class="nav"><button class="back" data-go="sFiche" aria-label="Retour">‹</button><div class="ttl">Album photos<small>Vendredi chez Maé</small></div>
    <button class="act" data-go="sDl" aria-label="Tout télécharger">⬇️</button><button class="act" data-go="sSet" aria-label="Réglages de l'album" style="margin-left:6px">⚙️</button></div>
  <div class="pad">
    <div class="ahead"><span class="pill openpill ok"></span><span class="pill ok">✨ Qualité originale</span><span class="muted small"><span data-count="all">18</span> photos · 6 personnes</span></div>
    <button class="drop addbtn" data-go="sPick"><span class="bx">📥</span><span><b>Dépose tes photos</b><small>Depuis ta pellicule, autant que tu veux. Visibles tout de suite par les participants.</small></span></button>
    <div class="chipsrow" id="aChips" style="margin:12px -16px 0"><button aria-pressed="true" data-f="all">Toutes · <span data-count="all"></span></button><button aria-pressed="false" data-f="who:toi">Les miennes · <span data-count="who:toi"></span></button><button aria-pressed="false" data-f="who:ines">🌸 Inès</button><button aria-pressed="false" data-f="who:leo">🐻 Léo</button><button aria-pressed="false" data-f="who:sam">🎧 Sam</button></div>
    <div class="gsec" style="margin-top:6px"><div><b>Les plus récentes</b><small>Rangées par heure de prise de vue</small></div></div>
    <div class="g3" id="aGrid" data-fill="all"></div>
  </div></div>'''

GROUP_SCREEN = f'''{status('23:24')}<div class="scr">
  <div class="nav"><button class="back" aria-label="Retour">‹</button><div class="ttl">Les Loustics</div><button class="act" aria-label="Réglages du groupe">⋯</button></div>
  <div class="cover"><span class="e">🎳</span><div><h3>Les Loustics</h3><small>14 membres · groupe libre</small></div></div>
  <div class="gtabs"><button aria-selected="false" data-keep>💬 Discussion</button><button aria-selected="false" data-keep>🎉 Événements</button><button aria-selected="true" data-keep>🖼️ Photos</button><button aria-selected="false" data-keep>👥 Membres</button></div>
  <div class="pad">
    <button class="drop mt"><span class="bx">📥</span><span><b>Boîte du groupe</b><small>Pour les photos hors soirée : un week-end, un souvenir. Tous les membres peuvent ajouter.</small></span></button>
    <div class="gsec"><div><b>🎂 Vendredi chez Maé</b><small>Ven. 20 nov. · <span data-count="all">18</span> photos · <span style="color:var(--mint)">en cours</span></small></div><button data-go="sAlbum">Tout voir ›</button></div>
    <div class="g4" data-fill="first:8"></div>
    <div class="gsec"><div><b>🎯 Paintball</b><small>Sam. 7 nov. · 42 photos · fermé</small></div><button class="fakebtn">Tout voir ›</button></div>
    <div class="g4">{fake(8, 0)}</div>
    <div class="gsec"><div><b>📥 Hors soirée</b><small>Boîte du groupe · 11 photos</small></div><button class="fakebtn">Tout voir ›</button></div>
    <div class="g4">{fake(4, 7)}</div>
    <p class="muted small" style="margin-top:14px;line-height:1.45">Les albums des soirées du groupe s'affichent ici tout seuls. Une photo n'existe qu'une fois : ajoutée sur la fiche, elle apparaît aussi dans le groupe.</p>
  </div></div>{TAB}<div class="toast"></div>'''

FICHE_SCREEN = f'''{status('23:20')}<div class="scr">
  <div class="nav"><button class="back" data-go="sGroup" aria-label="Retour">‹</button><div class="ttl">Événement</div><button class="act" aria-label="Plus">⋯</button></div>
  <div class="hero"><span class="e">🎂</span><div><h3>Vendredi chez Maé</h3>Ven. 20.11 · 19 h 30 → 2 h · Lausanne · 🎳 Les Loustics</div></div>
  <div class="pad">
    <div class="card mt" style="display:flex;gap:10px;align-items:center"><span style="font-size:20px">✅</span><div style="flex:1"><b>Tu viens</b><div class="muted small">12 présents · 3 peut-être</div></div></div>
    <div class="card mt">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px"><b style="font-size:17px;flex:1">🖼️ Album photos</b><span class="pill openpill ok"></span></div>
      <div class="g4" data-fill="first:4"></div>
      <p class="muted small" style="margin:10px 0 12px;line-height:1.45"><span data-count="all">18</span> photos de 6 personnes, visibles tout de suite. Qualité originale.</p>
      <div style="display:flex;gap:8px"><button class="btn primary sm addbtn" style="flex:1" data-go="sPick">📥 Ajouter mes photos</button><button class="btn ghost sm" data-go="sAlbum">Voir tout</button></div>
    </div>
    <div class="souv mt"><span class="disp"></span><div class="t"><b>📸 Souvenirs · appareil jetable</b>Tes 3 poses prises ce soir · dévoilées sam. 21.11 à 23 h 🔒</div></div>
    <div class="vs"><div class="a"><b>🖼️ Album</b>Ouvert tout de suite · tes photos de la pellicule · autant que tu veux · qualité originale</div><div class="s"><b>📸 Souvenirs</b>Pris dans Party · 3 poses sans les revoir · dévoilés 24 h après la fin</div></div>
    <p class="muted small" style="margin-top:10px">Aussi dans le groupe « Les Loustics » › Photos.</p>
  </div></div>{TAB}'''

SETTINGS = f'''{status('18:05')}<div class="scr">
  <div class="nav"><button class="back" data-go="sAlbum" aria-label="Retour">‹</button><div class="ttl">Album photos<small>Options · Vendredi chez Maé</small></div></div>
  <div class="pad">
    <div class="card">
      <div class="row"><div class="lbl"><b>🖼️ Album ouvert</b><small>Fermé : plus personne n'ajoute, tout reste visible et téléchargeable.</small></div><button class="sw" role="switch" aria-checked="true" id="swOpen" aria-label="Album ouvert"><i></i></button></div>
      <div class="state openstate open"></div>
    </div>
    <div class="sec">Qui peut ajouter des photos</div>
    <div class="card" style="padding:4px 16px">
      <button class="radio" aria-checked="true"><div class="lbl">Les participants<small>Présent et Peut-être, et l'organisation</small></div><span class="dot"></span></button><div class="sepl"></div>
      <button class="radio" aria-checked="false"><div class="lbl">Tous les invités<small>Même ceux qui n'ont pas répondu</small></div><span class="dot"></span></button><div class="sepl"></div>
      <button class="radio" aria-checked="false"><div class="lbl">Seulement l'organisation<small>Les autres regardent et téléchargent</small></div><span class="dot"></span></button>
    </div>
    <div class="sec">Fermer tout seul</div>
    <div class="card" style="padding:4px 16px">
      <button class="radio" aria-checked="false"><div class="lbl">Jamais</div><span class="dot"></span></button><div class="sepl"></div>
      <button class="radio" aria-checked="true"><div class="lbl">7 jours après la fin<small>Dim. 29.11 à 2 h · le temps que tout le monde envoie</small></div><span class="dot"></span></button><div class="sepl"></div>
      <button class="radio" aria-checked="false"><div class="lbl">30 jours après la fin</div><span class="dot"></span></button>
    </div>
    <div class="sec">Toi et l'organisation</div>
    <div class="card small muted" style="line-height:1.5">Tu peux retirer n'importe quelle photo de l'album (⋯ › Retirer). Les signalements arrivent chez toi et chez la modération. Une photo « Je suis sur la photo » est masquée tout de suite.</div>
    <div class="sec">Dans le groupe « Les Loustics »</div>
    <div class="card" style="padding:4px 16px">
      <div class="row"><div class="lbl"><b>Boîte du groupe ouverte</b><small>Réglée par les gérants du groupe : tous les membres ajoutent des photos hors soirée.</small></div><button class="sw" role="switch" aria-checked="true" aria-label="Boîte du groupe ouverte"><i></i></button></div>
    </div>
    <button class="btn primary mt" data-go="sAlbum">Enregistrer</button>
  </div></div>'''

CARDS = [
    ('<div class="illbox"><span class="pic" style="left:20px;background:linear-gradient(135deg,#FFB547,#FF4F9A)"></span><span class="pic" style="left:78px;animation-delay:1.4s;background:linear-gradient(135deg,#9B6BFF,#2BD4A4)"></span><span class="lid"></span></div>',
     'Une boîte pour les photos de tout le monde', 'Chacun dépose ses photos de la soirée depuis sa pellicule. Elles sont visibles tout de suite.'),
    ('✨', 'Qualité originale, jamais floue', 'Party envoie le fichier tel quel, sans compression. Tu télécharges exactement le même.'),
    ('📶', 'Envoie, puis range ton téléphone', 'Plus de réseau ? Ça reprend tout seul. Party fermée ? L\'envoi continue.'),
    ('🙋', 'Ton image, ton choix', 'Tu supprimes tes photos quand tu veux. Sur une photo sans ton accord ? « Signaler › Je suis sur la photo » la masque aussitôt.'),
]

BODY = f'''
<header class="intro">
  <h1>🖼️ Album photos <span>· A · La boîte de dépôt</span></h1>
  <p>La version la plus simple : <b>une boîte</b> où chacun dépose ses photos depuis la pellicule, et <b>une grille</b> comme l'app Photos, la plus récente en haut. Un album par soirée, sur la fiche. Le groupe a sa propre boîte pour le hors-soirée et <b>montre aussi les albums de ses soirées</b>, sans copie.</p>
  <div class="chips"><span>✨ <b>Qualité originale</b> · même fichier</span><span>📥 Autant de photos que tu veux</span><span>📶 Reprise après coupure</span><span>📱 Envoi en arrière-plan</span><span>⬇️ Originaux téléchargeables</span><span>🚩 Signaler · « Je suis sur la photo »</span></div>
  <p class="howto">Tout se touche : boîte, grille (filtres), pellicule, file d'envoi, visionneuse (glisse, double-touche ou pince pour zoomer, ⋯), interrupteurs. Fais défiler les écrans de côté.</p>
</header>
<main class="rail">
{tuto('sTuto', 1, CARDS, "À la première ouverture d'un album. « Passer » le reporte, « Ne plus me le rappeler » le coupe pour de bon. Glisse ou touche « Suivant ».")}
{slot('sGroup', 2, "L'album dans le groupe", "Onglet « Photos » du groupe : la boîte du groupe (hors soirée) et les albums de ses soirées, chacune à sa place. Proposition : un seul album par soirée, montré à deux endroits.", GROUP_SCREEN)}
{slot('sFiche', 3, "L'album sur la fiche, à côté des Souvenirs", "La différence se voit sur la fiche : l'album est ouvert tout de suite, les Souvenirs restent sous cadenas jusqu'au dévoilement.", FICHE_SCREEN)}
{slot('sAlbum', 4, "La grille de l'album", "Grille carrée sur 3 colonnes. Filtre « Les miennes » ou par personne. Touche une photo pour l'ouvrir, ⬇️ pour tout télécharger, ⚙️ pour les options (organisation).", ALBUM_SCREEN)}
{picker('sPick', 5, ALBUM_SCREEN.replace('id="aGrid" ', '').replace('id="aChips" ', ''))}
{queue('sQ', 6)}
{lock('sLock', 7)}
{viewer('sV', 8, "Glisse pour passer d'une photo à l'autre, double-touche ou pince pour zoomer, touche une fois pour masquer les boutons. ⋯ : Signaler (sur les photos des autres), Supprimer (sur les tiennes).")}
{download('sDl', 9, '<button class="radio" aria-checked="true"><div class="lbl">Tout l\'album<small><span data-count="all">18</span> photos · ≈ 52 Mo</small></div><span class="dot"></span></button><div class="sepl"></div><button class="radio" aria-checked="false"><div class="lbl">Seulement les nouvelles<small>Ajoutées depuis ton dernier téléchargement</small></div><span class="dot"></span></button>')}
{slot('sSet', 10, "Le réglage de l'organisation", "Vue de Maé, l'organisatrice. Coupe « Album ouvert » : l'état change partout (fiche, grille, bouton Ajouter).", SETTINGS)}
</main>
'''

JS = '''
document.addEventListener('chip',e=>{const b=e.target;if(!b.dataset.f)return;const g=document.getElementById('aGrid');g.dataset.fill=b.dataset.f;renderAll()});
document.addEventListener('click',e=>{if(e.target.closest('.fake,.fakebtn'))toast(e.target.closest('.phone'),'Maquette : seul l\\'album « Vendredi chez Maé » s\\'ouvre.')});
'''
JS += "window.viewerOrder=()=>fillSpec(document.getElementById('aGrid').dataset.fill);\n"
