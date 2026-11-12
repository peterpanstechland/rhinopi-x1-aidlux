/* Browser motion relay. Geometry comes from mirrored landmarks in camera-input.js. */
(() => {
  "use strict";
  const acts = [
    {id:"wings",name:"天台展翅",goal:"双臂平举，撑满 5 秒",target:5,unit:"秒"},
    {id:"flap",name:"老鹰起飞",goal:"双臂向两侧展开，上下扇动 8 次",target:8,unit:"次"},
    {id:"wave",name:"月台挥手",goal:"抬起一只手左右挥，送走 10 人",target:10,unit:"人"},
    {id:"lean",name:"雪岭穿梭",goal:"向旗子一侧倾身，碰到 6 面旗",target:6,unit:"面"},
    {id:"piano",name:"落日合奏",goal:"跟着亮键，弯指弹出 8 个音",target:8,unit:"音"},
    {id:"hands_up",name:"仙人掌跳跃",goal:"仙人掌靠近时轻挺上身，越过 5 个障碍",target:5,unit:"个"},
    {id:"turn",name:"左右转头",goal:"双肩朝前，左右各转 3 次，每次回正",target:6,unit:"次"},
    {id:"nod",name:"节拍点头",goal:"低头再抬回正中，完成 6 次",target:6,unit:"次"},
  ];
  const actById = new Map(acts.map(act => [act.id,act]));
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const keys = [2,7,3,6,1,8,4,5];
  const sides = [-1,1,1,-1,1,-1];

  class CameraRound {
    static ids = Object.freeze(acts.map(act => act.id));

    constructor(ids = CameraRound.ids) {
      if (!Array.isArray(ids) || !ids.length || ids.some(id => !actById.has(id))) {
        throw new RangeError("请选择有效的体感关卡。");
      }
      this.acts = ids.map(id => actById.get(id));
      this.limit = this.acts.length === 1 ? 45 : 120;
      this.index = 0;
      this.sub = "ready";
      this.elapsed = 0;
      this.phaseTime = 0;
      this.score = 0;
      this.cleared = 0;
      this.completed = [];
      this.lastFrame = null;
      this.home = null;
      this.doneAt = 0;
      this.resetAction();
    }
    resetAction() {
      this.count = 0;
      this.feedback = null;
      this.feedbackSeq = 0;
      this.feedbackUntil = 0;
      this.gateTime = 0;
      this.gate = 0;
      this.visual = {left_fill:0,right_fill:0,gates:[],target_key:keys[0],keys_lit:[],
        alt:0, obs:294, avatar_dy:0, left_got:0, right_got:0};
      this.obstaclePassed = false;
      this.fingers = this.acts[this.index].id==="piano" ? new window.FingerPiano.Tracker() : null;
      this.noteUntil=0;
      this.lastWaveSide = 0;
      this.resetTracking();
      this.cue = "";
    }
    resetTracking() {
      this.feedback = null;
      this.wingExtreme = null;
      this.wingPrevious = null;
      this.wingsRaised = false;
      this.waveHand = null;
      this.waveDirection = 0;
      this.turnReady = false;
      this.nodStage = "center";
      this.jumpReady = false;
      this.jumpClock = null;
      this.jumpClearance = 0;
      this.visual.avatar_dy = 0;
      this.visual.left_fill = 0;
      this.visual.right_fill = 0;
      this.visual.head_turn = 0;
      this.visual.head_dip = 0;
      this.visual.aim_keys = [];
      this.visual.keys_lit = [];
    }
    notify(kind, text) {
      this.feedback = {kind,text,seq:++this.feedbackSeq};
      this.feedbackUntil = this.elapsed + 0.75;
    }
    wings({points,span}, dt) {
      const fills = [0,1].map(i => {
        const shoulder = points[11+i], wrist = points[15+i], dir = i ? 1 : -1;
        const reach = (wrist.x - shoulder.x) * dir / span;
        const height = Math.abs(shoulder.y - wrist.y) / span;
        return clamp(reach / .75,0,1) * clamp(1 - height/.9,0,1);
      });
      [this.visual.left_fill,this.visual.right_fill] = fills;
      const matched = Math.min(...fills) >= .73;
      const old = Math.floor(this.count);
      this.count = clamp(this.count + (matched ? dt : -.5*dt),0,5);
      this.cue = matched ? "姿势对了，稳住双臂" : "双腕向两侧伸开，抬到肩膀高度";
      if (Math.floor(this.count) > old) this.notify("hit","展翅保持 +" + Math.floor(this.count) + " 秒");
    }
    flap({points,span}) {
      const leftReach = (points[11].x-points[15].x)/span;
      const rightReach = (points[16].x-points[12].x)/span;
      if (Math.min(leftReach,rightReach) < .35) {
        this.wingExtreme=null;
        this.wingPrevious=null;
        this.wingsRaised=false;
        this.cue="双臂先向两侧展开";
        return;
      }
      const heights=[(points[15].y-points[11].y)/span,(points[16].y-points[12].y)/span];
      if (!this.wingExtreme) this.wingExtreme=heights.slice();
      const dir=this.wingsRaised ? 1 : -1;
      const extreme=this.wingsRaised ? Math.min : Math.max;
      this.wingExtreme=heights.map((h,i) => extreme(h,this.wingExtreme[i]));
      const together=this.wingPrevious && heights.every((h,i) => dir*(h-this.wingPrevious[i])>.002);
      if (together && heights.every((h,i) => dir*(h-this.wingExtreme[i]) >= .20)) {
        if (this.wingsRaised) {
          this.count++;
          this.visual.alt=this.count*7;
          this.notify("hit","双翼扇动 +1");
        }
        this.wingsRaised=!this.wingsRaised;
        this.wingExtreme=heights.slice();
      }
      this.wingPrevious=heights;
      this.cue=this.wingsRaised ? "两臂同时落下，完成这一拍" : "保持双翼展开，同时向上扇";
    }
    wave({points,center,span}) {
      const raised = i => points[15+i] && points[15+i].y < points[11+i].y-.025*span;
      let hand=this.waveHand;
      if (hand===null || !raised(hand)) {
        hand=[0,1].find(raised) ?? null;
        this.waveHand=hand;
        this.waveDirection=0;
        this.waveExtreme=null;
      }
      this.cue="抬一只手到肩膀上方，左右摆动";
      if (hand===null) return;
      const x=(points[15+hand].x-center)/span;
      if (this.waveExtreme===null) this.waveExtreme=x;
      const travel=x-this.waveExtreme;
      const direction=Math.sign(travel);
      if (direction!==this.waveDirection && Math.abs(travel)>=.20) {
        this.waveDirection=direction;
        this.waveExtreme=x;
        if (direction!==this.lastWaveSide) {
          this.lastWaveSide=direction;
          this.count++;
          this.notify("hit","挥手送走一人");
        }
      } else if (direction===this.waveDirection) this.waveExtreme=x;
      this.cue=this.waveDirection===1 ? "挥回左边" : this.waveDirection===-1 ? "挥回右边" : "保持手掌举高，向一侧挥";
    }
    lean({points,center,span}, dt) {
      const headOffset = (points[0].x - center) / span - this.home.nose;
      const shoulderShift = (center - this.home.center) / span;
      const lean = clamp((headOffset + shoulderShift*.72)/.38,-1,1);
      this.visual.avatar_dx = lean * 58;
      const side = sides[this.gate % sides.length];
      const gateX = 160 + side * 48;
      this.gateTime += dt;
      const hitAt = 2.3;
      const gateY = 88*this.gateTime/hitAt;
      this.visual.gates = [{x:gateX,y:gateY,kind:"flag",state:0},{x:160-side*48,y:gateY,kind:"tree",state:0}];
      this.cue = side < 0 ? "向画面左侧倾，碰左旗" : "向画面右侧倾，碰右旗";
      if (this.gateTime < hitAt) return;
      if (Math.abs(160 + this.visual.avatar_dx - gateX) < 23) {
        this.count++;
        this.visual.gates[0].state = 1;
        this.notify("hit", "碰到旗子 +1");
        this.gate++;
      } else {
        this.notify("miss",lean*side < -.55 ? "撞树了，向旗子一侧倾" : "错过旗子，再试同一侧");
      }
      this.gateTime = 0;
    }
    piano({fingering}, dt) {
      const target = keys[this.count];
      const key=fingering.press;
      this.noteUntil=Math.max(0,this.noteUntil-dt);
      if (!this.noteUntil) this.visual.keys_lit=[];
      if (key!==undefined) {
        const match=key===target;
        this.visual.keys_lit=[key];
        this.noteUntil=.30;
        this.notify(match?"hit":"miss",window.FingerPiano.label(key)+(match?" · 命中":" · 再试一次"));
        this.feedback.key=key;
        if (match) this.count++;
      }
      this.visual.target_key=keys[this.count] ?? target;
      this.cue="轻弯"+window.FingerPiano.label(this.visual.target_key)+"，再伸直";
    }
    hands_up({shoulderY,span,tilt}, dt) {
      // Launch on a seated shoulder rise; a held high pose can't launch a second jump.
      const rise=(this.home.shoulderY-shoulderY)/span-Math.abs(tilt-this.home.tilt)/2;
      if (rise<.035) this.jumpReady=true;
      if (this.jumpReady && rise>.105 && this.jumpClock===null) {
        this.jumpClock=0;
        this.jumpReady=false;
      }
      if (this.jumpClock!==null) {
        const flight=.85;
        this.jumpClock+=dt;
        this.visual.avatar_dy=-48*Math.sin(Math.PI*Math.min(1,this.jumpClock/flight));
        if (this.jumpClock>=flight) { this.jumpClock=null; this.visual.avatar_dy=0; }
      }
      const previous=this.visual.obs;
      this.visual.obs-=dt*73;
      // Sample the crossing interval even when inference frames straddle the cactus.
      if (previous>=152 && this.visual.obs<=168) {
        this.jumpClearance=Math.max(this.jumpClearance,-this.visual.avatar_dy);
      }
      if (this.visual.obs<152 && !this.obstaclePassed) {
        this.obstaclePassed=true;
        if (this.jumpClearance>=31) {
          this.count++;
          this.notify("hit","越过仙人掌 +1");
        } else this.notify("miss","碰到仙人掌，靠近时再起跳");
      }
      if (this.visual.obs<100) {
        this.visual.obs=294;
        this.obstaclePassed=false;
        this.jumpClearance=0;
      }
      this.cue=this.jumpClock!==null ? "跳起来了，落回坐姿" : !this.jumpReady ? "回到初始坐姿再跳" :
        this.visual.obs>160 && this.visual.obs<211 ? "现在轻挺上身，双肩一起抬起！" : "坐稳，等仙人掌靠近";
    }
    turn({points,center,span,tilt}) {
      const yaw=(points[0].x-center)/span-this.home.nose;
      this.visual.head_turn=clamp(yaw/.16,-1,1);
      this.cue="双肩朝前，转脸后回到正中";
      if (Math.abs(tilt-this.home.tilt)>.18) { this.turnReady=false; return; }
      if (Math.abs(yaw)<=.065) this.turnReady=true;
      if (!this.turnReady || Math.abs(yaw)<.16) return;
      this.turnReady=false;
      const side=yaw<0?"left_got":"right_got";
      if (this.visual[side]>=3) {
        this.cue="这一侧已完成，回正再转另一侧";
        return;
      }
      this.visual[side]++;
      this.count++;
      this.notify("hit", yaw<0?"向左转 +1":"向右转 +1");
    }
    nod({points,shoulderY,span}) {
      const depth=(points[0].y-shoulderY)/span-this.home.depth;
      this.visual.head_dip=clamp(depth/.085,0,1);
      if (this.nodStage==="center" && Math.abs(depth)<.04) this.nodStage="lower";
      if (this.nodStage==="lower" && depth>=.085) this.nodStage="lift";
      if (this.nodStage==="lift" && depth<=.035) {
        this.nodStage="lower";
        this.count++;
        this.notify("hit","点头回正 +1");
      }
      this.cue=this.nodStage==="lift" ? "抬头，看正前方" : "保持双肩不动，轻轻低头再抬起";
    }
    update(frame, now) {
      // Settlement lasts 1.15 seconds even when the player steps out of view.
      // Resolve it before checking which landmarks the next action requires.
      if (this.sub === "clear" && !this.doneAt && now >= this.clearUntil) {
        if (this.index === this.acts.length - 1) this.doneAt = Date.now();
        else {
          this.index++;
          this.sub = "ready";
          this.phaseTime = 0;
          this.lastFrame = null;
          this.resetAction();
        }
      }
      const raw = frame.pose_points || [];
      const aspect = frame.pose_aspect || 1;
      const pts = raw.map(p => p && Number.isFinite(p[0]) && Number.isFinite(p[1]) ? {x:p[0]*aspect,y:p[1]} : null);
      const act = this.acts[this.index];
      const needsFace=["lean","turn","nod"].includes(act.id);
      const needsWrists=["wings","flap"].includes(act.id);
      let fingering;
      if (this.fingers) {
        const hands=window.FingerPiano.locate(frame.hand_points);
        fingering=this.fingers.read(hands,aspect,now);
        Object.assign(this.visual,{hand_points:hands,piano_input:"fingers",finger_depth:fingering.depths});
      }
      const tracked = this.fingers ? fingering.depths[this.visual.target_key]!==null : Boolean(frame.tracked !== false && pts[11] && pts[12] && pts[12].x-pts[11].x>.045
        && (!needsFace || pts[0]) && (!needsWrists || (pts[15] && pts[16]))
        && (act.id!=="wave" || pts[15] || pts[16]));
      const gap = this.lastFrame === null ? 0 : (now-this.lastFrame)/1000;
      const dt = gap > .8 ? 0 : clamp(gap,0,.25);
      this.lastFrame = tracked ? now : null;
      if (!tracked || gap > .8) {
        this.resetTracking();
        if (this.sub === "ready") this.phaseTime=0;
      }
      if (tracked && !this.doneAt && this.sub !== "clear") {
        let geometry={fingering};
        if (!this.fingers) {
          const span=pts[12].x-pts[11].x, center=(pts[11].x+pts[12].x)/2;
          const shoulderY=(pts[11].y+pts[12].y)/2, tilt=(pts[12].y-pts[11].y)/span;
          geometry={points:pts,center,span,shoulderY,tilt};
          if (this.sub==="ready") this.home={center,shoulderY,tilt,nose:pts[0]?(pts[0].x-center)/span:0,depth:pts[0]?(pts[0].y-shoulderY)/span:0};
        }
        if (this.sub === "ready") {
          this.phaseTime+=dt;
          if (this.phaseTime>=1.4) {
            this.sub="play"; this.phaseTime=0;
            if (this.fingers) this.cue="轻弯"+window.FingerPiano.label(this.visual.target_key)+"，再伸直";
          }
        } else {
          this.elapsed+=dt;
          const before=this.count;
          this[act.id](geometry,dt);
          if (act.id!=="wings" && this.count>before) this.score+=50;
          if (this.count>=act.target) {
            this.cleared++;
            this.completed.push({id:act.id,name:act.name,cleared:true});
            this.score+=100;
            this.sub="clear";
            this.clearUntil=now+1150;
          }
          if (this.elapsed>=this.limit) this.doneAt=Date.now();
        }
      }
      const current=this.acts[this.index];
      const cue = this.sub==="clear" ? "动作达成！" : !tracked ? (this.fingers ? "将"+window.FingerPiano.sideName(Number(this.visual.target_key>=5))+"放回画面同侧，张开手指" : "请让需要的部位回到画面，计时已暂停") : this.sub==="ready" ? (this.fingers?"掌心朝镜头，张开五指准备弹奏":"面对镜头回到正中，准备开始") : this.cue;
      return {
        source:"camera",camera_online:true,pose_points:raw,pose_aspect:aspect,
        phase:this.doneAt?"summary":"round",sub:this.sub,act:current.name,act_id:current.id,act_goal:current.goal,
        act_i:this.index,round_len:this.acts.length,round_left:Math.max(0,this.limit-this.elapsed),round_time:this.elapsed,
        cleared:this.cleared,round_score:this.score,round_ended_at:this.doneAt,results:this.completed,
        challenge:{frac:this.count/current.target,count:this.count,target:current.target,unit:current.unit,tracking:tracked,
          cue,text:cue,feedback:this.elapsed<this.feedbackUntil?this.feedback:null,visual:this.visual},
      };
    }
  }
  window.CameraRound=CameraRound;
})();
