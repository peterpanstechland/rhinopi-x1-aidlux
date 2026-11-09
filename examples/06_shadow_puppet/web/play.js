/* The pocket arcade also runs as a static, offline page. */
(() => {
  "use strict";

  const games = {
    rooftop: {
      title: "天台展翅", short: "ROOFTOP", mark: "01", art: "rooftop",
      color: "#d6bcff", target: 5, limit: 25, unit: "节拍",
      brief: "光标进入绿色节拍区时，帮小电展开双翼。",
      hint: "看准绿色区段，按空格或点击「展翅」。越靠近中心，得分越高。",
      pads: [["Space", "展翅"]],
    },
    alpine: {
      title: "雪岭穿梭", short: "ALPINE", mark: "02", art: "alpine",
      color: "#9ef3dc", target: 6, limit: 18, unit: "旗门",
      brief: "提前切到旗门所在雪道，让小电穿过六面旗。",
      hint: "用左右方向键换道，或点击下方雪道。旗门抵达小电脚下时判定。",
      pads: [["1", "左道"], ["2", "中道"], ["3", "右道"]],
    },
    synth: {
      title: "落日合奏", short: "SUNSET SYNTH", mark: "03", art: "synth",
      color: "#ffb29b", target: 8, limit: 25, unit: "音符",
      brief: "跟着亮起的琴键，用八个音符完成落日旋律。",
      hint: "按亮起的 A、S、D、F，或点击对应琴键。按错仍可弹回当前音。",
      pads: [["A", "哆"], ["S", "咪"], ["D", "索"], ["F", "高哆"]],
    },
  };
  const pitches = [261.63, 329.63, 392, 523.25];
  const lanes = ["左道", "中道", "右道"];
  const art = new Map();
  const key = "desk-arcade.history.v1";
  const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  const W = 320, H = 126;
  let dialog, shell, closeButton, session, refs, raf, audio, pressedTimer;
  let history = [];
  let stats = {day: "", runs: 0, best: 0, played: []};

  function el(tag, className, value) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (value !== undefined) node.textContent = value;
    return node;
  }
  function button(className, label, fn) {
    const node = el("button", className, label);
    node.type = "button";
    node.addEventListener("click", fn);
    return node;
  }
  function picture(name) {
    if (!art.has(name)) {
      const image = new Image();
      image.src = "art/" + name + ".png";
      art.set(name, image);
    }
    return art.get(name);
  }
  function inviteScore(id) {
    const params = new URLSearchParams(window.location.search);
    const raw = params.get("beat");
    return params.get("play") === id && /^\d{1,6}$/.test(raw || "") ? Number(raw) : null;
  }
  function number(value, fallback = 0) {
    return Number.isFinite(Number(value)) ? Math.max(0, Math.round(Number(value))) : fallback;
  }
  function cleanResult(value) {
    if (!value || typeof value !== "object") return null;
    const motion = value.mode === "board" || value.mode === "camera";
    if (!motion && !Object.hasOwn(games, value.id)) return null;
    const total = number(value.total);
    const at = typeof value.at === "string" && !Number.isFinite(Number(value.at))
      ? Date.parse(value.at) : Number(value.at);
    return {
      id: motion ? value.mode : value.id,
      title: motion ? String(value.title || "体感回血").slice(0, 40) : games[value.id].title,
      score: number(value.score), cleared: Math.min(number(value.cleared), total),
      total, seconds: number(value.seconds),
      at: Number.isFinite(at) && at > 0 && at <= 8640000000000000 ? at : Date.now(),
      mode: motion ? value.mode : "arcade",
      moves: motion && Array.isArray(value.moves) ? value.moves.filter(n=>typeof n==="string").slice(0,8).map(n=>n.slice(0,10)) : [],
    };
  }
  function addStats(r) {
    const today = new Date().toDateString();
    if (stats.day !== today) { stats.day = today; stats.runs = 0; }
    if (new Date(r.at).toDateString() === today) stats.runs++;
    stats.best = Math.max(stats.best, r.score);
    if (r.mode==="arcade" && !stats.played.includes(r.id)) stats.played.push(r.id);
  }
  function readSaved(raw) {
    const value = JSON.parse(raw || "[]");
    const rows = Array.isArray(value) ? value : value?.history;
    if (!Array.isArray(rows)) return;
    history = rows.map(cleanResult).filter(Boolean).slice(0, 15);
    const saved = value.stats;
    if (saved && Array.isArray(saved.played)) {
      stats = {day:String(saved.day), runs:number(saved.runs), best:number(saved.best),
        played:[...new Set(saved.played.filter(id => Object.hasOwn(games,id)))]};
    } else {
      stats = {day:"", runs:0, best:0, played:[]};
      history.forEach(addStats);
    }
  }
  try { readSaved(localStorage.getItem(key)); }
  catch { /* Storage is optional in private and local-file contexts. */ }

  function recordResult(value) {
    const result = cleanResult(value);
    if (!result) return;
    if (history.some(item => item.id === result.id && item.at === result.at)) return;
    history = [result, ...history].slice(0, 15);
    addStats(result);
    try { localStorage.setItem(key, JSON.stringify({history,stats})); } catch { /* Keep this visit in memory. */ }
    window.dispatchEvent(new CustomEvent("desk:result", {detail: {...result}}));
  }

  function initDialog() {
    if (dialog) return;
    dialog = el("dialog", "dp-dialog");
    dialog.setAttribute("aria-labelledby", "dp-title");
    document.body.append(dialog);
    dialog.addEventListener("cancel", () => teardown());
    dialog.addEventListener("close", () => { if (!dialog.open) teardown(); });
    dialog.addEventListener("click", event => {
      if (event.target !== dialog) return;
      const b = dialog.getBoundingClientRect();
      if (event.clientX < b.left || event.clientX > b.right || event.clientY < b.top || event.clientY > b.bottom) dialog.close();
    });
    dialog.addEventListener("keydown", keyDown);
    document.addEventListener("visibilitychange", () => {
      if (document.hidden && session && ["countdown", "playing"].includes(session.phase)) pause();
    });
  }
  function teardown() {
    cancelAnimationFrame(raf);
    clearTimeout(pressedTimer);
    session = null;
    refs = null;
  }
  function frame(title, tagline, mark, accent) {
    initDialog();
    teardown();
    dialog.replaceChildren();
    dialog.style.setProperty("--dp-accent", accent);
    shell = el("div", "dp-shell");
    const header = el("header", "dp-header");
    const name = el("div", "dp-game-name");
    const text = el("div");
    const h = el("h2", "", title);
    h.id = "dp-title";
    text.append(el("p", "dp-tag", tagline), h);
    const icon = el("span", "dp-cart-mark", mark);
    icon.setAttribute("aria-hidden", "true");
    name.append(icon, text);
    const actions = el("div", "dp-header-actions");
    closeButton = button("dp-icon", "×", () => dialog.close());
    closeButton.setAttribute("aria-label", "关闭并返回大厅");
    closeButton.title = "关闭 · Esc";
    actions.append(closeButton);
    header.append(name, actions);
    shell.append(header);
    dialog.append(shell);
    if (!dialog.open) dialog.showModal();
    return actions;
  }

  function open(id) {
    if (!Object.hasOwn(games, id)) return;
    const config = games[id];
    const actions = frame(config.title, "RE:CHARGE ARCADE / " + config.short, config.mark, config.color);
    picture(config.art);
    picture("bot");
    session = {
      id, config, phase: "brief", elapsed: 0, countdown: 0, last: 0, hits: 0,
      score: 0, combo: 0, flash: 0, good: true, cooldown: 0, cursor: .13,
      zone: .64, lane: 1, laneDraw: 1, gate: 0, gateTime: 0, lastKey: -1,
      gateLanes: [0, 2, 1, 0, 1, 2], notes: [0, 1, 2, 1, 3, 2, 1, 0],
    };
    const pauseButton = button("dp-icon", "Ⅱ", () => {
      if (!session) return;
      if (session.phase === "paused") resume(); else pause();
    });
    pauseButton.hidden = true;
    pauseButton.setAttribute("aria-label", "暂停挑战");
    actions.prepend(pauseButton);
    const stage = el("div", "dp-stage");
    const canvas = el("canvas", "dp-canvas");
    canvas.width = W;
    canvas.height = H;
    canvas.setAttribute("aria-label", config.title + "小游戏画面");
    const counts = el("div", "dp-counts");
    const clock = el("span", "dp-stat");
    const points = el("span", "dp-stat");
    counts.append(clock, points);
    const feedback = el("span", "dp-feedback");
    feedback.setAttribute("role", "status");
    const cover = el("div", "dp-cover");
    stage.append(canvas, counts, feedback, cover);
    const brief = el("div", "dp-brief");
    const head = el("div", "dp-progress-head");
    const objective = el("span");
    const count = el("output");
    head.append(objective, count);
    const meter = el("div", "dp-meter");
    const fill = el("i");
    meter.append(fill);
    const pads = el("div", "dp-pad-row");
    const controls = config.pads.map(([hotkey, label], index) => {
      const pad = button("dp-pad", "", () => input(index));
      pad.append(el("kbd", "", hotkey), document.createTextNode(label));
      pads.append(pad);
      return pad;
    });
    brief.append(head, meter, el("p", "dp-help", config.hint), pads);
    shell.append(stage, brief);
    refs = {canvas, ctx: canvas.getContext("2d"), cover, counts, clock, points, feedback, objective, count, fill, controls, pauseButton};
    canvas.addEventListener("pointerdown", event => {
      if (!session || session.phase !== "playing") return;
      const bounds = canvas.getBoundingClientRect();
      const x = (event.clientX - bounds.left) / bounds.width;
      if (id === "synth" && (event.clientY - bounds.top) / bounds.height * H < 73) return;
      const index = id === "alpine" ? Math.floor(x * 3) : id === "synth" ? Math.floor((x * W - 36) / 62) : 0;
      if (index >= 0 && index < controls.length) input(index);
    });
    const rival = inviteScore(id);
    showCover(rival === null ? "准备出发" : "好友擂台 · " + rival + " 分", config.brief, "开始挑战", start);
    syncUi();
    paint();
    const image = picture(config.art);
    if (!image.complete) image.addEventListener("load", () => { if (session?.id === id) paint(); }, {once:true});
  }

  function showCover(heading, description, label, fn) {
    const cover = refs.cover;
    cover.replaceChildren(el("strong", "dp-cover-title", heading), el("p", "", description));
    cover.hidden = false;
    if (fn) {
      const action = button("dp-primary", label, fn);
      cover.append(action);
      action.focus({preventScroll:true});
    }
  }
  function unlockAudio() {
    if (!window.deskSoundEnabled?.()) return;
    try {
      const Context = window.AudioContext || window.webkitAudioContext;
      if (!Context) return;
      audio ||= new Context();
      if (audio.state === "suspended") audio.resume().catch(() => {});
    } catch { /* Audio can be unavailable on embedded browsers. */ }
  }
  function tone(frequency, duration = .085, shape = "triangle") {
    if (!audio || audio.state !== "running" || !window.deskSoundEnabled?.()) return;
    const osc = audio.createOscillator();
    const gain = audio.createGain();
    osc.type = shape;
    osc.frequency.value = frequency;
    gain.gain.setValueAtTime(.04, audio.currentTime);
    gain.gain.exponentialRampToValueAtTime(.001, audio.currentTime + duration);
    osc.connect(gain).connect(audio.destination);
    osc.start();
    osc.stop(audio.currentTime + duration);
  }
  function start() {
    if (session?.phase !== "brief") return;
    unlockAudio();
    session.phase = "countdown";
    session.countdown = 3;
    showCover("3", "跟上小电的节奏");
    refs.pauseButton.hidden = false;
    refs.pauseButton.focus({preventScroll:true});
    schedule();
  }
  function schedule() {
    cancelAnimationFrame(raf);
    session.last = performance.now();
    raf = requestAnimationFrame(tick);
  }
  function pause() {
    if (!session || !["countdown","playing"].includes(session.phase)) return;
    session.resumePhase = session.phase;
    session.phase = "paused";
    cancelAnimationFrame(raf);
    refs.pauseButton.textContent = "▶";
    refs.pauseButton.setAttribute("aria-label", "继续挑战");
    showCover("已暂停", "回来后从这里继续。", "继续挑战", resume);
    syncUi();
  }
  function resume() {
    if (session?.phase !== "paused") return;
    unlockAudio();
    session.phase = session.resumePhase;
    refs.pauseButton.textContent = "Ⅱ";
    refs.pauseButton.setAttribute("aria-label", "暂停挑战");
    if (session.phase === "countdown") showCover(String(Math.ceil(session.countdown)), "跟上小电的节奏");
    else refs.cover.hidden = true;
    refs.pauseButton.focus({preventScroll:true});
    syncUi();
    schedule();
  }

  function keyDown(event) {
    if (event.altKey || event.ctrlKey || event.metaKey || !session || session.phase !== "playing") return;
    const keyName = event.key.toLowerCase();
    let index = -1;
    if (session.id === "rooftop" && keyName === " ") {
      if (event.target === closeButton || event.target === refs.pauseButton) return;
      index = 0;
    }
    if (session.id === "alpine") {
      if (keyName === "arrowleft") index = Math.max(0, session.lane - 1);
      if (keyName === "arrowright") index = Math.min(2, session.lane + 1);
      if (["1","2","3"].includes(keyName)) index = Number(keyName) - 1;
    }
    if (session.id === "synth") index = ["a","s","d","f"].indexOf(keyName);
    if (index < 0) return;
    event.preventDefault();
    if (!event.repeat) input(index);
  }
  function tell(message) {
    refs.feedback.hidden = !message;
    if (refs.feedback.textContent !== message) refs.feedback.textContent = message;
  }
  function award(success, points, message) {
    const s = session;
    s.good = success;
    s.flash = 1;
    s.combo = success ? s.combo + 1 : 0;
    if (success) {
      s.hits++;
      s.score += points + Math.min(5, s.combo - 1) * 10;
    }
    tell(message);
  }
  function input(index) {
    const s = session;
    if (!s || s.phase !== "playing") return;
    unlockAudio();
    refs.controls.forEach((pad, i) => pad.classList.toggle("dp-pressed", i === index));
    clearTimeout(pressedTimer);
    pressedTimer = setTimeout(() => refs?.controls?.forEach(p => p.classList.remove("dp-pressed")), 145);
    if (s.id === "rooftop" && s.cooldown <= 0) {
      const distance = Math.abs(s.cursor - s.zone);
      const hit = distance <= .125;
      award(hit, distance < .055 ? 120 : 80, hit ? (distance < .055 ? "完美节拍！" : "展翅成功！") : "早了一点？瞄准绿区再试");
      tone(hit ? 523 + 36 * s.combo : 174);
      if (hit) s.zone = [.31,.76,.42,.64][(s.hits - 1) % 4];
      s.cooldown = .26;
    } else if (s.id === "alpine") {
      s.lane = index;
    } else if (s.id === "synth" && s.cooldown <= 0) {
      const hit = index === s.notes[s.hits];
      s.lastKey = index;
      award(hit, 100, hit ? "合拍！" : "再试一次，跟着亮键弹");
      tone(pitches[index], .2);
      s.cooldown = .11;
    }
    if (s.hits >= s.config.target && s.id !== "alpine") return finish();
    syncUi();
    paint();
  }
  function tick(timestamp) {
    if (!session || !dialog.open) return;
    const s = session;
    const dt = Math.min(Math.max((timestamp - s.last) / 1000, 0), .2);
    s.last = timestamp;
    if (s.phase === "countdown") {
      const old = Math.ceil(s.countdown);
      s.countdown -= dt;
      if (s.countdown <= 0) {
        s.phase = "playing";
        refs.cover.hidden = true;
        refs.controls.forEach(p => { p.disabled = false; });
        refs.controls[0].focus({preventScroll:true});
        tone(660, .12);
      } else if (Math.ceil(s.countdown) !== old) {
        refs.cover.firstElementChild.textContent = String(Math.ceil(s.countdown));
        tone(390);
      }
    } else if (s.phase === "playing") {
      s.elapsed += dt;
      s.cooldown = Math.max(0, s.cooldown - dt);
      s.flash = Math.max(0, s.flash - dt * 1.8);
      s.cursor = .5 + .46 * Math.sin(s.elapsed * 2.85 - 1);
      if (s.id === "alpine") {
        s.laneDraw += (s.lane - s.laneDraw) * Math.min(1, dt * 15);
        s.gateTime += dt;
        if (s.gateTime >= 2.85) {
          const hit = s.lane === s.gateLanes[s.gate];
          award(hit, 100, hit ? "穿过旗门！" : "错过旗门，瞄准下一旗");
          tone(hit ? 620 : 192);
          s.gate++;
          s.gateTime -= 2.85;
          if (s.gate >= s.config.target) return finish();
        }
      }
      if (s.elapsed >= s.config.limit) return finish();
    } else return;
    syncUi();
    paint();
    raf = requestAnimationFrame(tick);
  }
  function syncUi() {
    const s = session;
    const r = refs;
    const enabled = s.phase === "playing";
    r.controls.forEach((pad, i) => {
      if (pad.disabled !== !enabled) pad.disabled = !enabled;
      const current = s.id === "alpine" ? s.lane === i : s.id === "synth" && s.notes[s.hits] === i;
      if (current && !pad.hasAttribute("aria-current")) pad.setAttribute("aria-current", "true");
      if (!current && pad.hasAttribute("aria-current")) pad.removeAttribute("aria-current");
    });
    const timeText = "◷ " + Math.ceil(Math.max(0,s.config.limit - s.elapsed)) + " s";
    const scoreText = String(s.score).padStart(4, "0") + " PT";
    if (r.clock.textContent !== timeText) r.clock.textContent = timeText;
    if (r.points.textContent !== scoreText) r.points.textContent = scoreText;
    if (r.counts.hidden !== !enabled) r.counts.hidden = !enabled;
    if (!s.flash) tell("");
    const target = s.id === "alpine" ? "第 " + (s.gate + 1) + " 旗 · " + lanes[s.gateLanes[s.gate]]
      : s.id === "synth" ? "下一个音 · " + s.config.pads[s.notes[s.hits]][0] : "抓住绿色节拍区";
    const label = enabled ? target : "挑战目标 · " + s.config.target + " " + s.config.unit;
    if (r.objective.textContent !== label) r.objective.textContent = label;
    const countText = s.hits + " / " + s.config.target;
    if (r.count.value !== countText) {
      r.count.value = countText;
      r.fill.style.width = (s.hits / s.config.target * 100) + "%";
    }
  }
  function finish() {
    const s = session;
    const result = {id:s.id, title:s.config.title, score:s.score, cleared:s.hits,
      total:s.config.target, seconds:Math.ceil(Math.min(s.elapsed, s.config.limit)), at:Date.now(), mode:"arcade"};
    recordResult(result);
    showResult(result);
  }

  // All game geometry is drawn at cartridge resolution, then enlarged by CSS.
  function box(ctx, color, x, y, width, height) {
    ctx.fillStyle = color;
    ctx.fillRect(Math.round(x), Math.round(y), Math.round(width), Math.round(height));
  }
  function poly(ctx, color, points) {
    ctx.fillStyle = color;
    ctx.beginPath();
    points.forEach(([x,y], index) => index ? ctx.lineTo(x,y) : ctx.moveTo(x,y));
    ctx.closePath();
    ctx.fill();
  }
  function star(ctx, x, y, color, size = 1) {
    box(ctx, color, x-size, y, size*2+1, 1);
    box(ctx, color, x, y-size, 1, size*2+1);
  }
  function bot(ctx, x, y, pose, frame = 0, allowImage = true) {
    ctx.save();
    ctx.translate(Math.round(x), Math.round(y));
    const ink = "#17283a", mint = "#b4ffc6", shade = "#66c6ae", light = "#e1ffe2";
    if (pose === "glide") {
      for (const d of [-1,1]) {
        for (let i = 0; i < 5; i++) {
          const yy = -12 - i * (1 + frame);
          box(ctx, ink, d * (11+i*3)-3, yy-1, 7, 5);
          box(ctx, i%2 ? shade : mint, d * (11+i*3)-2, yy, 5, 3);
        }
      }
    }
    const sprite = allowImage ? picture("bot") : null;
    if (sprite?.complete && sprite.naturalWidth) {
      ctx.drawImage(sprite, -15, -32, 30, 36);
    } else {
      box(ctx, ink, -8, -9, 16, 10);
      box(ctx, shade, -6, -8, 12, 7);
      box(ctx, mint, -5, -7, 8, 5);
      box(ctx, "#f39968", -3, -5, 3, 2);
      box(ctx, ink, -7, 0, 5, 3); box(ctx, ink, 3, 0, 5, 3);
      box(ctx, ink, -12, -23, 24, 13);
      box(ctx, ink, -9, -26, 18, 18);
      box(ctx, shade, -10, -22, 20, 11);
      box(ctx, mint, -8, -24, 16, 14);
      box(ctx, light, -8, -24, 14, 2);
      box(ctx, ink, -8, -21, 16, 8);
      box(ctx, "#edfbd4", -5, -19, 2, 3); box(ctx, "#edfbd4", 3, -19, 2, 3);
      box(ctx, ink, -2, -29, 3, 4); box(ctx, "#ffae69", -3, -31, 4, 3);
      box(ctx, "#7ed5c3", -13, -20, 3, 6); box(ctx, "#7ed5c3", 10, -20, 3, 6);
    }
    if (pose === "ski") {
      box(ctx, "#ffe29c", -14, 2, 12, 2); box(ctx, "#ffe29c", 3, 2, 12, 2);
      box(ctx, "#384453", -12, -9, 2, 11); box(ctx, "#384453", 11, -9, 2, 11);
    }
    ctx.restore();
  }
  function background(ctx, id) {
    const image = picture(id);
    const colors = id === "alpine" ? ["#3f7893","#90d9ca"] : id === "synth" ? ["#5a365d","#e58984"] : ["#292845","#68619a"];
    const grad = ctx.createLinearGradient(0,0,0,H);
    grad.addColorStop(0, colors[0]); grad.addColorStop(1, colors[1]);
    ctx.fillStyle = grad;
    ctx.fillRect(0,0,W,H);
    if (image.complete && image.naturalWidth) {
      if (id === "alpine") {
        ctx.drawImage(image, 0, 0, image.naturalWidth, image.naturalHeight*.26, 0, 0, W, 56);
      } else {
        ctx.drawImage(image, 0, 0, W, id === "rooftop" ? 96 : 91);
      }
    } else {
      for (let i=0;i<20;i++) star(ctx,(i*73+27)%W,(i*13+4)%62,"#d4cece",i%3===0?1:0);
    }
  }
  function rooftop(ctx,s) {
    const image = picture("rooftop");
    if (!image.complete || !image.naturalWidth) {
      box(ctx,"#282c48",0,82,W,13);
      box(ctx,"#9188aa",0,82,W,2);
      bot(ctx,160,79,"glide",s.good ? s.flash : 0);
    }
    box(ctx,"#202538",0,95,W,H-95);
    if (s.flash > .1 && s.good) {
      const spread = reducedMotion ? 6 : 18*(1-s.flash);
      for (const side of [-1,1]) {
        const x = 165 + side*(36+spread);
        for(let i=0;i<3;i++) box(ctx,i%2 ? "#d4fea9" : "#e2ffff",x+side*i*4,57-i*3,4,2);
      }
    }
    for (let i=0;i<6;i++) {
      const x = 120 + (i*23)%80;
      const y = 45 + (i*12)%28;
      if (s.flash>.1 && s.good) star(ctx,x,y - (reducedMotion?0:(1-s.flash)*7),"#e6ffc0");
    }
    const x = 30, width = 260, top = 104;
    box(ctx,"#151826",x-2,top-4,width+4,12);
    box(ctx,"#aaa0c0",x,top+1,width,2);
    for(let i=0;i<=24;i++) box(ctx,"#a89ab5",x+width*i/24,top-1,1,i%3===0?6:3);
    box(ctx,"#82c397",x+width*(s.zone-.125),top-3,width*.25,9);
    box(ctx,"#ccff9e",x+width*(s.zone-.055),top-3,width*.11,9);
    const cursor = x+width*s.cursor;
    box(ctx,"#202236",cursor-3,top-6,7,15);
    box(ctx,"#fff5d2",cursor-1,top-6,3,15);
    poly(ctx,"#ffbd78",[[cursor-4,top-8],[cursor+5,top-8],[cursor,top-4]]);
  }

  // Snow lanes converge at the skyline; gate and rider use the same projection.
  function laneX(lane, depth) { return W/2 + (lane-1)*(12+depth*69); }
  function alpine(ctx,s) {
    const horizon = 45;
    poly(ctx,"#93c4ca",[[0,64],[36,31],[75,53],[111,28],[158,57],[202,37],[243,49],[280,23],[320,55],[320,79],[0,79]]);
    poly(ctx,"#d8f0e0",[[15,48],[36,31],[50,39],[39,38],[34,40],[31,38]]);
    poly(ctx,"#d8f0e0",[[252,42],[280,23],[300,40],[284,32],[278,34],[273,31]]);
    poly(ctx,"#73a4a9",[[0,66],[34,53],[87,63],[125,47],[175,57],[221,47],[320,60],[320,126],[0,126]]);
    poly(ctx,"#c1e1db",[[138,horizon],[182,horizon],[312,H],[8,H]]);
    for(const boundary of [.5,1.5]) {
      const x0 = laneX(boundary,0), x1 = laneX(boundary,1.3);
      poly(ctx,"#91c6cb",[[x0,horizon],[x0+1,horizon],[x1+2,H],[x1,H]]);
    }
    for(let i=0;i<8;i++){
      const side=i%2===0?-1:1, depth=(i*17%54)/60;
      const y = horizon+depth*77, x=160+side*(25+depth*132);
      const u=2+depth*7;
      box(ctx,"#4e797d",x-1,y-4,2,7);
      poly(ctx,"#446e71",[[x,y-u*2.8],[x-u,y],[x+u,y]]);
      poly(ctx,"#92c3b6",[[x,y-u*2.8],[x-u*.65,y-u],[x+u*.55,y-u]]);
    }
    const phase = Math.min(1,s.gateTime/2.85);
    const depth = .08 + .92*phase*phase;
    const gate = s.gateLanes[s.gate] ?? 1;
    const x=laneX(gate,depth), y=horizon+depth*64;
    const rw=3+9*depth, ht=6+14*depth;
    for(const sign of [-1,1]) {
      const px=x+sign*rw;
      box(ctx,"#564459",px,y-ht,Math.max(1,2*depth),ht);
      box(ctx,"#ffae79",px,y-ht,2+depth*4,3+depth*2);
    }
    box(ctx,"#ffe3a2",x-rw,y-ht,2*rw,2);
    const playerX=laneX(s.laneDraw,1);
    box(ctx,"#8bb8bd",playerX-13,111,27,3);
    bot(ctx,playerX,107,"ski");
    if(s.flash>.1 && s.good) star(ctx,playerX+18,72,"#fff4bc",2);
  }
  function synth(ctx,s) {
    box(ctx,"#422e44",0,79,W,47);
    box(ctx,"#f0a993",0,79,W,2);
    const current=s.notes[s.hits];
    // A four-step phrase preview scrolls across the sequencer.
    for(let i=0;i<4;i++) {
      const note=s.notes[s.hits+i];
      const x=103+i*28;
      box(ctx,i===0?"#ffe0a9":"#8b737f",x,6,22,18);
      box(ctx,i===0?"#435246":"#3c3449",x+1,7,20,16);
      if(note!==undefined) {
        ctx.fillStyle=i===0?"#d2ffb7":"#f2cdb8";
        ctx.font="bold 12px monospace";
        ctx.textAlign="center";
        ctx.fillText("ASDF"[note],x+11,19);
      }
    }
    for(let i=0;i<4;i++) {
      const x=36+i*62, active=i===current, down=s.lastKey===i && s.flash>.75;
      box(ctx,"#24283b",x,73,60,41);
      box(ctx,down?"#ffb77d":active?"#baffad":"#d2bac2",x+2,75+Number(down)*2,56,33);
      box(ctx,active?"#649474":"#987f95",x+2,107,56,4);
      if(i!==3) box(ctx,"#383146",x+47,74,17,12);
      ctx.fillStyle="#3d414a";
      ctx.font="bold 14px monospace";
      ctx.textAlign="center";
      ctx.fillText("ASDF"[i],x+29,99);
      if(active) star(ctx,x+29,81,"#546b57",2);
    }
  }
  function paint() {
    const s = session;
    const ctx = refs?.ctx;
    if (!s || !ctx) return;
    ctx.save();
    ctx.imageSmoothingEnabled = false;
    background(ctx,s.id);
    if (s.id === "rooftop") rooftop(ctx,s);
    if (s.id === "alpine") alpine(ctx,s);
    if (s.id === "synth") synth(ctx,s);
    ctx.restore();
  }

  function showResult(value) {
    const r = cleanResult(value);
    if (!r) return;
    const isMotion = r.mode !== "arcade";
    const config = games[r.id];
    const name = isMotion ? "hero" : config.art;
    frame("回血战报", "RE:CHARGE ARCADE / RESULT", "★", "#bdff98");
    const body = el("div", "dp-result");
    const poster = el("div", "dp-poster");
    poster.style.setProperty("--dp-poster-art", "url('art/" + name + ".png')");
    const date = new Date(r.at).toLocaleDateString("zh-CN");
    const big = el("div", "dp-score-row");
    big.append(el("strong", "", String(r.score)), el("small", "", "PT"));
    const full = r.cleared === r.total && r.total > 0;
    poster.append(el("p", "dp-tag", "工位回血 / " + date),
      el("h3", "", r.title + (full ? " · 通关" : " · 战绩")), big,
      el("div", "dp-result-detail", "达成 " + r.cleared + " / " + r.total + "　·　用时 " + r.seconds + " 秒"));
    if (r.moves.length) poster.append(el("p","dp-result-detail","已完成 · "+r.moves.join("、")));
    const actions = el("div", "dp-actions");
    const message = el("p","dp-message");
    message.setAttribute("role","status");
    const rival = r.mode==="board" ? null : inviteScore(r.id);
    if (rival !== null) {
      const difference = r.score - rival;
      message.textContent = difference > 0 ? "超越好友 " + difference + " 分！可以把这张战报发回去。"
        : difference === 0 ? "平分！再来一局试试能否反超。" : "距离好友的成绩还差 " + (-difference) + " 分。";
    }
    const link = el("input","dp-invite-link");
    link.readOnly = true;
    link.hidden = true;
    link.setAttribute("aria-label","邀请链接，选择后可复制");
    const preview = el("figure","dp-export");
    preview.hidden = true;
    const download = button("dp-primary","保存战绩海报",async () => {
      if (!preview.hidden) {
        preview.querySelector("a").click();
        return;
      }
      download.disabled = true;
      link.hidden = true;
      try {
        const blob = await posterBlob(r);
        const data = await new Promise((resolve,reject) => {
          const reader = new FileReader();
          reader.addEventListener("load", () => resolve(reader.result), {once:true});
          reader.addEventListener("error", reject, {once:true});
          reader.readAsDataURL(blob);
        });
        if (!body.isConnected || !dialog.open) return;
        const exported = el("img");
        exported.alt = r.title + "的战绩海报，" + r.score + " 分，完成 " + r.cleared + " / " + r.total + "，用时 " + r.seconds + " 秒";
        exported.width = 800;
        exported.height = 1000;
        exported.src = data;
        const caption = el("figcaption");
        const fileLink = el("a","dp-secondary","下载 PNG");
        fileLink.href = data;
        fileLink.download = "工位回血-" + r.title.replace(/[\\/:*?"<>|]/g,"-") + "-" + r.score + ".png";
        const fileActions = el("div","dp-file-actions");
        fileActions.append(fileLink);
        if (window.File && navigator.canShare && navigator.share) {
          const file = new File([blob], fileLink.download, {type:"image/png"});
          const payload = {files:[file]};
          if (navigator.canShare(payload)) fileActions.append(button("dp-secondary","分享图片",async () => {
            try { await navigator.share(payload); }
            catch (error) { if (error.name !== "AbortError") message.textContent = "可长按海报，或下载 PNG 后分享。"; }
          }));
        }
        caption.append(el("span","","战绩海报 · 800 × 1000"), el("small","","手机可长按图片保存。"), fileActions);
        preview.append(exported, caption);
        preview.hidden = false;
        message.textContent = "海报已生成。";
        fileLink.click();
        preview.scrollIntoView({block:"nearest"});
      } catch {
        message.textContent = "海报生成失败，可以截图保存战报。";
      } finally { download.disabled = false; }
    });
    const invite = button("dp-secondary", "邀请好友", async () => {
      const url = new URL(location.href);
      const shareAddress = ["https:","http:"].includes(url.protocol) && !["localhost","127.0.0.1","[::1]","0.0.0.0"].includes(url.hostname);
      url.hash = "";
      url.search = "";
      if (r.mode!=="board") {
        url.searchParams.set("play", r.id);
        url.searchParams.set("beat", String(r.score));
      }
      const data = {title:"工位回血 · " + r.title,
        text:"我在《工位回血》的「" + r.title + "」拿到了 " + r.score + " 分，完成 " + r.cleared + " / " + r.total + "。换你来挑战！"};
      if (shareAddress) data.url = url.href;
      if (navigator.share) {
        try { await navigator.share(data); message.textContent = "挑战邀请已分享。"; return; }
        catch (error) { if (error.name === "AbortError") return; }
      }
      try {
        await navigator.clipboard.writeText(shareAddress ? url.href : data.text);
        message.textContent = shareAddress ? "已复制挑战链接，发给朋友就能打开。" : "已复制挑战文案，可和战绩海报一起发给朋友。";
      } catch {
        link.value = shareAddress ? url.href : data.text;
        link.setAttribute("aria-label", shareAddress ? "复制挑战链接" : "复制挑战文案");
        link.hidden = false;
        link.focus();
        link.select();
        message.textContent = shareAddress ? "请复制上方链接发给朋友。" : "请复制上方挑战文案，和海报一起发给朋友。";
      }
    });
    actions.append(download, invite, button("dp-secondary",isMotion ? "返回" : "再来一局",
      () => isMotion ? dialog.close() : open(r.id)));
    body.append(poster, actions, link, message, preview);
    shell.append(body);
    download.focus({preventScroll:true});
  }

  function posterCanvas(result, image) {
    const canvas = document.createElement("canvas");
    canvas.width=800;
    canvas.height=1000;
    const ctx = canvas.getContext("2d");
    const full = result.total>0 && result.cleared===result.total;
    const fg="#f7f8dc", mint="#caff9e";
    ctx.imageSmoothingEnabled=false;
    box(ctx,"#172623",0,0,800,1000);
    box(ctx,"#1f3030",26,26,748,948);
    box(ctx,"#8fad95",42,42,716,916);
    box(ctx,"#202c32",44,44,712,912);
    box(ctx,"#334846",46,156,708,310);
    if (image && image.complete && image.naturalWidth) {
      const scale=Math.max(708/image.naturalWidth,310/image.naturalHeight);
      const sw=708/scale, sh=310/scale;
      ctx.drawImage(image,(image.naturalWidth-sw)/2,(image.naturalHeight-sh)/2,sw,sh,46,156,708,310);
    } else {
      ctx.save();
      ctx.translate(380,385);
      ctx.scale(5,5);
      bot(ctx,0,0,"glide",1,false);
      ctx.restore();
      for(let i=0;i<22;i++)star(ctx,80+i*137%640,185+i*31%230,"#b7aee1",2);
    }
    const label=(text,x,y,size,color,weight=700,mono=false)=>{
      ctx.font=weight + " " + size + 'px ' + (mono?'Consolas,monospace':'"Microsoft YaHei",system-ui,sans-serif');
      ctx.fillStyle=color;
      ctx.fillText(text,x,y);
    };
    label("工位回血",74,113,40,fg,850);
    label("RE:CHARGE ARCADE",421,109,27,mint,750,true);
    label(full?"CHALLENGE CLEAR":"ROUND RESULT",76,525,22,mint,750,true);
    ctx.save();
    ctx.beginPath();ctx.rect(73,538,640,80);ctx.clip();
    label(result.title,73,597,55,fg,850);
    ctx.restore();
    ctx.font="900 112px Consolas,monospace";
    const score=String(result.score);
    const scoreWidth=Math.min(528,ctx.measureText(score).width);
    ctx.fillStyle=mint;
    ctx.fillText(score,70,723,528);
    label("PT",87+scoreWidth,714,26,mint,750,true);
    box(ctx,"#5a706a",74,764,650,2);
    label("目标达成",76,809,24,"#b3c6b8");
    label(result.cleared+" / "+result.total,76,864,40,fg,750,true);
    label("用时",422,809,24,"#b3c6b8");
    label(result.seconds+" s",422,864,40,fg,750,true);
    if (result.moves.length) {
      ctx.font='600 19px "Microsoft YaHei",system-ui,sans-serif';
      ctx.fillStyle=mint;
      ctx.fillText(result.moves.join(" · "),76,898,646);
    }
    label(new Date(result.at).toLocaleDateString("zh-CN"),76,925,22,"#b3c6b8",650,true);
    label(result.mode==="arcade"?"街机挑战":"体感挑战",540,925,22,"#b3c6b8");
    return canvas;
  }
  async function posterBlob(result) {
    const name=result.mode==="arcade"?games[result.id].art:"hero";
    const image=picture(name);
    try { await image.decode(); } catch { /* Generated fallback is self contained. */ }
    const encode=canvas=>new Promise((resolve,reject)=>{
      try { canvas.toBlob(blob => blob ? resolve(blob) : reject(new Error("PNG unavailable")), "image/png"); }
      catch(error){reject(error);}
    });
    try { return await encode(posterCanvas(result,image)); }
    catch { return encode(posterCanvas(result,null)); }
  }

  window.DeskPlay = Object.freeze({
    open, showResult, recordResult,
    getHistory: () => history.map(item => ({...item})),
    getStats: () => ({todayRuns: stats.day === new Date().toDateString() ? stats.runs : 0,
      bestScore: stats.best, playedGames: stats.played.length}),
  });
})();
