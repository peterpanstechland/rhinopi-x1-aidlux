/* Browser motion relay. Geometry comes from mirrored landmarks in camera-input.js. */
(() => {
  "use strict";
  const acts = [
    {id:"wings",name:"天台展翅",goal:"双臂平举，撑满 5 秒",target:5,unit:"秒"},
    {id:"lean",name:"雪岭穿梭",goal:"向旗子一侧倾身，碰到 6 面旗",target:6,unit:"面"},
    {id:"piano",name:"落日合奏",goal:"移动手腕选键，向下轻点 8 个黄键",target:8,unit:"键"},
  ];
  const limit = 120;
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const keys = [2,7,3,6,1,8,4,5];
  const sides = [-1,1,1,-1,1,-1];

  class CameraRound {
    constructor() {
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
      this.wrists = [null,null];
      this.visual = {left_fill:0,right_fill:0,gates:[],target_key:keys[0],keys_lit:[]};
      this.cue = "";
    }
    notify(kind, text) {
      this.feedback = {kind,text,seq:++this.feedbackSeq};
      this.feedbackUntil = this.elapsed + 0.75;
    }
    wings(points, span, dt) {
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
    ski(points, center, span, dt) {
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
    piano(points, center, span, dt) {
      const target = keys[this.count];
      this.visual.target_key = target;
      this.visual.piano_input = "wrist";
      const aimed = [];
      const pressed = [];
      for (let i=0; i<2; i++) {
        const wrist=points[15+i], shoulder=points[11+i];
        const y=(wrist.y-shoulder.y)/span;
        const key=clamp(Math.floor(((wrist.x-center)/span/2.6+.5)*10),0,9);
        aimed.push(key);
        if (!this.wrists[i]) this.wrists[i]={rest:y,armed:true};
        const state=this.wrists[i], dip=y-state.rest;
        if (dip < .045) state.armed=true;
        if (state.armed && dip > .14) {
          state.armed=false;
          pressed.push(key);
        }
        if (state.armed && dip < .10) state.rest += (y-state.rest)*Math.min(1,dt*1.8);
      }
      this.visual.aim_keys=aimed;
      this.visual.keys_lit=pressed;
      this.cue=aimed.includes(target) ? "已对准黄键，手腕向下轻点再抬起" : "左右移手，把手腕指示移到黄键后再下压";
      if (pressed.includes(target)) {
        this.count++;
        this.notify("hit","命中黄键 +1");
        this.visual.target_key=keys[this.count] ?? target;
      } else if (pressed.length) this.notify("miss","按错了，先把指示移到黄键");
    }
    update(frame, now) {
      const raw = frame.pose_points || [];
      const aspect = frame.pose_aspect || 1;
      const pts = raw.map(p => p && {x:p[0]*aspect,y:p[1]});
      const act = acts[this.index];
      const required = act.id === "lean" ? [0,11,12] : [0,11,12,15,16];
      const tracked = frame.tracked !== false && required.every(i => pts[i] && Number.isFinite(pts[i].x) && Number.isFinite(pts[i].y))
        && pts[12].x-pts[11].x > .045;
      const gap = this.lastFrame === null ? 0 : (now-this.lastFrame)/1000;
      const dt = gap > .8 ? 0 : clamp(gap,0,.25);
      this.lastFrame = tracked ? now : null;
      if (!tracked || gap > .8) {
        this.wrists=[null,null];
        if (this.sub === "ready") this.phaseTime=0;
      }
      if (tracked && !this.doneAt) {
        const center=(pts[11].x+pts[12].x)/2, span=pts[12].x-pts[11].x;
        if (this.sub === "ready") {
          this.home={center,nose:(pts[0].x-center)/span};
          this.phaseTime+=dt;
          if (this.phaseTime>=1.4) { this.sub="play"; this.phaseTime=0; }
        } else if (this.sub === "clear") {
          this.phaseTime+=dt;
          if (this.phaseTime>=1.15) {
            if (this.index===acts.length-1) this.doneAt=Date.now();
            else { this.index++; this.sub="ready"; this.phaseTime=0; this.resetAction(); }
          }
        } else {
          this.elapsed+=dt;
          const before=this.count;
          if (act.id==="wings") this.wings(pts,span,dt);
          if (act.id==="lean") this.ski(pts,center,span,dt);
          if (act.id==="piano") this.piano(pts,center,span,dt);
          if (act.id!=="wings" && this.count>before) this.score+=50;
          if (this.count>=act.target) {
            this.cleared++;
            this.completed.push({name:act.name,cleared:true});
            this.score+=100;
            this.sub="clear";
            this.phaseTime=0;
          } else if (this.elapsed>=limit) this.doneAt=Date.now();
        }
      }
      const current=acts[this.index];
      const cue = !tracked ? "请让需要的部位回到画面，计时已暂停" : this.sub==="ready" ? "面对镜头回到正中，准备开始" : this.sub==="clear" ? "动作达成！" : this.cue;
      return {
        source:"camera",camera_online:true,pose_points:raw,pose_aspect:aspect,
        phase:this.doneAt?"summary":"round",sub:this.sub,act:current.name,act_id:current.id,act_goal:current.goal,
        act_i:this.index,round_len:acts.length,round_left:Math.max(0,limit-this.elapsed),round_time:this.elapsed,
        cleared:this.cleared,round_score:this.score,round_ended_at:this.doneAt,results:this.completed,
        challenge:{frac:this.count/current.target,count:this.count,target:current.target,unit:current.unit,tracking:tracked,
          cue,text:cue,feedback:this.elapsed<this.feedbackUntil?this.feedback:null,visual:this.visual},
      };
    }
  }
  window.CameraRound=CameraRound;
})();
