/* Ten keys laid out in mirror view, from the left little finger to the right little finger. */
(() => {
  "use strict";
  const names = ["小指","无名指","中指","食指","拇指","拇指","食指","中指","无名指","小指"];
  const tips = [20,16,12,8,4,4,8,12,16,20];
  const notes = ["C4","D4","E4","F4","G4","A4","B4","C5","D5","E5"];
  const phrase = Object.freeze([2,7,3,6,1,8,4,5]);
  const chains = [[0,1,2,3,4],[0,5,6,7,8],[5,9,13,17,0],[9,10,11,12],[13,14,15,16],[17,18,19,20]];
  const sideName = side => side ? "右手" : "左手";
  const label = key => sideName(Number(key>=5)) + names[key];
  function locate(hands) {
    const slots = [null,null];
    for (const points of hands || []) {
      if (points?.length!==21 || !points.every(p=>p && p.length>=2 && Number.isFinite(p[0]) && Number.isFinite(p[1]))) continue;
      const x=points[0][0], side=Number(x>=.5);
      const center=side ? .75 : .25;
      if (!slots[side] || Math.abs(x-center)<Math.abs(slots[side][0][0]-center)) slots[side]=points;
    }
    return slots;
  }
  class Tracker {
    constructor() { this.hands=[null,null]; }
    read(slots,aspect,now) {
      const depths=Array(10).fill(null), presses=[];
      const distance=(a,b)=>Math.hypot((a[0]-b[0])*aspect,a[1]-b[1]);
      for (const [side,points] of slots.entries()) {
        const size=points && distance(points[0],points[9]);
        if (!points || size<.018) { this.hands[side]=null; continue; }
        const start=5*side;
        const reach=tips.slice(start,start+5).map(tip=>distance(points[tip===4?17:0],points[tip])/size);
        let hand=this.hands[side];
        if (!hand || now-hand.time>600 || distance(points[0],hand.wrist)>size*1.8) {
          hand={rest:reach.slice(),held:Array(5).fill(false)};
          this.hands[side]=hand;
        }
        hand.time=now; hand.wrist=points[0];
        const delta=reach.map((r,i)=>hand.rest[i]-r);
        // Subtract the common motion of the palm. A wrist bob or closing the whole
        // hand is not a note. Landmark IDs keep the keys stable when fingers overlap.
        const common=delta.slice().sort((a,b)=>a-b)[2];
        for (let i=0;i<5;i++) {
          const amount=delta[i]-common;
          depths[start+i]=Math.max(0,Math.min(1,amount/.22));
          if (amount<.075) hand.held[i]=false;
          if (!hand.held[i] && amount>=.22) {
            hand.held[i]=true;
            presses.push({key:start+i,amount});
          }
          if (!hand.held[i] && Math.abs(amount)<.1) hand.rest[i]+=(reach[i]-hand.rest[i])*.04;
          else if (reach[i]>hand.rest[i]) hand.rest[i]=reach[i];
        }
      }
      return {depths,press:presses.sort((a,b)=>b.amount-a.amount)[0]?.key};
    }
  }
  window.FingerPiano=Object.freeze({names,tips,notes,phrase,chains,label,sideName,locate,Tracker});
})();
