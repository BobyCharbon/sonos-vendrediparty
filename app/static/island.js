/* Shared island UI; the renderer loads only when this game opens. */
window.Island=(()=>{
  const icon='<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m5 29 10-7 11 3 10-4 7 8-9 12-13-4-9 4zM23 25l3-17M26 9c-5-8-12-4-14 1 7-3 10-1 14-1Zm0 0c7-6 13-1 13 4-5-3-9-4-13-4Z"/></svg>';
  const rules='<h3>Garde les pieds au sec</h3><p>De <b>1 à 8 joueurs</b>, chacun dans son navigateur. Seul, essaie de survivre <b>90 secondes</b> et bats ton record. À plusieurs, le dernier survivant gagne la manche.</p><h3>Bouger et sauter</h3><p>Glisse le joystick à gauche et touche <b>Saut</b> à droite. Sur ordinateur : flèches ou ZQSD / WASD, espace pour sauter. Relâche le bouton entre deux sauts. Les plateformes orange se fissurent environ 3 secondes avant de tomber : rejoins vite une zone verte.</p><h3>Jouer ensemble</h3><p>Partage le code ou le lien de la partie. L’animateur lance les manches. Une arrivée en cours de jeu attend la suivante. Une chute simultanée ou plusieurs survivants après 90 secondes donnent une égalité. Changer d’application arrête ton personnage, mais la partie continue. Le plein écran paysage donne la meilleure vue ; le portrait fonctionne aussi.</p>';
  let root=null,code='',current=null,snap=null,scene=null,timer=0,frame=0,token=0,request=null,signature='',loaded=false;
  let input={x:0,y:0,jump:false,cancel:true},stickId=null,jumpId=null,lastCount='',lastResult='',loadFailed=false,jumpPulse=false;
  const keys=new Set(),escape=x=>esc(String(x??''));
  function reset(){jumpPulse=false;input={x:0,y:0,jump:false,cancel:true};stickId=jumpId=null;keys.clear();root?.querySelector('.is-knob')?.style.removeProperty('transform');}
  function stop(){if(!root&&!code)return;token++;clearTimeout(timer);cancelAnimationFrame(frame);request?.abort();reset();scene?.dispose();scene=null;root=null;snap=null;code='';loaded=false;document.body.classList.remove('island-full');}
  function mount(g){
    current=g;
    if(!root?.isConnected||code!==g.code){
      stop();current=g;code=g.code;signature='';loaded=false;loadFailed=false;lastCount=lastResult='';
      document.body.classList.add('island-full');
      const el=document.getElementById('game');
      el.innerHTML=`<section class="is-root" aria-label="L’île qui s’effondre"><canvas class="is-canvas" role="img" aria-label="Île en 3D et positions des joueurs"></canvas>
      <header class="is-header"><h2>L’île qui<br><span>s’effondre</span></h2><div class="is-stats"><strong class="is-clock">01:30</strong><span class="is-count">Préparation</span></div></header>
      <div class="is-network" role="status">Chargement de l’île…</div><div class="is-callout" aria-live="polite"></div>
      <div class="is-label">Ton personnage porte une flèche blanche</div><div class="is-panel"></div>
      <div class="is-controls"><div class="is-stick" role="group" aria-label="Joystick tactile : glisser pour se déplacer"><span class="is-knob"></span><svg viewBox="0 0 100 100" aria-hidden="true"><path d="m46 14 4-5 4 5M46 86l4 5 4-5M14 46l-5 4 5 4m72-8 5 4-5 4"/></svg></div>
      <span class="is-hint">Évite les fissures.<br><b>Vise une zone verte.</b></span><button class="is-jump" type="button" aria-label="Sauter"><svg viewBox="0 0 32 32" aria-hidden="true"><path d="M16 5 5 17h7v10h8V17h7Z" fill="currentColor"/></svg><span>SAUT</span></button></div>
      <div class="is-error" role="alert" hidden></div></section>`;
      root=el.querySelector('.is-root');bind();accept(g.island);load(token);poll(token);
    }else accept(g.island);
    panel();
  }
  async function load(id){
    try{
      const {createScene}=await import('/static/island-scene.js?v=3');
      if(id!==token||!root?.isConnected)return;
      scene=createScene(root.querySelector('canvas'));loaded=true;loadFailed=false;panel();frame=requestAnimationFrame(draw);
    }catch(e){if(id!==token)return;reset();loadFailed=true;panel();const box=root.querySelector('.is-error');box.hidden=false;box.innerHTML='<strong>La 3D n’a pas pu démarrer.</strong><p>Vérifie que l’accélération graphique est activée, puis réessaie avec un navigateur récent.</p><button type="button" data-is-retry>Réessayer</button>';}
  }
  function accept(v){
    if(!v)return;
    if(snap&&(v.round<snap.round||(v.round===snap.round&&v.clock<snap.clock)))return;
    if(snap&&(v.round!==snap.round||v.phase!==snap.phase))reset();
    if(v.phase==='play'&&snap?.phase!=='play'&&realtimeControlsActive()){const c=root.querySelector('canvas');c.tabIndex=-1;c.focus({preventScroll:true});}
    const mineBefore=snap?.fighters.find(p=>p.pid===snap.me),mineNow=v.fighters.find(p=>p.pid===v.me);
    if(mineBefore?.alive&&mineNow&&!mineNow.alive)GameAudio.play('lose');
    snap=v;panel();
  }
  async function poll(id){
    if(id!==token||!root?.isConnected)return;
    const start=performance.now(),control=new AbortController();request=control;const deadline=setTimeout(()=>control.abort(),1800);
    try{
      if(!realtimeControlsActive()||!loaded)reset();
      const outgoing={guest_id:guestId,...input,jump:input.jump||jumpPulse};jumpPulse=false;
      const response=await fetch(`/api/games/${code}/island`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(outgoing),signal:control.signal});
      if(id!==token)return;
      if([403,404].includes(response.status)){stop();refreshGame();return;}
      if(!response.ok)throw Error('network');
      const v=await response.json();if(id!==token)return;accept(v);
      root.querySelector('.is-network').textContent=!loaded?'Chargement de l’île…':performance.now()-start>300?'Réseau lent':'En ligne';
      root.classList.remove('is-offline');
    }catch(e){if(id!==token)return;reset();root.classList.add('is-offline');root.querySelector('.is-network').textContent='Connexion perdue · reconnexion…';}
    finally{clearTimeout(deadline);}
    if(id===token)timer=setTimeout(()=>poll(id),!realtimeControlsActive()?500:Math.max(16,65-(performance.now()-start)));
  }
  function panel(){
    if(!root||!snap||!current)return;
    const playing=['countdown','play'].includes(snap.phase),mine=snap.fighters.find(p=>p.pid===snap.me),alive=snap.fighters.filter(p=>p.alive).length;
    root.classList.toggle('is-playing',playing);root.classList.toggle('is-lobby',snap.phase==='lobby');
    root.querySelector('.is-controls').classList.toggle('is-inactive',!playing||!mine?.alive||!loaded);
    root.querySelector('.is-jump').disabled=!playing||!mine?.alive||!loaded;
    const remaining=Math.max(0,Math.ceil(snap.duration-Math.max(0,snap.time)));
    root.querySelector('.is-clock').textContent=`${Math.floor(remaining/60).toString().padStart(2,'0')}:${(remaining%60).toString().padStart(2,'0')}`;
    root.querySelector('.is-count').textContent=snap.phase==='lobby'?`${current.players.length} / 8 joueurs`:snap.solo?'Survie solo':`${alive} / ${snap.fighters.length} en jeu`;
    root.querySelector('.is-label').hidden=playing;
    const callout=root.querySelector('.is-callout');let message='';
    if(snap.phase==='countdown'){
      message=String(Math.ceil(-snap.time));const count=`${snap.round}:${message}`;
      if(count!==lastCount){lastCount=count;GameAudio.play('tick');}
    }else if(snap.phase==='play'&&!mine?.alive)message=mine?'À l’eau ! Regarde la suite.':'Tu joueras à la prochaine manche.';
    else if(snap.phase==='play'&&snap.time<1.2)message='C’est parti !';
    callout.textContent=message;callout.classList.toggle('is-countdown',snap.phase==='countdown');
    const sig=JSON.stringify([snap.phase,snap.round,current.is_host,current.players,snap.winner,snap.best,snap.notice,loaded,loadFailed]);
    if(signature===sig)return;signature=sig;
    let html='';
    if(snap.phase==='lobby'){
      html='<h3>Le paradis ne tient qu’à un saut.</h3><p>Seul, tiens 90 secondes. Entre amis, sois le dernier sur l’île.</p>';
      html+=`<div class="is-roster">${current.players.map((p,i)=>`<span><i style="background:${['#20c9d0','#f66b60','#f4bd40','#a185e8','#78ba60','#ef91ba','#539cef','#ef984b'][i]}"></i>${escape(p.name)}${p.pid===snap.me?' · toi':''}</span>`).join('')}</div>`;
      html+=`<p class="is-invite">Invite tes amis avec le code <strong>${escape(code)}</strong><button type="button" data-is-copy aria-label="Copier le lien d’invitation">Copier le lien</button></p>`;
      if(current.is_host)html+=`<button type="button" class="is-primary" data-gact="start" ${!loaded||!current.players.length?'disabled':''}>${loaded?(current.players.length>1?'Lancer la manche':'Jouer en solo'):(loadFailed?'3D indisponible':'Préparation de la 3D…')}</button>`;
      else html+='<p>L’animateur lancera la manche.</p>';
      html+='<small class="is-keyboard">Joystick + saut · Au clavier : flèches et espace</small>';
    }else if(snap.phase==='results'){
      const winner=snap.fighters.find(p=>p.pid===snap.winner);
      const result=`${snap.round}:${snap.winner}`;if(result!==lastResult){lastResult=result;GameAudio.play(snap.winner===snap.me?'win':'reveal');}
      html=`<h3>${winner?(snap.solo?'Île maîtrisée !':`${escape(winner.name)} gagne !`):(snap.solo?'Un plongeon… et on repart ?':'Fin de la manche')}</h3><p>${escape(snap.notice)||'Un dernier survivant. Une nouvelle île à conquérir.'}</p>`;
      html+=`<div class="is-results">${snap.fighters.map(p=>`<div><span>${escape(p.name)}</span><strong>${(p.out_at??Math.max(0,snap.time)).toFixed(1)} s</strong><small>Record ${(snap.best[p.pid]||0).toFixed(1)} s · ${snap.scores[p.pid]||0} victoire(s)</small></div>`).join('')}</div>`;
      html+=current.is_host?'<button type="button" class="is-primary" data-gact="next">Rejouer sur l’île</button>':'<p>L’animateur prépare la prochaine manche.</p>';
    }
    if(!current.me&&current.players.length<8)html+='<button type="button" class="is-primary" data-gact="join">Rejoindre la partie</button>';
    root.querySelector('.is-panel').innerHTML=html;
  }
  function bind(){
    const stick=root.querySelector('.is-stick'),jump=root.querySelector('.is-jump');
    const move=e=>{const r=stick.getBoundingClientRect(),dx=e.clientX-r.left-r.width/2,dy=e.clientY-r.top-r.height/2,d=Math.max(32,Math.hypot(dx,dy));input.x=dx/d;input.y=dy/d;stick.querySelector('.is-knob').style.transform=`translate(${input.x*28}px,${input.y*28}px)`;};
    stick.addEventListener('pointerdown',e=>{if(stickId!==null||!loaded)return;e.preventDefault();stickId=e.pointerId;input.cancel=false;stick.setPointerCapture(e.pointerId);move(e);});
    stick.addEventListener('pointermove',e=>{if(e.pointerId===stickId)move(e);});
    const release=e=>{if(e.pointerId===stickId){stickId=null;input.x=input.y=0;stick.querySelector('.is-knob').style.removeProperty('transform');}};
    ['pointerup','pointercancel','lostpointercapture'].forEach(n=>stick.addEventListener(n,release));
    jump.addEventListener('pointerdown',e=>{if(jumpId!==null)return;e.preventDefault();jumpId=e.pointerId;input.cancel=false;input.jump=true;jumpPulse=true;jump.setPointerCapture(e.pointerId);});
    const releaseJump=e=>{if(e.pointerId===jumpId){jumpId=null;input.jump=false;}};
    ['pointerup','pointercancel','lostpointercapture'].forEach(n=>jump.addEventListener(n,releaseJump));
    // Keyboard/assistive click has no pointerdown sequence.
    jump.addEventListener('click',e=>{if(e.detail===0){input.cancel=false;input.jump=true;jumpPulse=true;setTimeout(()=>{input.jump=false;},120);}});
    root.addEventListener('contextmenu',e=>e.preventDefault());
    const boundToken=token;
    root.querySelector('canvas').addEventListener('webglcontextlost',e=>{if(boundToken!==token||!root?.isConnected)return;e.preventDefault();reset();loaded=false;loadFailed=true;panel();const box=root.querySelector('.is-error');box.hidden=false;box.innerHTML='<strong>La 3D a été interrompue.</strong><p>Recharge le décor pour reprendre.</p><button type="button" data-is-retry>Réessayer</button>';});
    root.addEventListener('click',async e=>{
      if(e.target.closest('[data-is-retry]')){const g=current;stop();mount(g);}
      if(e.target.closest('[data-is-copy]')){try{await navigator.clipboard.writeText(`${location.origin}/?game=${code}`);toast('Lien copié !');}catch{toast(`Code de la partie : ${code}`);}}
    });
  }
  function key(e,down){
    if(!root?.isConnected||!loaded||!realtimeControlsActive()||/INPUT|TEXTAREA|SELECT|BUTTON/.test(e.target.tagName))return;
    const k=e.key.toLowerCase();if(!['arrowleft','arrowright','arrowup','arrowdown','z','q','s','d','w','a',' '].includes(k))return;
    e.preventDefault();if(k===' '&&down&&!e.repeat)jumpPulse=true;down?keys.add(k):keys.delete(k);input.cancel=false;
    const has=(...ks)=>ks.some(k=>keys.has(k));input.x=+has('arrowright','d')-+has('arrowleft','q','a');input.y=+has('arrowdown','s')-+has('arrowup','z','w');input.jump=has(' ');
  }
  document.addEventListener('keydown',e=>key(e,true));document.addEventListener('keyup',e=>key(e,false));
  document.addEventListener('visibilitychange',reset);window.addEventListener('blur',reset);
  function draw(now){if(!root?.isConnected)return;frame=requestAnimationFrame(draw);if(realtimeControlsActive()&&snap&&loaded)scene?.draw(snap,now,current.players);}
  return{icon,rules,mount,stop};
})();
