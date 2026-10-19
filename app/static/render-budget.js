// Lower render resolution after sustained slow frames; gameplay coordinates stay unchanged.
export function renderBudget(renderer, maxRatio=1.5) {
  let ratio=Math.min(devicePixelRatio||1,maxRatio), previous=0, elapsed=0, frames=0;
  renderer.setPixelRatio(ratio);
  return function sample(now) {
    const dt=now-previous;previous=now;
    if(dt<=0||dt>250){elapsed=frames=0;return;}
    elapsed+=dt;frames++;
    if(elapsed<2000)return;
    if(elapsed/frames>27&&ratio>.85){ratio=Math.max(.85,ratio-.2);renderer.setPixelRatio(ratio);}
    elapsed=frames=0;
  };
}
