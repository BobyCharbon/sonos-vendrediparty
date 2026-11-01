import * as THREE from './vendor/three/three.module.min.js';
import {renderBudget} from './render-budget.js';

// Authored 3D geometry: no background image stands in for the playable terrain.
export function createScene(canvas) {
  const renderer = new THREE.WebGLRenderer({canvas, antialias:true, powerPreference:'high-performance'});
  const sampleBudget=renderBudget(renderer);
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  const scene = new THREE.Scene();
  scene.background = new THREE.Color('#b8e5eb');
  scene.fog = new THREE.Fog('#b8e5eb', 52, 115);
  const camera = new THREE.OrthographicCamera(-14,14,12,-12,.1,170);
  camera.position.set(0,25,28); camera.lookAt(0,-1,0);
  scene.add(new THREE.HemisphereLight('#e5fcff','#8c8060',1.8));
  const sun = new THREE.DirectionalLight('#fff0ce',2.6);
  sun.position.set(-14,25,10); sun.castShadow=true;
  sun.shadow.mapSize.set(1024,1024);
  Object.assign(sun.shadow.camera,{left:-15,right:15,top:15,bottom:-15,near:1,far:70});
  sun.shadow.bias=-.001; sun.shadow.normalBias=.035;
  scene.add(sun);
  const mat=(color,extra={})=>new THREE.MeshStandardMaterial({color,roughness:.88,flatShading:true,...extra});
  const stone=mat('#a88c67'), stoneLight=mat('#c2a078'), sand=mat('#e7c990'), leaves=mat('#4b9a51'), leafLight=mat('#83be50'), trunk=mat('#9a7751');
  const white=mat('#fff7dc'), black=mat('#163942'), straps=mat('#674e39');
  const tileRoot=new THREE.Group(); scene.add(tileRoot);
  const islands=new Map(), characters=new Map();
  const geos={rock:new THREE.CylinderGeometry(1.61,1.05,3.2,6,2),top:new THREE.CylinderGeometry(1.65,1.62,.24,6),
    sand:new THREE.CylinderGeometry(1.66,1.59,.20,6),boulder:new THREE.DodecahedronGeometry(.28),
    body:new THREE.CapsuleGeometry(.29,.28,4,8),head:new THREE.SphereGeometry(.35,12,8),
    foot:new THREE.SphereGeometry(.14,8,6),eye:new THREE.SphereGeometry(.07,8,6),
    leaf:new THREE.SphereGeometry(1,6,4),trunk:new THREE.CylinderGeometry(.065,.13,1.7,6)};
  const rand=n=>{const x=Math.sin(n*127.1+311.7)*43758.5453;return x-Math.floor(x);};
  function mesh(geo,material,parent,x=0,y=0,z=0) {
    const m=new THREE.Mesh(geo,material);m.position.set(x,y,z);m.castShadow=true;m.receiveShadow=true;parent.add(m);return m;
  }
  function palm(parent,x,z,size=1,angle=0) {
    const g=new THREE.Group();g.position.set(x,.16,z);g.scale.setScalar(size);g.rotation.y=angle;parent.add(g);
    const stem=mesh(geos.trunk,trunk,g,.12,.85,0);stem.rotation.z=-.12;
    for(let j=0;j<6;j++) {
      const a=j*Math.PI/3;const leaf=mesh(geos.leaf,j%2?leaves:leafLight,g,Math.cos(a)*.55,1.75,Math.sin(a)*.55);
      leaf.scale.set(.85,.09,.22);leaf.rotation.y=-a;leaf.rotation.z=Math.cos(a)*-.25;
    }
    mesh(geos.boulder,trunk,g,.18,1.62,.1).scale.setScalar(.5);
  }
  // Calm ocean with travelling highlights, generated entirely in the shader.
  const waterMat=new THREE.ShaderMaterial({uniforms:{uTime:{value:0}},vertexShader:`
    varying vec3 world; void main(){vec4 p=modelMatrix*vec4(position,1.0);world=p.xyz;gl_Position=projectionMatrix*viewMatrix*p;}`,
    fragmentShader:`precision highp float;varying vec3 world;uniform float uTime;
    void main(){float a=sin(world.x*1.7+world.z*.6+uTime*.8);float b=sin(world.z*2.2-world.x*.3-uTime*.65);
      float glint=pow(max(0.,a*b),14.);float waves=sin(world.x*.22+world.z*.36+uTime*.3)*.5+.5;
      vec3 c=mix(vec3(.025,.48,.58),vec3(.10,.73,.74),waves);
      c+=glint*.15;float faraway=smoothstep(20.,105.,length(world.xz));c=mix(c,vec3(.72,.9,.92),faraway);
      gl_FragColor=vec4(c,1.);
#include <tonemapping_fragment>\n#include <colorspace_fragment>}`});
  const water=new THREE.Mesh(new THREE.PlaneGeometry(260,260),waterMat);water.rotation.x=-Math.PI/2;water.position.y=-5.6;scene.add(water);
  // Distant, smaller islands establish scale without obscuring the arena.
  for(let i=0;i<12;i++) {
    const a=i/12*Math.PI*2,d=25+rand(i)*23,g=new THREE.Group();g.position.set(Math.cos(a)*d,-5,Math.sin(a)*d);scene.add(g);
    const scale=1.3+rand(i+30)*2.2;
    mesh(geos.rock,stoneLight,g,0,0,0).scale.set(scale,1.6,scale);
    mesh(geos.top,leaves,g,0,2.65,0).scale.set(scale,1,scale);
    const trees=new THREE.Group();trees.position.y=2.7;g.add(trees);palm(trees,0,0,1.5);
  }
  const clouds=[];
  for(let i=0;i<9;i++) {
    const g=new THREE.Group();g.position.set((i-4)*12,9+rand(i)*3,-38-rand(i+3)*18);scene.add(g);clouds.push(g);
    for(let j=0;j<3;j++){const c=mesh(geos.head,white,g,j*1.8,rand(j+i)*.5,0);c.scale.set(5,2,2.5);c.castShadow=false;}
  }
  function buildTiles(tiles) {
    for(const [i,t] of tiles.entries()) {
      if(islands.has(t.id))continue;
      const g=new THREE.Group();g.position.set(t.x,0,t.y);tileRoot.add(g);
      const cliff=geos.rock.clone(),vertices=cliff.attributes.position;
      for(let k=0;k<vertices.count;k++) {
        const y=vertices.getY(k),x=vertices.getX(k),z=vertices.getZ(k);
        const seed=Math.round(x*100)+Math.round(z*100)*31+Math.round(y*100)*7+i*53;
        const jitter=y>1.5?1:.84+rand(seed)*.26;
        vertices.setXYZ(k,x*jitter,y,z*jitter);
      }
      cliff.computeVertexNormals();
      const rock=mesh(cliff,i%3?stone:stoneLight,g,0,-1.75,0);
      mesh(geos.sand,sand,g,0,-.16,0);
      const grass=mat(['#81a947','#739d40','#93b151','#72994a'][i%4]);
      mesh(geos.top,grass,g,0,-.02,0);
      // Angular fracture on the top: it lights up only before collapse.
      const points=[new THREE.Vector3(-.8,.112,-.8),new THREE.Vector3(-.28,.113,-.35),new THREE.Vector3(.15,.113,-.45),new THREE.Vector3(.02,.113,.10),new THREE.Vector3(.5,.113,.55),new THREE.Vector3(.8,.113,1.)];
      const crack=new THREE.Group();
      const fractureMaterial=new THREE.MeshBasicMaterial({color:'#76250b',toneMapped:false});
      for(let j=1;j<points.length;j++) {
        const a=points[j-1],b=points[j],segment=mesh(new THREE.CylinderGeometry(.085,.085,a.distanceTo(b),5),fractureMaterial,crack);
        segment.position.copy(a).add(b).multiplyScalar(.5);segment.position.y=.14;
        segment.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),b.clone().sub(a).normalize());
      }
      crack.visible=false;g.add(crack);
      if(t.ring===3 && i%3===0)palm(g,.4,-.4,.85+rand(i)*.3,i);
      if(i%4===0) {
        const rocklet=mesh(geos.boulder,stoneLight,g,-1,.26,.25);rocklet.scale.set(1.3,.8,1);
        for(let j=0;j<3;j++){const leaf=mesh(geos.leaf,j%2?leaves:leafLight,g,-.95+j*.17,.24,.65);leaf.scale.set(.12,.37,.12);leaf.rotation.z=(j-1)*.5;}
      }
      islands.set(t.id,{g,grass,baseColor:grass.color.clone(),crack,rock,index:i});
    }
  }
  function character(p) {
    const g=new THREE.Group(),body=new THREE.Group();g.add(body);scene.add(g);
    const color=mat(p.color);mesh(geos.body,color,body,0,.55,0);mesh(geos.head,color,body,0,1.01,0);
    for(const side of [-1,1]) {
      mesh(geos.foot,color,body,side*.31,1.3,0).scale.set(.75,1.3,.75);
      mesh(geos.foot,color,body,side*.37,.63,0).scale.set(.7,1.4,.8);
      mesh(geos.eye,black,body,side*.13,1.05,.31);
      const eye=mesh(geos.eye,white,body,side*.13-.015,1.075,.365);eye.scale.setScalar(.28);
    }
    const feet=[mesh(geos.foot,straps,body,-.18,.14,.08),mesh(geos.foot,straps,body,.18,.14,.08)];feet.forEach(f=>f.scale.set(1,.7,1.5));
    mesh(new THREE.BoxGeometry(.36,.36,.18),sand,body,0,.58,-.27);
    const shadow=new THREE.Mesh(new THREE.CircleGeometry(.46,24),new THREE.MeshBasicMaterial({color:'#163d3a',transparent:true,opacity:.22,depthWrite:false}));
    shadow.rotation.x=-Math.PI/2;shadow.position.y=.12;g.add(shadow);
    const markerCanvas=document.createElement('canvas');markerCanvas.width=64;markerCanvas.height=64;
    const mark=markerCanvas.getContext('2d');mark.beginPath();mark.moveTo(8,10);mark.lineTo(56,10);mark.lineTo(32,55);mark.closePath();mark.fillStyle='#fff';mark.fill();mark.strokeStyle='#163d3a';mark.lineWidth=5;mark.stroke();
    const markerTexture=new THREE.CanvasTexture(markerCanvas);markerTexture.colorSpace=THREE.SRGBColorSpace;
    const marker=new THREE.Sprite(new THREE.SpriteMaterial({map:markerTexture,depthTest:false,toneMapped:false}));g.add(marker);marker.visible=false;marker.renderOrder=10;
    const labelCanvas=document.createElement('canvas');labelCanvas.width=256;labelCanvas.height=64;
    const ctx=labelCanvas.getContext('2d');ctx.font='bold 24px sans-serif';ctx.textAlign='center';ctx.fillStyle='#163d3a';
    ctx.beginPath();ctx.roundRect(0,5,256,48,22);ctx.fill();ctx.fillStyle='#fff9e6';ctx.fillText(p.name.slice(0,16),128,37);
    const texture=new THREE.CanvasTexture(labelCanvas);texture.colorSpace=THREE.SRGBColorSpace;
    const label=new THREE.Sprite(new THREE.SpriteMaterial({map:texture,depthTest:false}));label.scale.set(1.8,.45,1);label.position.y=2.18;body.add(label);
    characters.set(p.pid,{g,body,feet,marker,label,shadow,x:p.x,y:p.y,z:p.z||0,fallen:0});return characters.get(p.pid);
  }
  // Shared instanced ground details add vegetation without hundreds of draw calls.
  let groundDetails=false;
  function vegetation(tiles) {
    if(groundDetails)return;groundDetails=true;
    const bladeGeo=new THREE.ConeGeometry(.045,.20,3);
    for(const [i,t] of tiles.entries()) {
      const o=islands.get(t.id),grass=new THREE.InstancedMesh(bladeGeo,leaves,14),dummy=new THREE.Object3D();
      for(let j=0;j<14;j++){
        const a=rand(i*31+j)*Math.PI*2,r=.4+rand(i*23+j+80)*.95;
        dummy.position.set(Math.cos(a)*r,.17,Math.sin(a)*r);dummy.rotation.set(.2,rand(j)*6,.15);dummy.scale.setScalar(.6+rand(j+i)*.8);dummy.updateMatrix();grass.setMatrixAt(j,dummy.matrix);
      }
      grass.castShadow=false;o.g.add(grass);
      for(let j=0;j<2;j++){const pebble=mesh(geos.boulder,j%2?stoneLight:sand,o.g,rand(i+j)*1.8-.9,.14,rand(i+j+20)*1.8-.9);pebble.scale.set(.3,.2,.3);}
    }
  }
  // Éclaboussures : quelques anneaux réutilisés, posés sur l'eau quand une plateforme ou un joueur y tombe.
  const ringGeo=new THREE.RingGeometry(.55,.8,32),splashes=[];
  for(let i=0;i<10;i++){
    const m=new THREE.Mesh(ringGeo,new THREE.MeshBasicMaterial({color:'#eafcff',transparent:true,opacity:0,depthWrite:false,toneMapped:false}));
    m.rotation.x=-Math.PI/2;m.visible=false;scene.add(m);splashes.push({m,t:9,size:1});
  }
  const WATER_Y=-5.55,SPLASH_S=1.1;
  function splash(x,z,size=1){
    const s=splashes.reduce((a,b)=>b.t>a.t?b:a);  // l'anneau le plus ancien
    Object.assign(s,{t:0,size});s.m.position.set(x,WATER_Y,z);s.m.visible=true;
  }
  function drawSplashes(dt){
    for(const s of splashes){
      if(s.t>=SPLASH_S){s.m.visible=false;continue;}
      s.t+=dt;const k=Math.min(1,s.t/SPLASH_S);
      s.m.scale.setScalar(s.size*(.4+2.4*(1-(1-k)**3)));s.m.material.opacity=.85*(1-k);
    }
  }
  const WARN_COLOR=new THREE.Color('#f36a12'),WARN_GLOW=new THREE.Color('#d94c00'),NO_GLOW=new THREE.Color('#000000'),RIGHT=new THREE.Vector3();
  const motion=matchMedia('(prefers-reduced-motion: reduce)');
  // Horloge locale : le serveur envoie l'heure de la manche ~15 fois par seconde ; entre deux réponses, on avance
  // à la vitesse de l'écran et on se recale en douceur (les plateformes tombaient par à-coups).
  let clock=0,clockSnap=null,clockAt=0,clockRound=-1;
  function gameTime(v,now,dt){
    if(v!==clockSnap){clockSnap=v;clockAt=now;}
    const live=v.phase==='play'||v.phase==='countdown';
    const target=v.time+(live?Math.min(.25,(now-clockAt)/1000):0);
    if(!live||clockRound!==v.round||Math.abs(target-clock)>.5){clock=target;clockRound=v.round;return clock;}
    clock+=dt;clock+=(target-clock)*Math.min(1,dt*6);
    return clock;
  }
  let width=0,height=0,last=0,round=-1,disposed=false;
  function draw(v, now, roster) {
    if(disposed)return;
    const w=canvas.clientWidth,h=canvas.clientHeight;if(!w||!h)return;
    if(w!==width||h!==height) {
      width=w;height=h;renderer.setSize(w,h,false);
      const aspect=w/h, halfW=Math.max(11.8,8.8*aspect),halfH=halfW/aspect;
      camera.left=-halfW;camera.right=halfW;camera.top=halfH*(aspect<.85?.73:1.03);camera.bottom=-halfH*(aspect<.85?1.27:.97);camera.updateProjectionMatrix();
    }
    const dt=Math.min(.05,(now-last)/1000||.016);last=now;
    const reduced=motion.matches;
    const t=gameTime(v,now,dt);waterMat.uniforms.uTime.value=reduced?0:now/1000;
    buildTiles(v.tiles);vegetation(v.tiles);
    for(const tile of v.tiles) {
      const o=islands.get(tile.id),fall=Math.max(0,t-tile.fall),warn=t>=tile.fall-v.warning&&t<tile.fall;
      // Avant la chute, la fissure s'accélère : la plateforme tremble de plus en plus fort, puis bascule.
      const urgency=warn?1-(tile.fall-t)/v.warning:0,shake=warn&&!reduced?(.02+urgency*.06)*Math.sin(now*(.03+urgency*.03)+o.index):0;
      o.g.visible=fall<2.4;o.g.position.y=-Math.min(20,fall*fall*6);o.g.rotation.z=fall*.22+shake*.4;
      o.g.position.x=tile.x+shake;
      const sunk=o.g.position.y<WATER_Y+.3;
      if(sunk&&!o.splashed&&!reduced&&fall<1.3)splash(tile.x,tile.y,1.5);  // chute récente seulement (pas à l'ouverture)
      o.splashed=sunk;
      o.grass.color.copy(warn?WARN_COLOR:o.baseColor);
      o.grass.emissive.copy(warn?WARN_GLOW:NO_GLOW);o.grass.emissiveIntensity=warn?.12+urgency*.25*(.5+.5*Math.sin(now*.02)):0;
      o.crack.visible=warn;
    }
    const fighters=v.phase==='lobby'?roster.map((p,i)=>({...p,x:Math.cos(i*2.4)*4,y:Math.sin(i*2.4)*3,z:0,alive:true,color:['#20c9d0','#f66b60','#f4bd40','#a185e8','#78ba60','#ef91ba','#539cef','#ef984b'][i]})):v.fighters;
    const ids=new Set(fighters.map(p=>p.pid));
    for(const [id,c] of characters)c.g.visible=ids.has(id);
    for(const p of fighters) {
      const c=characters.get(p.pid)||character(p),fresh=round!==v.round;
      c.g.visible=true;const dx=p.x-c.x,dy=p.y-c.y,smooth=1-Math.exp(-dt*20);
      c.x=fresh?p.x:c.x+dx*smooth;c.y=fresh?p.y:c.y+dy*smooth;c.z=fresh?p.z:c.z+(p.z-c.z)*smooth;
      c.fallen=p.alive?0:c.fallen+dt;
      // Saut : étiré en montant, écrasé à l'atterrissage (le ressort revient en ~0,2 s).
      const vz=(c.z-(c.prevZ??c.z))/Math.max(dt,.001);c.prevZ=c.z;
      if(c.wasUp&&c.z<.04&&vz<=0)c.squash=1;c.wasUp=c.z>.12;
      c.squash=Math.max(0,(c.squash||0)-dt*5);
      const stretch=reduced||!p.alive?0:Math.max(-.12,Math.min(.18,vz*.035))-c.squash*.22;
      c.g.position.set(c.x,0,c.y);c.body.scale.set(1.18*(1-stretch*.5),1.18*(1+stretch),1.18*(1-stretch*.5));
      c.body.position.y=p.alive?c.z:-c.fallen*c.fallen*7;
      if(!p.alive&&!c.splashed&&c.body.position.y<WATER_Y+.4){c.splashed=true;if(!reduced)splash(c.x,c.y,.8);}
      if(p.alive)c.splashed=false;
      c.g.visible=c.fallen<1.3;c.shadow.visible=p.alive&&c.z<.2;c.marker.visible=p.pid===v.me;
      c.label.visible=p.alive;
      // Screen-sized marker stays clear of the name label on narrow phones.
      const unitPerPixel=(camera.top-camera.bottom)/h;
      c.marker.scale.setScalar(18*unitPerPixel);
      c.marker.position.set(0,c.body.position.y+2.18*1.18,0);
      c.marker.position.addScaledVector(RIGHT.set(1,0,0).applyQuaternion(camera.quaternion),1.8*1.18/2+14*unitPerPixel);
      const moving=Math.hypot(dx,dy)>.015;
      if(moving)c.body.rotation.y=Math.atan2(dx,dy);
      c.feet.forEach((f,i)=>f.position.y=.14+(moving&&!reduced?Math.sin(now*.018+i*Math.PI)*.08:0));
      c.body.rotation.z=p.alive?0:c.fallen;
    }
    drawSplashes(dt);
    round=v.round;sampleBudget(now);renderer.render(scene,camera);
  }
  function dispose() {
    disposed=true;
    const geometries=new Set(),materials=new Set(),textures=new Set();
    scene.traverse(o=>{if(o.geometry)geometries.add(o.geometry);if(o.material)for(const m of [].concat(o.material)){materials.add(m);if(m.map)textures.add(m.map);}});
    Object.values(geos).forEach(g=>geometries.add(g));
    geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());textures.forEach(t=>t.dispose());
    sun.shadow.map?.dispose();renderer.dispose();renderer.forceContextLoss();
  }
  return {draw,dispose};
}
