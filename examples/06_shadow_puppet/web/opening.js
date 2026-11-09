(() => {
  "use strict";
  const get = id => document.getElementById(id);
  const dialog = get("opening-dialog");
  const film = get("opening-film");
  const audio = window.DeskAudio;
  const storageKey = "desk.opening.seen.v1";
  const captions = [
    [0, "「最后改一行。」"],
    [1.78, "编译通过。"],
    [3.3, ""],
    [4, "还有一个 bug。"],
    [5.15, ""],
    [7.85, "「哎，我的回车！」"],
    [9.65, ""],
    [15.8, "呼……"],
    [16.55, ""],
    [17.86, "「我就再按一……」"],
    [18.95, ""],
    [22, "稍后回来。"]
  ];
  const stamp = seconds => "00:" + String(Math.floor(seconds)).padStart(2, "0");
  function updateTime() {
    const time = film.currentTime;
    const duration = Number.isFinite(film.duration) ? film.duration : Number(get("film-progress").max);
    get("film-progress").max = duration;
    get("film-progress").value = time;
    get("film-time").textContent = stamp(time) + " / " + stamp(Math.ceil(duration));
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
