/* Both the rehearsal and the live instrument use the same ten keys and fingertip IDs. */
(() => {
  "use strict";
  const piano=window.FingerPiano;
  const dark="#30293e", ivory="#fff0cc", amber="#ffcb78", colors=["#9de0b7","#c4b5ef"];
  const notes=["C4","D4","E4","F4","G4","A4","B4","C5","D5","E5"];
  const open=[
    [0,41],[7,33],[16,25],[23,18],[28,12], [9,16],[12,4],[13,-5],[14,-13],
    [2,13],[3,0],[3,-11],[3,-20], [-6,15],[-8,2],[-10,-7],[-11,-14],
    [-13,21],[-18,13],[-21,6],[-24,-1]
  ];
  function demoHand(side,depths) {
    return open.map(([x,y],i)=>{
      const finger=i ? Math.floor((i-1)/4) : -1;
      if (finger>=0) {
        const key=side?5+finger:4-finger, flex=depths?.[key] || 0;
        const joint=(i-1)%4;
        x-=Math.sign(x)*flex*joint*1.3; y+=flex*joint*6.5;
      }
      return [.25+.5*side+(side?-x:x)/230,.52+y/130];
    });
  }
  function text(c,word,x,y,size,color,align="left") {
    c.font="bold "+size+'px "Microsoft YaHei",system-ui,sans-serif';
    c.textAlign=align;c.textBaseline="middle";c.fillStyle=color;c.fillText(word,x,y);
  }
  function skeleton(c,points,color,targetTip,light=false) {
    const link=(ids,thick,ink)=>{
      c.strokeStyle=ink;c.lineWidth=thick;c.lineJoin="round";c.lineCap="round";
      c.beginPath();for (const [i,id] of ids.entries()) {const [x,y]=points[id];if(i)c.lineTo(x,y);else c.moveTo(x,y);}c.stroke();
    };
    const palm=[0,1,5,9,13,17];
    c.beginPath();for(const [i,id] of palm.entries()) {const [x,y]=points[id];if(i)c.lineTo(x,y);else c.moveTo(x,y);}c.closePath();
    c.fillStyle=light?"#12232566":"#4b495b";c.fill();
    for(const ids of piano.chains) link(ids,light?4:5,dark);
    for(const ids of piano.chains) link(ids,light?2:2.5,color);
    if (targetTip!=null) {
      const finger=Math.floor(targetTip/4)-1;
      link([4*finger+1,4*finger+2,4*finger+3,targetTip],light?3:3.5,amber);
    }
    points.forEach(([x,y],id)=>{
      const tip=id!==0 && id%4===0;
      c.beginPath();c.arc(x,y,id===targetTip?4.2:tip?2.4:1.65,0,Math.PI*2);
      c.fillStyle=id===targetTip?amber:tip?ivory:color;c.fill();
      c.strokeStyle=dark;c.lineWidth=id===targetTip?1.2:.6;c.stroke();
    });
  }
  function draw(c,width,height,visual,{demo=false,aspect=1,count=0,ready=false}={}) {
    c.save();c.scale(width/384,height/210);
    const target=visual.target_key ?? 2, hands=visual.hand_points || [null,null];
    const fill=(x,y,w,h,col)=>{c.fillStyle=col;c.fillRect(x,y,w,h);};
    // The status strip and the two hand windows sit over the sunset stage.
    fill(12,7,360,23,"#322a40");fill(14,9,3,19,amber);
    text(c,demo?"指法示范":"落日合奏",23,19,11,ivory);
    text(c,(ready?"准备 · ":"下一音 · ")+piano.label(target),192,19,13,amber,"center");
    text(c,demo?"♪":Math.floor(count)+" / 8",359,19,11,ivory,"right");
    for(const side of [0,1]) {
      const x=13+side*183,active=Number(target>=5)===side,pts=hands[side];
      fill(x,34,175,92,"#292639e8");fill(x,34,175,2,active?amber:"#72677f");
      text(c,piano.sideName(side),x+9,47,11,colors[side]);
      if(!pts){text(c,"等待入镜",x+89,82,12,"#d4c9cb","center");continue;}
      const xs=pts.map(p=>p[0]*aspect),ys=pts.map(p=>p[1]);
      const cx=(Math.min(...xs)+Math.max(...xs))/2, cy=(Math.min(...ys)+Math.max(...ys))/2;
      const scale=Math.min(110/Math.max(.02,Math.max(...xs)-Math.min(...xs)),74/Math.max(.02,Math.max(...ys)-Math.min(...ys)));
      const mapped=pts.map((_,i)=>[x+88+(xs[i]-cx)*scale,80+(ys[i]-cy)*scale]);
      skeleton(c,mapped,colors[side],active?piano.tips[target]:null);
      fill(x+157,43,4,4,colors[side]);
    }
    fill(10,130,364,75,dark);fill(13,133,358,69,"#9d7b7e");
    fill(16,136,352,61,"#534758");
    for(let k=0;k<10;k++) {
      const x=18+k*34.5+(k>=5?3:0),pressed=visual.keys_lit?.includes(k),selected=k===target;
      const down=pressed?4:0, col=pressed?colors[Number(k>=5)]:selected?amber:ivory;
      fill(x,138+down,32,55-down,"#a38a87");fill(x,138+down,32,50-down,col);
      fill(x+2,139+down,28,2,pressed?"#edffcb":"#fff3d6");
      text(c,notes[k],x+16,151+down,9,selected?dark:"#816d72","center");
      text(c,piano.names[k],x+16,174+down,piano.names[k].length===3?9:12,dark,"center");
      fill(x+9,183+down,14,2,selected?"#a25d3b":pressed?"#709d88":"#d9c7ae");
    }
    for(const k of [0,1,3,4,5,7,8]){
      const x=44+k*34.5+(k>=5?3:0);fill(x,137,11,13,"#312c3d");fill(x+2,138,7,8,"#605469");
    }
    c.restore();
  }
  function overlay(canvas,video,visual) {
    const w=video.videoWidth,h=video.videoHeight;
    if (!w || !h) return;
    if(canvas.width!==w)canvas.width=w;
    if(canvas.height!==h)canvas.height=h;
    const c=canvas.getContext("2d");c.clearRect(0,0,w,h);
    const target=visual.target_key;
    (visual.hand_points || []).forEach((hand,side)=>{
      if(hand)skeleton(c,hand.map(([x,y])=>[x*w,y*h]),colors[side],Math.floor(target/5)===side?piano.tips[target]:null,true);
    });
  }
  window.PianoStage=Object.freeze({draw,demoHand,overlay});
})();
