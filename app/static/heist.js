/* Shared heist UI; the renderer loads only when this game opens. */
window.Heist=(()=>{
  const icon='<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7 19 24 8l17 11H7Zm3 20h28M14 21v13m10-13v13m10-13v13M7 39v4h34v-4"/><path d="m19 30 5-4 5 4-5 7-5-7Z"/></svg>';
  const rules='<h3>Un seul butin, toute une équipe</h3><p>Solo ou coopération à 2–8. Rapportez au moins 6 trésors (jusqu’à 8 selon la taille de l’équipe) à la sortie verte en moins de 4 minutes. Chacun transporte un objet à la fois et avance un peu moins vite chargé.</p><h3>Une touche, plusieurs actions</h3><p>Approche une vitrine puis touche Prendre. À la sortie, touche Déposer. Au boîtier turquoise, Coupe les lasers pendant 15 secondes. Près de la prison, Libérer remet tous les coéquipiers en jeu. Clavier : flèches, ZQSD ou WASD ; espace ou E pour agir.</p><h3>Reste hors de vue</h3><p>Trois gardiens patrouillent dans chaque musée. Les cônes jaunes montrent la vision des gardiens. Les murs te cachent. Les lasers rouges alternent allumage et extinction. Une seconde dans une zone dangereuse suffit pour être pris : la jauge rouge te prévient. Le trésor tombe sur place. À plusieurs : prison ; en solo : retour à la sortie et 12 secondes perdues. Si toute l’équipe est emprisonnée, la manche est perdue.</p><p>Choisis parmi trois musées avant la manche. Les arrivées tardives attendent la suivante. Changer d’application arrête tes déplacements, mais pas le chronomètre. La carte miniature indique trésors, sortie et prison.</p>';
  let root=null,code='',current=null,snap=null,scene=null,timer=0,frame=0,token=0,request=null,signature='',loaded=false;
  let input={x:0,y:0,action:false,cancel:true},stickId=null,actionId=null,lastCount='',lastResult='',loadFailed=false,actionPulse=false,lastMap=0;
  const keys=new Set(),escape=x=>esc(String(x??''));
  function reset(){actionPulse=false;input={x:0,y:0,action:false,cancel:true};stickId=actionId=null;keys.clear();root?.querySelector('.hs-knob')?.style.removeProperty('transform');}
  function stop(){if(!root&&!code)return;token++;clearTimeout(timer);cancelAnimationFrame(frame);request?.abort();reset();scene?.dispose();scene=null;root=null;snap=null;code='';loaded=false;document.body.classList.remove('heist-full');}
  function mount(g){
    current=g;
    if(!root?.isConnected||code!==g.code){
      stop();current=g;code=g.code;signature='';loaded=false;loadFailed=false;lastCount=lastResult='';
      document.body.classList.add('heist-full');
      const el=document.getElementById('game');
      el.innerHTML=`<section class="hs-root" aria-label="Braquage en miniature"><canvas class="hs-canvas" role="img" aria-label="Musée en 3D, gardiens et trésors"></canvas>
      <header class="hs-header"><h2>Braquage<br><span>en miniature</span></h2><div class="hs-stats"><strong class="hs-clock">04:00</strong><span class="hs-count">Préparation</span></div></header>
      <div class="hs-network" role="status">Ouverture du musée…</div><div class="hs-callout" aria-live="polite"></div>
      <canvas class="hs-map" width="180" height="160" aria-label="Plan du musée : butin doré, sortie verte, prison rose"></canvas><button type="button" class="hs-zoom" data-hs-zoom aria-label="Changer le zoom">🔍 Proche</button><div class="hs-label">Ton personnage porte une flèche blanche</div><div class="hs-panel"></div>
      <div class="hs-controls"><div class="hs-stick" role="group" aria-label="Joystick tactile : glisser pour se déplacer"><span class="hs-knob"></span><svg viewBox="0 0 100 100" aria-hidden="true"><path d="m46 14 4-5 4 5M46 86l4 5 4-5M14 46l-5 4 5 4m72-8 5 4-5 4"/></svg></div>
      <span class="hs-hint">Trouve un trésor.<br><b>Rapporte-le à la sortie verte.</b></span><button class="hs-action" type="button" aria-label="Interagir"><svg viewBox="0 0 32 32" aria-hidden="true"><path d="M7 7h18l5 8-14 14L2 15Zm0 0 9 22L25 7M2 15h28" fill="currentColor"/></svg><span>AGIR</span></button></div>
      <div class="hs-error" role="alert" hidden></div></section>`;
      root=el.querySelector('.hs-root');bind();accept(g.heist);load(token);poll(token);
    }else accept(g.heist);
    panel();
  }
  async function load(id){
    try{
      const {createScene}=await import('/static/heist-scene.js?v=3');
      if(id!==token||!root?.isConnected)return;
      scene=createScene(root.querySelector('canvas'));loaded=true;loadFailed=false;panel();frame=requestAnimationFrame(draw);
    }catch(e){if(id!==token)return;reset();loadFailed=true;panel();const box=root.querySelector('.hs-error');box.hidden=false;box.innerHTML='<strong>La 3D n’a pas pu démarrer.</strong><p>Vérifie que l’accélération graphique est activée, puis réessaie avec un navigateur récent.</p><button type="button" data-hs-retry>Réessayer</button>';}
  }
  function accept(v){
    if(!v)return;
    if(snap&&(v.round<snap.round||(v.round===snap.round&&v.clock<snap.clock)))return;
    if(snap&&(v.round!==snap.round||v.phase!==snap.phase))reset();
    if(v.phase==='play'&&snap?.phase!=='play'&&realtimeControlsActive()){const c=root.querySelector('canvas');c.tabIndex=-1;c.focus({preventScroll:true});}
    const mineBefore=snap?.fighters.find(p=>p.pid===snap.me),mineNow=v.fighters.find(p=>p.pid===v.me);
    if(mineNow?.jailed&&!mineBefore?.jailed)GameAudio.play('lose');
    if(snap&&v.banked>snap.banked)GameAudio.play('win');
    if(mineNow?.bag!=null&&mineBefore?.bag==null)GameAudio.play('reveal');
    snap=v;panel();
  }
  async function poll(id){
    if(id!==token||!root?.isConnected)return;
    const start=performance.now(),control=new AbortController();request=control;const deadline=setTimeout(()=>control.abort(),1800);
    try{
      if(!realtimeControlsActive()||!loaded)reset();
      const outgoing={guest_id:guestId,...input,action:input.action||actionPulse};actionPulse=false;
      const response=await fetch(`/api/games/${code}/heist`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(outgoing),signal:control.signal});
      if(id!==token)return;
      if([403,404].includes(response.status)){stop();refreshGame();return;}
      if(!response.ok)throw Error('network');
      const v=await response.json();if(id!==token)return;accept(v);
      root.querySelector('.hs-network').textContent=!loaded?'Ouverture du musée…':performance.now()-start>300?'Réseau lent':'En ligne';
      root.classList.remove('hs-offline');
    }catch(e){if(id!==token)return;reset();root.classList.add('hs-offline');root.querySelector('.hs-network').textContent='Connexion perdue · reconnexion…';}
    finally{clearTimeout(deadline);}
    if(id===token)timer=setTimeout(()=>poll(id),!realtimeControlsActive()?500:Math.max(16,65-(performance.now()-start)));
  }
  function panel(){
    if(!root||!snap||!current)return;
    const playing=['countdown','play'].includes(snap.phase),mine=snap.fighters.find(p=>p.pid===snap.me);
    root.classList.toggle('hs-playing',playing);root.classList.toggle('hs-lobby',snap.phase==='lobby');
    const canMove=playing&&mine?.active&&!mine?.jailed&&loaded;
    root.querySelector('.hs-controls').classList.toggle('hs-inactive',!canMove);
    const action=root.querySelector('.hs-action');action.disabled=!canMove||!snap.action;
    action.querySelector('span').textContent=snap.action||'AGIR';
    action.setAttribute('aria-label',snap.action||'Aucune action à proximité');
    const remaining=Math.max(0,Math.ceil(snap.duration-Math.max(0,snap.time)));
    root.querySelector('.hs-clock').textContent=`${Math.floor(remaining/60).toString().padStart(2,'0')}:${(remaining%60).toString().padStart(2,'0')}`;
    root.querySelector('.hs-count').textContent=snap.phase==='lobby'?`${current.players.length} / 8 joueurs`:`Butin ${snap.banked} / ${snap.target}`;
    root.querySelector('.hs-label').hidden=playing;
    root.querySelector('.hs-map').hidden=!playing;
    const hint=root.querySelector('.hs-hint');
    hint.textContent=mine?.jailed?'En prison · un ami doit venir te libérer':mine?.bag!=null?'Trésor en sac · rejoins la sortie verte':snap.action?`À proximité : ${snap.action}`:'Prends les trésors dorés et rapporte-les à la sortie verte';
    root.style.setProperty('--hs-danger',mine?.exposure||0);
    let message='';
    if(snap.phase==='countdown'){
      message=String(Math.ceil(-snap.time));const count=`${snap.round}:${message}`;
      if(count!==lastCount){lastCount=count;GameAudio.play('tick');}
    }else if(snap.phase==='play'&&!mine?.active)message='Tu joueras au prochain braquage.';
    else if(snap.phase==='play'&&mine?.exposure>.2)message='Repéré ! Mets-toi à couvert.';
    root.querySelector('.hs-callout').textContent=message;root.querySelector('.hs-callout').classList.toggle('hs-countdown',snap.phase==='countdown');
    const sig=JSON.stringify([snap.phase,snap.round,snap.map.id,current.is_host,current.players,snap.success,snap.notice,loaded,loadFailed]);
    if(signature===sig)return;signature=sig;
    let html='',footer='';
    if(snap.phase==='lobby'||snap.phase==='results'){
      if(snap.phase==='results'){
        const result=`${snap.round}:${snap.success}`;if(result!==lastResult){lastResult=result;GameAudio.play(snap.success?'win':'lose');}
        html=`<h3>${snap.success?'Le coup parfait !':'Le musée a gagné…'}</h3><p>${escape(snap.notice)}</p><div class="hs-results"><strong>${snap.banked} / ${snap.target} trésors livrés</strong><span>${snap.captures} capture(s) · ${snap.wins} braquage(s) réussi(s)</span></div>`;
      }else html='<h3>Ce soir, le musée est à nous.</h3><p>Prends les trésors, évite les gardiens et ramène le butin à la sortie. Ensemble, libérez vos amis.</p>';
      html+=`<div class="hs-maps" role="group" aria-label="Choisir le musée">${snap.maps.map(m=>`<button type="button" data-hs-map="${m.id}" aria-pressed="${m.id===snap.map.id}" ${!current.is_host?'disabled':''}><b>0${m.id+1} · ${escape(m.name)}</b><span>${escape(m.subtitle)}</span></button>`).join('')}</div>`;
      html+=`<div class="hs-roster">${current.players.map((p,i)=>`<span><i style="background:${['#56ded7','#fc846c','#f4cc63','#b69cff','#91d077','#f397cc','#80b6ff','#ffac67'][i]}"></i>${escape(p.name)}${p.pid===snap.me?' · toi':''}</span>`).join('')}</div>`;
      html+=`<p class="hs-invite">Code <strong>${escape(code)}</strong><button type="button" data-hs-copy>Copier le lien</button></p>`;
      if(current.is_host)footer+=`<button type="button" class="hs-primary" data-gact="${snap.phase==='results'?'next':'start'}" ${!loaded||!current.players.length?'disabled':''}>${loaded?'Lancer le braquage':loadFailed?'3D indisponible':'Préparation de la 3D…'}</button>`;
      else footer+='<p>L’animateur choisit le musée et lance le braquage.</p>';
      footer+='<small class="hs-keyboard">4 minutes · Joystick + action · Clavier : flèches et espace</small>';
    }
    if(!current.me&&current.players.length<8)footer+='<button type="button" class="hs-primary" data-gact="join">Rejoindre l’équipe</button>';
    root.querySelector('.hs-panel').innerHTML=html||footer?`<div class="hs-panel-content">${html}</div><div class="hs-panel-footer">${footer}</div>`:'';
  }
  function minimap(){
    const c=root.querySelector('.hs-map'),ctx=c.getContext('2d'),v=snap;
    const [hx,hz]=v.map.half||[10.5,9.5],k=Math.min(166/(2*hx+1),146/(2*hz+1));  // échelle : le musée entier tient dans le cadre
    const x=n=>90+n*k,y=n=>80+n*k;
    ctx.clearRect(0,0,180,160);ctx.fillStyle='#17233c';ctx.fillRect(7,7,166,146);
    ctx.fillStyle='#8b9db9';for(const [a,b,w,h] of v.map.walls)ctx.fillRect(x(a-w/2),y(b-h/2),w*k,h*k);
    const dot=(a,b,r,color)=>{ctx.fillStyle=color;ctx.beginPath();ctx.arc(x(a),y(b),r,0,Math.PI*2);ctx.fill();};
    for(const t of v.treasures)if(t.status==='floor')dot(t.x,t.y,3,'#ffd263');
    dot(...v.map.exit,5,'#64e4b3');dot(...v.map.jail,5,'#f09abb');
    for(const p of v.fighters)if(p.active)dot(p.x,p.y,p.pid===v.me?4:2,p.pid===v.me?'#ffffff':p.color);
  }
  const ZOOMS=['🔍 Proche','🔍 Large','🔍 Musée entier'];
  function zoomLabel(z){const b=root?.querySelector('[data-hs-zoom]');if(b){b.textContent=ZOOMS[z]||ZOOMS[0];b.setAttribute('aria-label',`Zoom : ${(ZOOMS[z]||ZOOMS[0]).slice(3)} (toucher pour changer)`);}}
  function bind(){
    let z0=0;try{z0=+(localStorage.getItem('vp_hs_zoom')||0);}catch{}zoomLabel(z0);
    const stick=root.querySelector('.hs-stick'),action=root.querySelector('.hs-action');
    const move=e=>{const r=stick.getBoundingClientRect(),dx=e.clientX-r.left-r.width/2,dy=e.clientY-r.top-r.height/2,d=Math.max(32,Math.hypot(dx,dy));input.x=dx/d;input.y=dy/d;stick.querySelector('.hs-knob').style.transform=`translate(${input.x*28}px,${input.y*28}px)`;};
    stick.addEventListener('pointerdown',e=>{if(stickId!==null||!loaded)return;e.preventDefault();stickId=e.pointerId;input.cancel=false;stick.setPointerCapture(e.pointerId);move(e);});
    stick.addEventListener('pointermove',e=>{if(e.pointerId===stickId)move(e);});
    const release=e=>{if(e.pointerId===stickId){stickId=null;input.x=input.y=0;stick.querySelector('.hs-knob').style.removeProperty('transform');stick.style.removeProperty('translate');}};
    // Joystick flottant : un toucher n'importe où sur l'écran de jeu (hors boutons) l'amène sous le doigt.
    root.addEventListener('pointerdown',e=>{
      if(e.pointerType==='mouse'||stickId!==null||!loaded||e.target.closest('button,a,input,.hs-stick')||stick.closest('.hs-inactive')||!stick.offsetParent)return;  // seulement en jeu
      const r=stick.getBoundingClientRect();stick.style.translate=`${e.clientX-r.left-r.width/2}px ${e.clientY-r.top-r.height/2}px`;
      e.preventDefault();stickId=e.pointerId;input.cancel=false;stick.setPointerCapture(e.pointerId);move(e);
    });
    ['pointerup','pointercancel','lostpointercapture'].forEach(n=>stick.addEventListener(n,release));
    action.addEventListener('pointerdown',e=>{if(actionId!==null)return;e.preventDefault();actionId=e.pointerId;input.cancel=false;input.action=true;actionPulse=true;action.setPointerCapture(e.pointerId);});
    const releaseAction=e=>{if(e.pointerId===actionId){actionId=null;input.action=false;}};
    ['pointerup','pointercancel','lostpointercapture'].forEach(n=>action.addEventListener(n,releaseAction));
    // Keyboard/assistive click has no pointerdown sequence.
    action.addEventListener('click',e=>{if(e.detail===0){input.cancel=false;input.action=true;actionPulse=true;setTimeout(()=>{input.action=false;},120);}});
    root.addEventListener('contextmenu',e=>e.preventDefault());
    const boundToken=token;
    root.querySelector('canvas').addEventListener('webglcontextlost',e=>{if(boundToken!==token||!root?.isConnected)return;e.preventDefault();reset();loaded=false;loadFailed=true;panel();const box=root.querySelector('.hs-error');box.hidden=false;box.innerHTML='<strong>La 3D a été interrompue.</strong><p>Recharge le décor pour reprendre.</p><button type="button" data-hs-retry>Réessayer</button>';});
    root.addEventListener('click',async e=>{
      const map=e.target.closest('[data-hs-map]');if(map){gameAction('hset',{settings:{map:Number(map.dataset.hsMap)}});}
      if(e.target.closest('[data-hs-retry]')){const g=current;stop();mount(g);}
      if(e.target.closest('[data-hs-zoom]')){let z=0;try{z=(+(localStorage.getItem('vp_hs_zoom')||0)+1)%3;localStorage.setItem('vp_hs_zoom',z);}catch{}zoomLabel(z);}
      if(e.target.closest('[data-hs-copy]')){try{await navigator.clipboard.writeText(`${location.origin}/?game=${code}`);toast('Lien copié !');}catch{toast(`Code de la partie : ${code}`);}}
    });
  }
  function key(e,down){
    if(!root?.isConnected||!loaded||!realtimeControlsActive()||/INPUT|TEXTAREA|SELECT|BUTTON/.test(e.target.tagName))return;
    const k=e.key.toLowerCase();if(!['arrowleft','arrowright','arrowup','arrowdown','z','q','s','d','w','a',' ','e'].includes(k))return;
    e.preventDefault();if((k===' '||k==='e')&&down&&!e.repeat)actionPulse=true;down?keys.add(k):keys.delete(k);input.cancel=false;
    const has=(...ks)=>ks.some(k=>keys.has(k));input.x=+has('arrowright','d')-+has('arrowleft','q','a');input.y=+has('arrowdown','s')-+has('arrowup','z','w');input.action=has(' ','e');
  }
  document.addEventListener('keydown',e=>key(e,true));document.addEventListener('keyup',e=>key(e,false));
  document.addEventListener('visibilitychange',reset);window.addEventListener('blur',reset);
  function draw(now){if(!root?.isConnected)return;frame=requestAnimationFrame(draw);if(realtimeControlsActive()&&snap&&loaded){scene?.draw(snap,now,current.players);if(now-lastMap>100){minimap();lastMap=now;}}}
  return{icon,rules,mount,stop};
})();
