/* ===== Données factices : aucune image externe, des dégradés + emojis ===== */
const $=s=>document.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
const PEOPLE={toi:['Toi','😎','#5B2E8C'],mae:['Maé','🦊','#8C3B2E'],leo:['Léo','🐻','#2E5B8C'],ines:['Inès','🌸','#8C2E6A'],sam:['Sam','🎧','#1f6b57'],noa:['Noa','🐙','#6A2E8C']};
const COL=['#FFB547','#FF4F9A','#9B6BFF','#2BD4A4','#3d7bff','#ff8a3d','#ff6b7a','#5B2E8C'];
/* [emoji, couleur1, couleur2, auteur, heure de prise, orientation, moment] */
const RAW=[
 ['🥂✨',0,1,'mae','19:34','p','a'],['🍕🍕',5,2,'leo','19:41','l','a'],['😂😂',1,3,'toi','19:52','s','a'],
 ['🎂🕯️',1,7,'ines','20:05','p','a'],['🎶🔊',3,7,'sam','20:18','l','a'],['🥳🎈',2,3,'toi','20:26','p','a'],
 ['🃏🎲',4,2,'noa','20:44','l','a'],['🍹🍋',0,3,'mae','21:02','s','a'],
 ['💃🕺',1,0,'ines','22:10','p','b'],['🪩✨',7,3,'sam','22:18','p','b'],['🤳😂',2,1,'leo','22:31','l','b'],
 ['🎤🎶',1,4,'toi','22:47','p','b'],['🙌🎉',6,2,'noa','23:05','l','b'],['🎸🔥',5,1,'leo','23:20','p','b'],
 ['🌙🚕',7,2,'mae','00:42','l','c'],['👋💖',1,2,'ines','00:51','s','c'],['🍟🌭',0,5,'sam','01:15','l','c'],['🛋️😴',2,7,'noa','01:38','p','c']];
const MOMENTS={a:['🍕','L\'apéro','19:30 – 21:05'],b:['🪩','Le dancefloor','22:10 – 23:20'],c:['🌙','La fin de soirée','00:40 – 01:40']};
let P=RAW.map((r,i)=>({id:i,e:r[0],c1:COL[r[1]],c2:COL[r[2]],who:r[3],t:r[4],o:r[5],m:r[6],
  added:addT(r[4],7+(i*13)%40),mo:(2.3+((i*37)%17)/10).toFixed(1),fmt:i%5===4?'JPG':'HEIC',n:'IMG_'+(4810+i*7)}));
function addT(t,d){let[h,m]=t.split(':').map(Number);m+=d;h=(h+Math.floor(m/60))%24;m%=60;return String(h).padStart(2,'0')+':'+String(m).padStart(2,'0')}
const DIM={p:'3024 × 4032',l:'4032 × 3024',s:'3024 × 3024'};
const bg=p=>`radial-gradient(circle at 28% 24%,${p.c1}d0,transparent 56%),radial-gradient(circle at 76% 78%,${p.c2}d0,transparent 56%),radial-gradient(circle at 60% 30%,#ffffff22,transparent 30%),#140b26`;
const live=()=>P.filter(p=>!p.gone);
const tmin=t=>{let[h,m]=t.split(':').map(Number);if(h<6)h+=24;return h*60+m};
const byTime=a=>a.slice().sort((x,y)=>tmin(x.t)-tmin(y.t));
function ph(p,cls='',who=false){
  return `<button class="ph ${p.o} ${cls}${p.masked?' masked':''}${p.fresh?' in new':''}" data-ph="${p.id}" style="background:${bg(p)}" aria-label="Photo de ${PEOPLE[p.who][0]}, ${p.t}"><span class="em">${p.e}</span>${who?`<span class="who" style="background:${PEOPLE[p.who][2]}">${PEOPLE[p.who][1]}</span>`:''}</button>`}

/* rendus : chaque direction ajoute les siens */
const hooks=[];
function fillSpec(spec){
  if(spec==='all')return byTime(live()).reverse();
  if(spec==='chrono')return byTime(live());
  if(spec.startsWith('who:'))return byTime(live().filter(p=>p.who===spec.slice(4)));
  if(spec.startsWith('m:'))return byTime(live().filter(p=>p.m===spec.slice(2)));
  if(spec.startsWith('first:'))return byTime(live()).reverse().slice(0,+spec.slice(6));
  return spec.split(',').map(Number).map(i=>P[i]).filter(p=>p&&!p.gone)}
function renderAll(){
  $$('[data-fill]').forEach(el=>{const list=fillSpec(el.dataset.fill);el.innerHTML=list.map(p=>ph(p,el.dataset.cls||'',el.hasAttribute('data-who'))).join('')});
  $$('[data-count]').forEach(el=>{const s=el.dataset.count;const n=s==='all'?live().length:fillSpec(s).length;el.textContent=n});
  hooks.forEach(f=>f());buildViewer();}

/* ===== navigation dans le rail ===== */
function go(id){const el=document.getElementById(id);if(el)el.scrollIntoView({behavior:'smooth',inline:'center',block:'nearest'})}
document.addEventListener('click',e=>{
  const g=e.target.closest('[data-go]');if(g){go(g.dataset.go)}
  const t=e.target.closest('[data-ph]');
  if(t&&!t.closest('.picker')&&!t.closest('.viewer')){openViewer(+t.dataset.ph)}
  const sw=e.target.closest('.sw');if(sw){const v=sw.getAttribute('aria-checked')!=='true';sw.setAttribute('aria-checked',v);sw.dispatchEvent(new CustomEvent('toggle',{detail:v,bubbles:true}))}
  const r=e.target.closest('.radio');if(r){$$('.radio',r.parentElement).forEach(x=>x.setAttribute('aria-checked',x===r));r.dispatchEvent(new CustomEvent('pick',{bubbles:true}))}
  const c=e.target.closest('.check');if(c){c.setAttribute('aria-checked',c.getAttribute('aria-checked')!=='true');c.dispatchEvent(new CustomEvent('toggle',{bubbles:true}))}
  const ch=e.target.closest('.chipsrow button,.gtabs button');if(ch&&!ch.hasAttribute('data-keep')){const row=ch.parentElement,attr=row.classList.contains('gtabs')?'aria-selected':'aria-pressed';$$('button',row).forEach(b=>b.setAttribute(attr,b===ch));ch.dispatchEvent(new CustomEvent('chip',{bubbles:true}))}
  const o=e.target.closest('[data-sheet]');if(o)openSheet(o.dataset.sheet);
  if(e.target.closest('[data-close]')||e.target.classList.contains('shade'))closeSheets(e.target.closest('.phone'));
});

/* ===== feuilles et messages ===== */
function openSheet(id){const s=document.getElementById(id),ph=s.closest('.phone');closeSheets(ph);s.classList.add('open');$('.shade',ph)?.classList.add('open')}
function closeSheets(ph){if(!ph)return;$$('.sheet.open',ph).forEach(s=>s.classList.remove('open'));$$('.shade',ph).forEach(s=>s.classList.remove('open'))}
function toast(ph,msg,ms=3200){const t=$('.toast',ph);if(!t)return;t.innerHTML=msg;t.classList.add('show');clearTimeout(t._t);t._t=setTimeout(()=>t.classList.remove('show'),ms)}

/* ===== sélecteur d'iOS : la pellicule, photos seulement ===== */
const ROLL=[['🥳🎈',2,3,'p'],['😂😂',1,3,'s'],['🎤🎶',1,4,'p'],['🪩💜',7,1,'p'],['🍾🥂',0,2,'l'],['🕺💡',4,1,'p'],['🎊🎉',6,3,'l'],['🤪📸',2,0,'s'],
  ['🌃🏙️',4,7,'l'],['🎆✨',1,0,'p'],['🍔🍟',5,6,'s'],['😎🕶️',3,2,'p'],
  ['🐶🌳',3,0,'l'],['☕🥐',0,5,'s'],['🚲🌄',5,4,'l'],['🧾📄',7,7,'p']];
let pickOrder=[];
function buildPicker(){const g=$('#pkgrid');if(!g)return;
  g.innerHTML='<div class="day">Aujourd\'hui · ven. 20 nov.</div>'+ROLL.map((r,i)=>(i===12?'<div class="day">Hier</div>':'')+
   `<button class="ph" data-roll="${i}" aria-pressed="false" aria-label="Photo ${i+1}" style="background:${bg({c1:COL[r[1]],c2:COL[r[2]]})}"><span class="em">${r[0]}</span><span class="sel"></span></button>`).join('');
  g.onclick=e=>{const b=e.target.closest('[data-roll]');if(!b)return;const i=+b.dataset.roll,k=pickOrder.indexOf(i);
    if(k>=0)pickOrder.splice(k,1);else pickOrder.push(i);paintPicker()};
  [0,1,2,3,4,5,6,7].forEach(i=>pickOrder.push(i));paintPicker();
  $('#pkAdd').onclick=()=>{if(!pickOrder.length)return;startQueue(pickOrder.slice());go($('#pkAdd').dataset.next||'sQ')};
  $('#pkCancel').onclick=()=>{pickOrder=[];paintPicker()};}
function paintPicker(){$$('#pkgrid [data-roll]').forEach(b=>{const k=pickOrder.indexOf(+b.dataset.roll);b.setAttribute('aria-pressed',k>=0);b.querySelector('.sel').textContent=k>=0?k+1:''});
  const n=pickOrder.length;$('#pkAdd').textContent=n?`Ajouter (${n})`:'Ajouter';$('#pkAdd').disabled=!n;
  $('#pkCount').innerHTML=n?`<b>${n} photo${n>1?'s':''} sélectionnée${n>1?'s':''}</b>`:'<b>Choisis tes photos</b>'}

/* ===== file d'envoi : progression, coupure, reprise, arrière-plan ===== */
let Q=[],qTimer=null,offline=false,qTotal=0;
function startQueue(idx){
  Q=idx.map((ri,k)=>{const r=ROLL[ri];const mo=+(2.2+((ri*29)%19)/10).toFixed(1);return{ri,e:r[0],c1:COL[r[1]],c2:COL[r[2]],o:r[3],mo,done:0,state:'wait',n:'IMG_'+(5120+ri*3)+'.HEIC'}});
  qTotal=Q.reduce((s,q)=>s+q.mo,0);offline=false;$$('.netbar').forEach(n=>n.className='netbar');paintQueue();clearInterval(qTimer);qTimer=setInterval(tickQueue,260);}
function tickQueue(){if(offline)return;let active=0;
  for(const q of Q){if(q.state==='done')continue;if(active>=2)break;active++;q.state='up';q.done=Math.min(q.mo,q.done+0.16+Math.random()*0.2);
    if(q.done>=q.mo){q.state='done';arrive(q)}}
  paintQueue();if(Q.every(q=>q.state==='done')){clearInterval(qTimer);finishQueue()}}
function arrive(q){const id=P.length;P.push({id,e:q.e,c1:q.c1,c2:q.c2,who:'toi',t:addT('23:30',Q.indexOf(q)*3),o:q.o,m:'b',added:'maintenant',mo:q.mo.toFixed(1),fmt:'HEIC',n:q.n.replace('.HEIC',''),fresh:true});renderAll();setTimeout(()=>{P[id].fresh=false},1600)}
function paintQueue(){const L=$('#qlist');if(!L)return;if(!Q.length){L.innerHTML='<div class="muted small" style="text-align:center;padding:14px 6px;line-height:1.5">📥 Rien en cours.<br>Touche « Ajouter » dans la pellicule (écran d\'avant), ou « Simuler une coupure » ci-dessous.</div>';return}
  const sent=Q.reduce((s,q)=>s+q.done,0),pc=qTotal?Math.round(sent/qTotal*100):0,ndone=Q.filter(q=>q.state==='done').length;
  L.innerHTML=Q.map(q=>{const p=Math.round(q.done/q.mo*100);const cls=q.state==='done'?'done':(offline&&q.state==='up'?'paused':'');
    const st=q.state==='done'?`✓ Envoyée · ${q.mo.toFixed(1).replace('.',',')} Mo · originale`:q.state==='up'?(offline?`⏸ En pause · ${q.done.toFixed(1).replace('.',',')} / ${q.mo.toFixed(1).replace('.',',')} Mo gardés`:`${p} % · ${q.done.toFixed(1).replace('.',',')} / ${q.mo.toFixed(1).replace('.',',')} Mo`):'En attente';
    return `<div class="qrow ${cls}"><span class="ph" style="background:${bg(q)}"><span class="em">${q.e}</span></span><div class="inf"><b>${q.n}<small>${q.o==='l'?'4032 × 3024':q.o==='s'?'3024 × 3024':'3024 × 4032'}</small></b><div class="bar"><i style="width:${p}%"></i></div><div class="st">${st}</div></div></div>`}).join('');
  $$('.qring').forEach(r=>{r.style.setProperty('--p',pc);r.querySelector('span').textContent=pc+' %'});
  $$('.qcount').forEach(e=>e.textContent=`${ndone} / ${Q.length}`);
  $$('.qmo').forEach(e=>e.textContent=`${sent.toFixed(1).replace('.',',')} / ${qTotal.toFixed(1).replace('.',',')} Mo`);
  const la=$('#laBar');if(la){la.style.width=pc+'%';$('#laN').textContent=`${ndone}/${Q.length}`}}
function finishQueue(){$$('.qtitle').forEach(e=>e.textContent='Tout est envoyé ✓');const n=$('#lockNotif');if(n){n.hidden=false;n.classList.remove('drop');void n.offsetWidth;n.classList.add('drop');$('#laWrap').hidden=true;
  $('#lockNotifTxt').textContent=`${Q.length} photos ajoutées à l'album en qualité originale ✓`}}
function netCut(){if(!Q.length||Q.every(q=>q.state==='done'))startQueue([0,1,2,3,4,5,6,7]);offline=true;$$('.netbar').forEach(n=>{n.className='netbar show';n.innerHTML='<span>📶</span><div><b>Plus de réseau · envoi en pause</b>Rien n\'est perdu : chaque photo reprendra là où elle s\'est arrêtée, toute seule, dès que le réseau revient.</div>'});paintQueue()}
function netBack(){if(!offline)return;offline=false;$$('.netbar').forEach(n=>{n.className='netbar show back';n.innerHTML='<span>✅</span><div><b>Réseau revenu · ça reprend</b>Reprise au morceau près, rien n\'est renvoyé depuis le début.</div>'});setTimeout(()=>$$('.netbar').forEach(n=>n.className='netbar'),3500);paintQueue()}

/* ===== visionneuse : glisser, zoomer, auteur et heure, télécharger, ⋯ ===== */
let V={i:0,list:[],s:1,x:0,y:0};
function buildViewer(){const v=$('#viewer');if(!v)return;const cur=V.list[V.i]?.id;
  V.list=(window.viewerOrder||(()=>byTime(live())))();
  $('#vtrack').innerHTML=V.list.map(p=>`<div class="slide"><div class="ph ${p.o}${p.masked?' masked':''}" style="background:${bg(p)}"><span class="em">${p.e}</span></div></div>`).join('');
  const k=V.list.findIndex(p=>p.id===cur);V.i=k>=0?k:Math.min(V.i,V.list.length-1);showSlide(false)}
function openViewer(id){const k=V.list.findIndex(p=>p.id===id);if(k>=0)V.i=k;resetZoom();showSlide(false);closeSheets($('#viewer').closest('.phone'));$('#viewer').classList.remove('chromeless');go('sV')}
function showSlide(anim=true){const tr=$('#vtrack');if(!tr)return;tr.classList.toggle('drag',!anim);tr.style.transform=`translateX(${-V.i*100}%)`;
  const p=V.list[V.i];if(!p)return;const w=PEOPLE[p.who];
  $('#vAv').textContent=w[1];$('#vAv').style.background=w[2];$('#vWho').innerHTML=`${p.who==='toi'?'Toi':w[0]}<small>Prise à ${p.t} · ajoutée à ${p.added}</small>`;
  $('#vPos').textContent=`${V.i+1} / ${V.list.length}`;$('#vDim').textContent=`${DIM[p.o]} · ${p.mo.replace('.',',')} Mo · ${p.fmt}`;
  $('#vMask').classList.toggle('show',!!p.masked);if(window.onSlide)window.onSlide(p)}
function curSlidePh(){return $$('#vtrack .slide')[V.i]?.querySelector('.ph')}
function applyZoom(){const el=curSlidePh();if(el)el.style.transform=`translate(${V.x}px,${V.y}px) scale(${V.s})`;$('#viewer').classList.toggle('zoomed',V.s>1)}
function resetZoom(){V.s=1;V.x=V.y=0;$$('#vtrack .ph').forEach(e=>e.style.transform='');$('#viewer')?.classList.remove('zoomed')}
function zhint(t){const h=$('#zhint');h.textContent=t;h.classList.add('show');clearTimeout(h._t);h._t=setTimeout(()=>h.classList.remove('show'),700)}
function initViewer(){const v=$('#viewer');if(!v)return;const ptr=new Map();let st=null,lastTap=0;
  v.addEventListener('pointerdown',e=>{if(e.target.closest('button'))return;v.setPointerCapture(e.pointerId);ptr.set(e.pointerId,{x:e.clientX,y:e.clientY});
    if(ptr.size===2){const[a,b]=[...ptr.values()];st={pinch:Math.hypot(a.x-b.x,a.y-b.y),s0:V.s}}else st={x0:e.clientX,y0:e.clientY,t:Date.now(),px:V.x,py:V.y,dx:0}});
  v.addEventListener('pointermove',e=>{if(!ptr.has(e.pointerId)||!st)return;ptr.set(e.pointerId,{x:e.clientX,y:e.clientY});
    if(st.pinch&&ptr.size===2){const[a,b]=[...ptr.values()];V.s=Math.min(4,Math.max(1,st.s0*Math.hypot(a.x-b.x,a.y-b.y)/st.pinch));if(V.s===1){V.x=V.y=0}applyZoom();return}
    const dx=e.clientX-st.x0,dy=e.clientY-st.y0;st.dx=dx;
    if(V.s>1){V.x=st.px+dx;V.y=st.py+dy;applyZoom()}
    else{const tr=$('#vtrack');tr.classList.add('drag');tr.style.transform=`translateX(calc(${-V.i*100}% + ${dx}px))`}});
  const up=e=>{if(!ptr.has(e.pointerId))return;ptr.delete(e.pointerId);if(!st)return;
    if(st.pinch){if(ptr.size===0)st=null;zhint(V.s>1?'Zoom ×'+V.s.toFixed(1).replace('.',','):'Taille réelle');return}
    const W=v.clientWidth,dx=st.dx||0,quick=Date.now()-st.t<260&&Math.abs(dx)<8;
    if(V.s===1){if(dx<-W*.16&&V.i<V.list.length-1)V.i++;else if(dx>W*.16&&V.i>0)V.i--;if(Math.abs(dx)>8)resetZoom();showSlide(true)}
    if(quick){const now=Date.now();if(now-lastTap<300){if(V.s>1)resetZoom();else{V.s=2.5;applyZoom()}zhint(V.s>1?'Zoom ×2,5 · glisse pour te déplacer':'Taille réelle');lastTap=0}
      else{lastTap=now;setTimeout(()=>{if(lastTap===now)v.classList.toggle('chromeless')},300)}}
    st=null};
  v.addEventListener('pointerup',up);v.addEventListener('pointercancel',up);
  v.addEventListener('wheel',e=>{if(!e.ctrlKey)return;e.preventDefault();V.s=Math.min(4,Math.max(1,V.s*(1-e.deltaY/200)));if(V.s===1)V.x=V.y=0;applyZoom()},{passive:false});
  $('#vPrev').onclick=()=>{if(V.i>0){V.i--;resetZoom();showSlide()}};$('#vNext').onclick=()=>{if(V.i<V.list.length-1){V.i++;resetZoom();showSlide()}};
  $('#vZoom').onclick=()=>{if(V.s>1)resetZoom();else{V.s=2.5;applyZoom()}zhint(V.s>1?'Zoom ×2,5':'Taille réelle')};
  $('#vDl').onclick=()=>{const p=V.list[V.i];toast(v.closest('.phone'),`⬇️ Original enregistré dans Photos<br><span class="muted small">${p.n}.${p.fmt} · ${DIM[p.o]} · ${p.mo.replace('.',',')} Mo · identique au fichier envoyé</span>`)};
  $('#vMore').onclick=()=>{const p=V.list[V.i],mine=p.who==='toi',w=PEOPLE[p.who][0];
    $('#vMenuList').innerHTML=`<button class="opt" data-do="dl"><span>⬇️</span><div>Télécharger l'original<small>${DIM[p.o]} · ${p.mo.replace('.',',')} Mo · ${p.fmt}</small></div></button>
     <button class="opt" data-do="share"><span>↗️</span><div>Partager<small>Envoie le fichier original</small></div></button>
     ${mine?`<button class="opt red" data-do="del"><span>🗑️</span><div>Supprimer ma photo<small>Elle disparaît de l'album pour tout le monde</small></div></button>`:
     `<button class="opt red" data-sheet="vReport"><span>🚩</span><div>Signaler<small>Dont « Je suis sur la photo »</small></div></button>
      <button class="opt red" data-do="block"><span>🚫</span><div>Bloquer ${w}<small>Tu ne verras plus ses photos, ni ses messages</small></div></button>`}
     ${window.orgMenu?window.orgMenu(p):''}`;openSheet('vMenu')};
  $('#vMenu').addEventListener('click',e=>{const d=e.target.closest('[data-do]')?.dataset.do;if(!d)return;const ph=v.closest('.phone'),p=V.list[V.i];
    if(d==='dl'){closeSheets(ph);$('#vDl').click()}
    if(d==='share'){closeSheets(ph);toast(ph,'↗️ Feuille de partage d\'iOS · fichier original')}
    if(d==='del')openSheet('vDelete');
    if(d==='block'){closeSheets(ph);toast(ph,`🚫 ${PEOPLE[p.who][0]} est bloqué·e : ses photos sont masquées pour toi, et la modération est prévenue.`,4200)}
    if(d==='orgrm'){closeSheets(ph);p.gone=true;renderAll();toast(ph,'Photo retirée par l\'organisation. L\'auteur est prévenu.')}});
  $('#vReport').addEventListener('click',e=>{const m=e.target.closest('[data-motif]');if(!m)return;const ph=v.closest('.phone'),p=V.list[V.i];
    closeSheets(ph);p.masked=true;renderAll();
    toast(ph,m.dataset.motif==='me'?'🚩 Merci. Photo masquée pour tout le monde tout de suite. L\'auteur, l\'organisation et la modération sont prévenus ; elle sera retirée si c\'est bien toi.':'🚩 Merci. Photo masquée en attendant la décision de l\'organisation et de la modération.',5200)});
  $('#vDelYes').onclick=()=>{const ph=v.closest('.phone'),p=V.list[V.i];closeSheets(ph);p.gone=true;renderAll();toast(ph,'🗑️ Ta photo est supprimée de l\'album.')};
  document.addEventListener('keydown',e=>{if(e.key==='ArrowRight')$('#vNext').click();if(e.key==='ArrowLeft')$('#vPrev').click()});}

/* ===== didacticiel ===== */
function initTuto(){const t=$('#tuto');if(!t)return;let k=0;const cards=$$('.tcard',t),n=cards.length;
  const paint=()=>{$('.tcards',t).style.transform=`translateX(${-k*100}%)`;$$('.tdots i',t).forEach((d,j)=>d.classList.toggle('on',j===k));$('#tNext').textContent=k===n-1?'C\'est parti':'Suivant';
    cards.forEach((c,j)=>c.setAttribute('aria-hidden',j!==k))};
  const end=msg=>{t.hidden=true;$('#tdone').classList.add('show');$('#tdoneTxt').innerHTML=msg};
  $('#tNext').onclick=()=>{if(k<n-1){k++;paint()}else end('Bonne soirée ! L\'album t\'attend.')};
  $('#tSkip').onclick=()=>end('Didacticiel passé. Il reviendra à ta prochaine visite d\'un album, sauf si tu touches « Ne plus me le rappeler ».');
  $('#tNever').onclick=()=>end('C\'est noté, on ne te le montrera plus.<br>Tu le retrouves dans ⋯ › « Comment ça marche ».');
  $('#tAgain').onclick=()=>{k=0;paint();t.hidden=false;$('#tdone').classList.remove('show')};
  let sx=null;t.addEventListener('pointerdown',e=>sx=e.clientX);t.addEventListener('pointerup',e=>{if(sx===null)return;const d=e.clientX-sx;sx=null;if(d<-40&&k<n-1){k++;paint()}if(d>40&&k>0){k--;paint()}});paint()}

/* ===== tout télécharger ===== */
function initDl(){const b=$('#dlStart');if(!b)return;let tm=null;
  b.onclick=()=>{const n=live().length,total=(n*2.9).toFixed(0);$('#dlChoose').hidden=true;$('#dlRun').hidden=false;let p=0;clearInterval(tm);
    tm=setInterval(()=>{p=Math.min(100,p+3+Math.random()*4);const r=$('#dlRing');r.style.setProperty('--p',p);r.querySelector('span').textContent=Math.round(p)+' %';
      $('#dlTxt').textContent=`${Math.round(n*p/100)} / ${n} photos · ${Math.round(total*p/100)} / ${total} Mo`;
      if(p>=100){clearInterval(tm);$('#dlRunT').textContent='Tout est dans Photos ✓';$('#dlTxt').innerHTML=`${n} originaux dans <b>Photos › Albums › Vendredi chez Maé</b>`;$('#dlAgain').hidden=false}},180)};
  $('#dlAgain').onclick=()=>{$('#dlChoose').hidden=false;$('#dlRun').hidden=true;$('#dlAgain').hidden=true;$('#dlRunT').textContent='Téléchargement des originaux';const r=$('#dlRing');r.style.setProperty('--p',0)}}

/* ===== réglages : ouvert / fermé ===== */
function setOpen(v){$$('.openstate').forEach(e=>{e.className='state openstate '+(v?'open':'closed');e.innerHTML=v?'<span>🟢</span><div><b>Album ouvert</b>Les personnes choisies ci-dessous ajoutent leurs photos, visibles aussitôt.</div>':'<span>🔒</span><div><b>Album fermé</b>Plus personne n\'ajoute de photo. Tout le monde peut toujours regarder et télécharger les originaux.</div>'});
  $$('.openpill').forEach(e=>{e.className='pill openpill '+(v?'ok':'film');e.innerHTML=v?'<span class="dotlive"></span>Ouvert':'🔒 Fermé'});
  $$('.addbtn').forEach(e=>{e.style.opacity=v?1:.35;e.style.pointerEvents=v?'':'none'})}
document.addEventListener('toggle',e=>{if(e.target.id==='swOpen')setOpen(e.detail)});

function boot(){renderAll();paintQueue();buildPicker();initViewer();initTuto();initDl();setOpen(true)}
