(() => {
  "use strict";
  const get = id => document.getElementById(id);
  const dialog = get("opening-dialog");
  const film = get("opening-film");
  const audio = window.DeskAudio;
  const storageKey = "desk.opening.seen.v1";
  const captions = [
    [0, "凌晨，工作台的灯还亮着。"],
    [2.4, "大胡子在键盘和电路板之间忙了一夜，困得趴在了桌上。"],
    [7.4, "时间慢了下来。肩膀越缩越紧，他扶住了腰。"],
    [11.9, "屏幕里跳出一个小家伙。小电伸出手，拉他起身。"],
    [16.9, "跟着小电，先平举双臂，再一起扇动。"],
    [20.1, "挥一挥手，向侧面倾身滑过旗门。"],
    [23.3, "指尖敲下琴键，看准时机跳起来。"],
    [26.5, "向两侧转头、回正，最后跟着节拍点头。"],
    [29.7, "击掌！该你上场了。"]
  ];
  const stamp = seconds => "00:" + String(Math.floor(seconds)).padStart(2, "0");
  function updateTime() {
    const time = film.currentTime;
    const duration = Number.isFinite(film.duration) ? film.duration : 32;
    get("film-progress").max = duration;
    get("film-progress").value = time;
    get("film-time").textContent = stamp(time) + " / " + stamp(duration);
    if (!film.error) {
      let caption = captions[0][1];
      for (const [at, text] of captions) { if (at > time) break; caption = text; }
      get("film-caption").textContent = caption;
    }
  }
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
    audio.scene(null);
    if (!film.hasAttribute("src")) {
      film.poster = "cinema/opening-poster.jpg";
      film.src = "cinema/opening.mp4";
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
  film.addEventListener("ended", () => { if (dialog.open) dialog.close(); });
  film.addEventListener("error", () => {
    get("film-caption").textContent = "片头视频未能载入，可以跳过并进入游戏。";
  });
  dialog.addEventListener("close", () => {
    film.pause();
    try { localStorage.setItem(storageKey, "yes"); } catch {}
    if (location.hash === "#opening") history.replaceState(null, "", "#lobby");
    audio.restoreScene();
  });
  window.addEventListener("hashchange", () => {
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
