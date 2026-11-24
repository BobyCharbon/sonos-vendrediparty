"""Assemble les maquettes autonomes (CSS et JS en ligne) à partir de src/."""
import pathlib, re

SRC = pathlib.Path(__file__).parent
OUT = SRC.parent
CSS = (SRC / 'common.css').read_text()
JS = (SRC / 'common.js').read_text()


def status(t='21:14', light=False):
    return f'<div class="status"><span>{t}</span><i>●●● ▮</i></div>'


def slot(sid, num, title, note, inner):
    return f'''<section class="slot" id="{sid}">
  <h2><b>{num}</b>{title}</h2>
  <p class="note">{note}</p>
  <div class="phone">{inner}<div class="home-ind"></div></div>
</section>'''


def picker(sid, num, back_html, next_id='sQ'):
    inner = f'''{status('23:28')}<div class="pkback">{back_html}</div>
  <div class="picker">
    <div class="pkhead"><button id="pkCancel">Annuler</button><b>Photos</b><button class="add" id="pkAdd" data-next="{next_id}">Ajouter</button></div>
    <div class="pkseg"><span>Photos</span><span>Collections</span></div>
    <div class="pkgrid" id="pkgrid"></div>
    <div class="pkfoot"><span id="pkCount"></span><span>Photos seulement · aucune vidéo</span></div>
  </div>'''
    return slot(sid, num, '« Ajouter des photos » : la pellicule',
                "Le sélecteur d'iOS, en choix multiple (touche pour cocher ou décocher, le numéro suit l'ordre). Les vidéos n'y sont pas. Party ne voit que les photos choisies : aucune autorisation d'accès à toute la pellicule.",
                inner)


def queue(sid, num, head_extra='', foot_extra='', title='Envoi en cours', back='sAlbum'):
    inner = f'''{status('23:29')}<div class="scr">
    <div class="nav"><button class="back" data-go="{back}" aria-label="Retour">‹</button><div class="ttl"><span class="qtitle">{title}</span><small>Album · Vendredi chez Maé</small></div></div>
    <div class="pad">
      <div class="card"><div class="qtop"><div class="ring qring"><span>0 %</span></div><div style="flex:1"><b style="font-size:17px"><span class="qcount">0 / 8</span> photos</b><div class="muted small qmo">0 / 0 Mo</div><div class="muted small">2 envois à la fois · le reste attend son tour</div></div></div>
        <div class="quality"><span>✨</span><div><b>Qualité originale ✓</b>Chaque photo part telle quelle : même fichier, même taille (4032 × 3024), aucune compression. Seule la position GPS est retirée ; les pixels ne sont pas touchés.</div></div>
        {head_extra}
        <div class="netbar"></div>
      </div>
      <div class="card mt" id="qlist"></div>
      <div class="demo"><button onclick="netCut()">📶 Simuler une coupure</button><button onclick="netBack()">✅ Le réseau revient</button></div>
      <div class="card mt small muted" style="line-height:1.5">📱 <b style="color:var(--text)">Tu peux fermer Party.</b> L'envoi continue en arrière-plan, même téléphone verrouillé, et tu reçois une notification à la fin.{foot_extra}</div>
      <button class="btn ghost mt" data-go="sLock">Fermer Party</button>
    </div></div>'''
    return slot(sid, num, 'La file d\'envoi',
                'Chaque photo a sa barre. Touche « Simuler une coupure » puis « Le réseau revient » : l\'envoi reprend au morceau près. Les photos terminées apparaissent aussitôt dans l\'album.',
                inner)


def lock(sid, num):
    inner = f'''<div class="lock">{status('')}
    <div class="time">23:31</div><div class="date">vendredi 20 novembre</div>
    <div class="la" id="laWrap"><span class="ico">🖼️</span><div class="t"><b>Envoi vers l'album</b>Vendredi chez Maé · qualité originale<div class="bar"><i id="laBar"></i></div></div><span class="n" id="laN">0/8</span></div>
    <div class="notif" id="lockNotif" hidden><span class="ico">🖼️</span><div><b>Party<small>maintenant</small></b><p><b style="display:inline">Vendredi chez Maé</b><br><span id="lockNotifTxt"></span></p></div></div>
    <div class="lockfoot">Party est fermée : iOS termine l'envoi tout seul. L'activité en direct disparaît à la fin, puis une notification (qu'on peut couper dans Réglages › Notifications › « Album photos »).</div>
  </div>'''
    return slot(sid, num, 'L\'envoi continue en arrière-plan',
                'Écran verrouillé pendant l\'envoi : une activité en direct (épisode court, moins de 8 h) montre où on en est, puis une seule notification à la fin.',
                inner)


def viewer(sid, num, note, back='sAlbum', extra=''):
    inner = f'''<div class="viewer" id="viewer">{status('23:41')}
    <div class="track" id="vtrack"></div>
    <div class="vtop"><button class="vb" data-go="{back}" aria-label="Fermer">✕</button><span class="av" id="vAv"></span><div class="who" id="vWho"></div><button class="vb" id="vMore" aria-label="Plus d'options">⋯</button></div>
    <button class="vb side l" id="vPrev" aria-label="Photo précédente">‹</button><button class="vb side r" id="vNext" aria-label="Photo suivante">›</button>
    <div class="zhint" id="zhint"></div>
    <div class="maskmsg" id="vMask">🚩 Photo signalée<br><span class="small muted">Masquée pour tout le monde en attendant la décision.</span></div>
    <div class="vfoot">{extra}<div class="meta"><span id="vPos"></span><span id="vDim"></span></div>
      <div class="acts"><button class="dl" id="vDl">⬇️ Télécharger l'original</button><button id="vZoom" aria-label="Zoomer">🔍</button></div></div>
    <div class="shade"></div>
    <div class="sheet" id="vMenu"><div class="grab"></div><div id="vMenuList"></div><button class="btn ghost mt" data-close>Annuler</button></div>
    <div class="sheet" id="vReport"><div class="grab"></div><h3>Signaler cette photo</h3><p class="sub">L'auteur ne sait pas qui a signalé. La photo est masquée tout de suite, pour tout le monde.</p>
      <button class="opt" data-motif="me"><span>🙋</span><div>Je suis sur la photo<small>Et je ne veux pas qu'elle soit dans l'album</small></div></button>
      <button class="opt" data-motif="nu"><span>🔞</span><div>Nudité ou contenu sexuel</div></button>
      <button class="opt" data-motif="har"><span>😠</span><div>Moquerie ou harcèlement</div></button>
      <button class="opt" data-motif="vio"><span>⚠️</span><div>Violent ou choquant</div></button>
      <button class="opt" data-motif="autre"><span>💬</span><div>Autre chose</div></button>
      <button class="btn ghost mt" data-close>Annuler</button></div>
    <div class="sheet" id="vDelete"><div class="grab"></div><h3>Supprimer ta photo ?</h3><p class="sub">Elle disparaît de l'album pour tout le monde, tout de suite, original compris. Ceux qui l'ont déjà téléchargée gardent leur copie.</p>
      <button class="btn mt" style="background:var(--red);color:#fff" id="vDelYes">Supprimer ma photo</button><button class="btn ghost mt" data-close>Annuler</button></div>
    <div class="toast"></div>
  </div>'''
    return slot(sid, num, 'La visionneuse plein écran', note, inner)


def download(sid, num, choices, back='sAlbum'):
    inner = f'''{status('23:52')}<div class="scr">
    <div class="nav"><button class="back" data-go="{back}" aria-label="Retour">‹</button><div class="ttl">Tout télécharger<small>Album · Vendredi chez Maé</small></div></div>
    <div class="pad">
      <div id="dlChoose">
        <div class="card"><div class="dlbig"><div style="font-size:44px">⬇️</div><b style="font-size:20px"><span data-count="all">18</span> photos en qualité originale</b><span class="muted small">Les fichiers d'origine, exactement ceux qui ont été envoyés (HEIC ou JPG).</span></div></div>
        <div class="sec">Quoi</div>
        <div class="card" style="padding:4px 16px">{choices}</div>
        <div class="sec">Où</div>
        <div class="card" style="padding:4px 16px">
          <button class="radio" aria-checked="true"><div class="lbl">Dans Photos<small>Un album « Vendredi chez Maé » est créé dans ta pellicule</small></div><span class="dot"></span></button><div class="sepl"></div>
          <button class="radio" aria-checked="false"><div class="lbl">Dans Fichiers<small>Un dossier, sans toucher à ta pellicule</small></div><span class="dot"></span></button>
        </div>
        <p class="muted small" style="margin:10px 4px 0;line-height:1.45">≈ 3 Mo par photo. Mieux en Wi-Fi. iOS te demandera une fois l'autorisation « Ajouter à Photos » (ajout seulement : Party ne lit pas ta pellicule). Sur le web : un fichier .zip.</p>
        <button class="btn primary mt" id="dlStart">⬇️ Télécharger</button>
      </div>
      <div id="dlRun" hidden><div class="card"><div class="dlbig"><div class="ring" id="dlRing"><span>0 %</span></div><b id="dlRunT" style="font-size:18px;margin-top:8px">Téléchargement des originaux</b><span class="muted small" id="dlTxt"></span></div>
        <p class="muted small" style="margin-top:10px;text-align:center">Continue même si tu fermes Party.</p></div>
        <button class="btn ghost mt" id="dlAgain" hidden>Recommencer la démo</button></div>
    </div></div>'''
    return slot(sid, num, '« Tout télécharger »', 'Tout l\'album, en originaux, dans Photos ou Fichiers. Touche « Télécharger ».', inner)


def tuto(sid, num, cards, note):
    dots = ''.join('<i></i>' for _ in cards)
    tc = ''.join(f'<div class="tcard"><div class="ill">{c[0]}</div><h3>{c[1]}</h3><p>{c[2]}</p></div>' for c in cards)
    inner = f'''{status('21:10')}<div class="scr" style="padding:0"><div class="tuto" id="tuto">
      <button class="skip" id="tSkip">Passer</button>
      <div class="tcards">{tc}</div>
      <div class="tdots">{dots}</div>
      <div class="tfoot"><button class="btn primary" id="tNext">Suivant</button><button class="never" id="tNever">Ne plus me le rappeler</button></div>
    </div>
    <div class="tdone" id="tdone"><div style="font-size:54px">🖼️</div><h3 style="font-size:22px">C'est prêt</h3><p class="muted" id="tdoneTxt" style="line-height:1.5"></p><button class="btn ghost sm mt" id="tAgain">Revoir le didacticiel</button></div></div>'''
    return slot(sid, num, 'Le didacticiel', note, inner)


def build(name, title, body, extra_css='', extra_js=''):
    def rep(m):
        return eval(m.group(1))
    body = re.sub(r'\{\{(.+?)\}\}', rep, body, flags=re.S)
    html = f'''<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
{CSS}
{extra_css}
</style>
</head>
<body>
{body}
<script>
{JS}
{extra_js}
boot();
</script>
</body>
</html>
'''
    (OUT / name).write_text(html)
    print(name, len(html))


if __name__ == '__main__':
    import sys
    for d in sys.argv[1:] or ('A', 'B', 'C'):
        mod = dict(globals(), __name__=d)
        exec((SRC / f'{d}.py').read_text(), mod)
        build(mod['NAME'], mod['TITLE'], mod['BODY'], mod.get('CSS', ''), mod.get('JS', ''))
