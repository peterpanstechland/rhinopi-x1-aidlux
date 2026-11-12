/* Both the rehearsal and the live instrument use the same ten keys and fingertip IDs. */
(() => {
  "use strict";
  const piano=window.FingerPiano;
  const dark="#30293e", ivory="#fff0cc", amber="#ffcb78", colors=["#9de0b7","#c4b5ef"];
  const keyX = k => 16 + 35*k + (k>=5?3:0);
  const keyTop = 126, keyBottom = 198;
  function keyAt(x,y) {
    if (y<keyTop || y>keyBottom) return -1;
    return piano.tips.findIndex((_,k)=>x>=keyX(k) && x<keyX(k)+34);
  }
  const open=[
    [0,41],[7,33],[16,25],[23,18],[28,12], [9,16],[12,4],[13,-5],[14,-13],
    [2,13],[3,0],[3,-11],[3,-20], [-6,15],[-8,2],[-10,-7],[-11,-14],
    [-13,21],[-18,13],[-21,6],[-24,-1]
  ];
  function demoHand(side,depths) {
    const joints=open.map(([x,y])=>[x,y,0]);
    for(let finger=0;finger<5;finger++) {
      const base=1+4*finger, key=side?5+finger:4-finger;
      const flex=Math.max(0,Math.min(1,depths?.[key] || 0));
      const bends=finger===0?[.27,.72,1.24]:[.35,1.18,1.86];
      for(let j=1;j<=3;j++) {
        const id=base+j, dx=open[id][0]-open[id-1][0],dy=open[id][1]-open[id-1][1];
        const angle=bends[j-1]*flex, [x,y,z]=joints[id-1];
        // Ortho projection of rigid phalanges rotating toward the palm.
        joints[id]=[x+dx*Math.cos(angle),y+dy*Math.cos(angle),z+Math.hypot(dx,dy)*Math.sin(angle)];
      }
    }
    return joints.map(([x,y,z])=>[.25+.5*side+(side?-x:x)/230,.52+y/130,z/130]);
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
  function polygon(c,points,color) {
    c.fillStyle=color;c.beginPath();
    points.forEach(([x,y],i)=>i?c.lineTo(x,y):c.moveTo(x,y));
    c.closePath();c.fill();
  }
  function gradient(c,top,bottom,stops) {
    const g=c.createLinearGradient(0,top,0,bottom);
    for(const [at,color] of stops)g.addColorStop(at,color);
    return g;
  }
  let coast;
  function evening(c) {
    if(!coast) {
      coast=document.createElement("canvas");coast.width=384;coast.height=210;
      const p=coast.getContext("2d");
      p.fillStyle=gradient(p,0,111,[[0,"#273d55"],[.36,"#78738a"],[.7,"#da9a94"],[1,"#faca99"]]);
      p.fillRect(0,0,384,210);
      // A low sun seen across the bay. Horizontal breaks and stepped ridges keep the landscape pixel-sized.
      p.fillStyle="#ffddac";p.beginPath();p.arc(294,66,20,0,2*Math.PI);p.fill();
      for(const [x,y,w] of [[268,65,37],[284,68,33],[272,73,50]]) {
        p.fillStyle="#dca599";p.fillRect(x,y,w,1);
      }
      polygon(p,[[0,77],[28,73],[46,74],[69,69],[86,71],[107,65],[116,65],[135,58],[149,62],[160,59],[184,70],[206,72],[225,66],[241,67],[258,62],[269,63],[292,75],[306,73],[329,61],[340,60],[358,53],[366,54],[384,48],[384,96],[0,96]],"#ac8795");
      polygon(p,[[0,77],[29,75],[51,78],[78,73],[106,77],[128,73],[143,73],[157,77],[180,78],[204,75],[222,76],[246,70],[267,73],[288,75],[310,72],[327,69],[352,70],[372,63],[384,64],[384,96],[0,96]],"#83768b");
      p.fillStyle=gradient(p,81,110,[[0,"#dba79b"],[.35,"#a48a99"],[1,"#586e7e"]]);p.fillRect(0,81,384,34);
      for(let i=0;i<34;i++){
        const y=82+i%18,x=295+Math.sin(i*2.4)*(7+(y-80)*1.7);
        p.fillStyle=i%3?"#f1c4a48c":"#fce2ad";p.fillRect(Math.floor(x)-5,y,3+(i*7)%17,1);
      }
      for(const [x,y,w] of [[177,28,25],[198,27,11],[325,38,22],[340,37,11],[241,48,17],[258,47,10]]) {
        p.fillStyle="#ead2bf71";p.fillRect(x,y,w,1);
      }
      const wash=p.createLinearGradient(0,0,173,0);
      wash.addColorStop(0,"#1e344ad9");wash.addColorStop(.66,"#27374d80");wash.addColorStop(1,"#27374d00");
      p.fillStyle=wash;p.fillRect(0,0,173,78);
    }
    c.drawImage(coast,0,0);
  }
  function fingerPortrait(c,target,points,aspect) {
    const xs=points.map(p=>p[0]*aspect),ys=points.map(p=>p[1]);
    // A wrist and knuckle reference stays fixed when just one finger curls.
    const dx=xs[9]-xs[0],dy=ys[9]-ys[0],length=Math.max(.02,Math.hypot(dx,dy));
    const scale=16.3/length, ax=-dy/length, ay=dx/length;
    const mapped=xs.map((x,i)=>{
      const u=x-xs[0],v=ys[i]-ys[0];
      return [33+(u*ax+v*ay)*scale,51-(u*dx+v*dy)/length*scale];
    });
    const handInk="#ddc4ad", boneInk="#fff1d7";
    const [wx,wy]=mapped[0],thumbSign=Math.sign(mapped[5][0]-mapped[17][0]) || 1;
    const [littleX,littleY]=mapped[17], [thumbX,thumbY]=mapped[1];
    c.beginPath();c.moveTo(wx-3*thumbSign,wy+1);
    c.quadraticCurveTo(littleX,littleY+6,littleX,littleY);
    for(const id of [13,9,5,2])c.lineTo(...mapped[id]);
    c.quadraticCurveTo(thumbX,thumbY+3,wx+3*thumbSign,wy+1);
    c.closePath();c.fillStyle=handInk;c.fill();
    c.lineCap="round";c.lineJoin="round";
    for(let finger=0;finger<5;finger++) {
      const base=1+4*finger,selected=base+3===piano.tips[target];
      c.strokeStyle=selected?"#ffc674":handInk;
      for(let j=0;j<3;j++) {
        c.lineWidth=(finger===4?3.4:finger===0?4.4:4)-j*.65;
        c.beginPath();c.moveTo(...mapped[base+j]);c.lineTo(...mapped[base+j+1]);c.stroke();
      }
    }
    const [tx,ty]=mapped[piano.tips[target]];
    c.beginPath();c.arc(tx,ty,3.4,0,Math.PI*2);c.lineWidth=.9;c.strokeStyle="#ffe0a8";c.stroke();
    c.fillStyle=boneInk;c.fillRect(tx-.7,ty-.7,1.4,1.4);
  }
  function draw(c,width,height,visual,{demo=false,manual=false,count=0,ready=false,aspect=1,cue=""}={}) {
    c.save();c.scale(width/384,height/210);evening(c);
    const target=visual.target_key ?? piano.phrase[0],side=Number(target>=5);
    const depths=visual.finger_depth || [],pressure=Math.max(0,Math.min(1,depths[target] || 0));
    const hands=visual.hand_points || [],points=demo || manual ? demoHand(side,depths) : hands[side];
    const fill=(x,y,w,h,color)=>{c.fillStyle=color;c.fillRect(x,y,w,h);};
    c.beginPath();c.arc(33,33,23,0,Math.PI*2);c.fillStyle="#25384b89";c.fill();
    c.lineWidth=.6;c.strokeStyle="#edd3b083";c.stroke();
    if(points){
      c.save();c.beginPath();c.arc(33,33,22,0,Math.PI*2);c.clip();
      fingerPortrait(c,target,points,demo || manual ? 230/130 : aspect);c.restore();
    }
    else text(c,"入镜",33,33,10,ivory,"center");
    text(c,piano.notes[target]+"   /   "+(manual?"按键":demo?"指法示范":ready?"准备":"下一音"),64,17,8,"#ffdbac");
    text(c,piano.label(target),63,35,18,"#fff1d8");
    const message=!points?"将"+piano.sideName(side)+"放进画面":cue || (manual?"按数字或点亮键":pressure>.65?"伸直，松键":"轻弯这根手指");
    c.font='10px "Microsoft YaHei",system-ui,sans-serif';c.textAlign="left";c.fillStyle="#fff0de";c.fillText(message,65,53);
    // The walnut cheeks enclose one continuous keyboard, with brass markings on the rail.
    fill(0,103,384,107,gradient(c,103,210,[[0,"#644b49"],[.05,"#a37558"],[.09,"#493936"],[.86,"#4b3837"],[1,"#302b32"]]));
    fill(6,110,372,90,"#2a333b");fill(8,110,368,1,"#cbac84");
    fill(12,123,360,75,"#231f29");
    for(const [a,b,label] of [[17,188,"左手"],[195,367,"右手"]]) {
      const mid=(a+b)/2;
      fill(a,117,mid-a-13,.6,"#b19b81");fill(mid+13,117,b-mid-13,.6,"#b19b81");
      text(c,label,mid,117,8,"#e3c9a6","center");
    }
    const natural=gradient(c,keyTop,keyBottom,[[0,"#cfbdad"],[.22,"#f3e5cd"],[.84,"#fff2dc"],[1,"#e8d8bd"]]);
    const goldKey=gradient(c,keyTop,keyBottom,[[0,"#b58256"],[.3,"#e4b880"],[1,"#ffdea0"]]);
    for(let k=0;k<10;k++) {
      const x=keyX(k),held=visual.keys_lit?.includes(k),selected=k===target;
      const down=Math.round(Math.max(depths[k] || 0,held ? .5 : 0)*5);
      fill(x,keyTop+down,34,keyBottom-keyTop-down,held?"#ab8760":"#bead98");
      fill(x,keyTop+down,34,66-down,selected || held?goldKey:natural);
      fill(x+1,190,32,.8,"#ffefda");
      if(selected || held) {
        text(c,piano.names[k],x+17,168+down,10,"#59402d","center");
        fill(x+14,186,6,1,"#a67645");
      }
      text(c,manual?"1234567890"[k]:piano.notes[k],x+17,180,8,selected?"#5c402b":"#71685e","center");
    }
    const ebony=gradient(c,125,153,[[0,"#172330"],[.72,"#334250"],[1,"#17242f"]]);
    for(const k of [0,1,3,4,5,7,8]) {
      const x=keyX(k)+28;
      fill(x+1,126,13,30,"#746d6588");fill(x,125,12,29,"#16212b");fill(x+1,125,10,25,ebony);fill(x+2,126,1,22,"#627178");
    }
    // The note lands directly above its key as the measured finger flexes.
    const tx=keyX(target)+17,ny=80+pressure*23;
    fill(tx-.5,ny+5,1,106-ny,"#ffdda27a");
    c.beginPath();c.ellipse(tx,ny,4,2.9,-.35,0,Math.PI*2);c.fillStyle="#ffe1a2";c.fill();
    fill(tx+2.6,ny-10,1.4,10,"#ffe1a2");fill(tx+3.5,ny-10,3,1.4,"#ffe1a2");
    polygon(c,[[tx-3,123],[tx+3,123],[tx,126]],"#ffdfa1");
    if(!demo)text(c,Math.floor(count)+" / "+piano.phrase.length,367,15,9,"#ffe5c3","right");
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
  window.PianoStage=Object.freeze({draw,demoHand,overlay,keyAt});
})();
