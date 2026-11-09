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
  let deckMotion = !boardMode && location.protocol !== "file:" && window.isSecureContext;
  let sound = false;
  try { sound = localStorage.getItem("desk.sound") === "on"; } catch {}
  window.deskSoundEnabled = () => sound;
  function renderSound() {
    const button = $("sound");
    const label = sound ? "关闭音效" : "开启音效";
    button.setAttribute("aria-pressed", String(sound));
    button.setAttribute("aria-label", label);
    button.title = label;
    button.innerHTML = icon(sound ? "sound" : "mute");
  }
  $("sound").addEventListener("click", () => {
    sound = !sound;
    try { localStorage.setItem("desk.sound", sound ? "on" : "off"); } catch {}
    renderSound();
  });
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
    for (const game of catalog) {
      const move=window.ActionCoach.actions.find(action => action.id===game.moveId);
      const card=document.createElement("button");
      card.className="cart "+game.id;
      card.setAttribute("aria-label", game.title+" · "+(deckMotion?"摄像头体感":"键盘 / 触屏"));
      const art=textElement("span","","cart-art");
      const img=new Image(); img.alt=""; img.src="art/"+game.art+".png";
      art.append(img,textElement("span",game.short,"cart-code"));
      const info=textElement("span","","cart-info");
      const copy=textElement("span","","cart-text");
      const region=textElement("small",move.region);
      region.prepend(document.createElement("b"));
      copy.append(region,textElement("strong",game.title),textElement("span",deckMotion?move.goal:padHints[game.id]));
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
  $("mode-keys").addEventListener("click", () => {deckMotion=false; renderDeck();});
  $("mode-motion").addEventListener("click", () => {deckMotion=true; renderDeck();});
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
  let guideStart = performance.now();
  let guideTimer;
  let guideKey = "";
  const coach = window.ActionCoach;
  const cameraInfo = $("camera-info");
  const idle = () => !boardMode && !liveStatus;
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
      const snapshot = preview && action==="piano" ? {challenge:{visual:{piano_input:"wrist",target_key:2}}} : liveStatus;
      coach.draw(preview ? canvas : $("coach-canvas"), action, (performance.now()-guideStart)/1000, snapshot);
      guideTimer = setTimeout(drawGuide, 100);
    }
  }
  function renderPreview() {
    const action = coach.actions.find(a => a.id === guideId);
    $("phase").textContent = singleMove ? moves.get(singleMove).title : "八关连闯";
    $("round-label").textContent = singleMove ? "单关挑战 · " + action.region : "体感挑战 · 8 关";
    const cue=guideId==="piano" ? "左右移动手腕选中黄键，向下轻点再抬起。" : action.cue;
    $("live-tip").textContent = singleMove ? cue + " " + action.goal + "。" : "从天台展翅开始，连续完成八种动作。每一关都有示范，整轮有两分钟有效动作时间。";
    $("start-label").textContent = singleMove ? "开启摄像头玩这关" : "开启摄像头闯八关";
    $("round-metrics").hidden = true;
    $("guide-library").hidden = false;
    $("board-summary").hidden = !latestBoardResult;
    $("stage-heading").textContent = "动作预演";
    $("tracking-caption").textContent = "示范播放中 · 不计分";
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
  for (const item of [{value:"all",name:"八关连闯"}, ...catalog.map(game=>({value:game.moveId,name:game.title}))]) {
    const button = textElement("button", item.name);
    button.value = item.value;
    button.addEventListener("click", () => {
      const hash = item.value==="all" ? "#board" : "#board/"+item.value;
      if (location.hash===hash) {liveStatus=null;renderPreview();} else location.hash=hash;
    });
    $("guide-picker").append(button);
  }
  function endCamera(message, keepResult=false) {
    cameraRequest?.abort();
    cameraRequest = null;
    cameraState = "idle";
    document.querySelectorAll("#guide-picker button").forEach(b => { b.disabled = false; });
    cameraView = false;
    $("start-camera").hidden = false;
    $("stop-camera").hidden = true;
    $("show-camera").disabled = true;
    cameraInfo.textContent = message;
    resetHit();
    if (keepResult) { updateStream(); drawGuide(); }
    else { liveStatus=null; renderPreview(); }
  }
  $("start-camera").addEventListener("click", async () => {
    if (cameraRequest || boardMode) return;
    const request = new AbortController();
    const round = new window.CameraRound(singleMove ? [singleMove] : undefined);
    cameraRequest = request;
    liveStatus = null;
    cameraState = "loading";
    $("start-camera").hidden = true;
    $("stop-camera").hidden = false;
    renderPreview();
    try {
      await window.DeskCamera.start({
        video:$("local-video"), signal:request.signal,
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
        onError:error => { if (!request.signal.aborted) endCamera(error.message || String(error)); }
      });
    } catch (error) { if (!request.signal.aborted) endCamera(error.message || "摄像头启动失败，请重试。"); }
  });
  $("stop-camera").addEventListener("click", () => endCamera("摄像头已关闭。可重新开始一轮。"));
  function stopStream() {
    if (stream.hasAttribute("src")) stream.removeAttribute("src");
  }
  function updateStream() {
    canvas.hidden = cameraView;
    stream.hidden = !boardMode || !cameraView;
    $("local-video").hidden = boardMode || !cameraView;
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
    const online = Boolean(s);
    const local=s?.source==="camera";
    const challenge = s?.challenge || {};
    $("round-metrics").hidden=false;
    $("guide-library").hidden=!(local && s?.phase==="summary");
    $("stage-heading").textContent="玩家舞台";
    $("show-camera").disabled=!s || (local && cameraState!=="playing");
    $("connection").textContent = online ? local ? (s.phase==="summary" ? "回合结束" : "本机摄像头") : "板端已连接" : "正在重连";
    $("connection").classList.toggle("online", online);
    $("phase").textContent = online ? (s.phase === "round" ? (s.act || "体感挑战") : phases[s.phase]) : "等待板端响应";
    const playing = s?.phase === "round";
    let tip = online ? phaseTips[s.phase] : "请确认游戏仍在运行，连接恢复后会自动继续。";
    if (playing) {
      const step = (Number(s.act_i) + 1) + " / " + s.round_len;
      const instruction = challenge.cue || challenge.text;
      $("round-label").textContent = "第 " + step + " 关 · " + ({ready:"准备",play:"跟做",clear:"结算"}[s.sub] || "跟做");
      tip = [s.act_goal,instruction].filter(Boolean).join(" · ");
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
    $("challenge-row").hidden = !playing;
    const fraction = Math.max(0, Math.min(1, Number(s?.challenge?.frac) || 0));
    $("challenge-bar").value = fraction;
    $("challenge-percent").textContent = Number.isFinite(challenge.count) && challenge.target ?
      (challenge.unit==="秒" ? challenge.count.toFixed(1) : Math.floor(challenge.count)) + " / " + challenge.target + " " + challenge.unit : Math.round(fraction * 100) + "%";
    const tracked = Boolean(s?.pose_points?.[11] && s?.pose_points?.[12]);
    $("tracking-caption").textContent = !s ? "正在接入追踪…" : local && s.phase==="summary" ? "本轮已结束" : s.camera_online === false ? "摄像头离线" : playing && challenge.tracking===false ? "等待动作所需部位入镜" : tracked ? "上半身已追踪" : "等待玩家入镜";
    $("tracking-caption").closest(".stage-caption").classList.toggle("tracking", tracked);
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
    $("board-summary").hidden = !latestBoardResult;
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
      if (changeCourse || previousPage!=="board") liveStatus=null;
      singleMove=nextMove;
      guideId=singleMove || "wings";
    }
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
