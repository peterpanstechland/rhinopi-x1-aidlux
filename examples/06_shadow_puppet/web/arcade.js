/* Browser lobby and read-only companion to the Rhino Pi game. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const icons = {
    pad:'<path d="M6.5 6h11c2.1 0 3 1.7 3.5 4l1 5.5c.6 3.2-2 4.5-4 2.6L15.8 16H8.2L6 18.1c-2 1.9-4.6.6-4-2.6L3 10c.5-2.3 1.4-4 3.5-4Z"/><path d="M7.7 9v5m-2.5-2.5h5M16 10h.1m2.4 3h.1"/>',
    scan:'<path d="M3 9V4h5m8 0h5v5m0 6v5h-5m-8 0H3v-5M7 16c2-3 8-3 10 0"/><circle cx="12" cy="9" r="2.5"/>',
    cup:'<path d="M7 4h10v5a5 5 0 0 1-10 0ZM7 6H3v2a4 4 0 0 0 5 4m9-6h4v2a4 4 0 0 1-5 4m-4 2v5m-4 1h8"/>',
    mute:'<path d="M3 9h4l5-4v14l-5-4H3ZM16 9l5 6m0-6-5 6"/>',
    sound:'<path d="M3 9h4l5-4v14l-5-4H3Zm12-1a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14"/>',
    help:'<circle cx="12" cy="12" r="9"/><path d="M9 9a3 3 0 1 1 5 2.2c-1.4 1-2 1.3-2 3m0 2.3h.01"/>',
    play:'<path fill="currentColor" stroke="none" d="M5 3v18l16-9z"/>',
    grid:'<path d="M3 3h7v7H3zm11 0h7v7h-7zM3 14h7v7H3zm11 0h7v7h-7z"/>',
    pulse:'<path d="M2 12h5l3-7 4 14 3-7h5"/>',
    bolt:'<path d="m14 2-10 12h7l-1 8 10-13h-7z"/>',
    cartridge:'<path d="M5 3h13l2 2v16H4V4zM8 3v7h8V3M8 17v4m4-4v4m4-4v4"/>',
    arrow:'<path d="M4 12h15m-6-7 7 7-7 7"/>',
    save:'<path d="M3 3h14l4 4v14H3ZM7 3v6h10V3M7 21v-7h10v7"/>',
    close:'<path d="m6 6 12 12M18 6 6 18"/>'
  };
  function icon(name) {
    return '<svg class="ico" viewBox="0 0 24 24" aria-hidden="true">' + icons[name] + '</svg>';
  }
  document.querySelectorAll("[data-icon]").forEach(el => { el.outerHTML = icon(el.dataset.icon); });
  function textElement(tag, content, className) {
    const el = document.createElement(tag);
    el.textContent = content;
    if (className) el.className = className;
    return el;
  }

  const catalog = window.DeskPlay.catalog;
  const games = catalog.map(game => game.id);
  const moves = new Map(catalog.map(game => [game.moveId,game]));
  const boardMode = document.documentElement.dataset.device === "board";
  const cameraSupported = location.protocol !== "file:" && window.isSecureContext && Boolean(navigator.mediaDevices?.getUserMedia);
  let deckMotion = !boardMode && cameraSupported;
  try {
    const mode = localStorage.getItem("desk.arcade.input");
    if (mode === "keys") deckMotion = false;
  } catch {}
  let activeCartridge = catalog[0].id;
  const audio = window.DeskAudio;
  function renderSound() {
    const button = $("sound");
    const label = audio.enabled ? "关闭音乐与音效" : "开启音乐与音效";
    button.setAttribute("aria-pressed", String(audio.enabled));
    button.setAttribute("aria-label", label);
    button.title = label;
    button.innerHTML = icon(audio.enabled ? "sound" : "mute");
  }
  $("sound").addEventListener("click", () => audio.enable(!audio.enabled));
  window.addEventListener("desk:sound", renderSound);
  renderSound();
  const guide = $("help-dialog");
  $("help").addEventListener("click", () => guide.showModal());
  $("close-help").addEventListener("click", () => guide.close());
  $("help-done").addEventListener("click", () => guide.close());
  guide.addEventListener("click", (e) => { if (e.target === guide && !e.target.closest("button")) {
    const r = guide.getBoundingClientRect();
    if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) guide.close();
  }});
  const padHints = {
    rooftop:"找准节拍，给双翼充能。", flap:"抬翼再压翼，飞过山谷。", wave:"左右交替，向月台上的旅客道别。",
    alpine:"左右换道，穿过雪道上的旗门。", synth:"跟着亮起的琴键，奏响落日。",
    hands_up:"看准仙人掌靠近的时机起跳。", turn:"左转、回正、右转，点亮两侧的灯。", nod:"低头再抬头，让节拍灯亮起。"
  };
  function renderDeck() {
    const deck=$("game-deck");
    deck.replaceChildren();
    $("mode-motion").setAttribute("aria-pressed",String(deckMotion));
    $("mode-keys").setAttribute("aria-pressed",String(!deckMotion));
    $("hud-total").textContent="/ " + catalog.length;
    $("deck-instruction").textContent = deckMotion ? (cameraSupported ? "选一关看动作示范，再开启摄像头。" : "选一关看动作示范，也可以切换按键试玩。") : "选一关试试按键，再开始计分。";
    for (const game of catalog) {
      const move=window.ActionCoach.actions.find(action => action.id===game.moveId);
      const card=document.createElement("button");
      card.className="cart "+game.id;
      card.dataset.game=game.id;
      card.tabIndex=game.id===activeCartridge ? 0 : -1;
      const control = deckMotion ? move.goal : game.id==="synth" ? "1–0 · 十键" : game.pads.map(([key]) => key==="Space" ? "空格" : key).join(" / ");
      card.setAttribute("aria-label", game.title+" · "+(deckMotion?"摄像头体感":"键盘 / 触屏")+" · "+control);
      const art=textElement("span","","cart-art");
      const img=new Image(); img.alt=""; img.src="art/"+game.art+".png";
      art.append(img,textElement("span",game.short,"cart-code"));
      const info=textElement("span","","cart-info");
      const copy=textElement("span","","cart-text");
      const hint=textElement("small",deckMotion ? move.region : control);
      copy.append(hint,textElement("strong",game.title),textElement("span",deckMotion?move.goal:padHints[game.id]));
      const arrow=textElement("span","","cart-arrow");
      arrow.innerHTML=icon("arrow");
      info.append(copy,arrow);
      card.append(art,info);
      card.addEventListener("click", () => {
        if (deckMotion) location.hash="board/"+game.moveId;
        else window.DeskPlay.open(game.id);
      });
      deck.append(card);
    }
  }
  function setDeckMode(motion) {
    deckMotion = !boardMode && motion;
    try { localStorage.setItem("desk.arcade.input",deckMotion ? "motion" : "keys"); } catch {}
    renderDeck();
  }
  function chooseKeyboard() { setDeckMode(false); }
  const deck = $("game-deck");
  deck.addEventListener("focusin", event => {
    const card = event.target.closest(".cart");
    if (!card) return;
    activeCartridge = card.dataset.game;
    for (const item of deck.children) item.tabIndex = item===card ? 0 : -1;
  });
  deck.addEventListener("keydown", event => {
    if (event.altKey || event.ctrlKey || event.metaKey) return;
    const cards = [...deck.children];
    const index = cards.indexOf(event.target);
    if (index<0) return;
    const columns = getComputedStyle(deck).gridTemplateColumns.split(" ").length;
    const next = {ArrowLeft:index-1,ArrowRight:index+1,ArrowUp:index-columns,ArrowDown:index+columns,Home:0,End:cards.length-1}[event.key];
    if (next===undefined) return;
    event.preventDefault();
    cards[Math.max(0,Math.min(cards.length-1,next))].focus();
  });
  $("mode-keys").addEventListener("click", chooseKeyboard);
  $("followup-keys").addEventListener("click", chooseKeyboard);
  $("mode-motion").addEventListener("click", () => setDeckMode(true));
  if (boardMode) {
    $("mode-motion").hidden=true;
    $("hero-motion").querySelector("span").textContent="进入犀牛派体感";
  }
  renderDeck();

  function renderScores() {
    const history = window.DeskPlay.getHistory();
    const stats = window.DeskPlay.getStats();
    $("hud-runs").textContent = stats.todayRuns;
    $("hud-best").textContent = stats.bestScore.toLocaleString();
    $("hud-games").textContent = stats.playedGames;
    const list = $("records-list");
    list.replaceChildren();
    if (!history.length) {
      const empty = document.createElement("div");
      empty.className = "record-empty";
      empty.innerHTML = '<span class="empty-avatar"><img alt="" src="art/bot.png"></span><div><h2>第一张战报，等你来打。</h2><p>玩完一局，就能在这里回看成绩、保存海报。</p><a class="text-link" href="#cartridges">挑一张卡带 ' + icon("arrow") + '</a></div>';
      list.append(empty);
      return;
    }
    for (const record of history) {
      const row = document.createElement("button");
      row.className = "score-row";
      const cover = new Image();
      cover.alt = "";
      const entry=catalog.find(game=>game.id===record.id || record.id==="camera:"+game.moveId);
      cover.src = "art/" + (entry?.art || "hero") + ".png";
      const copy = document.createElement("span");
      const at = new Date(record.at).toLocaleString("zh-CN", {month:"numeric",day:"numeric",hour:"2-digit",minute:"2-digit"});
      const modes = {board:"犀牛派体感", camera:"摄像头体感", arcade:"键盘 / 触屏"};
      copy.append(textElement("strong", record.title), textElement("small", at + " · " + modes[record.mode]));
      const arrow = document.createElement("span");
      arrow.innerHTML = icon("arrow");
      row.append(cover, copy, textElement("span", record.score.toLocaleString(), "row-score"), arrow);
      row.addEventListener("click", () => window.DeskPlay.showResult(record));
      list.append(row);
    }
  }
  window.addEventListener("desk:result", renderScores);
  const phases = {monitor:"工位监测中", away:"等待玩家入镜", alert:"该活动一下了", summary:"本轮已结算", round:"体感挑战中"};
  const phaseTips = {monitor:"保持舒适坐姿。举手或展翅，就能提前开启一轮挑战。", away:"面对摄像头，让头、肩和双手进入画面。", alert:"举起双手或舒展双臂，开始本轮回血。", summary:"回合已结束，打开战报可查看得分和保存海报。"};
  let currentPage = "";
  let liveStatus = null;
  let latestBoardResult = null;
  let lastStoredRound = 0;
  const stream = $("stream");
  const streamWait = $("stream-wait");
  const canvas = $("motion-canvas");
  let cameraView = false;
  let cameraRequest = null;
  let cameraState = "idle";
  let guideId = "wings";
  let singleMove = null;
  let relayOrder=window.RoundPatterns.relay(window.CameraRound.ids);
  let guideStart = performance.now();
  let guideTimer;
  let guideKey = "";
  const coach = window.ActionCoach;
  const cameraInfo = $("camera-info");
  let cameraFailed = false;
  const cameraHint = "画面只在本机处理。把设备摆稳，让上半身入镜。";
  const framing = {wings:"双肩和两只手腕",flap:"双肩和两只手腕",piano:"双手和指尖",wave:"双肩和挥动的手腕",lean:"脸和双肩",turn:"脸和双肩",nod:"脸和双肩",hands_up:"双肩"};
  function setStageText(id, value) {
    const el = $(id);
    if (el.textContent !== value) el.textContent = value;
  }
  function stagePrompt(instruction, status, state, challenge) {
    setStageText("stage-now", instruction);
    setStageText("tracking-caption", status);
    $("stage-prompt").dataset.state = state;
    const progress = $("stage-progress");
    const count = $("stage-count");
    progress.hidden = count.hidden = !challenge;
    if (!challenge) return;
    const frac = Math.max(0, Math.min(1, Number(challenge.frac) || 0));
    progress.value = frac;
    const value = challenge.unit === "秒" ? Number(challenge.count).toFixed(1) : Math.floor(challenge.count);
    setStageText("stage-count", Number.isFinite(challenge.count) && challenge.target ?
      value + " / " + challenge.target + " " + (challenge.unit || "") : Math.round(frac * 100) + "%");
  }
  const idle = () => !boardMode && !liveStatus;
  let audioRound = "", audioFeedback = "", clearSoundPlayed = false, endedSoundAt = 0;
  function pageMusic() {
    if (currentPage !== "board") return "lobby";
    if (liveStatus?.phase === "round") return liveStatus.act_id;
    if (liveStatus?.phase === "summary") return null;
    return singleMove || "lobby";
  }
  function syncRoundAudio(s) {
    if (currentPage !== "board") return;
    audio.setBase(pageMusic());
    if (s?.phase !== "round") {
      if (s?.phase === "summary" && audioRound && s.round_ended_at !== endedSoundAt) {
        endedSoundAt = s.round_ended_at;
        if (s.cleared < s.round_len) audio.cue("fail");
        else if (!clearSoundPlayed) audio.cue("reward");
      }
      audioRound = "";
      return;
    }
    const key = s.act_i + "/" + s.act_id;
    if (key !== audioRound) {
      audioRound = key;
      audioFeedback = "";
      clearSoundPlayed = false;
      if (s.sub !== "clear") audio.cue("start");
    }
    const feedback = s.challenge?.feedback;
    if (s.act_id==="piano" && Number.isInteger(feedback?.key) && audioFeedback!==feedback.seq) {
      audioFeedback=feedback.seq;
      audio.note(feedback.key,true);
      if (feedback.kind==="miss") audio.cue("miss");
    }
    if (s.sub === "clear") {
      // The board uses the same settlement phase for a timeout and a clear.
      const completed = s.results?.[s.act_i]?.cleared ?? (s.challenge?.frac >= 1);
      if (completed && !clearSoundPlayed) {
        audio.cue("reward");
        clearSoundPlayed = true;
      }
      return;
    }
    if (s.sub !== "play" || s.challenge?.tracking === false || !feedback) return;
    if (!["hit", "miss"].includes(feedback.kind) || audioFeedback === feedback.seq) return;
    audioFeedback = feedback.seq;
    audio.cue(feedback.kind);
  }
  function drawGuide() {
    clearTimeout(guideTimer);
    guideTimer=null;
    if (currentPage !== "board" || document.hidden) return;
    const preview = idle();
    const action = preview ? guideId : liveStatus?.act_id || "wings";
    const key = (preview ? "preview-" : "live-") + action;
    if (key !== guideKey) { guideKey = key; guideStart = performance.now(); }
    $("coach-canvas").hidden = preview || liveStatus?.phase === "summary";
    if (preview || !$("coach-canvas").hidden) {
      const snapshot = preview ? null : liveStatus;
      coach.draw(preview ? canvas : $("coach-canvas"), action, (performance.now()-guideStart)/1000, snapshot);
      guideTimer = setTimeout(drawGuide, 100);
    }
  }
  function renderPreview() {
    const action = coach.actions.find(a => a.id === guideId);
    $("view-board").classList.toggle("piano-room",guideId==="piano");
    $("phase").textContent = singleMove ? moves.get(singleMove).title : "八关连闯";
    $("round-label").textContent = singleMove ? "单关挑战 · " + action.region : "随机连闯 · 8 关";
    const cue=action.cue;
    $("live-tip").textContent = singleMove ? cue : "首关「"+moves.get(guideId).title+"」先看左侧示范。两分钟内挑战八种动作。";
    $("relay-route").hidden=Boolean(singleMove);
    if(!singleMove) {
      $("relay-stops").replaceChildren(...relayOrder.map(id=>textElement("li",moves.get(id).title)));
      $("shuffle-relay").disabled=Boolean(cameraRequest);
    }
    $("start-label").textContent = cameraFailed ? "重试摄像头" : singleMove ? "开启摄像头玩这关" : "开启摄像头闯八关";
    $("start-camera").hidden = !cameraSupported || Boolean(cameraRequest);
    $("practice-keys").hidden = Boolean(cameraRequest);
    cameraInfo.hidden = false;
    $("practice-keys").classList.toggle("primary", !cameraSupported || cameraFailed);
    $("practice-label").textContent = guideId==="piano" ? "用键盘 / 触屏试弹十键" : "用键盘 / 触屏玩「" + moves.get(guideId).title + "」";
    if (!cameraSupported) cameraInfo.textContent = "这里可以看动作示范、用按键闯关。摄像头体感可从 HTTPS 或本机 localhost 开启。";
    $("round-metrics").hidden = true;
    $("guide-library").hidden = false;
    $("board-summary").hidden = Boolean(cameraRequest) || !latestBoardResult;
    $("stage-heading").textContent = guideId==="piano" ? "指法预演" : "动作预演";
    $("stage-source").textContent = moves.get(guideId).title;
    stagePrompt(action.goal, (guideId==="piano"?"指法示范":"小电示范中")+" · 不计分", "preview");
    $("tracking-caption").closest(".stage-caption").classList.remove("tracking");
    $("connection").textContent = cameraState === "loading" ? "正在启动" : "摄像头未开启";
    $("connection").classList.remove("online");
    $("show-camera").disabled = true;
    document.querySelectorAll("#guide-picker button").forEach(b => {
      b.setAttribute("aria-pressed", String(b.value === (singleMove || "all")));
      b.disabled=cameraState==="loading";
    });
    updateStream();
    drawGuide();
  }
  function shuffleRelay() {
    relayOrder=window.RoundPatterns.relay(window.CameraRound.ids,relayOrder[0]);
    guideId=relayOrder[0];
  }
  $("shuffle-relay").addEventListener("click",()=>{
    if(cameraRequest || boardMode || singleMove)return;
    shuffleRelay();
    cameraInfo.textContent=guideId==="piano" ? "首关需要双手入镜，掌心朝向镜头。" : cameraHint;
    renderPreview();
  });
  function chooseCourse(value) {
    const hash = value === "all" ? "#board" : "#board/" + value;
    if (location.hash !== hash) {
      location.hash = hash;
    } else {
      liveStatus = null;
      renderPreview();
    }
  }
  window.addEventListener("desk:practice", event => {
    const value = event.detail;
    if (boardMode || cameraRequest || !(value === "all" || moves.has(value))) return;
    const focusStart = () => requestAnimationFrame(() => (cameraSupported ? $("start-camera") : $("practice-keys")).focus());
    if (location.hash === (value === "all" ? "#board" : "#board/" + value)) focusStart();
    else window.addEventListener("hashchange", focusStart, {once:true});
    chooseCourse(value);
  });
  for (const item of [{value:"all",name:"八关连闯"}, ...catalog.map(game=>({value:game.moveId,name:game.title}))]) {
    const button = textElement("button", item.name);
    button.value = item.value;
    button.addEventListener("click", () => chooseCourse(item.value));
    $("guide-picker").append(button);
  }
  $("practice-keys").addEventListener("click", () => {
    if (cameraRequest || boardMode) return;
    $("mode-keys").click();
    window.DeskPlay.open(moves.get(guideId).id);
  });
  $("board-keys-link").addEventListener("click", () => $("mode-keys").click());
  function endCamera(message, keepResult=false, failed=false) {
    if(!singleMove && liveStatus?.source==="camera")shuffleRelay();
    cameraRequest?.abort();
    cameraRequest = null;
    cameraState = "idle";
    cameraFailed = failed;
    document.querySelectorAll("#guide-picker button").forEach(b => { b.disabled = false; });
    cameraView = false;
    $("start-camera").hidden = !cameraSupported;
    $("stop-camera").hidden = true;
    $("show-camera").disabled = true;
    cameraInfo.textContent = message;
    resetHit();
    if (keepResult) { updateStream(); drawGuide(); }
    else { liveStatus=null; audioRound=""; audio.setBase(pageMusic()); renderPreview(); }
  }
  $("start-camera").addEventListener("click", async () => {
    if (cameraRequest || boardMode || !cameraSupported) return;
    const request = new AbortController();
    const round = new window.CameraRound(singleMove ? [singleMove] : relayOrder);
    cameraRequest = request;
    liveStatus = null;
    cameraState = "loading";
    cameraFailed = false;
    $("start-camera").hidden = true;
    $("stop-camera").hidden = false;
    renderPreview();
    try {
      await window.DeskCamera.start({
        video:$("local-video"), signal:request.signal,getAction:()=>round.acts[round.index].id,
        onStatus:message => { if (!request.signal.aborted) cameraInfo.textContent=message; },
        onFrame:frame => {
          if (request.signal.aborted) return;
          cameraState="playing";
          liveStatus=round.update(frame,frame.time);
          renderBoard(liveStatus);
          if (liveStatus.round_ended_at) {
            endCamera("回合结束，摄像头已关闭。",true);
            window.DeskPlay.showResult(latestBoardResult);
          }
        },
        onError:error => { if (!request.signal.aborted) endCamera(error.message || String(error), false, true); }
      });
    } catch (error) { if (!request.signal.aborted) endCamera(error.message || "摄像头启动失败，请重试。", false, true); }
  });
  $("stop-camera").addEventListener("click", () => endCamera("摄像头已关闭。可重新开始一轮。"));
  function stopStream() {
    if (stream.hasAttribute("src")) stream.removeAttribute("src");
  }
  function updateStream() {
    canvas.hidden = cameraView;
    stream.hidden = !boardMode || !cameraView;
    $("local-video").hidden = boardMode || !cameraView;
    const handVisual=liveStatus?.challenge?.visual;
    const handCanvas=$("hand-overlay");
    handCanvas.hidden=boardMode || !cameraView || liveStatus?.phase!=="round" || liveStatus.act_id!=="piano" || !handVisual?.hand_points;
    if (!handCanvas.hidden) window.PianoStage.overlay(handCanvas,$("local-video"),handVisual);
    $("show-stage").setAttribute("aria-pressed", String(!cameraView));
    $("show-camera").setAttribute("aria-pressed", String(cameraView));
    if (!cameraView) {
      stopStream();
      streamWait.hidden = true;
      if (currentPage === "board" && !idle() && !document.hidden) window.MotionStage.paint(canvas, liveStatus || {});
      return;
    }
    if (!boardMode) { streamWait.hidden = true; return; }
    if (!boardMode || currentPage !== "board" || document.hidden || !liveStatus || liveStatus.camera_online === false) {
      stopStream();
      streamWait.hidden = false;
      streamWait.textContent = liveStatus?.camera_online === false ? "等待摄像头恢复…" : "正在接入画面…";
      return;
    }
    if (!stream.hasAttribute("src")) stream.src = "stream";
    streamWait.hidden = true;
  }
  $("show-camera").addEventListener("click", () => { cameraView = true; updateStream(); });
  $("show-stage").addEventListener("click", () => { cameraView = false; updateStream(); });
  stream.addEventListener("error", () => {
    if (!stream.hasAttribute("src")) return;
    stopStream();
    streamWait.textContent = "画面连接中断，正在重连…";
    streamWait.hidden = false;
  });
  function mmss(value) {
    const v = Math.max(0, Math.ceil(Number(value) || 0));
    return String(Math.floor(v / 60)).padStart(2, "0") + ":" + String(v % 60).padStart(2, "0");
  }
  let lastHitKey = "", hitTimer;
  function resetHit() {
    clearTimeout(hitTimer);
    lastHitKey="";
    $("hit-feedback").hidden = true;
  }
  function renderHit(s) {
    const f = s?.challenge?.feedback;
    if (!s || s.phase!=="round" || s.sub==="ready" || s.challenge?.tracking === false) {resetHit(); return;}
    if (!f || !["hit","miss"].includes(f.kind)) return;
    const key=s.act_i + "-" + s.act_id + "-" + f.seq;
    if (key===lastHitKey) return;
    lastHitKey=key;
    const hit=$("hit-feedback");
    hit.textContent=f.text;
    hit.dataset.kind=f.kind;
    hit.hidden=false;
    clearTimeout(hitTimer);
    hitTimer=setTimeout(() => {hit.hidden=true;},750);
  }
  function renderBoard(s) {
    $("relay-route").hidden=true;
    syncRoundAudio(s);
    const online = Boolean(s);
    const local=s?.source==="camera";
    const challenge = s?.challenge || {};
    $("view-board").classList.toggle("piano-room",s?.act_id==="piano" && s.phase==="round");
    $("round-metrics").hidden=false;
    $("guide-library").hidden=!(local && s?.phase==="summary");
    $("stage-heading").textContent="玩家舞台";
    $("stage-source").textContent=boardMode ? "RHINO PI X1" : "本机摄像头";
    $("show-camera").disabled=!s || (local && cameraState!=="playing");
    $("connection").textContent = online ? local ? (s.phase==="summary" ? "回合结束" : "本机摄像头") : "板端已连接" : "正在重连";
    $("connection").classList.toggle("online", online);
    $("phase").textContent = online ? (s.phase === "round" ? (s.act || "体感挑战") : phases[s.phase]) : "等待板端响应";
    const playing = s?.phase === "round";
    let tip = online ? phaseTips[s.phase] : "请确认游戏仍在运行，连接恢复后会自动继续。";
    if (playing) {
      const step = (Number(s.act_i) + 1) + " / " + s.round_len;
      $("round-label").textContent = "第 " + step + " 关 · " + ({ready:"准备",play:"跟做",clear:"结算"}[s.sub] || "跟做");
      tip = s.act_goal || "";
    } else {
      $("round-label").textContent = "体感挑战";
    }
    $("live-tip").textContent = tip;
    $("hp-label").textContent=local ? "本轮得分" : "工位能量";
    $("hp-bar").hidden=local;
    $("posture-row").hidden=local;
    $("hp").textContent = online ? local ? s.round_score + " PT" : s.hp + "%" : "—";
    $("hp-bar").value = s?.hp ?? 0;
    $("time-label").textContent = playing ? "回合剩余" : local ? "本轮用时" : "预计提醒";
    $("remain").textContent = online ? mmss(playing ? s.round_left : local ? s.round_time : s.remain_s) : "—";
    $("posture").textContent = s?.posture?.tracked ? Math.round(s.posture.score) + " / 100" : "等待识别";
    const pianoInput = playing && s.act_id==="piano" && (challenge.piano_input || challenge.visual?.piano_input);
    const fingerMode = pianoInput==="fingers";
    if (pianoInput==="wrists") $("stage-heading").textContent="板端手腕替代模式";
    const tracked = fingerMode ? challenge.tracking : Boolean(s?.pose_points?.[11] && s?.pose_points?.[12]);
    const missing = playing && s.sub !== "clear" && challenge.tracking === false;
    const status = !s ? "正在接入追踪…" : s.phase === "summary" ? "本轮已结束" : s.camera_online === false ? "摄像头离线" : missing ? (local ? "等待入镜 · 计时暂停" : "等待入镜") : tracked ? (fingerMode?"手部骨骼已识别":"上半身已追踪") : "等待玩家入镜";
    const instruction = missing ? (fingerMode ? challenge.cue : "让" + (pianoInput==="wrists" ? "双肩和手腕" : framing[s.act_id] || "上半身") + "进入画面") :
      playing ? challenge.cue || challenge.text || s.act_goal || "跟小电做动作" :
      s?.phase === "summary" ? "完成 " + s.cleared + " / " + s.round_len + " 关" : tip;
    stagePrompt(instruction, status, missing ? "waiting" : playing ? "playing" : "idle", playing ? challenge : null);
    $("tracking-caption").closest(".stage-caption").classList.toggle("tracking", tracked && !missing);
    if (s?.round_ended_at && s.round_ended_at !== lastStoredRound) {
      lastStoredRound = s.round_ended_at;
      const source=local?"camera":"board";
      const moves = (s.results || []).filter(act=>act.cleared).map(act=>act.name);
      const playedIds=(s.results || []).filter(act=>act.cleared || act.seconds>0).map(act=>act.id);
      if (local && s.act_id && !playedIds.includes(s.act_id)) playedIds.push(s.act_id);
      const game=local && s.round_len===1 ? catalog.find(game=>game.moveId===s.act_id) : null;
      const title=local ? game?.title || "体感八连关" : "工位体感挑战";
      latestBoardResult = {id:game?"camera:"+game.moveId:source,title,score:s.round_score,cleared:s.cleared,total:s.round_len,seconds:Math.round(s.round_time),at:s.round_ended_at,mode:source,moves,playedIds,course:local && !game ? 8 : undefined};
      window.DeskPlay.recordResult(latestBoardResult);
    }
    $("board-summary").hidden = !latestBoardResult || Boolean(cameraRequest && s?.phase !== "summary");
    $("practice-keys").hidden = Boolean(cameraRequest) || boardMode || s?.phase === "summary";
    cameraInfo.hidden = local && playing;
    $("share-board-label").textContent = s?.phase === "summary" ? "查看战报" : "上轮战报";
    updateStream();
    renderHit(s);
    if (guideKey!=="live-"+(s?.act_id || "wings") || !guideTimer) drawGuide();
  }
  $("share-board").addEventListener("click", () => { if (latestBoardResult) window.DeskPlay.showResult(latestBoardResult); });
  let pollTimer;
  let polling = false;
  async function pollBoard() {
    clearTimeout(pollTimer);
    if (!boardMode || document.hidden || polling) return;
    polling = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 3500);
    try {
      const response = await fetch("status", {cache:"no-store",signal:controller.signal});
      if (!response.ok) throw Error("offline");
      const data = await response.json();
      liveStatus = Object.hasOwn(phases, data.phase) ? data : null;
    } catch { liveStatus = null; }
    finally { clearTimeout(timeout); polling = false; }
    renderBoard(liveStatus);
    if (!document.hidden) pollTimer = setTimeout(pollBoard, liveStatus ? (currentPage === "board" ? 125 : 1000) : 2200);
  }
  $("connect-form").addEventListener("submit", event => {
    event.preventDefault();
    const value = $("board-address").value.trim();
    try {
      const url = new URL(/^https?:\/\//i.test(value) ? value : "http://" + value);
      if (!["http:","https:"].includes(url.protocol) || !url.hostname || url.username || url.password || url.pathname !== "/" || url.search || url.hash) throw Error();
      if (!url.port && !/^https?:\/\//i.test(value)) url.port = "8090";
      url.hash = "board";
      window.location.assign(url.href);
    } catch { $("address-error").textContent = "请输入板子 IP 或主机名，可附端口号。"; }
  });
  $("board-address").addEventListener("input", () => { $("address-error").textContent = ""; });
  function route() {
    const hash = location.hash.slice(1);
    const params=new URLSearchParams(location.search);
    const inviteCamera=!hash && params.get("play")==="camera";
    const boardHash=hash==="board" || hash.startsWith("board/");
    const previousPage=currentPage;
    currentPage = hash==="records" ? "records" : boardHash || inviteCamera || (!hash && boardMode) ? "board" : "lobby";
    const selected=inviteCamera ? params.get("move") : hash.split("/")[1];
    const nextMove=!boardMode && moves.has(selected) ? selected : null;
    const changeCourse=currentPage==="board" && singleMove!==nextMove;
    if (cameraRequest && (currentPage!=="board" || changeCourse)) endCamera("摄像头已关闭。");
    if (currentPage==="board" && !boardMode) {
      if (changeCourse || previousPage!=="board") {
        liveStatus=null;
        cameraFailed=false;
        cameraInfo.textContent=(nextMove || relayOrder[0])==="piano" ? "镜头只需拍清双手。左右手各管五键，手部画面只在本机处理。" : cameraHint;
      }
      singleMove=nextMove;
      guideId=singleMove || relayOrder[0];
    }
    if (currentPage !== "board") audioRound = "";
    audio.setBase(pageMusic());
    for (const name of ["lobby","board","records"]) {
      $("view-" + name).hidden = name !== currentPage;
      const link = document.querySelector('[data-page="' + name + '"]');
      if (name === currentPage) link.setAttribute("aria-current","page"); else link.removeAttribute("aria-current");
    }
    if (hash === "cartridges") requestAnimationFrame(() => $("cartridges").scrollIntoView({block:"start"}));
    else if (!(previousPage==="board" && currentPage==="board")) window.scrollTo({top:0,behavior:"instant"});
    updateStream();
    if (currentPage==="board" && idle()) renderPreview();
    else drawGuide();
    if (previousPage && previousPage!=="board" && currentPage==="board") $("board-title").focus({preventScroll:true});
  }
  $("board-offline").hidden = boardMode;
  $("local-controls").hidden = boardMode;
  $("stage-source").textContent = boardMode ? "RHINO PI X1" : "本机摄像头";
  $("connection").textContent = boardMode ? "连接中" : "浏览器模式";
  $("foot-mode").textContent = boardMode ? "犀牛派 X1 · 板端已启用" : "浏览器街机";
  window.addEventListener("hashchange", route);
  document.addEventListener("visibilitychange", () => { updateStream(); if (boardMode) pollBoard(); });
  window.addEventListener("pagehide", () => { clearTimeout(pollTimer); clearTimeout(guideTimer); if(cameraRequest) endCamera("摄像头已关闭。"); stopStream(); });
  document.addEventListener("visibilitychange", drawGuide);
  window.addEventListener("pageshow", e => { if (e.persisted && boardMode) pollBoard(); });
  renderScores();
  route();
  if (boardMode) pollBoard();
  const invitation = new URLSearchParams(location.search).get("play");
  if (games.includes(invitation)) window.DeskPlay.open(invitation);
})();
