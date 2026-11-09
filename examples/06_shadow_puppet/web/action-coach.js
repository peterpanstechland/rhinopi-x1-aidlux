/* A front-facing movement guide. Board snapshots supply the real target piano key. */
(() => {
  'use strict';
  const W = 256, H = 144;
  const ink = '#171a2a', mint = '#9af4c0', coral = '#ffac8e', gold = '#ffdb88';
  const lilac = '#c0b7f6', dim = '#72698c', hair = '#40384d', skin = '#ffd1ac';
  const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)');

  const actions = [
    {id:'wings', name:'展翅', cue:'双手向两边伸开，手腕和肩膀同高，稳稳保持。', goal:'平举保持 5 秒', region:'双臂'},
    {id:'flap', name:'老鹰', cue:'把双臂伸向两侧，像扇翅膀一样同时抬起、落下。', goal:'扇动 8 次', region:'双臂'},
    {id:'wave', name:'挥手', cue:'抬一只手到肩膀上方，在脸旁左右摆动手腕。', goal:'挥手送走 10 人', region:'单手'},
    {id:'lean', name:'滑雪', cue:'面对屏幕，把头和上身偏向旗子一侧，避开树。', goal:'碰到 6 面旗', region:'头和上身'},
    {id:'piano', name:'弹琴', cue:'双手张开对齐十个键，用黄键对应的手指向下点，再抬起。', goal:'弹中 8 个黄键', region:'手指'},
    {id:'hands_up', name:'跳跃', cue:'仙人掌靠近时，坐着让双肩随上身快速上提一次，再放松落回。', goal:'越过 5 个仙人掌', region:'双肩和上身'},
    {id:'turn', name:'转头', cue:'保持双肩朝前，转脸看向一侧，回正后再转向另一侧。', goal:'左右各转 3 次', region:'头部'},
    {id:'nod', name:'点头', cue:'双肩保持原位，低一下头，再抬起看正前方。', goal:'完成 6 次点头', region:'头部'}
  ];
  const calm = [69, 77, 69, 77], flat = [0, 0, 0, 0];
  // Arm angles start at the outward horizontal, positive below shoulder height.
  function pose(arms = calm, extras = {}) {
    return {arms, lean:0, lift:0, yaw:0, pitch:0, press:0, ...extras};
  }
  const neutral = pose();
  const demos = {
    wings:[
      ['展开双臂', 1, pose(flat)], ['保持肩高', 5, pose(flat)], ['放松', .7, neutral]
    ],
    flap:[
      ['展开', .6, pose(flat)], ['向上扇', .55, pose([-28,-36,-28,-36])],
      ['向下扇', .55, pose([24,32,24,32])]
    ],
    wave:[
      ['抬手', .6, pose([69,77,5,-87])], ['向外挥', .55, pose([69,77,5,-50])],
      ['向内挥', .55, pose([69,77,5,-132])]
    ],
    lean:[
      ['向左倾', .95, pose([57,67,57,67], {lean:-1})], ['回到中间', .6, neutral],
      ['向右倾', .95, pose([57,67,57,67], {lean:1})], ['回到中间', .6, neutral]
    ],
    piano:[
      ['手指悬起', .85, neutral], ['点下黄键', .55, pose(calm, {press:1})], ['抬起手指', .65, neutral]
    ],
    hands_up:[
      ['坐稳', .95, neutral], ['双肩上提', .42, pose([72,63,72,63], {lift:1})], ['落回座位', .8, neutral]
    ],
    turn:[
      ['转向左边', .85, pose(calm,{yaw:-1})], ['回正', .65, neutral],
      ['转向右边', .85, pose(calm,{yaw:1})], ['回正', .65, neutral]
    ],
    nod:[
      ['看前方', .8, neutral], ['低头', .8, pose(calm,{pitch:1})], ['抬头回正', .8, neutral]
    ]
  };
  function frame(steps, seconds) {
    const duration = steps.reduce((sum, s) => sum + s[1], 0);
    const loops = Math.floor(seconds / duration);
    let local = seconds - loops * duration, index = 0;
    while (index < steps.length - 1 && local >= steps[index][1]) local -= steps[index++][1];
    const step = steps[index], prev = steps[(index + steps.length - 1) % steps.length][2];
    const progress = local / step[1];
    // Reduced motion shows stable target pictures and still communicates the full sequence.
    const blend = reduced?.matches ? 1 : .5 - .5 * Math.cos(Math.min(1,progress / .68) * Math.PI);
    const mix = (a,b) => a + (b-a) * blend;
    const target = step[2];
    const sample = pose(target.arms.map((angle,i) => mix(prev.arms[i],angle)));
    for (const key of ['lean','lift','yaw','pitch','press']) sample[key] = mix(prev[key],target[key]);
    return {sample,index,label:step[0],progress,loops};
  }
  const round = Math.round;
  function box(c,x,y,w,h,color) {
    c.fillStyle = color;
    c.fillRect(round(x),round(y),round(w),round(h));
  }
  function polygon(c,points,color) {
    c.fillStyle = color;
    c.beginPath();
    points.forEach(([x,y],i) => i ? c.lineTo(round(x),round(y)) : c.moveTo(round(x),round(y)));
    c.closePath();
    c.fill();
  }
  function segment(c,a,b,width,color) {
    const length = Math.ceil(Math.max(Math.abs(a[0]-b[0]),Math.abs(a[1]-b[1]),1));
    for (let i=0;i<=length;i++) {
      const t=i/length;
      box(c,a[0]+(b[0]-a[0])*t-width/2,a[1]+(b[1]-a[1])*t-width/2,width,width,color);
    }
  }
  function arrow(c,x1,y1,x2,y2,color) {
    segment(c,[x1,y1],[x2,y2],2,color);
    const angle = Math.atan2(y2-y1,x2-x1);
    for (const offset of [-.65,.65]) segment(c,[x2,y2],
      [x2-5*Math.cos(angle+offset),y2-5*Math.sin(angle+offset)],2,color);
  }
  function backdrop(c) {
    box(c,0,0,W,H,'#242438');
    for (let x=7;x<W;x+=12) for (let y=7;y<123;y+=12) box(c,x,y,1,1,'#3a374d');
    box(c,0,112,W,13,'#29273c');
    box(c,0,112,W,1,'#3d394e');
    for (const x of [8,242]) for (const y of [8,116]) {
      box(c,x,y,6,1,dim); box(c,x+(x>128?5:0),y+(y>100?-5:0),1,6,dim);
    }
  }
  function limb(c,side,shoulder,angles,active) {
    const point = (base,angle,length) => [
      base[0]+side*Math.cos(angle*Math.PI/180)*length,
      base[1]+Math.sin(angle*Math.PI/180)*length
    ];
    const elbow = point(shoulder,angles[0],17), wrist = point(elbow,angles[1],18);
    segment(c,shoulder,elbow,10,ink); segment(c,elbow,wrist,8,ink);
    segment(c,shoulder,elbow,7,active ? '#7bd9ad' : '#77759d');
    segment(c,elbow,wrist,5,active ? '#8edfb0' : '#9284a7');
    box(c,wrist[0]-3,wrist[1]-3,7,7,ink);
    box(c,wrist[0]-2,wrist[1]-2,5,5,active ? gold : skin);
    if (active) {box(c,elbow[0]-1,elbow[1]-1,3,3,'#d7ffd6');box(c,wrist[0]-1,wrist[1]-2,2,2,'#fff4ce');}
  }
  function head(c,x,y,pose,active) {
    const yaw = pose.yaw, pitch = pose.pitch, off = round(yaw*6);
    c.save(); c.translate(round(x),round(y));
    polygon(c,[[-14,-11],[-9,-16],[8,-16],[14,-12],[16,-6],[14,9],[8,14],[-7,14],[-14,9],[-16,-3]],ink);
    polygon(c,[[-12,-9],[-7,-12],[9,-12],[13,-7],[12,7],[7,11],[-6,11],[-12,7]],skin);
    box(c,-15+Math.max(0,off),0,4,6,'#df9a86'); box(c,11+Math.min(0,off),0,4,6,'#df9a86');
    const hairY = round(pitch*5);
    polygon(c,[[-14,0],[-14,-10],[-9,-14],[8,-14],[13,-10],[14,-3],[8,-5+hairY],[0,-6+hairY],[-4,-3+hairY],[-9,-4+hairY],[-10,3]],hair);
    box(c,-9,-12,11,2,'#76607d');
    const eyeY = 0 + round(pitch*6);
    if(yaw < .8) box(c,-7+off,eyeY,3,3,ink);
    if(yaw > -.8) box(c,5+off,eyeY,3,3,ink);
    box(c,off*1.35,eyeY+3,3,2,'#d78a73');
    box(c,off-2,eyeY+7,4,1,'#b8766f');
    if (active) {box(c,-15,-8,3,6,mint);box(c,-12,-10,3,2,mint);}
    c.restore();
  }
  function chair(c) {
    box(c,106,101,45,7,'#514e68');box(c,109,101,39,2,'#817790');
    box(c,109,108,3,16,'#4d4c64');box(c,145,108,3,16,'#4d4c64');
  }
  function person(c,id,p) {
    chair(c);
    for(const x of [114,135]) {
      box(c,x,98,11,22,'#3d4767');box(c,x-2,118,15,5,'#afa6ba');box(c,x-2,122,15,2,ink);
    }
    const x=128+14*p.lean, y=69-10*p.lift;
    const tilt=p.lean*4;
    polygon(c,[[x-15,y-5-tilt],[x-8,y-8],[x+8,y-8],[x+15,y-5+tilt],[142,100],[114,100]],ink);
    polygon(c,[[x-13,y-3-tilt],[x-7,y-6],[x+7,y-6],[x+13,y-3+tilt],[140,97],[116,97]],'#579796');
    polygon(c,[[x-12,y-2-tilt],[x-7,y-5],[x+6,y-4],[x+9,y-1],[136,93],[117,93]],'#80ccb0');
    polygon(c,[[x-6,y-7],[x+6,y-7],[x+4,y-2],[x,y+1],[x-4,y-2]],ink);
    box(c,x-4,y-12,8,10,skin);
    box(c,x+3,y+5,5,3,'#f8d98e');box(c,x+4,y+8,2,2,'#f8d98e');
    const armsOn = ['wings','flap','hands_up'].includes(id);
    limb(c,-1,[x-13,y-tilt],p.arms.slice(0,2),armsOn);
    limb(c,1,[x+13,y+tilt],p.arms.slice(2),armsOn || id==='wave');
    head(c,x+p.lean*7,y-24+p.pitch*5,p,['lean','turn','nod'].includes(id));
  }
  function prompts(c,id,f) {
    const {sample:p,index,progress} = f;
    if(id==='wings') {
      for (const sign of [-1,1]) {
        const x=128+sign*55;
        for(let i=0;i<4;i++) box(c,x+sign*i*5,69,2,1,dim);
        if(index===0) arrow(c,x-sign*9,80,x+sign*3,69,mint);
      }
      if(index===1) for(let i=0;i<5;i++) box(c,112+i*7,13,5,3,i/5<=progress ? gold : dim);
    } else if(id==='flap') {
      for (const sign of [-1,1]) {
        const x=128+sign*59;
        arrow(c,x,index===2?55:72,x,index===2?75:52,coral);
      }
    } else if(id==='wave') {
      arrow(c,170,46,index===2?156:184,46,gold);
    } else if(id==='lean') {
      const side=p.lean<0?-1:1;
      const x=128+side*64;
      box(c,x-1,64,2,33,'#c2c5ac');
      polygon(c,[[x+1,65],[x+15,66],[x+11,71],[x+1,72]],coral);
      if(Math.abs(p.lean)>.15) arrow(c,128+side*26,51,128+side*42,51,mint);
    } else if(id==='hands_up') {
      for(const x of [97,159]) arrow(c,x,index===2?61:73,x,index===2?74:58,mint);
      for(let x=111;x<148;x+=5) box(c,x,68,2,1,dim);
    } else if(id==='turn') {
      const dir=p.yaw<0?-1:1;
      if(index%2===0) arrow(c,128+dir*21,44,128+dir*38,44,gold);
      else for(const dir of [-1,1]) arrow(c,128+dir*34,44,128+dir*23,44,mint);
    } else if(id==='nod') {
      arrow(c,155,index===1?37:55,155,index===1?55:39,gold);
      box(c,102,68,8,1,dim);box(c,146,68,8,1,dim);
    }
  }
  function keyboard(c,f,target,wrist) {
    const p=f.sample;
    const keyWidth=13, left=63, top=87;
    box(c,left-5,top-3,140,32,ink);box(c,left-3,top-2,136,2,lilac);
    for(let i=0;i<10;i++) {
      const active=i===target;
      const dx=left+i*keyWidth, dy=active?round(p.press*2):0;
      box(c,dx,top+dy,keyWidth-1,24-dy,active?coral:'#88839d');
      box(c,dx,top+dy,keyWidth-1,21-dy,active?gold:'#e3ddd9');
      if(active) { box(c,dx+4,103,5,2,ink);box(c,dx+6,101,1,6,ink); }
    }
    if(wrist) {
      const tx=left+target*keyWidth+6;
      const park=target<5?left+2.5*keyWidth:left+7.5*keyWidth;
      const x=round(f.index===0 ? park+(tx-park)*Math.min(1,f.progress/.62) : tx);
      const y=69+round(p.press*14);
      if(f.index===0 && Math.abs(tx-x)>6) arrow(c,x,45,tx,45,gold);
      else arrow(c,x+23,f.index===2?81:58,x+23,f.index===2?61:78,gold);
      // Show the whole hand dipping with its wrist; all fingers keep the same relative height.
      const side=target<5?-1:1;
      segment(c,[x+11*side,29],[x, y-12],14,ink);
      segment(c,[x+11*side,29],[x, y-12],10,'#7ad1aa');
      box(c,x-6,y-13,13,5,mint);
      box(c,x-8,y-8,17,13,ink);box(c,x-6,y-7,13,11,skin);
      for(let j=0;j<4;j++) box(c,x-6+j*4,y+3,3,4,j===1?gold:skin);
      box(c,x+7*side-2,y-8,5,7,skin);
      return;
    }
    for(let side=0;side<2;side++) {
      const base=left+side*5*keyWidth;
      const palmY=58;
      box(c,base+21,20,20,palmY-20,ink);box(c,base+23,21,16,palmY-20,'#7ad1aa');
      box(c,base+22,palmY-15,18,4,'#b0f3bf');
      polygon(c,[[base+9,palmY],[base+18,palmY-14],[base+44,palmY-14],[base+54,palmY],[base+54,palmY+7],[base+7,palmY+7]],ink);
      polygon(c,[[base+11,palmY],[base+19,palmY-11],[base+43,palmY-11],[base+51,palmY],[base+51,palmY+4],[base+10,palmY+4]],skin);
      for(let f=0;f<5;f++) {
        const i=side*5+f, active=i===target, tipX=base+f*keyWidth+6;
        const finger=side?4-f:f;
        const lengths=[14,19,21,18,12];
        const tipY=palmY+6+lengths[finger]+(active?round(p.press*13):0);
        const root=[base+10+f*11,palmY+2], end=[tipX,tipY];
        segment(c,root,end,8,ink);segment(c,root,end,5,active?mint:skin);
        box(c,tipX-1,tipY,3,2,active?gold:'#e2aa92');
      }
      if (Math.floor(target/5)===side) {
        const tipX=left+target*keyWidth+6;
        arrow(c,tipX,23,tipX,35,gold);
      }
    }
  }
  function footer(c,steps,f,wrist) {
    box(c,0,125,W,19,'#191c2b');
    const margin=11;
    c.fillStyle='#eee9f1';
    c.font='bold 10px "Microsoft YaHei","PingFang SC",sans-serif';
    c.textBaseline='middle';
    const wristLabels=['手腕对准亮键','手腕向下点','抬起手腕'];
    c.fillText(wrist?wristLabels[f.index]:f.label,margin,135);
    for(let i=0;i<steps.length;i++) box(c,W-margin-(steps.length-i)*11,133,8,3,i===f.index?mint:'#575369');
  }
  function draw(canvas,id,elapsedSeconds=0,snapshot=null) {
    const steps = demos[id];
    if (!steps || !canvas?.getContext) return;
    const c=canvas.getContext('2d'); if(!c) return;
    if(canvas.width!==W) canvas.width=W;
    if(canvas.height!==H) canvas.height=H;
    c.imageSmoothingEnabled=false;
    const seconds=Math.max(0,Number.isFinite(elapsedSeconds)?elapsedSeconds:0);
    const f=frame(steps,seconds);
    backdrop(c);
    const input=snapshot?.challenge?.piano_input || snapshot?.challenge?.visual?.piano_input;
    const wrist=id==='piano' && (input==='wrists' || input==='wrist');
    if(id==='piano') {
      const target=snapshot?.challenge?.visual?.target_key;
      const demoKeys=[1,7,4,6];
      keyboard(c,f,Number.isInteger(target)&&target>=0&&target<10?target:demoKeys[f.loops%demoKeys.length],wrist);
    } else {
      person(c,id,f.sample);
      prompts(c,id,f);
    }
    footer(c,steps,f,wrist);
  }
  window.ActionCoach = Object.freeze({actions,draw});
})();
