import * as THREE from './vendor/three/three.module.min.js';

export function createScene(canvas){
  const renderer=new THREE.WebGLRenderer({canvas,antialias:true,powerPreference:'high-performance'});
  renderer.setPixelRatio(Math.min(devicePixelRatio||1,1.6));renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;
  renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.05;
  const scene=new THREE.Scene();scene.background=new THREE.Color('#101a30');
  const camera=new THREE.OrthographicCamera(-15,15,12,-12,.1,100);
  scene.add(new THREE.HemisphereLight('#ccddff','#514364',1.4));
  const moon=new THREE.DirectionalLight('#d4e6ff',3);moon.position.set(-10,25,12);moon.castShadow=true;moon.shadow.mapSize.set(1024,1024);
  Object.assign(moon.shadow.camera,{left:-15,right:15,top:14,bottom:-14,near:1,far:65});moon.shadow.normalBias=.03;scene.add(moon);
  const geo=new Set(),mats=new Set(),textures=new Set();
  const material=(color,extra={})=>{const m=new THREE.MeshStandardMaterial({color,roughness:.7,...extra});mats.add(m);return m;};
  const basic=(color,extra={})=>{const m=new THREE.MeshBasicMaterial({color,...extra});mats.add(m);return m;};
  const navy=material('#243557'),gold=material('#e7b854',{metalness:.5,roughness:.3}),ivory=material('#e2d7bd'),dark=material('#1b2038'),skin=material('#f6cfac'),pink=basic('#ef8fb2'),green=basic('#5ddfb0'),red=basic('#ff4568'),cyan=basic('#62dce0');
  const boxGeo=new THREE.BoxGeometry(1,1,1),sphereGeo=new THREE.SphereGeometry(1,12,8),cylinderGeo=new THREE.CylinderGeometry(1,1,1,12),gemGeo=new THREE.OctahedronGeometry(.32);[boxGeo,sphereGeo,cylinderGeo,gemGeo].forEach(g=>geo.add(g));
  function mesh(g,m,parent,x=0,y=0,z=0){const o=new THREE.Mesh(g,m);o.position.set(x,y,z);o.castShadow=true;o.receiveShadow=true;parent.add(o);return o;}
  function box(parent,m,x,y,z,w,h,d){const o=mesh(boxGeo,m,parent,x,y,z);o.scale.set(w,h,d);return o;}
  function sphere(parent,m,x,y,z,r){const o=mesh(sphereGeo,m,parent,x,y,z);o.scale.setScalar(r);return o;}
  function text(parent,value,x,y,z,color='#fff3ce',width=2.8){
    const c=document.createElement('canvas');c.width=384;c.height=96;const ctx=c.getContext('2d');
    ctx.fillStyle='#132039';ctx.beginPath();ctx.roundRect(4,8,376,80,20);ctx.fill();ctx.fillStyle=color;ctx.font='bold 38px sans-serif';ctx.textAlign='center';ctx.fillText(value,192,62);
    const t=new THREE.CanvasTexture(c);t.colorSpace=THREE.SRGBColorSpace;textures.add(t);const m=new THREE.SpriteMaterial({map:t,depthTest:false});mats.add(m);
    const o=new THREE.Sprite(m);o.position.set(x,y,z);o.scale.set(width,width/4,1);parent.add(o);return o;
  }
  const sharedMaterials=new Set(mats),sharedGeometry=new Set(geo);
  let world=null,mapID=-1,round=-1,lasers=[],treasures=[],guardModels=[],characters=new Map(),width=0,height=0,last=0,disposed=false;
  function statue(parent,x,z,kind){
    box(parent,ivory,x,.25,z,.9,.5,.9);box(parent,gold,x,.53,z,1,.08,1);
    if(kind===2){const a=mesh(cylinderGeo,gold,parent,x,1,z);a.scale.set(.38,.9,.38);sphere(parent,ivory,x,1.65,z,.3);}
    else if(kind===1){const a=mesh(gemGeo,gold,parent,x,1,z);a.scale.setScalar(2);a.rotation.y=.4;}
    else{const a=mesh(cylinderGeo,ivory,parent,x,.95,z);a.scale.set(.22,.8,.22);sphere(parent,ivory,x,1.5,z,.33);box(parent,ivory,x,1.08,z,.8,.18,.24);}
  }
  function build(v){
    if(world){scene.remove(world);characters.clear();for(const m of mats)if(!sharedMaterials.has(m)){m.dispose();mats.delete(m);}for(const g of geo)if(!sharedGeometry.has(g)){g.dispose();geo.delete(g);}textures.forEach(t=>t.dispose());textures.clear();}world=new THREE.Group();scene.add(world);mapID=v.map.id;lasers=[];treasures=[];guardModels=[];
    const palette=[['#364f74','#405c80','#314667'],['#386567','#487c78','#294c54'],['#81634e','#98765a','#644e43']][mapID];
    const floorM=[material(palette[0]),material(palette[1])],wallM=material(palette[2]),glass=material('#92cfec',{transparent:true,opacity:.16,depthWrite:false,roughness:.1});
    box(world,dark,0,-.45,0,22,.9,20);box(world,gold,0,-.08,0,21.8,.12,19.8);
    // Two instanced batches keep the marble floor inexpensive on phones.
    for(let shade=0;shade<2;shade++){
      const tiles=[];for(let x=-10;x<=10;x+=2)for(let z=-9;z<=9;z+=2)if((x/2+Math.floor(z/2)+20)%2===shade)tiles.push([x,z]);
      const floor=new THREE.InstancedMesh(boxGeo,floorM[shade],tiles.length),dummy=new THREE.Object3D();
      tiles.forEach(([x,z],i)=>{dummy.position.set(x,.01,z);dummy.scale.set(1.96,.12,1.96);dummy.updateMatrix();floor.setMatrixAt(i,dummy.matrix);});floor.receiveShadow=true;world.add(floor);
    }
    // Low cutaway walls leave every route visible from above.
    for(const [x,z,w,d] of v.map.walls){box(world,wallM,x,.55,z,w,1.1,d);box(world,wallM,x,1.12,z,w+.05,.06,d+.05);for(const edge of [-1,1]){box(world,gold,x+edge*w/2,1.17,z,.055,.05,d);box(world,gold,x,1.17,z+edge*d/2,w,.05,.055);}}
    box(world,wallM,0,.85,-10,22,1.7,.35);box(world,gold,0,1.72,-10,22,.08,.4);
    for(const x of [-11,11]){box(world,wallM,x,.35,0,.35,.7,20);box(world,gold,x,.73,0,.4,.06,20);}
    // Back-wall gallery: gilded frames with authored abstract canvases.
    for(let i=0;i<5;i++){
      const x=(i-2)*4;box(world,gold,x,1.05,-9.77,1.7,1.3,.12);box(world,navy,x,1.05,-9.68,1.45,1.08,.08);
      const orb=sphere(world,material(['#b484d7','#e8b95e','#79bdc7'][mapID]),x,1.12,-9.58,.34);orb.scale.z=.1;
      box(world,ivory,x+.25,.75,-9.57,.8,.12,.05);
    }
    for(const x of [-10.5,10.5])for(const z of [-8,0,8]){const col=mesh(cylinderGeo,ivory,world,x,.9,z);col.scale.set(.22,1.8,.22);box(world,gold,x,1.82,z,.6,.12,.6);}
    for(const [i,w] of v.map.walls.entries())statue(world,w[0],w[1],mapID);
    const [ex,ez]=v.map.exit,[jx,jz]=v.map.jail;
    box(world,green,ex,.11,ez,2.8,.08,2.1);text(world,'SORTIE',ex,.7,ez+1,'#9bffcd',2.2);
    box(world,pink,jx,.12,jz,2.6,.08,2);text(world,'PRISON',jx,1.8,jz,'#ffb8d1',2.4);
    for(let x=jx-1.2;x<=jx+1.3;x+=.4)box(world,gold,x,.7,jz+.9,.08,1.4,.08);
    box(world,gold,jx,1.4,jz+.9,2.6,.1,.1);
    const [sx,sz]=v.map.switch;box(world,navy,sx,.45,sz,.65,.9,.5);box(world,cyan,sx,.95,sz,.6,.12,.5);text(world,'LASERS',sx,1.65,sz,'#89f2ef',1.7);
    for(const line of v.map.lasers){
      const [ax,az,bx,bz]=line,l=Math.hypot(bx-ax,bz-az),g=new THREE.Group();world.add(g);
      for(const [x,z] of [[ax,az],[bx,bz]]){box(world,navy,x,.35,z,.35,.7,.35);sphere(world,red,x,.73,z,.13);}
      for(const h of [.3,.65]){const beam=box(g,red,(ax+bx)/2,h,(az+bz)/2,l,.06,.06);beam.rotation.y=-Math.atan2(bz-az,bx-ax);}
      lasers.push(g);
    }
    const source=v.treasures.length?v.treasures:v.map.treasures.map(([x,y],id)=>({x,y,id,status:'floor'}));
    for(const t of source){
      const g=new THREE.Group();g.position.set(t.x,0,t.y);world.add(g);box(g,navy,0,.25,0,.65,.5,.65);box(g,gold,0,.52,0,.72,.06,.72);
      box(g,glass,0,.88,0,.73,.68,.73);const gem=mesh(gemGeo,gold,g,0,.88,0);treasures[t.id]={g,gem};
    }
    for(let i=0;i<v.map.patrols.length;i++){
      const c=person('#526d9c',true);world.add(c.g);guardModels.push(c);
      const shape=new THREE.Shape();shape.moveTo(0,0);for(let a=-.55;a<=.551;a+=.055)shape.lineTo(Math.sin(a)*4.6,Math.cos(a)*4.6);shape.lineTo(0,0);
      const cg=new THREE.ShapeGeometry(shape);geo.add(cg);const cone=mesh(cg,basic('#ffd96a',{transparent:true,opacity:.22,depthWrite:false,side:THREE.DoubleSide}),c.g,0,.16,0);cone.rotation.x=Math.PI/2;
      // Shape y maps to world +z through the negative X rotation.
      cone.rotation.x=-Math.PI/2;cone.scale.y=-1;c.cone=cone;
    }
  }
  function person(color,guard=false){
    const g=new THREE.Group(),body=new THREE.Group();g.add(body);const suit=material(color);
    const torso=mesh(cylinderGeo,suit,body,0,.52,0);torso.scale.set(.28,.58,.24);
    sphere(body,skin,0,1.0,0,.27);box(body,dark,0,1.03,.225,.53,.15,.08);
    for(const x of [-.12,.12])sphere(body,ivory,x,1.04,.278,.045);
    const cap=sphere(body,guard?navy:suit,0,1.19,0,.28);cap.scale.y=.5;
    if(guard){box(body,navy,0,1.2,.22,.5,.08,.3);box(body,gold,0,.66,.25,.12,.16,.04);}
    else{box(body,ivory,0,.52,.25,.54,.07,.025);box(body,ivory,0,.38,.25,.53,.07,.025);}
    const feet=[box(body,dark,-.14,.1,.06,.2,.2,.32),box(body,dark,.14,.1,.06,.2,.2,.32)];
    const bag=sphere(body,gold,0,.55,-.32,.3);bag.visible=false;
    return{g,body,feet,bag,x:0,y:0};
  }
  function draw(v,now,roster){
    if(disposed)return;
    if(!world||mapID!==v.map.id)build(v);
    const w=canvas.clientWidth,h=canvas.clientHeight;if(!w||!h)return;
    if(w!==width||h!==height){width=w;height=h;renderer.setSize(w,h,false);}
    const aspect=w/h,playing=['play','countdown'].includes(v.phase),mine=v.fighters.find(p=>p.pid===v.me),dt=Math.min(.05,(now-last)/1000||.016);last=now;
    let cx=0,cz=0,halfW;
    if(playing&&(aspect<.85||h<500)&&mine){halfW=aspect<.85?6.3:10;cx=Math.max(-5,Math.min(5,mine.x));cz=Math.max(-6,Math.min(6,mine.y-1));}
    else{halfW=Math.max(13,10*aspect);if(!playing&&aspect>1.3)cx=-3;}
    const halfH=halfW/aspect;camera.left=-halfW;camera.right=halfW;camera.top=halfH;camera.bottom=-halfH;camera.position.set(cx,30,cz+18);camera.lookAt(cx,0,cz);camera.updateProjectionMatrix();
    for(let i=0;i<lasers.length;i++)lasers[i].visible=playing?v.lasers[i]:true;
    for(const t of v.treasures){const o=treasures[t.id];o.g.visible=t.status==='floor';o.g.position.set(t.x,0,t.y);o.gem.rotation.y=now*.001;}
    for(let i=0;i<guardModels.length;i++){
      const c=guardModels[i],p=v.guards[i]||{x:v.map.patrols[i][0][0],y:v.map.patrols[i][0][1],angle:0};
      c.g.position.set(p.x,0,p.y);c.g.rotation.y=p.angle;c.feet.forEach((f,j)=>f.position.y=.12+Math.sin(now*.009+j*Math.PI)*.06);
    }
    const people=playing||v.phase==='results'?v.fighters:roster.map((p,i)=>({...p,x:(i%4-1.5)*1.5,y:7.8+Math.floor(i/4)*.8,color:['#56ded7','#fc846c','#f4cc63','#b69cff','#91d077','#f397cc','#80b6ff','#ffac67'][i],active:true}));
    const ids=new Set(people.map(p=>p.pid));for(const [id,c] of characters)c.g.visible=ids.has(id);
    for(const p of people){
      let c=characters.get(p.pid);if(!c){c=person(p.color);world.add(c.g);c.label=text(c.g,p.name,0,1.8,0,'#ffffff',1.8);const mc=document.createElement('canvas');mc.width=64;mc.height=64;const pen=mc.getContext('2d');pen.beginPath();pen.moveTo(7,10);pen.lineTo(57,10);pen.lineTo(32,56);pen.closePath();pen.fillStyle='#fff';pen.fill();pen.lineWidth=5;pen.strokeStyle='#17233c';pen.stroke();const mt=new THREE.CanvasTexture(mc);textures.add(mt);const mm=new THREE.SpriteMaterial({map:mt,depthTest:false,toneMapped:false});mats.add(mm);c.marker=new THREE.Sprite(mm);c.g.add(c.marker);characters.set(p.pid,c);c.x=p.x;c.y=p.y;}
      const dx=p.x-c.x,dy=p.y-c.y,fresh=round!==v.round||Math.hypot(dx,dy)>3;
      c.x=fresh?p.x:c.x+dx*(1-Math.exp(-dt*18));c.y=fresh?p.y:c.y+dy*(1-Math.exp(-dt*18));c.g.position.set(c.x,0,c.y);c.g.visible=p.active;
      c.bag.visible=p.bag!=null;c.marker.visible=p.pid===v.me;c.label.material.color.set(p.jailed?'#ff9cbc':'#ffffff');
      const units=2*halfW/w;c.body.scale.setScalar(1.2);c.label.visible=p.pid===v.me||p.jailed;c.label.scale.set(80*units,20*units,1);c.label.position.y=2.05;c.marker.scale.set(22*units,18*units,1);c.marker.position.set(0,2.7,0);
      if(Math.hypot(dx,dy)>.01)c.body.rotation.y=Math.atan2(dx,dy);
      c.feet.forEach((f,i)=>f.position.y=.1+(Math.hypot(dx,dy)>.01?Math.sin(now*.015+i*Math.PI)*.07:0));
    }
    round=v.round;renderer.render(scene,camera);
  }
  function dispose(){disposed=true;geo.forEach(g=>g.dispose());mats.forEach(m=>m.dispose());textures.forEach(t=>t.dispose());moon.shadow.map?.dispose();renderer.dispose();renderer.forceContextLoss();}
  return{draw,dispose};
}
