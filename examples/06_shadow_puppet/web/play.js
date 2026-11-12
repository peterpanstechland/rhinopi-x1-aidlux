/* The pocket arcade also runs as a static, offline page. */
(() => {
  "use strict";

  const extra = window.ExtraCartridges;
  const games = {
    rooftop: {
      title: "天台展翅", short: "ROOFTOP", mark: "01", art: "rooftop",
      color: "#d6bcff", target: 5, limit: 25, unit: "节拍",
      brief: "光标进入绿色节拍区时，帮小电展开双翼。",
      hint: "光标进入绿区就按空格或点「展翅」。越靠近浅绿中心，得分越高。",
      pads: [["Space", "展翅"]],
    },
    alpine: {
      title: "雪岭穿梭", short: "ALPINE", mark: "04", art: "alpine",
      color: "#9ef3dc", target: 6, limit: 18, unit: "旗门",
      brief: "提前切到旗门所在雪道，让小电穿过六面旗。",
      hint: "用 ← → 换道，或点下方雪道。让小电站稳在下一面旗门所在的道上。",
      pads: [["1", "左道"], ["2", "中道"], ["3", "右道"]],
    },
    synth: {
      title: "落日合奏", short: "SUNSET SYNTH", mark: "05", art: "synth",
      color: "#ffb29b", target: 8, limit: 25, unit: "音符",
      brief: "跟着亮起的琴键，用八个音符完成落日旋律。",
      hint: "按亮起的 A、S、D、F，或点击对应琴键。按错仍可弹回当前音。",
      pads: [["A", "哆"], ["S", "咪"], ["D", "索"], ["F", "高哆"]],
    },
    ...extra.games,
  };
  const motionToCartridge = Object.freeze({wings:"rooftop",flap:"flap",wave:"wave",
    lean:"alpine",piano:"synth",hands_up:"hands_up",turn:"turn",nod:"nod"});
  const catalog = Object.freeze(Object.entries(motionToCartridge).map(([moveId,id]) => Object.freeze({
    id,moveId,title:games[id].title,art:games[id].art,short:games[id].short,
    pads:games[id].pads.map(pair=>pair.slice()),
  })));
  const lanes = ["左道", "中道", "右道"];
  const art = new Map();
  const key = "desk-arcade.history.v1";
  const roundPrefix = "desk-arcade.round.v2/";
  const tabId = globalThis.crypto?.randomUUID?.() || Math.random().toString(36).slice(2);
  const unsaved = new Map();
  let legacySnapshot = null, storedRounds = new Map();
  const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  const W = 320, H = 126;
  let dialog, shell, closeButton, session, refs, raf, arcadeScene;
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
  function inviteScore(id, course) {
    const params = new URLSearchParams(window.location.search);
    const raw = params.get("beat");
    if (!/^\d{1,6}$/.test(raw || "")) return null;
    if (id.startsWith("camera:")) {
      return params.get("play")==="camera" && params.get("move")===id.slice(7) ? Number(raw) : null;
    }
    if (id==="camera" && (course!==8 || params.get("course")!=="8" || params.has("move"))) return null;
    return params.get("play") === id ? Number(raw) : null;
  }
  function cameraMove(result) {
    const id=String(result.id);
    const move=id.startsWith("camera:") ? id.slice(7) : "";
    return result.mode==="camera" && Object.hasOwn(motionToCartridge,move) ? move : "";
  }
  function resultArt(result) {
    const move=cameraMove(result);
    return move ? motionToCartridge[move] : result.mode==="arcade" ? games[result.id].art : "hero";
  }
  function number(value, fallback = 0) {
    return Number.isFinite(Number(value)) ? Math.max(0, Math.round(Number(value))) : fallback;
  }
  function cleanResult(value) {
    if (!value || typeof value !== "object") return null;
    const motion = value.mode === "board" || value.mode === "camera";
    if (!motion && !Object.hasOwn(games, value.id)) return null;
    const move = cameraMove(value);
    const visited = motion && Array.isArray(value.playedIds)
      ? value.playedIds.filter(id => typeof id==="string" && Object.hasOwn(motionToCartridge,id)) : [];
    if (move) visited.push(move);
    const total = number(value.total);
    const at = typeof value.at === "string" && !Number.isFinite(Number(value.at))
      ? Date.parse(value.at) : Number(value.at);
    return {
      id: move ? "camera:"+move : motion ? value.mode : value.id,
      title: motion ? String(value.title || "体感回血").slice(0, 40) : games[value.id].title,
      score: number(value.score), cleared: Math.min(number(value.cleared), total),
      total, seconds: number(value.seconds),
      at: Number.isFinite(at) && at > 0 && at <= 8640000000000000 ? at : Date.now(),
      mode: motion ? value.mode : "arcade",
      tab: typeof value.tab === "string" ? value.tab.slice(0,64) : undefined,
      course: value.mode==="camera" && !move && value.course===8 ? 8 : undefined,
      playedIds: [...new Set(visited)],
      moves: motion && Array.isArray(value.moves) ? value.moves.filter(n=>typeof n==="string").slice(0,8).map(n=>n.slice(0,10)) : [],
    };
  }
  function addStats(r) {
    const today = new Date().toDateString();
    if (stats.day !== today) { stats.day = today; stats.runs = 0; }
    if (new Date(r.at).toDateString() === today) stats.runs++;
    stats.best = Math.max(stats.best, r.score);
    for (const id of playedGames(r)) if (!stats.played.includes(id)) stats.played.push(id);
  }
  function playedGames(r) {
    return r.mode==="arcade" ? [r.id] : r.playedIds.map(id=>motionToCartridge[id]);
  }
  function roundKey(r) {
    return roundPrefix + r.id + "/" + r.at + "/" + (r.tab || "");
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
  function reloadResults(prune=false) {
    let store;
    try {
      store = localStorage;
      const current = new Map();
      for (const id of Object.keys(store)) {
        if (!id.startsWith(roundPrefix)) continue;
        try {
          const row = cleanResult(JSON.parse(store.getItem(id)));
          if (row && roundKey(row)===id) current.set(id,row);
        } catch { /* Ignore this damaged round and keep the others. */ }
      }
      legacySnapshot = store.getItem(key);
      storedRounds = current;
    } catch { /* Keep the last readable snapshot when storage becomes unavailable. */ }
    const rounds = new Map([...storedRounds,...unsaved]);
    history = [];
    stats = {day:"", runs:0, best:0, played:[]};
    try { readSaved(legacySnapshot); } catch { /* Ignore an unreadable legacy snapshot. */ }
    // Old installs keep their fifteen visible rows and their full lifetime totals.
    // A mixed-version tab may also have published a board round to the old snapshot.
    const legacy = new Set(history.map(r=>r.id + "/" + r.at));
    const rows = [...rounds.values()].filter(r=>!legacy.has(r.id + "/" + r.at));
    rows.forEach(addStats);
    history = history.concat(rows).sort((a,b)=>b.at-a.at || roundKey(a).localeCompare(roundKey(b))).slice(0,15);
    if (!prune) return;

    // Retain this day's count, the recent list, and a witness for the lifetime
    // best and each played cartridge. All other older rows can be discarded.
    const keep = new Set(history.map(roundKey));
    const played = new Set();
    const midnight = new Date().setHours(0,0,0,0);
    rows.sort((a,b)=>b.score-a.score || b.at-a.at || roundKey(a).localeCompare(roundKey(b)));
    for (const [i,row] of rows.entries()) {
      const ids = playedGames(row);
      if (!i || row.at>=midnight || ids.some(id=>!played.has(id))) keep.add(roundKey(row));
      ids.forEach(id=>played.add(id));
    }
    for (const id of rounds.keys()) {
      if (keep.has(id)) continue;
      try { store?.removeItem(id); storedRounds.delete(id); } catch { /* Retry on the next completed round. */ }
      unsaved.delete(id);
    }
    if (store) for (const [id,row] of unsaved) {
      try {
        store.setItem(id,JSON.stringify(row));
        storedRounds.set(id,row);
        unsaved.delete(id);
      } catch { break; }
    }
  }
  reloadResults(true);
  window.addEventListener("storage", event => {
    if (event.key!==null && event.key!==key && !event.key.startsWith(roundPrefix)) return;
    reloadResults();
    window.dispatchEvent(new CustomEvent("desk:result"));
  });

  function recordResult(value) {
    const result = cleanResult(value);
    if (!result) return;
    if (history.some(item => !item.tab && item.id===result.id && item.at===result.at)) return;
    // Two local games may finish in the same millisecond. Multiple viewers of
    // a board are seeing one shared round, identified by its ending timestamp.
    if (result.mode!=="board" && !result.tab) result.tab = tabId;
    const id = roundKey(result);
    if (unsaved.has(id)) return;
    try {
      if (localStorage.getItem(id)!==null) return;
      localStorage.setItem(id,JSON.stringify(result));
    } catch { unsaved.set(id,result); }
    reloadResults(true);
    window.dispatchEvent(new CustomEvent("desk:result", {detail: {...result}}));
  }

  function initDialog() {
    if (dialog) return;
    dialog = el("dialog", "dp-dialog");
    dialog.setAttribute("aria-labelledby", "dp-title");
    document.body.append(dialog);
    dialog.addEventListener("cancel", event => {
      if (["countdown","playing"].includes(session?.phase)) {
        event.preventDefault();
        pause();
      }
    });
    dialog.addEventListener("close", () => { if (!dialog.open) teardown(); });
    dialog.addEventListener("click", event => {
      if (event.target !== dialog) return;
      const b = dialog.getBoundingClientRect();
      if (event.clientX < b.left || event.clientX > b.right || event.clientY < b.top || event.clientY > b.bottom) {
        if (["countdown","playing"].includes(session?.phase)) pause();
        else dialog.close();
      }
    });
    dialog.addEventListener("keydown", keyDown);
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) pause();
    });
    window.addEventListener("blur",pause);
  }
  function teardown(restoreAudio = true) {
    cancelAnimationFrame(raf);
    session = null;
    refs = null;
    if (restoreAudio && arcadeScene) {
      arcadeScene = null;
      if (window.DeskAudio?.restoreScene) window.DeskAudio.restoreScene();
      else window.DeskAudio?.scene("lobby");
    }
  }
  function frame(title, tagline, mark, accent, keepScene = false) {
    initDialog();
    teardown(!keepScene);
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
    closeButton.title = "关闭并返回大厅";
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
    const moveId = catalog.find(game => game.id === id).moveId;
    const actions = frame(config.title, config.short, config.mark, config.color, true);
    shell.classList.add("dp-console");
    arcadeScene = moveId;
    window.DeskAudio?.scene(moveId);
    picture(config.art);
    session = {
      id, moveId, config, avatar: extra.newAvatar(), pressAt: -10, phase: "brief", elapsed: 0, countdown: 0, last: 0, hits: 0,
      score: 0, combo: 0, flash: 0, good: true, cooldown: 0, cursor: .13, practice: false,
      zone: .64, lane: 1, laneDraw: 1, gate: 0, gateTime: 0, lastKey: -1,
      gateLanes: [0, 2, 1, 0, 1, 2], notes: [0, 1, 2, 1, 3, 2, 1, 0],
    };
    if (Object.hasOwn(extra.games,id)) session.extra = extra.init();
    extra.animate(session,null);
    const pauseButton = button("dp-icon", "Ⅱ", () => {
      if (!session) return;
      if (session.phase === "paused") resume(); else pause();
    });
    pauseButton.hidden = true;
    pauseButton.setAttribute("aria-label", "暂停挑战");
    pauseButton.title = "P 暂停或继续 · Esc 暂停";
    pauseButton.setAttribute("aria-keyshortcuts","P");
    actions.prepend(pauseButton);
    const stage = el("div", "dp-stage");
    const canvas = el("canvas", "dp-canvas");
    canvas.width = W;
    canvas.height = H;
    canvas.setAttribute("aria-label", config.title + "小游戏画面");
    canvas.tabIndex = -1;
    const counts = el("div", "dp-counts");
    const clock = el("span", "dp-stat");
    const points = el("span", "dp-stat");
    const phaseLabel=el("span","dp-phase-label");
    counts.append(phaseLabel, clock, points);
    const feedback = el("span", "dp-feedback");
    feedback.setAttribute("role", "status");
    const cover = el("div", "dp-cover");
    stage.append(canvas, cover);
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
      const pad = el("button", "dp-pad");
      pad.type="button";
      // Keyboard activation and assistive technology issue a click without a pointer.
      pad.addEventListener("click",event=>{if(event.detail===0) input(index);});
      pad.addEventListener("animationend",()=>pad.classList.remove("dp-pressed"));
      pad.append(el("kbd", "", hotkey==="Space" ? "空格" : hotkey), el("span","",label));
      pads.append(pad);
      return pad;
    });
    const help=el("p","dp-help",config.hint);
    const commands=el("div","dp-commands");
    const launch=button("dp-primary","开始挑战",start);
    const rehearse=button("dp-secondary","先试按键",practice);
    commands.append(launch,rehearse);
    const status=el("div","dp-input-status");
    status.append(feedback);
    brief.append(head, meter, help, pads, status, commands);
    shell.append(counts, stage, brief);
    refs = {canvas, ctx: canvas.getContext("2d"), cover, counts, clock, points, feedback, objective, count, fill, controls, pauseButton, phaseLabel, help, commands, launch, rehearse, status};
    bindPads(pads,controls);
    const contacts=new Map();
    function playAt(event) {
      if (session?.phase !== "playing") return;
      const bounds = canvas.getBoundingClientRect();
      const x = (event.clientX - bounds.left) / bounds.width;
      const y = (event.clientY - bounds.top) / bounds.height * H;
      if (x<0 || x>=1 || y<0 || y>H || (id==="synth" && (y<73 || y>114))) {
        contacts.set(event.pointerId,-1);
        return;
      }
      let index = 0;
      if (session.extra || id==="alpine") index = Math.min(controls.length-1, Math.floor(x * controls.length));
      if (id==="synth") index = Math.floor((x * W - 36) / 62);
      if (index >= 0 && index < controls.length && contacts.get(event.pointerId)!==index) input(index);
      contacts.set(event.pointerId,index);
    }
    canvas.addEventListener("pointerdown", event => {
      if(session?.phase!=="playing" || event.button!==0) return;
      event.preventDefault();
      canvas.setPointerCapture(event.pointerId);
      playAt(event);
    });
    canvas.addEventListener("pointermove",event=>{
      if(contacts.has(event.pointerId) && (id==="synth" || id==="alpine")) playAt(event);
    });
    canvas.addEventListener("lostpointercapture",event=>contacts.delete(event.pointerId));
    canvas.addEventListener("pointerup",event=>contacts.delete(event.pointerId));
    canvas.addEventListener("pointercancel",event=>contacts.delete(event.pointerId));
    cover.hidden=true;
    syncUi();
    paint();
    launch.focus({preventScroll:true});
    const image = picture(config.art);
    if (!image.complete) image.addEventListener("load", () => { if (session?.id === id) paint(); }, {once:true});
  }

  function bindPads(row, controls) {
    const pointers=new Map();
    function hit(event) {
      const pad=document.elementFromPoint(event.clientX,event.clientY)?.closest(".dp-pad");
      if (pointers.get(event.pointerId)===pad) return;
      pointers.set(event.pointerId,pad);
      const index=controls.indexOf(pad);
      if(index>=0) input(index);
    }
    row.addEventListener("pointerdown",event=>{
      if(session?.phase!=="playing" || event.button!==0 || !event.target.closest(".dp-pad")) return;
      // A final press can focus a new action before the browser's default mousedown.
      event.preventDefault();
      row.setPointerCapture(event.pointerId);
      hit(event);
    });
    row.addEventListener("pointermove",event=>{
      if(!pointers.has(event.pointerId) || session?.phase!=="playing") return;
      if(session.id==="synth" || session.id==="alpine") hit(event);
    });
    row.addEventListener("lostpointercapture",event=>pointers.delete(event.pointerId));
    row.addEventListener("pointercancel",event=>pointers.delete(event.pointerId));
    row.addEventListener("pointerup",event=>pointers.delete(event.pointerId));
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
  function start() {
    if (!session) return;
    if (session.practice) open(session.id);
    if (session.phase !== "brief") return;
    window.DeskAudio?.cue("start");
    session.phase = "countdown";
    session.countdown = 3;
    showCover("3", "跟上小电的节奏");
    refs.pauseButton.hidden = false;
    refs.canvas.focus({preventScroll:true});
    syncUi();
    schedule();
  }
  function practice() {
    if(session?.phase!=="brief") return;
    session.practice=true;
    session.phase="playing";
    refs.pauseButton.hidden=false;
    refs.canvas.focus({preventScroll:true});
    syncUi();
    paint();
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
    window.DeskAudio?.scene(null);
    cancelAnimationFrame(raf);
    refs.pauseButton.textContent = "▶";
    refs.pauseButton.setAttribute("aria-label", "继续挑战");
    showCover("已暂停", "回来后从这里继续。", "继续挑战", resume);
    syncUi();
  }
  function resume() {
    if (session?.phase !== "paused") return;
    session.phase = session.resumePhase;
    window.DeskAudio?.scene(arcadeScene);
    refs.pauseButton.textContent = "Ⅱ";
    refs.pauseButton.setAttribute("aria-label", "暂停挑战");
    if (session.phase === "countdown") showCover(String(Math.ceil(session.countdown)), "跟上小电的节奏");
    else refs.cover.hidden = true;
    refs.canvas.focus({preventScroll:true});
    syncUi();
    schedule();
  }

  function keyDown(event) {
    if (event.altKey || event.ctrlKey || event.metaKey || event.isComposing || !session) return;
    const keyName = event.key.toLowerCase();
    if (keyName==="p" && ["playing","countdown","paused"].includes(session.phase)) {
      event.preventDefault();
      if (!event.repeat) { if(session.phase==="paused") resume(); else pause(); }
      return;
    }
    if (session.phase !== "playing") return;
    if (keyName===" " && event.target.closest("button:not(.dp-pad)")) return;
    let index = -1;
    if (session.id === "rooftop" && keyName === " ") {
      index = 0;
    }
    if (session.id === "alpine") {
      if (keyName === "arrowleft") index = Math.max(0, session.lane - 1);
      if (keyName === "arrowright") index = Math.min(2, session.lane + 1);
      if (["1","2","3"].includes(keyName)) index = Number(keyName) - 1;
    }
    if (session.id === "synth") index = ["a","s","d","f"].indexOf(keyName);
    if (session.extra) {
      index=session.config.keys.indexOf(keyName);
    }
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
    if (success && s.id === "synth") window.DeskAudio?.note(s.lastKey);
    else window.DeskAudio?.cue(success ? "hit" : "miss");
    refs.feedback.dataset.kind=success ? "hit" : "miss";
    tell(success && !s.practice ? message + "　+" + (points+Math.min(5,s.combo-1)*10) : message);
  }
  function input(index) {
    const s = session;
    if (!s || s.phase !== "playing") return;
    const pressed=refs.controls[index];
    if(!pressed) return;
    pressed.classList.remove("dp-pressed");
    void pressed.offsetWidth;
    pressed.classList.add("dp-pressed");
    if (s.extra) {
      extra.press(s,index,award);
    } else if (s.id === "rooftop" && s.cooldown <= 0) {
      s.pressAt = s.elapsed;
      const distance = Math.abs(s.cursor - s.zone);
      const hit = distance <= .125;
      award(hit, distance < .055 ? 120 : 80, hit ? (distance < .055 ? "完美节拍！" : "展翅成功！") : "光标在绿区外，再试一次");
      if (hit) s.zone = [.31,.76,.42,.64][(s.hits - 1) % 4];
      s.cooldown = .26;
    } else if (s.id === "alpine") {
      s.lane = index;
    } else if (s.id === "synth") {
      const hit = index === s.notes[s.hits];
      s.lastKey = index;
      s.pressAt = s.elapsed;
      award(hit, 100, hit ? "合拍！" : "再试一次，跟着亮键弹");
    }
    if ((s.practice && s.hits>0) || (s.hits >= s.config.target && s.id !== "alpine")) return finish();
    extra.animate(s,1/60);
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
        refs.canvas.focus({preventScroll:true});
      } else if (Math.ceil(s.countdown) !== old) {
        refs.cover.firstElementChild.textContent = String(Math.ceil(s.countdown));
      }
    } else if (s.phase === "playing") {
      s.elapsed += dt;
      s.cooldown = Math.max(0, s.cooldown - dt);
      s.flash = Math.max(0, s.flash - dt * 1.8);
      s.cursor = .5 + .46 * Math.sin(s.elapsed * 2.85 - 1);
      if (s.extra) {
        extra.tick(s,dt,award);
        if (s.hits>=(s.practice ? 1 : s.config.target)) return finish();
      }
      if (s.id === "alpine") {
        s.laneDraw += (s.lane - s.laneDraw) * Math.min(1, dt * 15);
        s.gateTime += dt;
        if (s.gateTime >= 2.85) {
          const hit = s.lane === s.gateLanes[s.gate];
          award(hit, 100, hit ? "穿过旗门！" : "错过旗门，瞄准下一旗");
          s.gate++;
          s.gateTime -= 2.85;
          if (s.practice) {
            if (hit) return finish();
            s.gate%=s.gateLanes.length;
          } else if (s.gate >= s.config.target) return finish();
        }
      }
      if (!s.practice && s.elapsed >= s.config.limit) return finish();
      extra.animate(s,dt);
    } else return;
    syncUi();
    paint();
    raf = requestAnimationFrame(tick);
  }
  function syncUi() {
    const s = session;
    const r = refs;
    const enabled = s.phase === "playing";
    const before = s.phase==="brief";
    if (r.shownPhase!==s.phase) {
      r.shownPhase=s.phase;
      const rival=before ? inviteScore(s.id) : null;
      let phaseText="计分挑战";
      if (s.phase==="paused") phaseText="已暂停";
      else if (s.practice) phaseText="试按 · 不计分";
      else if (before) phaseText=rival===null ? "键盘 / 触屏" : "好友挑战 · "+rival+" 分";
      r.phaseLabel.textContent=phaseText;
      r.help.hidden=!before;
      r.commands.hidden=!(before || (enabled && s.practice));
      r.rehearse.hidden=!before;
      r.clock.hidden=s.practice;
      r.points.hidden=before || s.practice;
      r.status.hidden=!enabled;
      if (s.practice) r.launch.textContent="开始计分";
    }
    r.controls.forEach((pad, i) => {
      if (pad.disabled !== !enabled) pad.disabled = !enabled;
      const current = enabled && (s.extra ? extra.wanted(s)===i : s.id === "alpine" ? s.lane === i : s.id === "synth" ? s.notes[s.hits]===i : Math.abs(s.cursor-s.zone)<=.125);
      if (current && !pad.hasAttribute("aria-current")) pad.setAttribute("aria-current", "true");
      if (!current && pad.hasAttribute("aria-current")) pad.removeAttribute("aria-current");
    });
    const timeText = Math.ceil(Math.max(0,s.config.limit - s.elapsed)) + " 秒";
    const scoreText = String(s.score).padStart(4, "0") + " PT";
    if (r.clock.textContent !== timeText) r.clock.textContent = timeText;
    if (r.points.textContent !== scoreText) r.points.textContent = scoreText;
    if (!s.flash) tell("");
    const target = s.extra ? extra.objective(s) : s.id === "alpine" ? "第 " + (s.gate + 1) + " 旗 · " + lanes[s.gateLanes[s.gate]]
      : s.id === "synth" ? "下一个音 · " + s.config.pads[s.notes[s.hits]][0] : "抓住绿色节拍区";
    const label = enabled ? target : s.practice ? s.config.brief : "挑战目标 · " + s.config.target + " " + s.config.unit;
    if (r.objective.textContent !== label) r.objective.textContent = label;
    const goalCount=s.practice ? 1 : s.config.target;
    const countText = s.hits + " / " + goalCount;
    if (r.count.value !== countText) {
      r.count.value = countText;
      r.fill.style.width = (s.hits / goalCount * 100) + "%";
    }
  }
  function finish() {
    const s = session;
    if (s.practice) {
      s.phase="learned";
      cancelAnimationFrame(raf);
      extra.animate(s,null);
      paint();
      refs.pauseButton.hidden=true;
      syncUi();
      showCover("动作成功！",s.config.brief,"开始计分",start);
      return;
    }
    window.DeskAudio?.cue(s.hits >= s.config.target ? "reward" : "fail");
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
  function posterBot(ctx) {
    const ink = "#17283a", mint = "#b4ffc6", shade = "#66c6ae", light = "#e1ffe2";
    for (const d of [-1,1]) {
      for (let i = 0; i < 5; i++) {
        const yy = -12 - i*2;
        box(ctx, ink, d * (11+i*3)-3, yy-1, 7, 5);
        box(ctx, i%2 ? shade : mint, d * (11+i*3)-2, yy, 5, 3);
      }
    }
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
  function background(ctx, id, cover = false) {
    const image = picture(!cover && id === "synth" ? "stage-plates" : id);
    const colors = id === "alpine" ? ["#3f7893","#90d9ca"] : id === "synth" ? ["#5a365d","#e58984"] : ["#292845","#68619a"];
    const grad = ctx.createLinearGradient(0,0,0,H);
    grad.addColorStop(0, colors[0]); grad.addColorStop(1, colors[1]);
    ctx.fillStyle = grad;
    ctx.fillRect(0,0,W,H);
    if (image.complete && image.naturalWidth) {
      if (cover) {
        const scale=Math.max(W/image.naturalWidth,H/image.naturalHeight);
        const width=W/scale, height=H/scale;
        ctx.drawImage(image,(image.naturalWidth-width)/2,(image.naturalHeight-height)/2,width,height,0,0,W,H);
      } else if (id === "alpine") {
        ctx.drawImage(image, 0, 0, image.naturalWidth, image.naturalHeight*.26, 0, 0, W, 56);
      } else if (id === "synth") {
        ctx.drawImage(image,384,216,384,216,0,0,W,85);
      }
    } else {
      for (let i=0;i<20;i++) star(ctx,(i*73+27)%W,(i*13+4)%62,"#d4cece",i%3===0?1:0);
    }
  }
  function rooftop(ctx,s) {
    extra.draw(ctx,s);
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
    window.MotionStage.paintAvatar(ctx,extra.snapshot(s),playerX,107,.57);
    box(ctx,"#bd7669",playerX-16,109,15,2);
    box(ctx,"#bd7669",playerX+1,109,15,2);
    box(ctx,"#ffdf9d",playerX+14,107,3,2);
    if(s.flash>.1 && s.good) star(ctx,playerX+18,72,"#fff4bc",2);
  }
  function synth(ctx,s) {
    box(ctx,"#422e44",0,79,W,47);
    box(ctx,"#f0a993",0,79,W,2);
    window.MotionStage.paintAvatar(ctx,extra.snapshot(s),s.avatar.keyboardX,78,.64);
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
      const x=36+i*62, active=i===current, down=s.lastKey===i && s.elapsed-s.pressAt<.22;
      box(ctx,"#24283b",x,73,60,41);
      box(ctx,down?"#ffb77d":active?"#baffad":"#d2bac2",x+2,75+Number(down)*2,56,33);
      box(ctx,active?"#649474":"#987f95",x+2,107,56,4);
      if(i!==3) box(ctx,"#383146",x+47,74,17,12);
      ctx.fillStyle="#3d414a";
      ctx.font="bold 14px monospace";
      ctx.textAlign="center";
      ctx.fillText("ASDF"[i],x+29,99);
      if(active) star(ctx,x+29,81,"#546b57",2);
      if(down) {
        box(ctx,"#344653",x+25,74,8,3);
        box(ctx,"#bdf2aa",x+26,73,6,3);
      }
    }
  }
  function paint() {
    const s = session;
    const ctx = refs?.ctx;
    if (!s || !ctx) return;
    ctx.save();
    ctx.imageSmoothingEnabled = false;
    if (s.phase==="brief") background(ctx,s.id,true);
    else if (s.extra) extra.draw(ctx,s);
    else if (s.id === "rooftop") rooftop(ctx,s);
    else {
      background(ctx,s.id);
      if (s.id === "alpine") alpine(ctx,s);
      if (s.id === "synth") synth(ctx,s);
    }
    ctx.restore();
  }

  function resultNavigation(r, full) {
    const row=el("div","dp-result-nav");
    row.setAttribute("role","group");
    row.setAttribute("aria-label","接着玩");
    const move=cameraMove(r);
    const index=catalog.findIndex(game => r.mode==="arcade" ? game.id===r.id : game.moveId===move);
    const localCamera = r.mode==="camera" && document.documentElement.dataset.device!=="board" &&
      location.protocol!=="file:" && window.isSecureContext && Boolean(navigator.mediaDevices?.getUserMedia);
    if (r.mode!=="arcade" && !localCamera) return row;
    const play=game => {
      if (!localCamera) { open(game.id); return; }
      dialog.close();
      window.dispatchEvent(new CustomEvent("desk:practice",{detail:game?.moveId || "all"}));
    };
    const replay=button("dp-secondary",index<0 ? "再闯八关" : "再玩这一关",() => play(catalog[index]));
    const next=index>=0 && catalog[index+1];
    if (full && next) {
      const advance=button("dp-primary","下一关 · "+next.title,() => play(next));
      row.append(advance,replay);
    } else {
      replay.className="dp-primary";
      row.append(replay);
    }
    return row;
  }

  function showResult(value) {
    const r = cleanResult(value);
    if (!r) return;
    const name = resultArt(r);
    frame("回血战报", "RE:CHARGE ARCADE / RESULT", "★", "#bdff98", session?.id === r.id);
    const body = el("div", "dp-result");
    const poster = el("div", "dp-poster");
    poster.style.setProperty("--dp-poster-art", "url('art/" + name + ".png')");
    if (name === "hero") poster.style.setProperty("--dp-poster-position", "right center");
    const date = new Date(r.at).toLocaleDateString("zh-CN");
    const big = el("div", "dp-score-row");
    big.append(el("strong", "", String(r.score)), el("small", "", "PT"));
    const full = r.cleared === r.total && r.total > 0;
    const modeName={arcade:"键盘 / 触屏",camera:"摄像头体感",board:"犀牛派体感"}[r.mode];
    const stats=el("dl","dp-result-stats");
    for (const [label,value] of [["目标达成",r.cleared+" / "+r.total],["用时",r.seconds+" 秒"]]) {
      const group=el("div");
      group.append(el("dt","",label),el("dd","",value));
      stats.append(group);
    }
    poster.append(el("p", "dp-tag",modeName+" · "+date),
      el("h3", "", r.title + (full ? " · 通关" : " · 战绩")), big,stats);
    if (r.moves.length>1) {
      const cleared=el("details","dp-result-moves");
      cleared.append(el("summary","","已完成 "+r.moves.length+" 个动作"),el("p","",r.moves.join("、")));
      poster.append(cleared);
    }
    const again = resultNavigation(r,full);
    const actions = el("div", "dp-actions");
    const message = el("p","dp-message");
    message.setAttribute("role","status");
    const rival = r.mode==="board" ? null : inviteScore(r.id,r.course);
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
        url.searchParams.set("play", r.mode==="camera" ? "camera" : r.id);
        const move=cameraMove(r);
        if (move) url.searchParams.set("move",move);
        if (r.course===8) url.searchParams.set("course","8");
        if (move || r.course===8 || r.mode==="arcade") url.searchParams.set("beat", String(r.score));
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
    actions.append(download, invite);
    body.append(poster, again, actions, link, message, preview);
    shell.append(body);
    (again.firstElementChild || download).focus({preventScroll:true});
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
      const left=(image.naturalWidth-sw)*(resultArt(result)==="hero" ? 1 : .5);
      ctx.drawImage(image,left,(image.naturalHeight-sh)/2,sw,sh,46,156,708,310);
    } else {
      ctx.save();
      ctx.translate(380,385);
      ctx.scale(5,5);
      posterBot(ctx);
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
    const name=resultArt(result);
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
    open, showResult, recordResult, catalog,
    getHistory: () => history.map(item => ({...item})),
    getStats: () => ({todayRuns: stats.day === new Date().toDateString() ? stats.runs : 0,
      bestScore: stats.best, playedGames: stats.played.length}),
  });
})();
