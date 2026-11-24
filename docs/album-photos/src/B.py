NAME = 'B-mur.html'
TITLE = 'Album B · Le mur'

CSS = '''
.seg{display:flex;background:var(--surface);border-radius:14px;padding:3px;margin:0 16px 12px}
.seg button{flex:1;min-height:44px;border-radius:11px;font-weight:600;font-size:14px;color:var(--muted);text-align:center}
.seg button[aria-selected=true]{background:var(--surface2);color:var(--text);box-shadow:0 2px 8px rgba(0,0,0,.3)}
.mos{display:grid;grid-template-columns:repeat(3,1fr);grid-auto-rows:104px;grid-auto-flow:dense;gap:4px}
.mos .ph{border-radius:12px;font-size:28px;width:100%;height:100%}
.mos .ph.p{grid-row:span 2}
.mos .ph.l{grid-column:span 2}
.mos .ph.big{grid-column:span 2;grid-row:span 2;font-size:44px}
.mhead{display:flex;align-items:center;gap:10px;margin:18px 0 8px;min-height:44px}
.mhead .ic{width:40px;height:40px;border-radius:12px;background:var(--surface);display:grid;place-items:center;font-size:20px;flex:0 0 auto}
.mhead b{font-size:17px;display:block}
.mhead small{color:var(--muted);font-size:12.5px}
.mhead .avs{margin-left:auto;display:flex}
.mhead .avs i{width:26px;height:26px;border-radius:50%;display:grid;place-items:center;font-size:13px;font-style:normal;border:2px solid var(--bg);margin-left:-8px}
.pers{margin-top:16px}
.pers .ph{flex:0 0 auto;height:132px;border-radius:12px;font-size:30px}
.pers .ph.p{width:99px}.pers .ph.l{width:176px}.pers .ph.s{width:132px}
.hstrip{display:flex;gap:4px;overflow-x:auto;scrollbar-width:none;margin:0 -16px;padding:0 16px}
.hstrip::-webkit-scrollbar{display:none}
.phead{display:flex;align-items:center;gap:10px;margin-bottom:8px;min-height:44px}
.phead .av{width:40px;height:40px;border-radius:50%;display:grid;place-items:center;font-size:20px;flex:0 0 auto}
.phead b{flex:1;font-size:16px}
.phead b small{display:block;font-weight:400;color:var(--muted);font-size:12.5px}
.addtile{flex:0 0 auto;width:99px;height:132px;border-radius:12px;border:2px dashed rgba(255,79,154,.6);display:grid;place-items:center;text-align:center;font-size:12.5px;font-weight:600;color:var(--neon);padding:6px;background:rgba(255,79,154,.07)}
.addtile b{display:block;font-size:26px;font-weight:400}
.livebar{display:flex;align-items:center;gap:10px;font-size:13.5px;margin:0 16px 4px;background:rgba(255,79,154,.1);border:1px solid rgba(255,79,154,.4);border-radius:14px;padding:10px 12px}
.livebar span:first-child{color:var(--neon)}
.wcard{display:block;width:100%;background:var(--surface);border-radius:20px;padding:10px;margin-top:12px}
.wcard .mos{grid-auto-rows:62px}
.wcard .mos .ph{font-size:20px;border-radius:9px}
.wcard .mos .ph.big{font-size:30px}
.wcard .t{display:flex;align-items:center;gap:8px;padding:10px 4px 2px}
.wcard .t b{flex:1;font-size:16px}
.wcard .t b small{display:block;font-weight:400;font-size:12.5px;color:var(--muted)}
.dock{position:absolute;left:0;right:0;bottom:0;z-index:25;background:var(--surface);border-radius:22px 22px 0 0;padding:8px 16px 30px;box-shadow:0 -12px 30px rgba(0,0,0,.5);max-height:58%;overflow-y:auto;scrollbar-width:none}
.dock::-webkit-scrollbar{display:none}
.dock .grab{width:40px;height:5px;border-radius:3px;background:#5d5480;margin:0 auto 10px}
.dock .quality{margin-top:10px}
.dock #qlist{padding:0;background:none;margin-top:6px;max-height:190px;overflow-y:auto;scrollbar-width:none}
.illmos{display:grid;grid-template-columns:repeat(3,44px);grid-auto-rows:44px;gap:5px}
.illmos i{border-radius:8px;animation:pop .6s backwards}
.illmos i.b{grid-column:span 2;grid-row:span 2}
.illmos i.t{grid-row:span 2}
.rename{display:flex;align-items:center;gap:10px;min-height:52px;width:100%}
.rename span:first-child{font-size:20px;width:28px;text-align:center}
.rename div{flex:1}
.rename small{display:block;color:var(--muted);font-size:12.5px}
.rename i{font-style:normal;color:var(--neon);font-size:14px;font-weight:600;min-width:44px;min-height:44px;display:grid;place-items:center}
'''

TAB = '<div class="tabbar"><div><b>🎵</b>Musique</div><div class="on"><b>🎉</b>Événements</div><div><b>🎮</b>Jeux</div><div><b>💬</b>Discussions</div><div><b>⚙️</b>Réglages</div></div>'


def wall(mode, sid_suffix):
    return f'''{status('23:26')}<div class="scr">
  <div class="nav"><button class="back" data-go="sFiche" aria-label="Retour">‹</button><div class="ttl">Le mur de la soirée<small>Vendredi chez Maé · <span data-count="all"></span> photos</small></div>
    <button class="act" data-go="sDl" aria-label="Tout télécharger">⬇️</button><button class="act" data-go="sSet" aria-label="Options" style="margin-left:6px">⚙️</button></div>
  <div class="seg" role="tablist"><button role="tab" data-mode="moment" aria-selected="{str(mode=='moment').lower()}">🕰️ Par moment</button><button role="tab" data-mode="person" aria-selected="{str(mode=='person').lower()}">👥 Par personne</button></div>
  <div class="livebar"><span class="dotlive"></span><span style="flex:1"><b>En direct</b> · les photos arrivent au fil de la soirée</span><span class="pill openpill ok"></span></div>
  <div class="pad" data-mur="{mode}"></div>
</div>
<button class="fab addbtn" data-go="sPick"><b>＋</b>Ajouter</button>{TAB}'''


GROUP = f'''{status('23:24')}<div class="scr">
  <div class="nav"><button class="back" aria-label="Retour">‹</button><div class="ttl">Les Loustics</div><button class="act" aria-label="Plus">⋯</button></div>
  <div class="cover"><span class="e">🎳</span><div><h3>Les Loustics</h3><small>14 membres</small></div></div>
  <div class="gtabs"><button aria-selected="false" data-keep>💬 Discussion</button><button aria-selected="false" data-keep>🎉 Événements</button><button aria-selected="true" data-keep>🖼️ Les murs</button></div>
  <div class="pad">
    <button class="wcard" data-go="sMur"><div class="mos" data-fill="first:5" data-cls="" id="gMos"></div>
      <div class="t"><b>🎂 Vendredi chez Maé<small>Ce soir · <span data-count="all"></span> photos · 6 personnes</small></b><span class="pill live"><span class="dotlive"></span>En direct</span></div></button>
    <button class="wcard fake"><div class="mos" id="gMos2"></div>
      <div class="t"><b>🎯 Paintball<small>Sam. 7 nov. · 42 photos · 9 personnes</small></b><span class="pill film">🔒 Fermé</span></div></button>
    <button class="wcard fake"><div class="mos" id="gMos3"></div>
      <div class="t"><b>📥 Le mur du groupe<small>Hors soirée · 11 photos · tous les membres ajoutent</small></b></div></button>
    <p class="muted small" style="margin-top:14px;line-height:1.45">Chaque soirée du groupe a son mur, et le groupe les montre tous ici. Une photo n'existe qu'une fois.</p>
  </div></div>{TAB}<div class="toast"></div>'''

FICHE = f'''{status('23:20')}<div class="scr">
  <div class="nav"><button class="back" data-go="sGroup" aria-label="Retour">‹</button><div class="ttl">Événement</div><button class="act" aria-label="Plus">⋯</button></div>
  <div class="hero"><span class="e">🎂</span><div><h3>Vendredi chez Maé</h3>Ven. 20.11 · 19 h 30 → 2 h · Lausanne</div></div>
  <div class="pad">
    <div class="card mt">
      <div style="display:flex;align-items:center;gap:8px"><b style="font-size:17px;flex:1">🧱 Le mur de la soirée</b><span class="pill openpill ok"></span></div>
      <p class="small" style="margin:6px 0 10px"><span style="color:var(--neon)">●</span> Inès vient d'ajouter 3 photos · <span class="muted"><span data-count="all"></span> en tout</span></p>
      <button style="display:block;width:100%" data-go="sMur"><div class="mos" data-fill="first:5" id="fMos" style="grid-auto-rows:74px"></div></button>
      <div style="display:flex;gap:8px;margin-top:12px"><button class="btn primary sm addbtn" style="flex:1" data-go="sPick">＋ Ajouter mes photos</button><button class="btn ghost sm" data-go="sMur">Voir le mur</button></div>
    </div>
    <div class="souv mt"><span class="disp"></span><div class="t"><b>📸 Souvenirs</b>3 poses prises · dévoilées sam. 21.11 à 23 h 🔒</div></div>
    <div class="vs"><div class="a"><b>🧱 Le mur · maintenant</b>Les photos de ta pellicule, visibles dès qu'elles arrivent, en qualité originale</div><div class="s"><b>📸 Souvenirs · plus tard</b>L'appareil jetable de Party : 3 poses sans les revoir, la surprise 24 h après la fin</div></div>
  </div></div>{TAB}'''

QUEUE = f'''{status('23:29')}<div class="scr" style="padding-bottom:0">
  <div class="nav"><button class="back" data-go="sMur" aria-label="Retour">‹</button><div class="ttl">Le mur de la soirée<small>Tes photos s'y posent une à une</small></div></div>
  <div class="pad" data-mur="moment" data-only="b"></div></div>
  <div class="dock"><div class="grab"></div>
    <div class="qtop"><div class="ring qring" style="width:56px;height:56px"><span style="font-size:13px">0 %</span></div><div style="flex:1"><b class="qtitle" style="font-size:16px">Envoi en cours</b><div class="muted small"><span class="qcount">0 / 8</span> · <span class="qmo"></span></div></div><span class="pill ok">✨ Originale ✓</span></div>
    <div class="quality"><span>✨</span><div><b>Qualité originale ✓</b>Le fichier part tel quel, sans compression : 4032 × 3024 comme dans ta pellicule. Seule la position GPS est retirée.</div></div>
    <div class="netbar"></div>
    <div id="qlist"></div>
    <div class="demo"><button onclick="netCut()">📶 Simuler une coupure</button><button onclick="netBack()">✅ Le réseau revient</button></div>
    <p class="muted small" style="margin-top:10px;line-height:1.45">Tu peux fermer Party : l'envoi continue en arrière-plan.</p>
    <button class="btn ghost mt" data-go="sLock">Fermer Party</button>
  </div>'''

SET = f'''{status('18:05')}<div class="scr">
  <div class="nav"><button class="back" data-go="sMur" aria-label="Retour">‹</button><div class="ttl">Le mur<small>Options · Vendredi chez Maé</small></div></div>
  <div class="pad">
    <div class="card">
      <div class="row"><div class="lbl"><b>🧱 Mur ouvert</b><small>Fermé : plus d'ajout, tout reste visible et téléchargeable.</small></div><button class="sw" role="switch" aria-checked="true" id="swOpen" aria-label="Mur ouvert"><i></i></button></div>
      <div class="state openstate open"></div>
    </div>
    <div class="sec">Qui peut ajouter</div>
    <div class="card" style="padding:4px 16px">
      <button class="radio" aria-checked="true"><div class="lbl">Les participants<small>Présent, Peut-être et l'organisation</small></div><span class="dot"></span></button><div class="sepl"></div>
      <button class="radio" aria-checked="false"><div class="lbl">Tous les invités</div><span class="dot"></span></button><div class="sepl"></div>
      <button class="radio" aria-checked="false"><div class="lbl">Seulement l'organisation</div><span class="dot"></span></button>
    </div>
    <div class="sec">Les moments <em>faits d'après l'heure des photos</em></div>
    <div class="card" style="padding:4px 16px">
      <button class="rename"><span>🍕</span><div>L'apéro<small>19:30 – 21:05</small></div><i>Renommer</i></button><div class="sepl"></div>
      <button class="rename"><span>🪩</span><div>Le dancefloor<small>22:10 – 23:20</small></div><i>Renommer</i></button><div class="sepl"></div>
      <button class="rename"><span>🌙</span><div>La fin de soirée<small>00:40 – 01:40</small></div><i>Renommer</i></button>
    </div>
    <p class="muted small" style="margin:8px 4px 0;line-height:1.45">Un trou de plus de 45 min sans photo commence un nouveau moment. Les noms sont proposés, tu les changes d'un toucher.</p>
    <div class="sec">Fermer tout seul</div>
    <div class="card" style="padding:4px 16px">
      <button class="radio" aria-checked="false"><div class="lbl">Jamais</div><span class="dot"></span></button><div class="sepl"></div>
      <button class="radio" aria-checked="true"><div class="lbl">7 jours après la fin</div><span class="dot"></span></button>
    </div>
    <button class="btn primary mt" data-go="sMur">Enregistrer</button>
  </div></div><div class="toast"></div>'''

CARDS = [
    ('<div class="illmos"><i class="b" style="background:linear-gradient(135deg,#FFB547,#FF4F9A)"></i><i class="t" style="animation-delay:.15s;background:linear-gradient(135deg,#9B6BFF,#2BD4A4)"></i><i style="animation-delay:.3s;background:#3d7bff"></i><i style="animation-delay:.45s;background:#ff6b7a"></i><i style="animation-delay:.6s;background:#2BD4A4"></i></div>',
     'Le mur de la soirée', 'Les photos de tout le monde, en direct, rangées par moment ou par personne.'),
    ('✨', 'En qualité originale', 'Tes photos partent telles quelles, sans compression. Les télécharger donne le même fichier.'),
    ('📶', 'Ajoute et retourne danser', 'L\'envoi continue Party fermée, et reprend tout seul après une coupure.'),
    ('🙋', 'Tu gardes la main', 'Supprime tes photos quand tu veux. « Je suis sur la photo » la masque aussitôt.'),
]

BODY = f'''
<header class="intro">
  <h1>🖼️ Album photos <span>· B · Le mur de la soirée</span></h1>
  <p>Une <b>mosaïque vivante</b> : grandes et petites tuiles qui suivent le format des photos, rangées <b>par moment</b> (faits tout seuls d'après l'heure de prise de vue) ou <b>par personne</b>. On voit les photos arriver pendant la soirée, et les tiennes se poser sur le mur pendant l'envoi. Un mur par soirée ; le groupe montre les murs de ses soirées.</p>
  <div class="chips"><span>🕰️ <b>Par moment</b> · 👥 <b>par personne</b></span><span>✨ Qualité originale</span><span>📶 Reprise après coupure</span><span>📱 Arrière-plan</span><span>⬇️ Tout ou un moment</span><span>🚩 « Je suis sur la photo »</span></div>
  <p class="howto">Tout se touche : « Par moment / Par personne », tuiles, pellicule, file d'envoi, visionneuse (glisse, double-touche ou pince, ⋯), interrupteurs. Fais défiler les écrans de côté.</p>
</header>
<main class="rail">
{tuto('sTuto', 1, CARDS, "À la première ouverture d'un mur. « Passer » ou « Ne plus me le rappeler ».")}
{slot('sGroup', 2, "Les murs dans le groupe", "Le groupe montre le mur de chaque soirée (en direct, fermé) et son propre mur pour le hors-soirée. Même album, montré à deux endroits.", GROUP)}
{slot('sFiche', 3, "Le mur sur la fiche, à côté des Souvenirs", "Le mur est en direct, les Souvenirs sous cadenas jusqu'au dévoilement. Les deux cartes se suivent, avec leur différence en clair.", FICHE)}
{slot('sMur', 4, "Le mur · par moment", "Les moments sont faits d'après l'heure de prise de vue. La première photo de chaque moment prend la grande tuile.", wall('moment', 'm'))}
{slot('sMurP', 5, "Le mur · par personne", "Une rangée par personne, à faire glisser de côté. Ta rangée d'abord, avec « Ajouter » au bout.", wall('person', 'p'))}
{picker('sPick', 6, '<div style="height:100%"></div>')}
{slot('sQ', 7, "L'envoi : les photos se posent sur le mur", "Le panneau montre chaque photo avec sa barre. Au-dessus, le moment « Dancefloor » : tes photos y apparaissent une à une. Teste la coupure.", QUEUE)}
{lock('sLock', 8)}
{viewer('sV', 9, "Glisse, double-touche ou pince pour zoomer. Le moment s'affiche en bas. ⋯ : Signaler, Bloquer, ou Supprimer ta photo.", back='sMur', extra='<span class="vtag" id="vMoment"></span>')}
{download('sDl', 10, '<button class="radio" aria-checked="true"><div class="lbl">Tout le mur<small><span data-count="all"></span> photos</small></div><span class="dot"></span></button><div class="sepl"></div><button class="radio" aria-checked="false"><div class="lbl">Un moment<small>🍕 Apéro · 🪩 Dancefloor · 🌙 Fin de soirée</small></div><span class="dot"></span></button><div class="sepl"></div><button class="radio" aria-checked="false"><div class="lbl">Les photos d\'une personne<small>Par exemple toutes celles d\'Inès</small></div><span class="dot"></span></button>', back='sMur')}
{slot('sSet', 11, "Le réglage de l'organisation", "Vue de Maé. Coupe « Mur ouvert » : le bouton Ajouter s'éteint partout. Les moments se renomment.", SET)}
</main>
'''

JS = r'''
const ORD=['toi','ines','leo','mae','sam','noa'];
function mosaic(list){return list.map((p,k)=>ph(p,k===0?'big':'')).join('')}
function renderMur(){
  document.querySelectorAll('[data-mur]').forEach(el=>{
    if(el.dataset.mur==='moment'){
      const ms=el.dataset.only?[el.dataset.only]:['a','b','c'],rev=!!el.dataset.only;
      el.innerHTML=ms.map(m=>{let l=fillSpec('m:'+m);if(rev)l=l.reverse();const who=[...new Set(l.map(p=>p.who))];const M=MOMENTS[m];
        return `<div class="mhead"><span class="ic">${M[0]}</span><div><b>${M[1]}</b><small>${M[2]} · ${l.length} photos</small></div><span class="avs">${who.slice(0,4).map(w=>`<i style="background:${PEOPLE[w][2]}">${PEOPLE[w][1]}</i>`).join('')}</span></div><div class="mos">${mosaic(l)}</div>`}).join('');
    } else {
      el.innerHTML=ORD.map(w=>{const l=fillSpec('who:'+w);const P_=PEOPLE[w];
        return `<div class="pers"><div class="phead"><span class="av" style="background:${P_[2]}">${P_[1]}</span><b>${w==='toi'?'Toi':P_[0]}<small>${l.length} photo${l.length>1?'s':''}${w==='toi'?' · les tiennes d\'abord':''}</small></b></div><div class="hstrip">${l.map(p=>ph(p)).join('')}${w==='toi'?'<button class="addtile addbtn" data-go="sPick"><span><b>＋</b>Ajouter</span></button>':''}</div></div>`}).join('');
    }});
  ['fMos','gMos'].forEach(id=>{const g=document.getElementById(id);if(g)g.innerHTML=mosaic(fillSpec('first:5'))});
  const fk=(s)=>{const em=['🎯🟢','🔫🎨','😂🎯','🏆🎉','🍻🌭','🌲🏃','🎳🎳','☀️🏖️'];return [0,1,2,3,4].map(k=>{const i=s+k;return `<span class="ph fake ${k===0?'big':''}" style="background:${bg({c1:COL[(i*3)%8],c2:COL[(i*5+2)%8]})}"><span class="em">${em[i%8]}</span></span>`}).join('')};
  if(document.getElementById('gMos2')){gMos2.innerHTML=fk(0);gMos3.innerHTML=fk(3)}
}
hooks.push(renderMur);
document.addEventListener('click',e=>{
  const b=e.target.closest('.seg [data-mode]');if(b){const ph=b.closest('.phone');ph.querySelectorAll('.seg button').forEach(x=>x.setAttribute('aria-selected',x===b));ph.querySelector('[data-mur]').dataset.mur=b.dataset.mode;renderMur()}
  if(e.target.closest('.fake'))toast(e.target.closest('.phone'),'Maquette : seul le mur « Vendredi chez Maé » s\'ouvre.');
  if(e.target.closest('.rename'))toast(e.target.closest('.phone')||document.body,'Maquette : un champ s\'ouvrirait ici.');
});
window.onSlide=p=>{const m=MOMENTS[p.m];document.getElementById('vMoment').textContent=m[0]+' '+m[1]};
'''
