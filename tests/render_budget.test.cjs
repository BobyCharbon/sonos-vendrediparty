const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const source=fs.readFileSync('app/static/render-budget.js','utf8');
async function setup(){
 global.devicePixelRatio=3;
 const {renderBudget}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
 const ratios=[];return {sample:renderBudget({setPixelRatio:r=>ratios.push(r)}),ratios};
}
test('sustained slow frames reduce resolution to a bounded floor',async()=>{
 const {sample,ratios}=await setup();
 for(let t=40;t<18000;t+=40)sample(t);
 assert.equal(ratios[0],1.5);assert.equal(ratios.at(-1),.85);
 assert.ok(ratios.every((r,i)=>!i||r<ratios[i-1]));
});
test('smooth rendering and a hidden-tab gap do not lower resolution',async()=>{
 const {sample,ratios}=await setup();
 for(let t=16;t<4000;t+=16)sample(t);
 sample(20000);
 for(let t=20016;t<24000;t+=16)sample(t);
 assert.deepEqual(ratios,[1.5]);
});
