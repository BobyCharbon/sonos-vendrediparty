const {test}=require('node:test');
const assert=require('node:assert/strict');
const M=require('../app/static/motion.js');

test('a critically damped spring settles on the target without overshooting',()=>{
 let s={x:0,v:0},max=0;
 for(let i=0;i<120;i++){s=M.stepSpring(s,100,1/60,0.35,1);max=Math.max(max,s.x);}
 assert.ok(Math.abs(s.x-100)<0.5,`ended at ${s.x}`);
 assert.ok(max<=100.01,`overshot to ${max}`);
});
test('a bouncy spring (damping 0.8) overshoots a little, then settles',()=>{
 let s={x:0,v:0},max=0;
 for(let i=0;i<180;i++){s=M.stepSpring(s,100,1/60,0.3,0.8);max=Math.max(max,s.x);}
 assert.ok(max>100.5&&max<110,`peak ${max}`);
 assert.ok(Math.abs(s.x-100)<0.5);
});
test('the release velocity carries the value forward before it returns (no seam)',()=>{
 const s=M.stepSpring({x:0,v:2000},0,1/60,0.35,1);
 assert.ok(s.x>20,`moved only ${s.x}`);
});
test('stepping never mutates the previous state',()=>{
 const before=Object.freeze({x:3,v:4});
 M.stepSpring(before,10,1/60,0.3,1);
 assert.deepEqual(before,{x:3,v:4});
});
test('momentum projection follows the iOS scroll deceleration',()=>{
 assert.equal(M.project(0),0);
 assert.ok(Math.abs(M.project(1000)-499)<1);
 assert.ok(M.project(-500)<0);
});
test('rubber-banding resists more the further past the edge',()=>{
 const a=M.rubberband(50,800),b=M.rubberband(200,800),c=M.rubberband(-200,800);
 assert.ok(a<50&&b<200&&b>a);
 assert.equal(c,-b);
 assert.ok(b/200<a/50);
});
test('velocity comes from the recent finger points only',()=>{
 const v=M.velocityTracker(100);
 v.add(0,0,0);v.add(500,0,400);          // vieux points, ignorés
 v.add(510,0,550);v.add(530,20,600);
 const {x,y}=v.velocity();
 assert.ok(Math.abs(x-400)<1&&Math.abs(y-400)<1,`${x},${y}`);
 v.reset();assert.deepEqual(v.velocity(),{x:0,y:0});
});
test('spring() animates to the target and calls onDone once',async()=>{
 const values=[];let done=0;
 await new Promise((ok)=>M.spring({from:0,to:50,response:0.2,onUpdate:(x)=>values.push(x),onDone:()=>{done++;ok();}}));
 assert.equal(values.at(-1),50);assert.equal(done,1);
});
test('a spring can be grabbed mid-flight and reports where it was',async()=>{
 let anim;
 const state=await new Promise((ok)=>{let n=0;anim=M.spring({from:0,to:300,onUpdate:()=>{if(++n===5)ok(anim.stop());}});});
 assert.ok(state.x>0&&state.x<300&&state.v>0);
});
