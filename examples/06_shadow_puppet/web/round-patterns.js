/* Deal each route once, so previews, cues and scoring follow the same round. */
(() => {
  "use strict";
  function shuffle(values) {
    const result=values.slice();
    for(let i=result.length-1;i>0;i--) {
      const j=Math.floor(Math.random()*(i+1));
      [result[i],result[j]]=[result[j],result[i]];
    }
    return result;
  }
  function relay(ids,previousFirst) {
    const order=shuffle(ids);
    if(order.length>1 && order[0]===previousFirst) {
      const j=1+Math.floor(Math.random()*(order.length-1));
      [order[0],order[j]]=[order[j],order[0]];
    }
    return order;
  }
  function melody() {
    // Two familiar opening notes. Then each hand plays a two-note phrase.
    const left=shuffle([0,1,3,4]), right=shuffle([5,6,8,9]);
    const [a,b]=Math.random()<.5 ? [left,right] : [right,left];
    return [2,7,a[0],a[1],b[0],b[1],a[2],b[2]];
  }
  function gates(lanes) {
    // Six gates, balanced across the two camera sides or the three keyboard lanes.
    return Array.from({length:6/lanes.length},()=>shuffle(lanes)).flat();
  }
  function gatePeriod(base,cleared) {return cleared>=3 ? base/1.2 : base;}
  function jumpTempo(cleared) {return cleared>=2 ? 1.16 : 1;}
  window.RoundPatterns=Object.freeze({relay,melody,gates,gatePeriod,jumpTempo});
})();
