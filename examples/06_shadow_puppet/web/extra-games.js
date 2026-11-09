/* Keyboard and touch controls for five of the original motion challenges. */
(() => {
  "use strict";
  const games = {
    flap: {
      title:"老鹰起飞", short:"EAGLE FLIGHT", mark:"02", art:"flap", color:"#f2d795",
      target:8, limit:30, unit:"次扇翅",
      brief:"把双翼抬起再压下，扇动八次飞到山旗。",
      hint:"依次按 ↑、↓ 或点「抬翼」「压翼」。完成一对动作就升高一级。",
      pads:[["↑","抬翼"],["↓","压翼"]], keys:["arrowup","arrowdown"],
    },
    wave: {
      title:"月台挥手", short:"PLATFORM WAVE", mark:"03", art:"wave", color:"#8ee0cf",
      target:10, limit:25, unit:"位乘客",
      brief:"举起小电的手，左右交替挥动，送别十位乘客。",
      hint:"按 ←、→ 或点左右挥手。看腕带的指向，每次挥到另一侧就送走一位。",
      pads:[["←","向左挥"],["→","向右挥"]], keys:["arrowleft","arrowright"],
    },
    hands_up: {
      title:"仙人掌跳跃", short:"CACTUS RUN", mark:"06", art:"hands_up", color:"#f8b58c",
      target:5, limit:30, unit:"个障碍",
      brief:"让仙人掌靠近脚边再起跳，越过五个就通关。",
      hint:"按空格或点「起跳」。小电落地后才能开始下一跳，仙人掌经过时双脚要高过尖刺。",
      pads:[["Space","起跳"]], keys:[" "],
    },
    turn: {
      title:"左右转头", short:"SIGNAL LOOKOUT", mark:"07", art:"turn", color:"#afc7ff",
      target:6, limit:35, unit:"次转头",
      brief:"向左和向右各看三次，回到正中时点亮侧边信号灯。",
      hint:"用 ← 或 → 转头，再按 ↓ 回正，也可以点击三个方向。每侧需要三次完整往返。",
      pads:[["←","左转"],["↓","回正"],["→","右转"]], keys:["arrowleft","arrowdown","arrowright"],
    },
    nod: {
      title:"节拍点头", short:"BEACON NOD", mark:"08", art:"nod", color:"#ffb4cb",
      target:6, limit:30, unit:"次点头",
      brief:"低头、抬头，用六次完整点头逐级点亮灯塔。",
      hint:"按 ↓ 或点「低头」，等灯芯变绿再按 ↑ 或点「抬头」。回到正前方时记一次。",
      pads:[["↓","低头"],["↑","抬头"]], keys:["arrowdown","arrowup"],
    },
  };
  const JUMP_DURATION = .92;
  const CROSSING = 2.15;
  const NEXT_CACTUS = 2.75;

  function init() {
    return {raised:false, side:0, left:0, right:0, down:false, downAt:0, lastWave:1,
      jumpTime:JUMP_DURATION, obstacleTime:0, judged:false, stage:null};
  }
  function jumpHeight(s) {
    return 51*Math.sin(Math.PI*Math.min(1,s.extra.jumpTime/JUMP_DURATION));
  }
  function wanted(s) {
    const e=s.extra;
    switch (s.id) {
      case "flap": return e.raised ? 1 : 0;
      case "wave": return 1-e.lastWave;
      case "nod": return e.down ? (s.elapsed-e.downAt>=.35 ? 1 : -1) : 0;
      case "turn": return e.side ? 1 : e.left<=e.right ? 0 : 2;
      default: return -1;
    }
  }
  function objective(s) {
    const e=s.extra;
    switch (s.id) {
      case "turn": return "左 " + e.left + "/3 · 右 " + e.right + "/3 · " + (e.side ? "回正点灯" : "转向未满的一侧");
      case "nod": return !e.down ? "向下点头给灯芯充能" : s.elapsed-e.downAt<.35 ? "保持片刻，等待绿灯" : "绿灯亮起 · 抬头";
      case "hands_up":
        if (e.jumpTime<JUMP_DURATION) return "腾空中";
        return e.obstacleTime<CROSSING-.7 || e.judged ? "等待仙人掌靠近" : "现在起跳";
      default: return "下一步 · " + s.config.pads[wanted(s)][1];
    }
  }
  function press(s, i, award, tone) {
    const e=s.extra;
    switch (s.id) {
      case "flap":
        if (i===0) { if (!e.raised) tone(410); e.raised=true; }
        else if (e.raised) {
          e.raised=false;
          award(true,100,"向上飞了一层！");
          tone(530+s.hits*24);
        } else award(false,0,"先抬翼，再压下");
        break;
      case "wave":
        if (i!==e.lastWave) {
          e.lastWave=i;
          award(true,90,"再见！送走一位乘客");
          tone(i ? 520 : 420);
        } else award(false,0,"向另一边挥手");
        break;
      case "turn":
        if (i===1 && e.side!==0) {
          const direction=e.side<0?"left":"right";
          if (e[direction]<3) {
            e[direction]++;
            award(true,100,(e.side<0?"左":"右")+"侧信号灯点亮");
            tone(430+e[direction]*50);
          } else award(false,0,"这一侧已满，转向另一侧");
          e.side=0;
        } else if (i!==1 && !e.side) {
          e.side=i===0?-1:1;
        } else if (i!==1 && e.side) award(false,0,"先回正，再转向");
        break;
      case "nod":
        if (i===0 && !e.down) { e.down=true; e.downAt=s.elapsed; }
        else if (e.down) {
          if (i!==1) break;
          const ready=s.elapsed-e.downAt>=.35;
          award(ready,100,ready?"回正，点亮一级！":"抬早了，绿灯亮起再抬头");
          tone(ready?425+s.hits*45:175);
          e.down=false;
        }
        break;
      case "hands_up":
        if (e.jumpTime>=JUMP_DURATION) {
          e.jumpTime=0;
          tone(635,.12);
        }
        break;
    }
  }
  function tick(s, dt, award, tone) {
    if (s.id!=="hands_up") return;
    const e=s.extra, before=e.obstacleTime;
    e.obstacleTime+=dt;
    const jumpBefore=e.jumpTime;
    e.jumpTime=Math.min(JUMP_DURATION,e.jumpTime+dt);
    if (!e.judged && e.obstacleTime>=CROSSING) {
      e.judged=true;
      // Sample the jump at the crossing instant, including on slow displays.
      const t=Math.min(JUMP_DURATION,jumpBefore+CROSSING-before);
      const passed=51*Math.sin(Math.PI*t/JUMP_DURATION)>25;
      award(passed,120,passed?"越过仙人掌！":"碰到尖刺，试试下一株");
      tone(passed?640:165);
    }
    if (e.obstacleTime>=NEXT_CACTUS) {
      e.obstacleTime-=NEXT_CACTUS;
      e.judged=false;
    }
  }
  function draw(ctx,s) {
    const e=s.extra;
    if (!e.stage) e.stage=document.createElement("canvas");
    const points=Array(25).fill(null);
    points[0]=[.5,.32];
    points[11]=[.42,.51]; points[12]=[.58,.51];
    points[13]=[.40,.59]; points[14]=[.60,.59];
    points[15]=[.41,.67]; points[16]=[.59,.67];
    const visual={left_got:e.left,right_got:e.right};
    if (s.id==="flap") {
      points[13]=[.34,e.raised?.44:.54]; points[14]=[.66,e.raised?.44:.54];
      points[15]=[.24,e.raised?.36:.60]; points[16]=[.76,e.raised?.36:.60];
      visual.alt=56*s.hits/s.config.target;
    } else if (s.id==="wave") {
      points[14]=[.63,.45]; points[16]=[e.lastWave?.71:.57,.27];
    } else if (s.id==="turn") {
      points[0][0]+=e.side*.12;
    } else if (s.id==="nod") {
      points[0][1]=e.down?.51:.28;
    } else if (s.id==="hands_up") {
      visual.avatar_dy=-jumpHeight(s);
      visual.obs=160+(CROSSING-e.obstacleTime)*81;
    }
    window.MotionStage.paint(e.stage,{phase:"round",sub:"play",act_id:s.id,
      pose_aspect:16/9,pose_points:points,challenge:{frac:s.hits/s.config.target,visual}});
    // Keep the stage proportions while trimming its decorative skyline.
    ctx.drawImage(e.stage,0,52,384,151,0,0,320,126);
    if (s.id==="nod") {
      const fraction=e.down?Math.min(1,(s.elapsed-e.downAt)/.35):0;
      ctx.fillStyle="#262638";
      ctx.fillRect(139,8,42,9);
      for(let i=0;i<6;i++) {
        ctx.fillStyle=i<Math.floor(fraction*6)?(fraction>=1?"#b5ffc2":"#ffc793"):"#66607b";
        ctx.fillRect(142+i*6,10,4,5);
      }
    }
  }
  window.ExtraCartridges = {games,init,press,tick,objective,wanted,draw};
})();
