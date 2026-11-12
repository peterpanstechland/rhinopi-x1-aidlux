(() => {
  "use strict";
  const get = id => document.getElementById(id);
  const dialog = get("opening-dialog");
  const film = get("opening-film");
  const audio = window.DeskAudio;
  const storageKey = "desk.opening.night-shift.seen.v1";
  const followup = get("film-followup");
  const seek = get("film-progress");
  const trial = get("film-trial");
  const sceneEnds = [18,21.5,25,28.5,32,35.5,39,42.5];
  let chosenGame = null;
  let pendingSeek = null;
  let seekableCopy = null;
  let resumeAfterSeek = false;
  const onBoard = document.documentElement.dataset.device === "board";
  const canPlayMotion = location.protocol !== "file:" && window.isSecureContext && Boolean(navigator.mediaDevices?.getUserMedia);
  if (onBoard) {
    get("followup-motion").querySelector("span").textContent = "进入犀牛派体感舞台";
    get("followup-wings").hidden = true;
    get("followup-instruction").textContent = "站到犀牛派摄像头前，跟着小电做本轮抽到的动作。";
  } else if (!canPlayMotion) {
    get("followup-motion").hidden = true;
    get("followup-keys").classList.replace("glass", "primary");
    get("followup-wings").hidden = true;
    get("followup-instruction").textContent = "八张卡带，任选一关，用键盘或触屏开始挑战。";
  }
  function showFollowup(visible) {
    get("lobby-intro").hidden = visible;
    followup.hidden = !visible;
  }
  const stamp = seconds => "00:" + String(Math.floor(seconds)).padStart(2, "0");
  function updateTime() {
    const time = pendingSeek ?? film.currentTime;
    const duration = Number.isFinite(film.duration) ? film.duration : Number(seek.max);
    seek.disabled = !Number.isFinite(film.duration) || Boolean(film.error);
    seek.max = duration;
    seek.value = time;
    seek.setAttribute("aria-valuetext",Math.floor(time)+" 秒，共 "+Math.ceil(duration)+" 秒");
    get("film-time").textContent = stamp(time) + " / " + stamp(Math.ceil(duration));
    const scene = time>=10.05 ? sceneEnds.findIndex(end=>time<end) : -1;
    const game = window.DeskPlay.catalog[scene];
    trial.hidden = !game;
    if (game && trial.dataset.game !== game.id) {
      trial.dataset.game = game.id;
      trial.textContent = "试玩 · "+game.title;
    }
  }
  seek.addEventListener("input", async () => {
    if (seek.disabled) return;
    const target = Number(seek.value);
    if (pendingSeek !== null) {
      pendingSeek = target;
      updateTime();
      return;
    }
    const ranges = film.seekable;
    const inRange = Array.from({length:ranges.length}, (_,i)=>target>=ranges.start(i) && target<=ranges.end(i)).some(Boolean);
    if (!/^https?:/.test(film.currentSrc) || inRange) {
      film.currentTime = target;
      return;
    }
    // Static servers without HTTP Range support can play linearly but cannot
    // seek. Load the MP4 as a seekable local resource only when the player scrubs.
    pendingSeek = target;
    resumeAfterSeek = !film.paused;
    updateTime();
    try {
      if (!seekableCopy) seekableCopy = fetch(film.currentSrc).then(response => {
        if (!response.ok) throw Error("Film unavailable");
        return response.blob();
      }).then(blob => URL.createObjectURL(blob));
      const src = await seekableCopy;
      if (!dialog.open || pendingSeek===null) return;
      if (film.getAttribute("src") !== src) film.src = src;
    } catch {
      seekableCopy = null;
      pendingSeek = null;
      updateTime();
    }
  });
  film.addEventListener("loadedmetadata", () => {
    if (!film.currentSrc.startsWith("blob:") || pendingSeek===null || !dialog.open) return;
    film.currentTime = pendingSeek;
    pendingSeek = null;
    if (resumeAfterSeek) startPlayback();
  });
  trial.addEventListener("click", () => {
    chosenGame = window.DeskPlay.catalog.find(game=>game.id===trial.dataset.game);
    if (chosenGame) dialog.close("play-scene");
  });
  function updateControls() {
    get("film-play").textContent = film.paused ? "播放" : "暂停";
    get("film-audio").textContent = film.muted ? "开启声音" : "关闭声音";
    get("film-audio").setAttribute("aria-pressed", String(!film.muted));
  }
  function startPlayback() {
    const attempt = film.play();
    if (attempt) attempt.catch(() => {
      if (dialog.open && !film.error && film.paused) updateControls();
    });
  }
  function show(gesture = false) {
    if (dialog.open) return;
    showFollowup(false);
    dialog.returnValue = "";
    chosenGame = null;
    pendingSeek = null;
    audio.scene(null);
    get("film-story").open = false;
    if (!film.hasAttribute("src")) {
      film.poster = "cinema/opening-poster.jpg";
      film.src = "cinema/opening.mp4";
    } else if (film.error || (film.currentSrc.startsWith("http") && (film.ended || film.currentTime>0) &&
        (!film.seekable.length || film.seekable.end(0)===0 || film.seekable.start(0)>0))) {
      film.load();
    }
    film.currentTime = 0;
    film.muted = !gesture || !audio.enabled;
    dialog.showModal();
    updateTime();
    updateControls();
    startPlayback();
  }
  get("replay-opening").addEventListener("click", () => show(true));
  get("skip-opening").addEventListener("click", () => dialog.close());
  get("film-story").addEventListener("toggle", event => {
    if (event.currentTarget.open) film.pause();
  });
  get("film-play").addEventListener("click", () => {
    if (film.paused) startPlayback(); else film.pause();
  });
  get("film-audio").addEventListener("click", () => {
    const turnOn = film.muted;
    audio.enable(turnOn);
    film.muted = !turnOn;
    updateControls();
  });
  for (const event of ["loadedmetadata", "timeupdate", "seeked"]) film.addEventListener(event, updateTime);
  for (const event of ["play", "pause", "volumechange"]) film.addEventListener(event, updateControls);
  film.addEventListener("ended", () => { if (dialog.open) dialog.close("play-next"); });
  film.addEventListener("error", () => { get("film-error").hidden = false; });
  film.addEventListener("loadeddata", () => { get("film-error").hidden = true; });
  dialog.addEventListener("close", () => {
    if (dialog.open) return;
    film.pause();
    pendingSeek = null;
    try { localStorage.setItem(storageKey, "yes"); } catch {}
    if (location.hash === "#opening") history.replaceState(null, "", "#lobby");
    audio.restoreScene();
    if (dialog.returnValue === "play-scene" && chosenGame) {
      if (!onBoard && canPlayMotion && get("mode-motion").getAttribute("aria-pressed")==="true") {
        window.dispatchEvent(new CustomEvent("desk:practice",{detail:chosenGame.moveId}));
      } else {
        window.DeskPlay.open(chosenGame.id);
      }
      chosenGame = null;
    } else if (dialog.returnValue === "play-next" && !get("view-lobby").hidden) {
      showFollowup(true);
      get("followup-title").focus();
    }
  });
  window.addEventListener("hashchange", () => {
    showFollowup(false);
    if (location.hash === "#opening") show(true);
    else if (dialog.open) dialog.close();
  });
  document.addEventListener("visibilitychange", () => { if (document.hidden && dialog.open) film.pause(); });
  window.addEventListener("pagehide", () => film.pause());

  let seen = false;
  try { seen = localStorage.getItem(storageKey) === "yes"; } catch {}
  const firstVisit = !seen && !location.hash && !location.search &&
    document.documentElement.dataset.device === "arcade" && !matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (location.hash === "#opening" || firstVisit) show();
})();
