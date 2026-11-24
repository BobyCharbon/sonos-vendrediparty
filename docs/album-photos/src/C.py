NAME = 'C-frise.html'
TITLE = 'Album C · La frise'

CSS = '''
.newpill{display:flex;align-items:center;gap:8px;margin:0 16px 6px;min-height:44px;border-radius:22px;padding:0 14px;background:linear-gradient(90deg,rgba(255,79,154,.22),rgba(155,107,255,.22));border:1px solid rgba(255,79,154,.5);font-size:14px;font-weight:600;width:calc(100% - 32px)}
.newpill span:last-child{margin-left:auto;color:var(--neon)}
.hblock{display:grid;grid-template-columns:44px 1fr;gap:8px;margin-top:10px;padding-right:40px}
.hblock .h{font-size:13px;font-weight:700;color:var(--muted);padding-top:2px;position:sticky;top:0;align-self:start;font-variant-numeric:tabular-nums}
.hblock .h b{display:block;font-size:20px;color:var(--text);letter-spacing:-.02em}
.hgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:3px}
.hgrid .ph{aspect-ratio:3/4;border-radius:8px;font-size:22px}
.hgrid .ph .tm{position:absolute;left:4px;bottom:4px;font-size:10.5px;letter-spacing:0;font-weight:700;background:rgba(0,0,0,.5);border-radius:6px;padding:1px 5px;font-variant-numeric:tabular-nums}
.gap{margin:10px 40px 0 52px;border:1.5px dashed #5d5480;border-radius:14px;padding:10px 12px;display:flex;align-items:center;gap:10px;font-size:13px;color:var(--muted);line-height:1.35}
.gap b{color:var(--text);display:block;font-size:13.5px}
.gap button{min-height:44px;padding:0 12px;border-radius:22px;background:var(--surface2);color:var(--neon);font-weight:700;font-size:13px;flex:0 0 auto}
.scrub{position:absolute;right:2px;top:200px;bottom:96px;width:40px;z-index:15;display:flex;flex-direction:column;justify-content:space-between;align-items:center;padding:6px 0;touch-action:none;cursor:ns-resize}
.scrub::before{content:"";position:absolute;top:0;bottom:0;left:50%;width:3px;margin-left:-1.5px;border-radius:2px;background:linear-gradient(var(--film),var(--neon),var(--violet))}
.scrub span{position:relative;font-size:10.5px;font-weight:700;background:var(--bg);padding:2px 3px;border-radius:6px;color:var(--muted);font-variant-numeric:tabular-nums}
.scrub span.on{color:var(--text);background:var(--neon)}
.scrubtip{position:absolute;right:48px;z-index:16;background:var(--neon);color:#fff;font-weight:800;font-size:20px;padding:6px 12px;border-radius:14px;opacity:0;transition:opacity .2s;pointer-events:none;box-shadow:0 6px 20px -6px var(--neon)}
.scrubtip.show{opacity:1}
.hist{display:flex;align-items:flex-end;gap:3px;height:70px;margin:12px 0 4px}
.hist i{flex:1;border-radius:4px 4px 2px 2px;background:linear-gradient(var(--neon),var(--violet));min-height:3px;animation:grow .6s backwards}
.hist i.zero{background:#3A2F63}
@keyframes grow{from{transform:scaleY(0);transform-origin:bottom}}
.histx{display:flex;justify-content:space-between;font-size:11px;color:var(--muted);font-variant-numeric:tabular-nums}
.chap{display:grid;grid-template-columns:22px 1fr;gap:10px;margin-top:14px}
.chap .dot{width:14px;height:14px;border-radius:50%;background:var(--surface2);border:3px solid var(--bg);box-shadow:0 0 0 2px var(--line);margin:4px auto 0;position:relative}
.chap .dot.live{background:var(--neon);box-shadow:0 0 0 2px var(--neon),0 0 12px var(--neon)}
.chap .rail2{position:relative}
.chap .rail2::after{content:"";position:absolute;left:50%;top:22px;bottom:-18px;width:2px;margin-left:-1px;background:var(--line)}
.chap .body{background:var(--surface);border-radius:18px;padding:10px;display:block;width:100%}
.chap .body .t{display:flex;align-items:center;gap:8px;padding:2px 4px 8px}
.chap .body .t b{flex:1;font-size:15px}
.chap .body .t b small{display:block;font-weight:400;font-size:12.5px;color:var(--muted)}
.strip5{display:grid;grid-template-columns:repeat(5,1fr);gap:3px}
.strip5 .ph{aspect-ratio:3/4;border-radius:7px;font-size:16px}
.month{font-size:13px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;margin:18px 0 0 32px}
.vfrise{position:relative;height:30px;margin-bottom:10px}
.vfrise::before{content:"";position:absolute;left:0;right:0;top:14px;height:2px;background:rgba(255,255,255,.25)}
.vfrise i{position:absolute;top:9px;width:3px;height:12px;border-radius:2px;background:rgba(255,255,255,.5);margin-left:-1.5px}
.vfrise i.on{background:var(--neon);height:20px;top:5px;width:5px;margin-left:-2.5px;box-shadow:0 0 8px var(--neon)}
.vfrise span{position:absolute;top:-2px;font-size:10px;opacity:.7}
.ctx{display:flex;background:var(--surface);border-radius:14px;padding:3px;margin-bottom:12px}
.ctx button{flex:1;min-height:44px;border-radius:11px;font-weight:600;font-size:13.5px;color:var(--muted);text-align:center}
.ctx button[aria-selected=true]{background:var(--surface2);color:var(--text)}
.illfrise{width:170px;height:140px;position:relative}
.illfrise::before{content:"";position:absolute;left:20px;right:20px;top:70px;height:4px;border-radius:2px;background:linear-gradient(90deg,var(--film),var(--neon),var(--violet))}
.illfrise i{position:absolute;width:34px;height:44px;border-radius:7px;border:2px solid #fff;animation:pop .6s backwards}
'''

TAB = '<div class="tabbar"><div><b>🎵</b>Musique</div><div class="on"><b>🎉</b>Événements</div><div><b>🎮</b>Jeux</div><div><b>💬</b>Discussions</div><div><b>⚙️</b>Réglages</div></div>'

FRISE = f'''{status('23:26')}<div class="scr" id="friseScr">
  <div class="nav"><button class="back" data-go="sFiche" aria-label="Retour">‹</button><div class="ttl">La frise de la soirée<small>Vendredi chez Maé · <span data-count="all"></span> photos</small></div>
    <button class="act" data-go="sDl" aria-label="Tout télécharger">⬇️</button><button class="act" data-go="sSet" aria-label="Options" style="margin-left:6px">⚙️</button></div>
  <div style="display:flex;gap:8px;padding:0 16px 10px;align-items:center"><span class="pill openpill ok"></span><span class="pill ok">✨ Originales</span><span class="muted small">à l'heure de prise de vue</span></div>
  <button class="newpill" id="newPill">✨ 4 nouvelles depuis ta visite<span>Voir ↓</span></button>
  <div id="frise"></div>
</div>
<div class="scrub" id="scrub" aria-label="Frise des heures"></div><div class="scrubtip" id="scrubTip"></div>
<button class="fab addbtn" data-go="sPick" style="right:52px"><b>＋</b>Ajouter</button>{TAB}<div class="toast"></div>'''

GROUP = f'''{status('23:24')}<div class="scr">
  <div class="nav"><button class="back" aria-label="Retour">‹</button><div class="ttl">Les Loustics</div><button class="act" aria-label="Plus">⋯</button></div>
  <div class="cover"><span class="e">🎳</span><div><h3>Les Loustics</h3><small>14 membres · 3 soirées en photos</small></div></div>
  <div class="gtabs"><button aria-selected="false" data-keep>💬 Discussion</button><button aria-selected="false" data-keep>🎉 Événements</button><button aria-selected="true" data-keep>🕰️ Frise</button></div>
  <div class="pad">
    <div class="month">Novembre 2026</div>
    <div class="chap"><div class="rail2"><div class="dot live"></div></div><button class="body" data-go="sFrise"><div class="t"><b>🎂 Vendredi chez Maé<small>Ce soir · <span data-count="all"></span> photos · 19:34 → 01:38</small></b><span class="pill live"><span class="dotlive"></span>En direct</span></div><div class="strip5" data-fill="first:5"></div></button></div>
    <div class="chap"><div class="rail2"><div class="dot"></div></div><button class="body fake"><div class="t"><b>🎯 Paintball<small>Sam. 7 nov. · 42 photos</small></b><span class="pill film">🔒</span></div><div class="strip5" id="cf1"></div></button></div>
    <div class="month">Octobre 2026</div>
    <div class="chap"><div class="rail2"><div class="dot"></div></div><button class="body fake"><div class="t"><b>📥 Hors soirée<small>Boîte du groupe · 11 photos</small></b></div><div class="strip5" id="cf2"></div></button></div>
    <div class="chap"><div class="rail2"><div class="dot"></div></div><button class="body fake"><div class="t"><b>🎈 Les 30 ans de Léo<small>Sam. 17 oct. · 87 photos</small></b><span class="pill film">🔒</span></div><div class="strip5" id="cf3"></div></button></div>
    <p class="muted small" style="margin-top:14px;line-height:1.45">Une seule frise pour tout le groupe : chaque soirée en est un chapitre, avec sa propre frise heure par heure. L'album de la fiche et celui du groupe sont le même.</p>
  </div></div>{TAB}<div class="toast"></div>'''

FICHE = f'''{status('23:20')}<div class="scr">
  <div class="nav"><button class="back" data-go="sGroup" aria-label="Retour">‹</button><div class="ttl">Événement</div><button class="act" aria-label="Plus">⋯</button></div>
  <div class="hero"><span class="e">🎂</span><div><h3>Vendredi chez Maé</h3>Ven. 20.11 · 19 h 30 → 2 h · Lausanne</div></div>
  <div class="pad">
    <button class="card mt" style="display:block;width:100%" data-go="sFrise">
      <div style="display:flex;align-items:center;gap:8px"><b style="font-size:17px;flex:1">🕰️ La frise de la soirée</b><span class="pill openpill ok"></span></div>
      <div class="hist" id="hist"></div><div class="histx"><span>19 h</span><span>21 h</span><span>23 h</span><span>1 h</span></div>
      <p class="muted small" style="margin-top:8px"><span data-count="all"></span> photos, heure par heure · touche pour parcourir</p>
    </button>
    <div class="gap" style="margin:10px 0 0"><span style="font-size:22px">🕳️</span><div><b>Rien entre 21:02 et 22:10</b>Tu as des photos de ce moment-là ?</div><button class="addbtn" data-go="sPick">Ajouter</button></div>
    <div class="souv mt"><span class="disp"></span><div class="t"><b>📸 Souvenirs</b>3 poses prises · dévoilées sam. 21.11 à 23 h 🔒</div></div>
    <div class="vs"><div class="a"><b>🕰️ La frise · tout de suite</b>Les photos de la pellicule de chacun, à leur heure, en qualité originale</div><div class="s"><b>📸 Souvenirs · la surprise</b>3 poses dans Party, sans les revoir, montrées 24 h après la fin</div></div>
  </div></div>{TAB}'''

SET = f'''{status('18:05')}<div class="scr">
  <div class="nav"><button class="back" data-go="sFrise" aria-label="Retour">‹</button><div class="ttl">Options des photos</div></div>
  <div class="pad">
    <div class="ctx" role="tablist"><button role="tab" aria-selected="true" data-ctx="ev">🎂 La soirée</button><button role="tab" aria-selected="false" data-ctx="gr">🎳 Le groupe</button></div>
    <div data-pane="ev">
      <p class="muted small" style="margin:0 4px 10px">Réglé par l'organisation de la soirée (vue de Maé).</p>
      <div class="card">
        <div class="row"><div class="lbl"><b>Album ouvert</b><small>Fermé : plus d'ajout ; regarder et télécharger restent possibles.</small></div><button class="sw" role="switch" aria-checked="true" id="swOpen" aria-label="Album ouvert"><i></i></button></div>
        <div class="state openstate open"></div>
      </div>
      <div class="sec">Qui peut ajouter</div>
      <div class="card" style="padding:4px 16px">
        <button class="radio" aria-checked="true"><div class="lbl">Les participants<small>Présent, Peut-être et l'organisation</small></div><span class="dot"></span></button><div class="sepl"></div>
        <button class="radio" aria-checked="false"><div class="lbl">Tous les invités</div><span class="dot"></span></button><div class="sepl"></div>
        <button class="radio" aria-checked="false"><div class="lbl">Seulement l'organisation</div><span class="dot"></span></button>
      </div>
      <div class="sec">Photos prises hors de la soirée</div>
      <div class="card" style="padding:4px 16px">
        <div class="row"><div class="lbl"><b>Les accepter quand même</b><small>Éteint : une photo prise plus de 12 h avant ou après est refusée, avec un message clair.</small></div><button class="sw" role="switch" aria-checked="false" aria-label="Accepter les photos hors soirée"><i></i></button></div>
      </div>
    </div>
    <div data-pane="gr" hidden>
      <p class="muted small" style="margin:0 4px 10px">Réglé par les gérants du groupe.</p>
      <div class="card">
        <div class="row"><div class="lbl"><b>Boîte du groupe ouverte</b><small>Pour les photos hors soirée.</small></div><button class="sw" role="switch" aria-checked="true" aria-label="Boîte du groupe ouverte"><i></i></button></div>
      </div>
      <div class="sec">Qui peut ajouter</div>
      <div class="card" style="padding:4px 16px">
        <button class="radio" aria-checked="true"><div class="lbl">Tous les membres</div><span class="dot"></span></button><div class="sepl"></div>
        <button class="radio" aria-checked="false"><div class="lbl">Seulement les gérants</div><span class="dot"></span></button>
      </div>
      <div class="sec">Les soirées du groupe</div>
      <div class="card small muted" style="line-height:1.5">Leurs albums suivent les réglages de chaque soirée. Le groupe les montre dans sa frise, sans rien copier.</div>
    </div>
    <button class="btn primary mt" data-go="sFrise">Enregistrer</button>
  </div></div>'''

CARDS = [
    ('<div class="illfrise"><i style="left:12px;top:20px;background:linear-gradient(135deg,#FFB547,#FF4F9A)"></i><i style="left:62px;top:80px;animation-delay:.2s;background:linear-gradient(135deg,#FF4F9A,#9B6BFF)"></i><i style="left:112px;top:20px;animation-delay:.4s;background:linear-gradient(135deg,#9B6BFF,#2BD4A4)"></i></div>',
     'Toute la soirée, heure par heure', 'Les photos de tout le monde se rangent à l\'heure où elles ont été prises. Glisse le long de la frise pour voyager dans la soirée.'),
    ('✨', 'Qualité originale, jamais floue', 'Le fichier part tel quel, sans compression. Tu télécharges exactement le même.'),
    ('🕳️', 'Comble les trous', 'Personne n\'a de photo entre 21 h et 22 h ? La frise te le dit. Ajoute les tiennes, même en partant : l\'envoi continue Party fermée.'),
    ('🙋', 'Ton image, ton choix', 'Supprime tes photos quand tu veux. « Je suis sur la photo » la masque aussitôt.'),
]

BODY = f'''
<header class="intro">
  <h1>🖼️ Album photos <span>· C · La frise de la soirée</span></h1>
  <p>Mon idée : <b>ranger par l'heure de prise de vue</b> (pas d'envoi). La soirée se lit comme une frise, de l'apéro à la fin, avec <b>une réglette des heures</b> à faire glisser. La frise montre aussi <b>les trous</b> (« rien entre 21:02 et 22:10, tu en as ? ») et ce qui est nouveau depuis ta visite. Dans le groupe, une seule frise où chaque soirée est un chapitre : <b>même album, montré à deux endroits</b>.</p>
  <div class="chips"><span>🕰️ <b>Heure de prise de vue</b></span><span>🕳️ Les trous à combler</span><span>✨ Qualité originale</span><span>📶 Reprise · arrière-plan</span><span>⬇️ Tout ou une tranche d'heures</span><span>🚩 « Je suis sur la photo »</span></div>
  <p class="howto">Tout se touche : réglette des heures (glisse dessus), « nouvelles », pellicule, file d'envoi, visionneuse (glisse, double-touche ou pince, ⋯), réglages. Fais défiler les écrans de côté.</p>
</header>
<main class="rail">
{tuto('sTuto', 1, CARDS, "À la première ouverture d'une frise. « Passer » ou « Ne plus me le rappeler ».")}
{slot('sGroup', 2, "La frise du groupe", "Chaque soirée est un chapitre ; celle de ce soir est en direct. La boîte du groupe y a aussi sa place pour le hors-soirée.", GROUP)}
{slot('sFiche', 3, "Sur la fiche, à côté des Souvenirs", "Un aperçu heure par heure de l'album (ouvert tout de suite), le trou à combler, puis les Souvenirs sous cadenas.", FICHE)}
{slot('sFrise', 4, "La frise de la soirée", "Glisse le doigt sur la réglette à droite pour sauter à une heure. Le point rose marque les nouvelles photos. Les trous de plus de 45 min s'affichent.", FRISE)}
{picker('sPick', 5, '<div style="height:100%"></div>')}
{queue('sQ', 6, head_extra='<div class="state open" style="margin-top:10px"><span>🕰️</span><div><b>Rangées à leur heure</b>Chaque photo se place à l\'heure où elle a été prise, pas à l\'heure d\'envoi.</div></div>', back='sFrise')}
{lock('sLock', 7)}
{viewer('sV', 8, "Glisse pour avancer dans la soirée : la mini-frise en bas montre où tu es. Double-touche ou pince pour zoomer, ⋯ pour Signaler ou Supprimer.", back='sFrise', extra='<div class="vfrise" id="vFrise"></div>')}
{download('sDl', 9, '<button class="radio" aria-checked="true"><div class="lbl">Toute la frise<small><span data-count="all"></span> photos</small></div><span class="dot"></span></button><div class="sepl"></div><button class="radio" aria-checked="false"><div class="lbl">Une tranche d\'heures<small>Par exemple de 22 h à minuit</small></div><span class="dot"></span></button><div class="sepl"></div><button class="radio" aria-checked="false"><div class="lbl">Seulement les miennes</div><span class="dot"></span></button>', back='sFrise')}
{slot('sSet', 10, "Les réglages : soirée et groupe", "Deux onglets : l'organisation règle l'album de la soirée, les gérants la boîte du groupe. Coupe « Album ouvert ».", SET)}
</main>
'''

JS = r'''
const NEW=new Set([14,15,16,17]);
const hlabel=m=>{const h=Math.floor(m/60)%24;return h+' h'};
function renderFrise(){
  const el=document.getElementById('frise');if(!el)return;const l=fillSpec('chrono');let html='',cur=null,prev=null;
  l.forEach(p=>{const m=tmin(p.t),h=Math.floor(m/60);
    if(prev!==null&&m-prev>45){if(cur!==null)html+='</div></div>';cur=null;html+=`<div class="gap"><span style="font-size:22px">🕳️</span><div><b>Rien entre ${l[l.indexOf(p)-1].t} et ${p.t}</b>Tu en as ?</div><button class="addbtn" data-go="sPick">Ajouter</button></div>`}
    if(h!==cur){if(cur!==null)html+='</div></div>';cur=h;html+=`<div class="hblock" data-h="${h}"><div class="h"><b>${h%24}</b>h</div><div class="hgrid">`}
    html+=ph(p,NEW.has(p.id)?'new':'').replace('</button>',`<span class="tm">${p.t}</span></button>`);prev=m});
  if(cur!==null)html+='</div></div>';el.innerHTML=html;
  const s=document.getElementById('scrub');if(s&&!s.children.length)s.innerHTML=[19,20,21,22,23,24,25].map(h=>`<span data-sh="${h}">${h%24}</span>`).join('');
  const hist=document.getElementById('hist');if(hist){const b=[];for(let t=19*60;t<26*60;t+=30)b.push(live().filter(p=>{const m=tmin(p.t);return m>=t&&m<t+30}).length);const mx=Math.max(...b);hist.innerHTML=b.map((n,k)=>`<i class="${n?'':'zero'}" style="height:${n?Math.max(10,n/mx*100):4}%;animation-delay:${k*30}ms"></i>`).join('')}
  const fk=s=>{const em=['🎯🟢','🔫🎨','😂🎯','🏆🎉','🍻🌭','🎈🎂','🎳🎳','☀️🏖️'];return [0,1,2,3,4].map(k=>{const i=s+k;return `<span class="ph" style="background:${bg({c1:COL[(i*3)%8],c2:COL[(i*5+2)%8]})}"><span class="em">${em[i%8]}</span></span>`}).join('')};
  ['cf1','cf2','cf3'].forEach((id,k)=>{const g=document.getElementById(id);if(g)g.innerHTML=fk(k*3)});
}
hooks.push(renderFrise);
(function(){const s=document.getElementById('scrub'),scr=document.getElementById('friseScr'),tip=document.getElementById('scrubTip');let on=false;
  const pick=e=>{const r=s.getBoundingClientRect(),f=Math.min(1,Math.max(0,(e.clientY-r.top)/r.height)),h=19+Math.round(f*6);
    const blocks=[...document.querySelectorAll('#frise .hblock')];let best=blocks[0];blocks.forEach(b=>{if(+b.dataset.h<=h)best=b});
    if(best)scr.scrollTo({top:best.offsetTop-90,behavior:on?'auto':'smooth'});
    tip.textContent=(h%24)+' h';tip.style.top=(e.clientY-s.closest('.phone').getBoundingClientRect().top-20)+'px';tip.classList.add('show');
    s.querySelectorAll('span').forEach(x=>x.classList.toggle('on',+x.dataset.sh===h))};
  s.addEventListener('pointerdown',e=>{on=true;s.setPointerCapture(e.pointerId);pick(e)});
  s.addEventListener('pointermove',e=>{if(on)pick(e)});
  const end=()=>{on=false;setTimeout(()=>tip.classList.remove('show'),500)};s.addEventListener('pointerup',end);s.addEventListener('pointercancel',end);
  document.getElementById('newPill').onclick=()=>{const n=document.querySelector('#frise .ph.new');if(n)scr.scrollTo({top:n.closest('.hblock').offsetTop-90,behavior:'smooth'})};
})();
window.onSlide=p=>{const v=document.getElementById('vFrise');if(!v)return;const a=19*60,z=26*60,x=m=>((m-a)/(z-a)*100).toFixed(1)+'%';
  v.innerHTML=[19,21,23,25].map(h=>`<span style="left:${x(h*60)}">${h%24} h</span>`).join('')+V.list.map(q=>`<i class="${q.id===p.id?'on':''}" style="left:${x(tmin(q.t))}"></i>`).join('')};
document.addEventListener('click',e=>{
  const c=e.target.closest('[data-ctx]');if(c){const ph=c.closest('.phone');ph.querySelectorAll('[data-ctx]').forEach(x=>x.setAttribute('aria-selected',x===c));ph.querySelectorAll('[data-pane]').forEach(p=>p.hidden=p.dataset.pane!==c.dataset.ctx)}
  if(e.target.closest('.fake'))toast(e.target.closest('.phone'),'Maquette : seule la soirée « Vendredi chez Maé » s\'ouvre.');
});
'''
