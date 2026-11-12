/* A front-facing movement guide. Board snapshots supply the real target piano key. */
(() => {
  'use strict';
  const W = 256, H = 144;
  const ink = '#171a2a', mint = '#9af4c0', coral = '#ffac8e', gold = '#ffdb88';
  const lilac = '#c0b7f6', dim = '#72698c', glove = '#86cbb0';
  const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)');

  const actions = [
    {id:'wings', name:'展翅', cue:'双手向两边伸开，手腕和肩膀同高，稳稳保持。', goal:'平举保持 5 秒', region:'双臂'},
    {id:'flap', name:'老鹰', cue:'把双臂伸向两侧，像扇翅膀一样同时抬起、落下。', goal:'扇动 8 次', region:'双臂'},
    {id:'wave', name:'挥手', cue:'抬一只手到肩膀上方，在脸旁左右摆动手腕。', goal:'挥手送走 10 人', region:'单手'},
    {id:'lean', name:'滑雪', cue:'把头和上身偏向旗子一侧。收集三面旗后雪道提速，对准旗门中心还有精准奖励。', goal:'碰到 6 面旗', region:'头和上身'},
    {id:'piano', name:'弹琴', cue:'一根手指对应一个琴键。掌心朝镜头，轻弯金色指尖对应的手指，伸直就松键。', goal:'跟着金色指尖弹出 8 个音', region:'十指'},
    {id:'hands_up', name:'跳跃', cue:'仙人掌靠近时，坐着轻挺上身再落回。越过两株后速度提高，看清间距再跳。', goal:'越过 5 个仙人掌', region:'双肩和上身'},
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
      ['向左倾', .95, pose([57,67,57,67], {lean:-1})], ['身体回正', .6, neutral],
      ['向右倾', .95, pose([57,67,57,67], {lean:1})], ['身体回正', .6, neutral]
    ],
    piano:[
      ['张开五指', .85, neutral], ['轻弯指尖', .55, pose(calm, {press:1})], ['伸直松键', .65, neutral]
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
  function liveFrame(id,steps,f,s) {
    if (s?.sub!=='play' || s.challenge?.tracking===false) return f;
    const visual=s.challenge?.visual || {};
    function target(index,label) {
      return {...f,index,label,sample:steps[index][2]};
    }
    if (id==='wings' && s.challenge.count>0) {
      const held=target(1,'维持肩高');
      held.progress=s.challenge.frac || 0;
      return held;
    }
    if (id==='lean' && Array.isArray(visual.gates)) {
      const next=visual.gates.filter(g=>!g.state && g.y>=0 && g.y<=96).sort((a,b)=>b.y-a.y)[0];
      if (!next) return f;
      const right=next.kind==='tree' ? next.x<=160 : next.x>160;
      const label=(right?'向右倾':'向左倾') + (next.kind==='tree'?' · 躲树':' · 碰旗');
      return {...target(right?2:0,label), obstacle:next.kind};
    }
    if (id==='hands_up' && Number.isFinite(visual.obs)) {
      if (visual.avatar_dy < -1) return target(2,'落回坐姿');
      const launch=visual.launch_x ?? (s.source==='camera' ? 211 : 260);
      return visual.obs>160 && visual.obs<launch ? target(1,'现在轻挺上身') : target(0,'坐稳，等仙人掌');
    }
    if (id==='turn') {
      const turn=visual.head_turn || 0;
      if (Math.abs(turn)>=1) return target(1,'回到正中');
      if (visual.left_got>=3 && visual.right_got<3) return target(2,'转向右边');
      if (visual.right_got>=3 && visual.left_got<3) return target(0,'转向左边');
    }
    if (id==='nod' && visual.head_dip>=1) return target(2,'抬头回正');
    return f;
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
    const angle = Math.atan2(y2-y1,x2-x1);
    for (const [width,tint] of [[4,ink],[2,color]]) {
      segment(c,[x1,y1],[x2,y2],width,tint);
      for (const offset of [-.65,.65]) segment(c,[x2,y2],
        [x2-5*Math.cos(angle+offset),y2-5*Math.sin(angle+offset)],width,tint);
    }
  }
  function backdrop(c,id) {
    window.MotionStage.paintBackdrop(c,id,W,125);
    box(c,0,0,W,125,id==='piano'?'#251b383e':'#28233920');
  }
  function skiDemoX(f) {
    if (f.obstacle || reduced?.matches) return 128 + 31*f.sample.lean;
    // Carry the glide through the release. The skier turns the other way on the next lean.
    const step = f.index - f.index%2;
    const turn = demos.lean[step][1], release = demos.lean[step+1][1];
    const elapsed = f.index===step ? turn*f.progress : turn+release*f.progress;
    const t = Math.min(1,elapsed/(turn+.68*release));
    const travel = t*t*(3-2*t);
    return 128 + (step===0 ? 1 : -1)*31*(1-2*travel);
  }
  // The guide feeds the same shoulder, elbow and wrist landmarks as a live player.
  function demoAvatar(c, id, f) {
    const pose = f.sample;
    const points = [];
    points[0] = [.5 + pose.yaw * .04, .34 + .045 * pose.pitch];
    for (let side = 0; side < 2; side++) {
      const direction = side ? 1 : -1;
      const shoulder = [.5 + direction * .12, .50 + direction * .02 * pose.lean];
      const extend = (joint, angle) => {
        const radians = angle * Math.PI / 180;
        return [joint[0] + direction * .12 * Math.cos(radians), joint[1] + .12 * Math.sin(radians)];
      };
      const elbow = extend(shoulder, pose.arms[side * 2]);
      points[11 + side] = shoulder;
      points[13 + side] = elbow;
      points[15 + side] = extend(elbow, pose.arms[side * 2 + 1]);
    }
    const visual = {avatar_dx: pose.lean * 58, head_turn: pose.yaw, head_dip: pose.pitch};
    if (id === 'hands_up') {
      box(c,108,111,40,5,'#76738a');
      box(c,112,116,3,8,dim); box(c,141,116,3,8,dim);
    }
    const px=id==='lean' ? skiDemoX(f) : 128+pose.lean*7;
    if(id!=='flap' && id!=='lean') box(c,px-20,115,40,3,'#29233770');
    const feetY=id==='lean' ? 102 : 116 - pose.lift * 11 - (id==='flap'?7:0);
    window.MotionStage.paintAvatar(c, {
      phase:'round', act_id:id, pose_points:points, pose_aspect:1, challenge:{visual}
    },px,feetY,.98);
  }
  function prompts(c,id,f) {
    const {sample:p,index,progress} = f;
    if(id==='wings') {
      for (const sign of [-1,1]) {
        const x=128+sign*55;
        for(let i=0;i<4;i++) box(c,x+sign*i*5,86,2,1,dim);
        if(index===0) arrow(c,x-sign*9,98,x+sign*3,86,mint);
      }
      if(index===1) for(let i=0;i<5;i++) box(c,15+i*7,18,5,3,i/5<=progress ? gold : dim);
    } else if(id==='flap') {
      for (const sign of [-1,1]) {
        const x=128+sign*85;
        arrow(c,x,index===2?64:78,x,index===2?78:64,coral);
      }
    } else if(id==='wave') {
      arrow(c,170,46,index===2?156:184,46,gold);
    } else if(id==='lean') {
      const side=index<2?-1:1;
      const x=128+(f.obstacle==='tree'?-side:side)*91;
      if (f.obstacle==='tree') {
        box(c,x-2,85,4,12,'#ac9280');
        polygon(c,[[x,62],[x+12,88],[x-12,88]],'#76c4a7');
        polygon(c,[[x,62],[x+5,74],[x-6,75]],'#d5ece4');
      } else {
        box(c,x-1,74,2,39,'#664954');
        polygon(c,[[x+1,75],[x+16,76],[x+12,82],[x+1,84]],coral);
        box(c,x+2,78,8,2,'#fff0ce');
      }
      if(Math.abs(p.lean)>.15) arrow(c,128+side*83,56,128+side*96,56,mint);
    } else if(id==='hands_up') {
      for(const x of [77,179]) arrow(c,x,index===2?72:87,x,index===2?87:72,mint);
    } else if(id==='turn') {
      const dir=p.yaw<0?-1:1;
      if(index%2===0) arrow(c,128+dir*44,48,128+dir*61,48,gold);
      else for(const dir of [-1,1]) arrow(c,128+dir*59,48,128+dir*44,48,mint);
    } else if(id==='nod') {
      arrow(c,181,index===1?42:63,181,index===1?63:42,gold);
      box(c,85,86,8,1,dim);box(c,163,86,8,1,dim);
    }
  }
  function wristKeyboard(c,f,target) {
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
    box(c,x-8,y-8,17,13,ink);box(c,x-6,y-7,13,11,glove);
    for(let j=0;j<4;j++) box(c,x-6+j*4,y+3,3,4,j===1?gold:glove);
    box(c,x+7*side-2,y-8,5,7,glove);
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
    if(canvas.width!==W*3) canvas.width=W*3;
    if(canvas.height!==H*3) canvas.height=H*3;
    c.setTransform(3,0,0,3,0,0);
    c.imageSmoothingEnabled=false;
    const seconds=Math.max(0,Number.isFinite(elapsedSeconds)?elapsedSeconds:0);
    const f=liveFrame(id,steps,frame(steps,seconds),snapshot);
    backdrop(c,id);
    const input=snapshot?.challenge?.piano_input || snapshot?.challenge?.visual?.piano_input;
    const wrist=id==='piano' && (input==='wrists' || input==='wrist');
    if(id==='piano') {
      const target=snapshot?.challenge?.visual?.target_key;
      const demoKeys=window.FingerPiano.phrase;
      const note=Number.isInteger(target)&&target>=0&&target<10?target:demoKeys[f.loops%demoKeys.length];
      if (wrist) wristKeyboard(c,f,note);
      else {
        const depth=Array(10).fill(0);depth[note]=f.sample.press;
        window.PianoStage.draw(c,W,H,{target_key:note,finger_depth:depth,keys_lit:depth[note]>.6?[note]:[]},{demo:true,cue:f.label});
        return;
      }
    } else {
      c.save();
      // Show the waving arm on the same screen side as the player's raised wrist.
      if (id==='wave' && snapshot?.challenge?.tracking) {
        const p=snapshot.pose_points || [];
        const raised=side=>p[11+side] && p[15+side] && p[15+side][1]<p[11+side][1];
        if (raised(0) && !raised(1)) {c.translate(W,0);c.scale(-1,1);}
      }
      demoAvatar(c,id,f);
      prompts(c,id,f);
      c.restore();
    }
    footer(c,steps,f,wrist);
  }
  window.ActionCoach = Object.freeze({actions,draw});
})();
