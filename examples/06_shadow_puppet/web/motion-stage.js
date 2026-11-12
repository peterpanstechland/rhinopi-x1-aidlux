/* Render the player's mirrored landmarks and the obstacle positions used by the game. */
(() => {
  'use strict';
  const W = 384, H = 216, CENTER = W / 2, FLOOR = 189;
  const INK = '#202638', MINT = '#a2efb2', GOLD = '#ffdc99', CORAL = '#ed8d88';
  const plates = { night: 0, wings: 1, flap: 2, wave: 0, lean: 2, piano: 3, hands_up: 1, turn: 0, nod: 3 };
  const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)');
  const loading = new Map();
  let images;
  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
  const number = (value, fallback = 0) => Number.isFinite(value) ? value : fallback;
  const round = Math.round;
  const rect = (c, x, y, w, h, color) => {
    c.fillStyle = color;
    c.fillRect(round(x), round(y), round(w), round(h));
  };
  function path(c, points, color) {
    c.fillStyle = color;
    c.beginPath();
    points.forEach(([x, y], i) => i ? c.lineTo(round(x), round(y)) : c.moveTo(round(x), round(y)));
    c.closePath();
    c.fill();
  }
  function line(c, a, b, width, color) {
    const steps = Math.max(1, Math.ceil(Math.max(Math.abs(b.x - a.x), Math.abs(b.y - a.y))));
    c.fillStyle = color;
    for (let i = 0; i <= steps; i++) {
      const f = i / steps;
      c.fillRect(round(a.x + (b.x - a.x) * f - width / 2),
        round(a.y + (b.y - a.y) * f - width / 2), width, width);
    }
  }
  function star(c, x, y, radius, color) {
    rect(c, x - radius, y, radius * 2 + 1, 1, color);
    rect(c, x, y - radius, 1, radius * 2 + 1, color);
  }
  function ensureImages() {
    if (images) return;
    images = {};
    for (const key of ['plates', 'partner']) {
      const image = new Image();
      images[key] = image;
      image.onload = image.onerror = () => {
        for (const [canvas, snapshot] of loading) draw(canvas, snapshot);
        if (Object.values(images).every(img => img.complete)) loading.clear();
      };
      image.src = key==='partner' ? 'art/partner-parts.png' : 'art/stage-plates.png';
    }
  }
  function background(c, plate) {
    const picture = images.plates;
    if (picture?.complete && picture.naturalWidth) {
      c.drawImage(picture, (plate % 2) * W, Math.floor(plate / 2) * H, W, H, 0, 0, W, H);
      return;
    }
    rect(c, 0, 0, W, H, '#302c4d');
    for (let x = 0; x < W; x += 12) {
      const h = 24 + (x * 31) % 59;
      rect(c, x, FLOOR - h, 11, h, '#4c425e');
      for (let y = FLOOR - h + 5; y < FLOOR - 5; y += 8) rect(c, x + 3, y, 3, 1, '#a88794');
    }
    rect(c, 0, FLOOR, W, H - FLOOR, '#493950');
  }
  function point(points, i) {
    const p = points[i];
    return Array.isArray(p) && Number.isFinite(p[0]) && Number.isFinite(p[1])
      ? { x: p[0], y: p[1] } : null;
  }
  function poseInfo(snapshot) {
    const points = snapshot.camera_online === false ? [] : snapshot.pose_points || [];
    const aspect = clamp(number(snapshot.pose_aspect, 16 / 9), .4, 4);
    const left = point(points, 11), right = point(points, 12), nose = point(points, 0);
    if (!left || !right) return { points: [], aspect, yaw: 0, nod: 0, tilt: 0 };
    const span = Math.max(.045, Math.abs(right.x - left.x) * aspect);
    const yaw = nose ? clamp((nose.x - (left.x + right.x) / 2) * aspect / span, -.7, .7) : 0;
    const nod = nose ? clamp(((nose.y - (left.y + right.y) / 2) / span + .68) * 9, -3, 5) : 0;
    const tilt = clamp((right.y - left.y) / span * 13, -4, 4);
    return { points, aspect, yaw, nod, tilt };
  }
  function extend(start, from, to, length, fallback, aspect) {
    let dx = fallback[0], dy = fallback[1];
    if (from && to) {
      const vx = (to.x - from.x) * aspect, vy = to.y - from.y;
      if (Math.hypot(vx, vy) > .004) { dx = vx; dy = vy; }
    }
    const k = length / Math.hypot(dx, dy);
    return { x: start.x + dx * k, y: start.y + dy * k };
  }
  function limbs(pose, side, idleLift) {
    const dir = side ? 1 : -1;
    const shoulder = { x: side ? 51 : 25, y: 50 + pose.tilt * dir };
    const s = point(pose.points, 11 + side), e = point(pose.points, 13 + side);
    const w = point(pose.points, 15 + side);
    if (s && !e && w) {
      // Some crops show both wrists but lose an elbow. Place the hand from its
      // observed shoulder-relative position, then bend a two-segment arm to it.
      const span = Math.max(.045,Math.abs(pose.points[12][0]-pose.points[11][0])*pose.aspect);
      const dx=(w.x-s.x)*pose.aspect*26/span, dy=(w.y-s.y)*26/span;
      const distance=Math.hypot(dx,dy);
      const ux=distance>.01 ? dx/distance : dir, uy=distance>.01 ? dy/distance : 0;
      const length=clamp(distance,2,25);
      const along=(13*13-12*12+length*length)/(2*length);
      const bend=Math.sqrt(Math.max(0,13*13-along*along));
      // For a raised hand the elbow bends away from the body; for an extended arm it hangs below it.
      const sign=Math.abs(uy)>.05 ? Math.sign(-uy*dir) : Math.sign(ux);
      return {shoulder, elbow:{x:shoulder.x+ux*along-sign*uy*bend,y:shoulder.y+uy*along+sign*ux*bend},
        hand:{x:shoulder.x+ux*length,y:shoulder.y+uy*length}, tracked:true};
    }
    const elbow = extend(shoulder, s, e, 13, [dir, .7], pose.aspect);
    const hand = extend(elbow, e, w, 12, [dir * .38, .9 - (side ? idleLift : 0)], pose.aspect);
    return { shoulder, elbow, hand, tracked:Boolean(w) };
  }
  function forearm(c, elbow, hand) {
    line(c,elbow,hand,6,'#42142b');
    line(c,elbow,hand,3,'#b5ce8b');
    rect(c,elbow.x-2,elbow.y-2,4,4,'#659975');
    part(c,5,hand.x-24,hand.y-24);
  }
  function arm(c, { shoulder, elbow, hand }) {
    line(c,shoulder,elbow,7,'#42142b');
    line(c,shoulder,elbow,4,'#83ad79');
    forearm(c,elbow,hand);
  }
  function shin(c, hip, knee, ankle, near) {
    line(c,hip,knee,8,'#42142b'); line(c,knee,ankle,7,'#42142b');
    line(c,hip,knee,5,near?'#83ad79':'#609575');
    line(c,knee,ankle,4,near?'#609575':'#395c51');
    rect(c,knee.x-3,knee.y-2,7,4,near?'#b5ce8b':'#83ad79');
  }
  function leg(c, hip, knee, foot, near) {
    shin(c,hip,knee,{x:foot.x,y:foot.y-5},near);
    c.save();
    c.translate(round(foot.x),round(foot.y));
    if(!near) c.scale(-1,1);
    part(c,4,-25,-30);
    c.restore();
  }
  function part(c, index, x, y, width=48, height=48) {
    const art=images.partner;
    if (art?.complete && art.naturalWidth) {
      c.drawImage(art,index*48,0,48,48,round(x),round(y),width,height);
    } else if(index<2 || index>=6) {
      rect(c,x+3,y+16,40,27,'#568b72'); rect(c,x+7,y+19,32,21,'#173624');
      rect(c,x+13,y+24,5,8,'#ffedb2'); rect(c,x+27,y+25,5,8,'#ffedb2');
      rect(c,x+33,y+8,3,9,'#83ad79'); rect(c,x+34,y+4,6,6,GOLD);
    } else if(index===4) {
      rect(c,x+18,y+23,14,7,'#d75e1d');
    } else if(index===5) {
      rect(c,x+20,y+19,8,8,'#ffdf9b');
    } else {
      rect(c,x+10,y+10,24,16,'#a8c38a');rect(c,x+10,y+8,25,4,'#ed5225');
    }
  }
  let wingSprite;
  function gliderWing(c,side,angle) {
    if(!wingSprite) {
      wingSprite=document.createElement("canvas");wingSprite.width=54;wingSprite.height=41;
      const w=wingSprite.getContext("2d");w.translate(1,16);
      path(w,[[0,1],[5,-3],[14,-5],[23,-4],[32,-5],[40,-9],[48,-15],[50,-15],[49,-8],[45,-3],[41,0],[46,-2],[45,2],[40,7],[34,10],[38,9],[35,14],[28,18],[20,19],[23,20],[17,22],[10,20],[5,16],[1,9]],'#614956');
      path(w,[[1,1],[6,-2],[15,-4],[24,-3],[33,-4],[41,-8],[48,-13],[47,-8],[41,-2],[32,3],[21,7],[9,9],[3,7]],'#fff0bc');
      path(w,[[3,6],[14,5],[25,2],[36,-1],[43,-4],[39,0],[27,6],[16,11],[7,12]],'#eed09b');
      path(w,[[4,9],[12,9],[24,6],[38,1],[44,-1],[41,4],[34,8],[24,11],[15,14],[8,14]],'#d4e1b5');
      path(w,[[7,13],[16,12],[26,10],[35,7],[31,10],[22,14],[13,17],[8,16]],'#9cc6b2');
      path(w,[[9,16],[20,14],[31,11],[35,10],[31,14],[26,16],[16,18],[11,18]],'#bed8b5');
      path(w,[[7,15],[13,18],[21,17],[16,20],[11,19]],'#82a99d');
      path(w,[[1,1],[8,-2],[16,-3],[23,-2],[26,-3],[24,0],[20,2],[16,2],[14,4],[10,5],[7,5],[5,7],[2,7]],'#dc9a63');
      path(w,[[2,1],[8,-1],[15,-2],[22,-1],[19,1],[14,1],[10,3],[5,4],[2,5]],'#ffdc91');
      rect(w,6,0,6,1,'#fff2be');rect(w,18,5,4,1,'#fff2cb');rect(w,25,3,5,1,'#fff2cb');
    }
    c.save(); c.translate(side*9,-33); c.scale(side,1); c.rotate(angle);
    c.drawImage(wingSprite,-1,-16);
    c.restore();
  }
  function skiStance(c, hip, bank) {
    // Both skis pivot about their bindings in the plane of the slope.
    // Positive forward points downhill, toward the viewer when centered.
    const yaw = bank * Math.PI / 3, sin = Math.sin(yaw), cos = Math.cos(yaw);
    const feet = [-1,1].map(side => {
      const x = side * (8 + 2*cos), y = -side * sin * 4;
      const project = ([across,forward,height=0]) => [
        x + across*cos + forward*sin, y + (forward*cos - across*sin)*.65 - height
      ];
      return {side,x,y,face:(points,color) => path(c,points.map(project),color)};
    }).sort((a,b) => a.y-b.y);

    for (const {face} of feet) {
      // Raised coral tips and a blue running edge make the fore/aft direction legible.
      face([[-2,-15,-1],[2,-15,-1],[3,14,-1],[2,26,0],[-2,26,0],[-3,14,-1]],'#45667247');
      face([[-3,-18,1],[3,-18,1],[4,17,1],[4,25,2],[2,30,4],[-2,30,4],[-4,25,2],[-4,17,1]],'#373a51');
      face([[-2,-16,2],[2,-16,2],[3,17,2],[3,24,3],[-3,24,3],[-3,17,2]],'#84cee1');
      face([[-2,-12,2],[0,-12,2],[1,17,2],[-2,17,2]],'#e5f9e4');
      face([[-3,17,2],[3,17,2],[3,24,3],[-3,24,3]],'#ed7147');
      face([[-3,24,3],[3,24,3],[1,29,4],[-1,29,4]],'#ffdf94');
    }
    for (const {side,x,y,face} of feet) {
      const inside = side*bank;
      const knee = {x:x + sin*6, y:y-10-inside*2};
      shin(c,{x:hip.x+side*5,y:hip.y},knee,{x,y:y-5},inside<=0);
      // A high cuff, a low toe box and the sole all share the runner's local axes.
      face([[-4,-4,6],[4,-4,6],[5,4,5],[4,9,3],[3,10,1],[-3,10,1],[-5,7,2],[-5,0,4]],'#513348');
      face([[-4,-4,8],[4,-4,8],[4,2,7],[4,7,5],[2,9,3],[-3,9,3],[-4,6,5],[-4,0,6]],'#dd692d');
      face([[-3,-4,8],[3,-4,8],[3,1,8],[-3,1,8]],'#ffb154');
      face([[-4,1,7],[4,1,7],[4,3,6],[-4,3,6]],'#803d39');
      face([[-2,1,8],[1,1,8],[1,3,7],[-2,3,7]],'#ffe6a3');
      face([[-3,5,5],[3,5,5],[2,8,4],[-2,8,4]],'#ffb65d');
    }
  }
  function sportAvatar(c,pose,at,action,visual,time,scale) {
    const flight=action==='flap', bank=clamp(number(visual.avatar_dx)/58,-1,1);
    const arms=[limbs(pose,0,0),limbs(pose,1,0)];
    const angles=arms.map((a,i)=>clamp(Math.atan2(a.hand.y-a.shoulder.y,(i?1:-1)*(a.hand.x-a.shoulder.x)),-1.15,1.15));
    const bob=flight ? -3*Math.cos((angles[0]+angles[1])*.5+1.6) : 0;
    const hip={x:flight?0:bank*5,y:flight?-23+bob:-19+2*Math.abs(bank)};
    const neck={x:hip.x+(flight?0:bank*6),y:hip.y-15};
    c.save(); c.translate(round(at.x),round(at.y)); c.scale(scale*1.32,scale*1.32);
    if (flight) {
      for (const i of [0,1]) gliderWing(c,i?1:-1,angles[i]);
      leg(c,{x:-4,y:hip.y},{x:-10,y:-15+bob},{x:-15,y:-10+bob},false);
      leg(c,{x:5,y:hip.y},{x:9,y:-13+bob},{x:7,y:-3+bob},true);
    } else {
      skiStance(c,hip,bank);
    }
    const tail=round(Math.sin(time*6)*1.5);
    const scarf=flight||bank>=0?-1:1;
    c.save();c.translate(neck.x,neck.y+6);c.scale(scarf,1);
    path(c,[[0,0],[9,1],[18,-4],[27,-3+tail],[22,0+tail],[26,2+tail],[15,2],[8,6],[0,5]],'#763340');
    path(c,[[0,1],[9,2],[18,-2],[24,-2+tail],[18,0],[9,5],[0,4]],'#ff7443');c.restore();
    part(c,2,hip.x-23,hip.y-27);
    if (!flight) {
      for (const side of [-1,1]) {
        const hand={x:neck.x+side*23,y:hip.y-14-side*bank*5};
        const tip={x:hand.x+side*7-bank*8,y:-1};
        line(c,hand,tip,2,'#3b4552');line(c,{x:tip.x-3,y:tip.y-2},{x:tip.x+3,y:tip.y-2},2,'#e1ae7d');
        arm(c,{shoulder:{x:hip.x+side*10,y:hip.y-15},elbow:{x:hip.x+side*16,y:hip.y-9},hand});
      }
    } else {
      for (let i=0;i<2;i++) {
        const side=i?1:-1, a=angles[i], shoulder={x:side*9,y:-33};
        const elbow={x:side*(9+11*Math.cos(a)),y:-32+10*Math.sin(a)};
        const hand={x:side*(9+21*Math.cos(a)),y:-34+20*Math.sin(a)};
        arm(c,{shoulder,elbow,hand});
      }
    }
    c.save(); c.translate(round(neck.x),round(neck.y)); c.rotate(flight ? (angles[1]-angles[0])*.07 : bank*.15);
    if (!flight && bank<-.35) c.scale(-1,1);
    part(c,Math.abs(bank)>.35?1:0,-24,-40);c.restore();
    c.restore();
  }
  function player(c, pose, at, action, visual, time, scale, celebrate) {
    if (action==='flap'||action==='lean') return sportAvatar(c,pose,at,action,visual,time,scale);
    const size = scale * (action === 'piano' ? 1.23 : 1.32);
    const freeArms=[limbs(pose,0,0),limbs(pose,1,celebrate?1.8:.45)];
    const faceVisible=Boolean(point(pose.points,0));
    const turn=action==='turn'&&faceVisible ? clamp(number(visual.head_turn,pose.yaw/.17),-1,1) : 0;
    const dip=action==='nod'&&faceVisible ? clamp(number(visual.head_dip,pose.nod/2),0,1) : 0;
    const airborne=action==='hands_up' ? clamp(-number(visual.avatar_dy)/45,0,1) : 0;
    const breath=pose.points.length ? 0 : Math.sin(time*2)*.75;
    const hip={x:52,y:65+2*dip-5*airborne+breath};
    const neck={x:hip.x+2*turn,y:hip.y-23};
    c.save();
    c.translate(round(at.x),round(at.y));
    c.scale(size,size); c.translate(-52,-83);
    const arms=freeArms.map((limb,i)=>{
      const x=hip.x+(i?11:-11);
      const y=hip.y-17+pose.tilt*(i?1:-1);
      const dx=x-limb.shoulder.x,dy=y-limb.shoulder.y;
      const offset=p=>({x:p.x+dx,y:p.y+dy});
      return {shoulder:offset(limb.shoulder),elbow:offset(limb.elbow),hand:offset(limb.hand),tracked:limb.tracked};
    });
    const feet=[[41-5*airborne,83-7*airborne],[63+2*airborne,83-15*airborne]];
    const knees=[[41-7*airborne,73-12*airborne],[61+8*airborne,72-18*airborne]];
    for(let i=0;i<2;i++) leg(c,{x:hip.x+(i?5:-5),y:hip.y},{x:knees[i][0],y:knees[i][1]},
      {x:feet[i][0],y:feet[i][1]},Boolean(i));
    const tail=0;
    c.save();
    c.translate(round(neck.x+9),round(neck.y+4));
    path(c,[[0,0],[5,1],[13,-2+tail],[21,-3+tail],[23,-1+tail],[20,2+tail],
      [21,5+tail],[14,4+tail],[9,6],[14,9+tail],[8,11+tail],[2,8],[-2,5]],'#42142b');
    path(c,[[1,2],[6,2],[14,-1+tail],[21,-1+tail],[18,2+tail],[19,3+tail],[14,2+tail],[8,5],[2,4]],'#f05325');
    path(c,[[1,5],[5,5],[12,7+tail],[13,9+tail],[8,9+tail],[7,10+tail],[3,8]],'#ca3823');
    c.restore();
    arm(c,arms[0]);
    part(c,2,hip.x-23,hip.y-27);
    const profile=Math.abs(turn)>.42;
    c.save();
    c.translate(round(neck.x+pose.yaw*3+4*turn),round(neck.y+6*dip));
    if (turn<-.42) c.scale(-1,1);
    const blink=action==='wave' && time%3.5>3.35;
    part(c,(blink?6:0)+(profile?1:0),-24,-42,48,round(48-7*dip));
    c.restore();
    arm(c,arms[1]);
    for (const {elbow,hand,shoulder,tracked} of arms) {
      // A raised forearm should remain visible when it crosses the CRT.
      if (tracked && hand.x>neck.x-20 && hand.x<neck.x+21 && hand.y<neck.y) forearm(c,elbow,hand);
      if (action==='wave' && tracked && hand.y<shoulder.y) {
        rect(c,hand.x-2,hand.y-6,4,2,GOLD);
        rect(c,hand.x-5,hand.y-4,2,2,'#fbe4ac');
      }
    }
    c.restore();
  }
  function paintAvatar(ctx,snapshot,x,feetY,scale=1) {
    if (!ctx || !snapshot) return;
    ensureImages();
    const action=snapshot.phase==='round' ? snapshot.act_id : '';
    const challenge=snapshot.challenge || {};
    const celebrate=snapshot.phase==='summary' || (snapshot.sub==='clear' && challenge.frac>=1);
    const time=reducedMotion?.matches ? 0 : performance.now()/1000;
    player(ctx,poseInfo(snapshot),{x,y:feetY},action,challenge.visual || {},time,scale,celebrate);
  }
  function flag(c, x, y, height, collected) {
    const width = round(height * .7);
    rect(c, x - 1, y - height, 2, height, '#536375');
    rect(c, x, y - height, 1, height - 2, '#e5ddb4');
    path(c, [[x+1,y-height],[x+width,y-height+2],[x+width-3,y-height+6],[x+1,y-height+5]],
      collected ? '#b2f1a5' : '#ed857d');
    rect(c, x+2, y-height+1, Math.max(2, width/2), 1, collected ? '#e1ffc7' : '#ffd0a0');
  }
  function tree(c, x, y, h) {
    rect(c, x-2, y-h/3, 4, h/3, '#6d6c70');
    for (const [top, wide] of [[-.98,.16],[-.77,.25],[-.54,.34]]) {
      const y1 = y + h * top, y2 = y1 + h * .46;
      path(c, [[x,y1],[x+h*wide,y2],[x-h*wide,y2]], '#3d7074');
      path(c, [[x,y1],[x,y2-3],[x-h*wide,y2]], '#61988c');
      path(c, [[x,y1],[x+2,y1+5],[x-4,y1+6]], '#d5e5b9');
    }
  }
  function slalom(c, v) {
    if (!Array.isArray(v.gates)) return;
    const visible = v.gates.filter(g => g && g.y >= 0 && g.y <= 125).sort((a, b) => a.y - b.y);
    for (const gate of visible) {
      const x = CENTER + (gate.x - 160) * 1.65;
      const y = FLOOR + (gate.y - 88) * .88;
      const h = 13 + gate.y * .23;
      if (gate.kind === 'tree') tree(c, x, y, h);
      else flag(c, x, y, h, gate.state > 0);
    }
  }
  function wristCursor(c, x, y, side) {
    const color = side === 0 ? '#a4f8c7' : '#d4b7ff';
    rect(c,x-5,y-11,11,9,INK);
    rect(c,x-5,y-11,11,1,color);
    // L / R stay distinct on the same key and when displayed without color.
    rect(c,x-2,y-9,1,5,color);
    if (side===0) rect(c,x-2,y-5,4,1,color);
    else {
      rect(c,x-1,y-9,3,1,color);rect(c,x+1,y-8,1,2,color);
      rect(c,x-1,y-7,2,1,color);rect(c,x,y-6,1,1,color);rect(c,x+1,y-5,1,1,color);
    }
    path(c,[[x-4,y-2],[x+4,y-2],[x,y+2]],color);
  }
  function keyboard(c, visual, progress, points, tracked) {
    const left = 82, top = 165, width = 22;
    rect(c, left-6, top-6, 232, 38, INK);
    rect(c, left-4, top-4, 228, 34, '#68566d');
    rect(c, left-3, top+24, 226, 5, '#443b50');
    const lit = Array.isArray(visual.keys_lit) ? visual.keys_lit : [];
    for (let i = 0; i < 10; i++) {
      const x = left + i * width, held = lit.includes(i), target = i === visual.target_key;
      const y = top + (held ? 2 : 0);
      rect(c, x, y, width-1, 23, target ? '#e9a568' : held ? '#6bbbaa' : '#baaa9e');
      rect(c, x+1, y, width-3, 19, target ? GOLD : held ? MINT : '#f0dec0');
      if (held) rect(c,x+2,y+17,width-5,2,MINT);
      if (target) { rect(c,x+7,y+13,6,2,INK); rect(c,x+9,y+11,2,6,INK); }
      if (i % 5 !== 2 && i !== 4 && i !== 9) rect(c, x+width-4, top-1, 7, 11, '#3b3a50');
    }
    if (tracked && Array.isArray(visual.aim_keys)) {
      const aim = visual.aim_keys;
      const together = aim[0] === aim[1];
      for (const side of [0,1]) {
        const key = aim[side];
        if (!Number.isInteger(key) || key<0 || key>=10 || !point(points,15+side)) continue;
        const offset = together ? (side===0 ? -5 : 5) : 0;
        wristCursor(c,left+(key+.5)*width+offset,top-2,side);
      }
    }
    if (tracked && Array.isArray(visual.finger_depth)) {
      // In board finger mode each physical finger owns one key. Missing fingers
      // stay absent until the hand tracker sees them again.
      visual.finger_depth.forEach((press,i)=>{
        if (i>=10 || !Number.isFinite(press)) return;
        const x=left+(i+.5)*width, y=top-9+clamp(press,0,1)*10;
        rect(c,x-2,y-5,5,9,INK);
        rect(c,x-1,y-4,3,6,i<5?MINT:'#cbb7fb');
        rect(c,x-1,y+1,3,2,press>.55?GOLD:'#fae4bc');
      });
    }
    for (let i=0;i<8;i++) rect(c,left+i*5,top+27,3,1,i<round(progress*8)?GOLD:'#766171');
  }
  function chargeTowers(c, pos, progress, side) {
    for (const dir of [-1, 1]) {
      const x = pos.x + dir * 83, y = FLOOR - 23;
      rect(c,x-12,y+18,25,5,INK); rect(c,x-8,y-42,17,61,INK);
      rect(c,x-6,y-40,13,58,'#55556a');
      const fill = clamp(number(dir < 0 ? side.left_fill : side.right_fill, progress), 0, 1);
      for (let i=0;i<8;i++) rect(c,x-4,y+9-i*6,9,4,i<round(fill*8)?MINT:'#30394f');
      rect(c,x-9,y-42,19,3,fill>.8?GOLD:'#8b8991');
      if (progress > .02) star(c,x,y-47,round(1+3*progress),GOLD);
    }
  }
  function train(c, progress) {
    const x=14-round(progress*101);
    rect(c,0,166,W,4,'#4c485c'); rect(c,0,168,W,1,'#a49da1');
    for (let i=0;i<5;i++) {
      const l=x+i*66;
      rect(c,l,141,64,22,'#42435c'); rect(c,l+2,143,60,17,'#b99aa0');
      rect(c,l+2,143,59,2,'#e2c0a8'); rect(c,l,155,63,3,'#84758c');
      for (let j=0;j<4;j++) rect(c,l+6+j*13,146,9,7,(i+j)%3===0?GOLD:'#738398');
      rect(c,l+6,163,9,3,INK); rect(c,l+49,163,9,3,INK);
    }
    const departed=round(clamp(progress,0,1)*10);
    for(let i=departed;i<10;i++){
      const px=i<5 ? 25+i*23 : 267+(i-5)*22;
      const coat=[MINT,'#d4b7ee',CORAL,'#e2cea7'][i%4];
      rect(c,px,155,4,4,INK);rect(c,px-1,156,5,3,'#ffd6ae');
      rect(c,px-1,159,6,5,coat);rect(c,px+4,157,2,4,coat);
      rect(c,px-1,164,2,2,INK);rect(c,px+2,164,2,2,INK);
    }
  }
  function cactus(c,x,y) {
    rect(c,x-6,y-32,13,32,INK); rect(c,x-4,y-32,8,30,'#63a38b');
    rect(c,x-14,y-21,5,13,INK); rect(c,x-13,y-10,12,5,INK);
    rect(c,x-12,y-21,2,12,'#87ce99'); rect(c,x-10,y-10,6,3,'#77b994');
    rect(c,x+7,y-20,7,6,INK); rect(c,x+11,y-27,5,13,INK);
    rect(c,x+7,y-18,7,3,'#619b84');rect(c,x+13,y-25,2,9,'#94c79a');
    rect(c,x-2,y-29,2,26,'#a6d59a'); rect(c,x-3,y-34,5,3,CORAL);
  }
  function venueLights(c, action, progress, v) {
    const total = action==='turn' ? 3 : 6;
    for (const dir of [-1,1]) {
      const x=CENTER+dir*90;
      const filled = action==='turn' ? number(dir<0?v.left_got:v.right_got) : round(total*progress);
      rect(c,x-3,FLOOR-70,6,70,'#4b425e'); rect(c,x-9,FLOOR-2,19,3,INK);
      rect(c,x-11,FLOOR-77,23,8,INK);rect(c,x-9,FLOOR-76,18,4,'#9a8494');
      for(let i=0;i<total;i++){
        const y=FLOOR-61+i*(action==='turn'?15:8);
        rect(c,x-6,y,12,7,INK);rect(c,x-4,y+1,8,4,i<filled?GOLD:'#75647d');
      }
    }
  }
  function confetti(c, time) {
    const colors=[MINT,GOLD,CORAL,'#c6b3e6'];
    for(let i=0;i<32;i++){
      const x=(i*73+25)%W, y=(i*47+time*(9+i%5))%151+22;
      if(i%4===0) star(c,x,y,2,colors[i%4]);
      else rect(c,x,y,i%3+1,2,colors[i%4]);
    }
  }
  function draw(canvas, snapshot) {
    const c = canvas.getContext('2d');
    if (!c) return;
    const roundActive=snapshot.phase==='round';
    const action=roundActive ? snapshot.act_id : '';
    const challenge=roundActive ? (snapshot.challenge || {}) : {};
    const visual=challenge.visual || {}, progress=clamp(number(challenge.frac),0,1);
    const pose=poseInfo(snapshot), time=reducedMotion?.matches ? 0 : performance.now()/1000;
    const summary=snapshot.phase==='summary', clear=roundActive && snapshot.sub==='clear' && progress>=1;
    const pianoInput=challenge.piano_input || visual.piano_input || (visual.aim_keys ? 'wrists' : 'fingers');
    const fingerView=action==='piano' && !['wrists','wrist'].includes(pianoInput);
    const resolution=fingerView ? 2 : 1;
    if (canvas.width!==W*resolution) canvas.width=W*resolution;
    if (canvas.height!==H*resolution) canvas.height=H*resolution;
    c.imageSmoothingEnabled=false;
    if (fingerView) {
      c.save();c.scale(resolution,resolution);
      window.PianoStage.draw(c,W,H,visual,{aspect:snapshot.pose_aspect || 1,count:challenge.count,ready:snapshot.sub==='ready'});
      if(clear) confetti(c,time);
      c.restore();
      return;
    }
    const at={x:CENTER, y:FLOOR};
    scenery(c,action);
    if(action==='lean') {
      at.x+=clamp(number(visual.avatar_dx, pose.yaw*56),-65,65)*1.65;
      slalom(c,visual);
    } else if(action==='flap') {
      at.y-=15+clamp(number(visual.alt,progress*56),0,56)*.67;
      // Each successful downstroke lifts the pilot toward the summit marker.
      flag(c,337,FLOOR-13,64,progress>=1);
    } else if(action==='wave') {
      train(c,progress);
    } else if(action==='hands_up') {
      at.y+=clamp(number(visual.avatar_dy),-72,0)*1.12;
      if(Number.isFinite(visual.obs)) cactus(c,CENTER+(visual.obs-160)*1.55,FLOOR);
    } else if(action==='wings') {
      chargeTowers(c,at,progress,visual);
    } else if(action==='turn'||action==='nod') {
      venueLights(c,action,progress,visual);
    }
    const shadowWidth=clamp(52-(FLOOR-at.y)*.4,19,52);
    if(action!=='flap' && action!=='lean'){
      rect(c,at.x-shadowWidth/2,FLOOR+1,shadowWidth,3,'#4c4759');
      rect(c,at.x-shadowWidth*.35,FLOOR+4,shadowWidth*.7,1,'#575362');
    }
    player(c,pose,at,action,visual,time,1,summary||clear);
    if(action==='piano') keyboard(c,visual,progress,pose.points,challenge.tracking!==false);
    if (clear || (summary && snapshot.cleared > 0)) confetti(c,time);
    if (snapshot.phase==='alert') {
      // An empty battery sits beside the player while the board waits for their first motion.
      const x=CENTER+48,y=77+round(Math.sin(time*2));
      rect(c,x,y,24,13,INK);rect(c,x+23,y+4,3,5,INK);
      rect(c,x+2,y+2,20,9,'#bd8288');rect(c,x+4,y+4,16,5,'#483d54');
      rect(c,x+4,y+4,3,5,CORAL);
    }
    if(roundActive && snapshot.sub==='ready'){
      for (const dir of [-1,1]){
        const x=CENTER+dir*65;
        rect(c,x,95,2,10,GOLD);rect(c,dir<0?x:x-6,95,8,2,GOLD);
      }
    }
  }
  function paint(canvas, snapshot = {}) {
    if (!canvas?.getContext) return;
    ensureImages();
    if (Object.values(images).some(img=>!img.complete)) loading.set(canvas,snapshot||{});
    draw(canvas,snapshot||{});
  }
  function paintBackdrop(context, action, width, height) {
    ensureImages();
    context.save();
    context.scale(width/W,height/H);
    scenery(context,action);
    context.restore();
  }
  function scenery(c,action) {
    if(action!=='flap') {background(c,plates[action] ?? plates.night);return;}
    const sky=['#8686ad','#a198b8','#c3a8b8','#e3b6b2','#f4c6aa','#f9d3ae'];
    sky.forEach((t,i)=>rect(c,0,i*36,W,36,t));
    const sx=281;
    for(let y=-25;y<=25;y+=2) {
      const half=round(Math.sqrt(Math.max(0,625-y*y)));
      rect(c,sx-half,45+y,2*half,2,'#ffe3a9');
    }
    path(c,[[0,166],[27,153],[53,160],[99,131],[129,148],[161,139],[187,151],[223,119],[255,145],[296,130],[342,153],[384,137],[384,216],[0,216]],'#bc9fac');
    path(c,[[0,184],[44,170],[77,175],[113,156],[164,182],[199,163],[247,178],[284,154],[326,177],[384,153],[384,216],[0,216]],'#9d8ea7');
    const drift=reducedMotion?.matches?0:(performance.now()/420)%425;
    for (const [start,y,w] of [[29,52,43],[173,68,30],[370,38,52],[63,130,57],[311,159,69],[130,194,91]]) {
      const x=(start-drift+425)%425-25;
      rect(c,x,y,w,3,'#f8dec0');rect(c,x+w*.2,y-3,w*.55,4,'#ffe9c9');rect(c,x+w*.36,y-6,w*.19,4,'#fff1d5');
      rect(c,x+4,y+3,w*.64,2,'#dfbab1');
    }
  }
  window.MotionStage = {paint,paintAvatar,paintBackdrop};
})();
