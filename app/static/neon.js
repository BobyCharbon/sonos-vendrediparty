/* Néon Knockout: server physics, interpolated canvas, independent multitouch controls. */
window.Neon = (() => {
  const colors = ['#55e8ff','#ff668f','#ffce66','#ad96ff','#73f5ad','#ff985c','#86a9ff','#f893eb'];
  const teams = ['Cyan','Rose','Or','Iris'];
  const icon = '<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linejoin="round" aria-hidden="true"><path d="M6 29 24 39 42 29M6 23 24 33 42 23 24 13Z"/><path d="m25 4-9 16h8l-1 10 11-17h-9z" fill="currentColor" stroke="none"/></svg>';
  const rules = `<h3>Reste sur la plateforme</h3><p>De <b>2 à 8 joueurs</b>, chacun sur son téléphone. Déplace-toi avec le joystick à gauche. Maintiens <b>DASH</b> à droite pour charger, vise avec le joystick, puis relâche pour éjecter tes adversaires. Une charge complète prend 1,1 seconde ; le dash se recharge ensuite.</p><h3>La dernière équipe debout gagne</h3><p>Chacun pour soi, ou <b>2 à 4 équipes de deux</b>. Choisissez vos duos avant le match. Les coéquipiers partagent leur couleur et ne se repoussent pas. Une équipe reste en jeu tant qu'un de ses membres tient sur la plateforme.</p><p>La bordure commence à se refermer après 12 secondes. Une manche dure au maximum <b>45 secondes</b>. Le dernier joueur ou duo marque un point ; une chute simultanée donne une égalité. Premier à <b>5 victoires</b> ! L'animateur lance chaque manche.</p><h3>Revenir dans la partie</h3><p>En solo, un nouvel arrivant attend la prochaine manche. En duo, les inscriptions sont fermées pendant le match : les nouveaux peuvent regarder et rejoindre au prochain match. Après un départ, l’animateur peut préparer un nouveau match depuis les résultats, en remettant les scores à zéro. Si tu changes d'application, ton personnage s'arrête et peut être éliminé. Reviens dans le même navigateur pour retrouver ta place. Sur ordinateur : flèches ou ZQSD, espace pour charger.</p>`;
  let root, canvas, ctx, current, snap, code='', frame=0, timer=0, session=0, latest=0, received=0, signature='',request=null;
  let input={x:0,y:0,charging:false,cancel:true}, stickId=null, dashId=null, particles=[], ghosts=new Map(), shown=new Map();
  const keys=new Set();
  const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
  const svgBolt='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m14 2-9 12h7l-2 8 9-13h-7z" fill="currentColor"/></svg>';
  const escName = x => esc(String(x ?? ''));
  function reset() {
    input={x:0,y:0,charging:false,cancel:true}; stickId=dashId=null; keys.clear();
    root?.querySelector('.nk-stick-knob')?.style.removeProperty('transform');
    root?.querySelector('.nk-dash')?.classList.remove('holding');
  }
  function stop() {
    session++; request?.abort(); cancelAnimationFrame(frame); clearTimeout(timer); reset(); root=null; snap=null; code='';
    particles=[]; ghosts.clear(); shown.clear();
  }
  function mount(g) {
    const el=document.getElementById('game');
    if (!root?.isConnected || code!==g.code) {
      stop(); code=g.code; current=g; signature='';
      el.innerHTML=`<section class="nk-root" aria-label="Néon Knockout">
        <header class="nk-heading"><h2>Néon <span>Knockout</span></h2><span class="nk-network" role="status">Connexion…</span></header>
        <div class="nk-hud"><span class="nk-round">Prépare ton dash</span><strong class="nk-clock">45<span>s</span></strong><span class="nk-target">Objectif <b>5 victoires</b></span></div>
        <div class="nk-stage"><canvas class="nk-canvas" aria-label="Arène partagée, positions des joueurs" role="img"></canvas><div class="nk-callout" aria-live="polite"></div></div>
        <div class="nk-score" aria-label="Scores"></div><div class="nk-panel"></div>
        <div class="nk-controls"><div class="nk-stick" role="group" aria-label="Joystick tactile : glisser pour se déplacer"><span class="nk-stick-cross"></span><span class="nk-stick-knob"></span><span class="nk-control-label">DÉPLACER</span></div>
        <p class="nk-control-tip">Maintiens, vise.<br><b>Relâche pour frapper.</b></p><button type="button" class="nk-dash" aria-label="Maintenir pour charger le dash, relâcher pour frapper">${svgBolt}<strong>DASH</strong><small>Maintenir</small></button></div>
        <p class="nk-footnote">Dernier debout. Premier à cinq.</p></section>`;
      root=el.querySelector('.nk-root'); canvas=root.querySelector('canvas'); ctx=canvas.getContext('2d');
      bind(); accept(g.neon); frame=requestAnimationFrame(draw); poll(session);
    }
    current=g;
    if (!snap || g.phase==='lobby' || g.neon.clock>=snap.clock) accept(g.neon);
    panel();
  }
  function accept(v) {
    if (!v) return;
    if (snap && v.round===snap.round && v.clock<snap.clock && v.phase!=='lobby') return;
    if (snap && (v.round!==snap.round || v.phase!==snap.phase)) reset();
    const old=snap;
    if(v.phase==='play'&&snap?.phase!=='play'&&realtimeControlsActive()){const c=root.querySelector('canvas');c.tabIndex=-1;c.focus({preventScroll:true});}
    snap=v; received=performance.now();
    for (const p of v.fighters) {
      const prev=old?.fighters.find(x=>x.pid===p.pid);
      if (prev?.alive && !p.alive) burst(p.x,p.y,p.color,32);
      if (prev && prev.pulse!==p.pulse) burst(p.x,p.y,p.color,10);
    }
    panel();
  }
  async function poll(token) {
    if (token!==session || !root?.isConnected) return;
    const start=performance.now();
    const control=new AbortController();request=control;const deadline=setTimeout(()=>control.abort(),1800);
    try {
      const active=realtimeControlsActive();
      if (!active) reset();
      const response=await fetch(`/api/games/${code}/neon`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({guest_id:guestId,...input}),signal:control.signal});
      if (token!==session) return;
      if (!response.ok) {
        reset();
        if ([403,404].includes(response.status)) { stop(); refreshGame(); return; }
        throw new Error('Connexion perdue');
      }
      const v=await response.json();
      if (token!==session) return;
      latest=performance.now(); accept(v);
      const net=root.querySelector('.nk-network'), ms=Math.round(latest-start);
      net.textContent=ms>250 ? 'Réseau lent' : 'En ligne'; net.classList.toggle('slow',ms>250);
    } catch {
      if (token!==session) return;
      reset();
      root.querySelector('.nk-network').textContent='Reconnexion…';
      root.querySelector('.nk-network').classList.add('slow');
    } finally { clearTimeout(deadline); }
    if (token===session && root?.isConnected) timer=setTimeout(()=>poll(token),!realtimeControlsActive()?500:Math.max(10,66-(performance.now()-start)));
  }
  function winnerName() {
    if (snap.winner===null) return 'Égalité';
    return snap.mode==='duo' ? `Duo ${teams[Number(snap.winner)]}` : snap.fighters.find(p=>p.group===snap.winner)?.name || 'Victoire';
  }
  function panel() {
    if (!root || !snap || !current) return;
    const phase=snap.phase, playing=['play','countdown'].includes(phase), mine=snap.fighters.find(p=>p.pid===snap.me);
    root.classList.toggle('nk-playing',playing); root.classList.toggle('nk-lobby',phase==='lobby');
    root.querySelector('.nk-round').textContent=phase==='lobby' ? 'Ton terrain de jeu' : `Manche ${snap.round} · ${snap.mode==='duo'?'Duos':'Solo'}`;
    const canPlay=playing && mine?.alive;
    root.querySelector('.nk-controls').classList.toggle('nk-disabled',!canPlay);
    root.querySelector('.nk-dash').disabled=!canPlay;
    const sig=JSON.stringify([phase,current.is_host,current.me?.pid,current.players,snap.mode,snap.teams,snap.scores,snap.winner,snap.notice]);
    if(sig===signature) return;
    signature=sig;
    const scorePlayers=phase==='lobby' ? current.players.map((p,i)=>({...p,color:colors[snap.mode==='duo'?snap.teams[p.pid]:i],group:snap.mode==='duo'?String(snap.teams[p.pid]):p.pid,alive:true})) : snap.fighters;
    const groups=[...new Set(scorePlayers.map(p=>p.group))];
    root.querySelector('.nk-score').innerHTML=groups.map(id=>{
      const members=scorePlayers.filter(p=>p.group===id), p=members[0];
      return `<div class="nk-score-item" style="--fighter:${p.color}"><i></i><span>${snap.mode==='duo'?teams[Number(id)]:escName(p.name)}${members.some(p=>p.pid===snap.me)?' · toi':''}</span><b>${snap.scores[id]||0}<small>/5</small></b></div>`;
    }).join('');
    let html='';
    if(phase==='lobby' || phase==='end') {
      if(phase==='lobby') html='<h3>Charge. Vise. Éjecte.</h3><p>Un joystick, un dash. Et surtout, ne tombe pas.</p>';
      else html=`<h3>${escName(winnerName())} remporte le match !</h3><p>Cinq victoires. Une arène conquise.</p>`;
      if(current.is_host) html+=`<div class="nk-modes" role="group" aria-label="Mode de jeu"><button type="button" data-nmode="solo" aria-pressed="${snap.mode==='solo'}">Chacun pour soi</button><button type="button" data-nmode="duo" aria-pressed="${snap.mode==='duo'}">Équipes de 2</button></div>`;
      if(snap.mode==='duo') html+=`<p class="nk-team-help">Choisis ton duo · 2 joueurs par équipe</p><div class="nk-teams">${teams.map((name,i)=>{
        const players=current.players.filter(p=>snap.teams[p.pid]===i),selected=snap.teams[snap.me]===i;
        return `<button type="button" data-nteam="${i}" style="--fighter:${colors[i]}" aria-pressed="${selected}" ${!snap.me||(!selected&&players.length===2)?'disabled':''}><b>${name} <span>${players.length}/2</span></b><small>${players.map(p=>escName(p.name)).join(' + ')||'Rejoindre ce duo'}</small></button>`;
      }).join('')}</div>`;
      const counts=teams.map((_,i)=>current.players.filter(p=>snap.teams[p.pid]===i).length);
      const ready=snap.mode==='solo'?current.players.length>=2:current.players.length>=4 && counts.every(n=>n===0||n===2);
      html+=current.is_host?`<button type="button" class="nk-primary" data-gact="${phase==='end'?'restart':'start'}" ${!ready?'disabled':''}>${ready?(phase==='end'?'Rejouer un match':'Entrer dans l’arène'):(snap.mode==='duo'?'Complétez vos duos':'En attente d’un deuxième joueur')}</button>`:`<p class="nk-wait">${escName(current.host_name)} lancera le match.</p>`;
    } else if(phase==='results') {
      html=`<h3>${escName(winnerName())}${snap.winner===null?' !':' gagne la manche !'}</h3><p>${escName(snap.notice)||(snap.winner===null?'Chute simultanée. Aucun point, on remet ça.':'Le premier à cinq victoires remporte le match.')}</p>`;
      html+=current.is_host?'<button type="button" class="nk-primary" data-gact="next">Manche suivante</button>':`<p class="nk-wait">${escName(current.host_name)} lancera la prochaine manche.</p>`;
    }
    if(phase==='results' && current.is_host) html+=`<button type="button" class="nk-new-match" data-nmode="${snap.mode}">Nouveau match · remettre les scores à zéro</button>`;
    if(!current.me && snap.mode==='duo' && !['lobby','end'].includes(phase)) html+='<p>Match en duo en cours. Tu pourras rejoindre le prochain match.</p>';
    else if(!current.me && current.players.length<8) html+='<button type="button" class="nk-primary" data-gact="join">Rejoindre la partie</button>';
    root.querySelector('.nk-panel').innerHTML=html;
  }
  function bind() {
    const stick=root.querySelector('.nk-stick'), dash=root.querySelector('.nk-dash');
    function move(e) {
      const r=stick.getBoundingClientRect(), dx=e.clientX-(r.left+r.width/2), dy=e.clientY-(r.top+r.height/2), d=Math.max(34,Math.hypot(dx,dy));
      input.x=dx/d; input.y=dy/d;
      stick.querySelector('.nk-stick-knob').style.transform=`translate(${input.x*29}px,${input.y*29}px)`;
    }
    stick.addEventListener('pointerdown',e=>{if(stickId!==null)return;e.preventDefault();input.cancel=false;stickId=e.pointerId;stick.setPointerCapture(e.pointerId);move(e);});
    stick.addEventListener('pointermove',e=>{if(e.pointerId===stickId)move(e);});
    const endStick=e=>{if(e.pointerId===stickId){stickId=null;input.x=input.y=0;stick.querySelector('.nk-stick-knob').style.removeProperty('transform');}};
    ['pointerup','pointercancel','lostpointercapture'].forEach(type=>stick.addEventListener(type,endStick));
    dash.addEventListener('pointerdown',e=>{if(dashId!==null)return;e.preventDefault();input.cancel=false;dashId=e.pointerId;dash.setPointerCapture(e.pointerId);input.charging=true;dash.classList.add('holding');});
    const endDash=e=>{if(e.pointerId===dashId){dashId=null;input.charging=false;dash.classList.remove('holding');}};
    ['pointerup','lostpointercapture'].forEach(type=>dash.addEventListener(type,endDash));
    dash.addEventListener('pointercancel',()=>reset());
    stick.addEventListener('pointercancel',()=>reset());
    root.addEventListener('contextmenu',e=>e.preventDefault());
  }
  document.addEventListener('visibilitychange',reset); window.addEventListener('blur',reset);
  function keyboard(e,down) {
    if(!root?.isConnected || !realtimeControlsActive() || /INPUT|TEXTAREA|SELECT/.test(e.target.tagName))return;
    const key=e.key.toLowerCase();
    if(!['arrowleft','arrowright','arrowup','arrowdown','z','q','s','d','w','a',' '].includes(key))return;
    e.preventDefault(); input.cancel=false; down?keys.add(key):keys.delete(key);
    const has=(...k)=>k.some(x=>keys.has(x));
    input.x=Number(has('arrowright','d'))-Number(has('arrowleft','q','a'));
    input.y=Number(has('arrowdown','s'))-Number(has('arrowup','z','w'));
    input.charging=has(' ');
  }
  document.addEventListener('keydown',e=>keyboard(e,true)); document.addEventListener('keyup',e=>keyboard(e,false));
  document.addEventListener('click',e=>{
    const mode=e.target.closest('[data-nmode]'), team=e.target.closest('[data-nteam]');
    if(mode) gameAction('nset',{settings:{mode:mode.dataset.nmode}});
    if(team) gameAction('nteam',{amount:Number(team.dataset.nteam)});
  });
  function burst(x,y,color,n) {
    if(reduced)return;
    for(let i=0;i<n;i++){const a=Math.random()*Math.PI*2,v=1+Math.random()*4;particles.push({x,y,vx:Math.cos(a)*v,vy:Math.sin(a)*v,life:1,color});}
    particles=particles.slice(-180);
  }
  function draw(now) {
    if(!root?.isConnected)return;
    frame=requestAnimationFrame(draw);
    if(!realtimeControlsActive())return;
    const w=canvas.clientWidth,h=canvas.clientHeight,dpr=Math.min(devicePixelRatio||1,2);
    if(canvas.width!==Math.round(w*dpr)||canvas.height!==Math.round(h*dpr)){canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);}
    ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);
    const sc=w/25.5, cx=w/2, cy=h*.54, sy=.72;
    const point=(x,y,z=0)=>[cx+x*sc,cy+y*sc*sy-z*sc];
    const line=(points,color,width=1,fill=null)=>{ctx.beginPath();points.forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));if(fill){ctx.closePath();ctx.fillStyle=fill;ctx.fill();}if(color){ctx.strokeStyle=color;ctx.lineWidth=width;ctx.stroke();}};
    const ring=(radius,z=0)=>Array.from({length:97},(_,i)=>point(Math.cos(i*Math.PI/48)*radius,Math.sin(i*Math.PI/48)*radius,z));
    const glow=(color,blur)=>{ctx.shadowColor=color;ctx.shadowBlur=reduced?0:blur;};
    const bg=ctx.createRadialGradient(cx,cy,5,cx,cy,w*.7);bg.addColorStop(0,'#13253e');bg.addColorStop(.6,'#080e22');bg.addColorStop(1,'#060a18');ctx.fillStyle=bg;ctx.fillRect(0,0,w,h);
    // Distant constellations and orbital gantries give the arena its scale.
    for(let i=0;i<48;i++){const x=((i*137.51)%1)*w,y=((i*79.317)%1)*h;ctx.fillStyle=`rgba(159,202,242,${.16+(i%4)*.07})`;ctx.fillRect(x,y,i%5===0?2:1,1);}
    line(ring(11.8,-.65),'#263551',1);line(ring(12.15,-.65),'#17263f',1);
    const radius=snap?.phase==='lobby'?10:Math.max(.15,snap?.radius??10), t=snap?.time||0;
    const danger=radius<5, rim=danger?'#ff668f':'#55e8ff';
    // Suspended slab, front wall and individually lit plates.
    const top=ring(radius), bottom=ring(radius,-.7);
    for(let i=0;i<48;i++) {
      const a=i*Math.PI/48,b=(i+1)*Math.PI/48;
      line([point(Math.cos(a)*radius,Math.sin(a)*radius),point(Math.cos(b)*radius,Math.sin(b)*radius),point(Math.cos(b)*radius,Math.sin(b)*radius,-.7),point(Math.cos(a)*radius,Math.sin(a)*radius,-.7)],null,0,i%4===0?'#213a54':'#0b1b30');
    }
    glow(rim,12);line(bottom, '#23526a',2);ctx.shadowBlur=0;
    const floor=ctx.createLinearGradient(0,cy-radius*sc*sy,0,cy+radius*sc*sy);floor.addColorStop(0,'#162f45');floor.addColorStop(1,'#0d2033');line(top,null,0,floor);
    ctx.save();ctx.beginPath();top.forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));ctx.closePath();ctx.clip();
    for(let i=-10;i<=10;i+=2){line([point(i,-11),point(i,11)],'#284157',.65);line([point(-11,i),point(11,i)],'#284157',.65);}
    line(ring(3.1),'#3a5267',1);line(ring(2.7),'#263f53',1);
    // Arena insignia is actual geometry in the floor, not UI decoration.
    line([point(.4,-1.8),point(-1.2,.3),point(.1,.3),point(-.4,1.8),point(1.3,-.4),point(0,-.4)],null,0,'#36536a');
    ctx.restore();glow(rim,14);line(top,rim,2.2);ctx.shadowBlur=0;
    for(let i=0;i<12;i++){const a=i*Math.PI/6, aa=a+.07;line([point(Math.cos(a)*radius,Math.sin(a)*radius,.08),point(Math.cos(aa)*radius,Math.sin(aa)*radius,.08)],'#e4ffff',2.5);}
    if(snap?.phase==='lobby') {
      const previews=current.players.length?current.players:[{pid:'preview1',name:''},{pid:'preview2',name:''}];
      previews.forEach((p,i)=>{const a=-Math.PI/2+i*Math.PI*2/previews.length;fighter({...p,x:Math.cos(a)*5.6,y:Math.sin(a)*5.6,color:colors[snap.mode==='duo'?snap.teams[p.pid]||0:i%8],alive:true,charge:0,ax:0,ay:1},now);});
    } else if(snap) {
      const lag=Math.min(.09,(now-received)/1000);
      [...snap.fighters].sort((a,b)=>a.y-b.y).forEach(p=>{
        if(!p.alive)return;
        const target={x:p.x+p.vx*lag,y:p.y+p.vy*lag};
        const last=shown.get(p.pid)||target;
        const pos={x:last.x+(target.x-last.x)*.36,y:last.y+(target.y-last.y)*.36};shown.set(p.pid,pos);
        fighter({...p,...pos},now);
      });
    }
    function fighter(p,now) {
      const [x,y]=point(p.x,p.y), r=sc*.53, z=sc*.65;
      const trail=ghosts.get(p.pid)||[];
      if(p.dashing&&!reduced){trail.push([x,y]);if(trail.length>7)trail.shift();}else trail.shift();
      ghosts.set(p.pid,trail);
      trail.forEach((v,i)=>{ctx.globalAlpha=i/trail.length*.27;glow(p.color,12);ctx.fillStyle=p.color;ctx.beginPath();ctx.ellipse(v[0],v[1]-z,r*.8,r*.9,0,0,Math.PI*2);ctx.fill();});ctx.globalAlpha=1;ctx.shadowBlur=0;
      ctx.fillStyle='rgba(0,0,0,.5)';ctx.beginPath();ctx.ellipse(x+3,y+4,r*1.2,r*.5,0,0,Math.PI*2);ctx.fill();
      if(p.pid===snap.me){line([[x-5,y+10],[x,y+14],[x+5,y+10]],'#ffffff',2);}
      if(p.charge>0){glow(p.color,10);ctx.strokeStyle=p.color;ctx.lineWidth=3;ctx.beginPath();ctx.ellipse(x,y,r*1.65,r,0,-Math.PI/2,-Math.PI/2+p.charge*Math.PI*2);ctx.stroke();ctx.shadowBlur=0;}
      const material=ctx.createLinearGradient(x-r,y-z-r,x+r,y);material.addColorStop(0,'#e4fcff');material.addColorStop(.2,p.color);material.addColorStop(1,'#172b43');
      glow(p.color,7);ctx.fillStyle=material;ctx.beginPath();ctx.roundRect(x-r,y-z-r,r*2,r*2.25,r*.65);ctx.fill();ctx.shadowBlur=0;
      ctx.fillStyle='#071421';ctx.beginPath();ctx.roundRect(x-r*.8,y-z-r*.35,r*1.6,r*.72,r*.25);ctx.fill();
      ctx.fillStyle='#e7ffff';ctx.fillRect(x-r*.46+p.ax*2,y-z-r*.15,Math.max(2,r*.22),Math.max(2,r*.17));ctx.fillRect(x+r*.17+p.ax*2,y-z-r*.15,Math.max(2,r*.22),Math.max(2,r*.17));
      ctx.fillStyle=p.color;ctx.beginPath();ctx.roundRect(x-r*.9,y-r*.35,r*.6,r*.5,2);ctx.roundRect(x+r*.3,y-r*.35,r*.6,r*.5,2);ctx.fill();
      if(p.name){ctx.font=`600 ${Math.max(10,Math.min(12,w/32))}px system-ui`;ctx.textAlign='center';ctx.fillStyle='#f3f8ff';ctx.shadowColor='#050c19';ctx.shadowBlur=4;ctx.fillText(p.name.length>13?p.name.slice(0,12)+'…':p.name,x,y-z-r-9);ctx.shadowBlur=0;}
    }
    particles=particles.filter(p=>p.life>0);
    particles.forEach(p=>{p.x+=p.vx*.016;p.y+=p.vy*.016;p.life-=.025;const [x,y]=point(p.x,p.y,.3+p.life);ctx.globalAlpha=p.life;ctx.fillStyle=p.color;ctx.fillRect(x,y,3,3);});ctx.globalAlpha=1;
    if(snap){
      const playing=snap.phase==='play', mine=snap.fighters.find(p=>p.pid===snap.me);
      root.querySelector('.nk-clock').innerHTML=`${Math.ceil(Math.max(0,45-Math.max(0,t)))}<span>s</span>`;
      const callout=root.querySelector('.nk-callout');
      const msg=snap.phase==='countdown'?String(Math.max(1,Math.ceil(-t))):playing&&!mine?.alive?(mine?'Éliminé · regarde la suite':'Spectateur · prochaine manche'):playing&&t<1?'GO !':playing&&t>=12&&t<14?'La bordure se referme':'';
      if(callout.textContent!==msg)callout.textContent=msg;
      callout.classList.toggle('nk-count',snap.phase==='countdown'||msg==='GO !');
      const dash=root.querySelector('.nk-dash'), cool=mine?.cooldown||0;
      dash.style.setProperty('--charge',`${Math.round((mine?.charge||0)*100)}%`);
      dash.querySelector('small').textContent=cool>0?`${cool.toFixed(1)} s`:input.charging?'Relâche !':'Maintenir';
      dash.classList.toggle('cooling',cool>0);
      if(latest && now-latest>1200) {reset();root.querySelector('.nk-network').textContent='Reconnexion…';}
    }
  }
  return {icon,rules,mount,stop};
})();
