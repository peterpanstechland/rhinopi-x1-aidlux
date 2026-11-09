/* Render the player's mirrored landmarks and the obstacle positions used by the game. */
(() => {
  'use strict';
  const W = 384, H = 216, CENTER = W / 2, FLOOR = 189;
  const INK = '#202638', MINT = '#a2efb2', GOLD = '#ffdc99', CORAL = '#ed8d88';
  const plates = { night: 0, wings: 1, flap: 1, wave: 0, lean: 2, piano: 3, hands_up: 1, turn: 0, nod: 3 };
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
    for (const key of ['plates', 'player']) {
      const image = new Image();
      images[key] = image;
      image.onload = image.onerror = () => {
        for (const [canvas, snapshot] of loading) draw(canvas, snapshot);
        if (Object.values(images).every(img => img.complete)) loading.clear();
      };
      image.src = 'art/stage-' + key + '.png';
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
    line(c, elbow, hand, 6, INK);
    line(c, elbow, hand, 4, '#88dba7');
    rect(c, elbow.x - 2, elbow.y - 2, 5, 5, '#526e7a');
    rect(c, elbow.x - 1, elbow.y - 1, 2, 2, '#adc8ad');
    rect(c, hand.x - 4, hand.y - 3, 8, 6, INK);
    rect(c, hand.x - 3, hand.y - 4, 5, 8, INK);
    rect(c, hand.x - 3, hand.y - 2, 6, 4, '#73c4a3');
    rect(c, hand.x - 2, hand.y - 3, 3, 3, '#c4ecae');
  }
  function arm(c, { shoulder, elbow, hand }) {
    line(c, shoulder, elbow, 7, INK);
    line(c, shoulder, elbow, 4, '#438c8b');
    forearm(c, elbow, hand);
  }
  function player(c, pose, at, action, visual, time, scale, celebrate) {
    const size = scale * (action === 'piano' ? 1.43 : 1.5);
    const bob = !pose.points.length ? round(Math.sin(time * 1.7)) : 0;
    c.save();
    c.translate(round(at.x), round(at.y+bob));
    c.scale(size, size);
    if (action==='lean') c.rotate(clamp(number(visual.avatar_dx)/58,-1,1)*.19);
    c.translate(-38,-70);
    const idleLift = celebrate ? 1.8 : .45;
    const arms = [limbs(pose, 0, 0), limbs(pose, 1, idleLift)];
    if (action==='flap') {
      for (const {shoulder,hand,tracked} of arms) {
        const dx=hand.x-shoulder.x, dy=hand.y-shoulder.y;
        if (!tracked || Math.abs(dx)<10) continue;
        // Feathers follow each wing's actual slope, with their tips trailing below.
        for (let i=0;i<3;i++) {
          const t=.40+i*.18, x=shoulder.x+dx*t, y=shoulder.y+dy*t;
          const sign=Math.sign(dx);
          path(c,[[x,y],[x+sign*6,y+dy*.16],[x+sign*(3-i),y+9-i]],i===1?MINT:'#72c3b0');
        }
      }
    }
    for (const limb of arms) arm(c, limb);
    const sprite = images.player;
    const ready=Boolean(sprite?.complete && sprite.naturalWidth);
    if (ready) c.drawImage(sprite,78,0,78,78,0,0,78,78);
    else {
      rect(c, 26, 44, 25, 20, INK); rect(c, 28, 46, 21, 15, MINT);
      rect(c, 23, 65, 11, 5, INK); rect(c, 40, 65, 11, 5, INK);
    }
    // Keep the neck in place while the CRT turns into profile or pitches down.
    const faceVisible=Boolean(point(pose.points,0));
    const turn=action==='turn' && faceVisible ? clamp(number(visual.head_turn,pose.yaw/.17),-1,1) : 0;
    const dip=action==='nod' && faceVisible ? clamp(number(visual.head_dip,pose.nod/2),0,1) : 0;
    c.save();
    const headX=round(pose.yaw*4+turn*7);
    c.translate(38+headX,48+(dip ? round(dip*3) : round(pose.nod)));
    c.scale((turn>.40?-1:1)*(1-Math.abs(turn)*.30),1-dip*.27);
    c.translate(-38,-48);
    if (ready) c.drawImage(sprite,0,0,78,78,0,0,78,78);
    else {
      rect(c,16,17,44,32,INK); rect(c,18,19,40,28,MINT);
      rect(c,21,23,32,19,INK); rect(c,26,28,4,7,MINT); rect(c,41,28,4,7,MINT);
      rect(c,40,10,3,8,MINT); rect(c,39,7,6,5,CORAL);
    }
    c.restore();
    for (const {elbow,hand,shoulder,tracked} of arms) {
      // A raised forearm should remain visible when it crosses the CRT.
      if (tracked && hand.x>15 && hand.x<62 && hand.y<53) forearm(c,elbow,hand);
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
    if (canvas.width!==W) canvas.width=W;
    if (canvas.height!==H) canvas.height=H;
    c.imageSmoothingEnabled=false;
    const roundActive=snapshot.phase==='round';
    const action=roundActive ? snapshot.act_id : '';
    const challenge=roundActive ? (snapshot.challenge || {}) : {};
    const visual=challenge.visual || {}, progress=clamp(number(challenge.frac),0,1);
    const pose=poseInfo(snapshot), time=reducedMotion?.matches ? 0 : performance.now()/1000;
    const summary=snapshot.phase==='summary', clear=roundActive && snapshot.sub==='clear' && progress>=1;
    const at={x:CENTER, y:FLOOR};
    background(c,plates[action] ?? 0);
    if(action==='lean') {
      at.x+=clamp(number(visual.avatar_dx, pose.yaw*56),-65,65)*1.65;
      slalom(c,visual);
    } else if(action==='flap') {
      at.y-=clamp(number(visual.alt,progress*56),0,56)*.77;
      flag(c,304,FLOOR-39,74,progress>=1);
      for(let i=0;i<4;i++) {
        const x=72+i*61, y=(37+i*39+(FLOOR-at.y)*.4)%128+25;
        rect(c,x,y,13+i*3,2,'#efd6c6');rect(c,x+4,y-2,8,2,'#efd6c6');
      }
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
    rect(c,at.x-shadowWidth/2,FLOOR+1,shadowWidth,3,'#4c4759');
    rect(c,at.x-shadowWidth*.35,FLOOR+4,shadowWidth*.7,1,'#575362');
    player(c,pose,at,action,visual,time,1,summary||clear);
    if(action==='piano') keyboard(c,visual,progress,pose.points,challenge.tracking!==false);
    if(action==='lean'){
      rect(c,at.x-30,at.y+4,30,2,'#d77d7a');rect(c,at.x+3,at.y+3,29,2,'#c57377');
      rect(c,at.x+30,at.y+1,4,2,'#d77d7a');
    }
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
  window.MotionStage = {paint,paintAvatar};
})();
