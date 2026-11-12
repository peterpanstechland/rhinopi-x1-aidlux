/* One music channel follows the current scene. Short effects may overlap it. */
(() => {
  "use strict";
  const tracks = new Set(["lobby", "wings", "flap", "wave", "lean", "piano", "hands_up", "turn", "nod"]);
  const effects = ["start", "hit", "miss", "reward", "fail"];
  const music = new Audio();
  music.loop = true;
  music.preload = "none";
  const musicVolume = 0.34;
  music.volume = musicVolume;
  let enabled = true;
  try { enabled = localStorage.getItem("desk.sound") !== "off"; } catch {}
  let unlocked = false;
  let ambient = "lobby";
  let override; // undefined follows the page, null is a silent scene.
  let loaded = null;
  let audioContext;
  let duckTimer;
  const voices = new Map();

  function refresh() {
    const scene = override === undefined ? ambient : override;
    if (!enabled || !unlocked || document.hidden || !tracks.has(scene)) {
      music.pause();
      return;
    }
    if (loaded !== scene) {
      music.src = "audio/" + scene + ".mp3";
      music.volume = musicVolume;
      loaded = scene;
    }
    if (music.paused) music.play().catch(() => {});
  }

  function unlock() {
    if (!enabled) return;
    if (!unlocked) {
      unlocked = true;
      for (const name of effects) {
        const sound = new Audio("audio/" + name + ".mp3");
        sound.preload = "auto";
        voices.set(name, sound);
      }
    }
    refresh();
  }
  for (const event of ["pointerdown", "click", "keydown"]) {
    document.addEventListener(event, unlock, {capture:true});
  }
  function stopEffects() {
    for (const sound of voices.values()) sound.pause();
    clearTimeout(duckTimer);
    music.volume = musicVolume;
  }
  function enable(value) {
    enabled = Boolean(value);
    try { localStorage.setItem("desk.sound", enabled ? "on" : "off"); } catch {}
    if (enabled) unlock();
    else { stopEffects(); refresh(); }
    window.dispatchEvent(new Event("desk:sound"));
  }
  function cue(name) {
    const sound = voices.get(name);
    if (!sound || !enabled || document.hidden) return;
    if (name === "reward" || name === "fail") {
      for (const short of ["start", "hit", "miss"]) voices.get(short)?.pause();
      music.volume = 0.13;
      clearTimeout(duckTimer);
      duckTimer = setTimeout(() => { music.volume = musicVolume; }, name === "reward" ? 1500 : 1150);
    }
    sound.volume = name === "hit" || name === "miss" ? 0.48 : 0.62;
    sound.currentTime = 0;
    sound.play().catch(() => {});
  }
  function note(index, tenKeys=false) {
    if (!enabled || !unlocked || document.hidden) return;
    const frequency = (tenKeys ? [261.63,293.66,329.63,349.23,392,440,493.88,523.25,587.33,659.25] : [261.63,329.63,392,523.25])[index];
    const Context = window.AudioContext || window.webkitAudioContext;
    if (!frequency || !Context) return;
    audioContext ||= new Context();
    if (audioContext.state === "suspended") audioContext.resume().catch(() => {});
    const oscillator = audioContext.createOscillator();
    const gain = audioContext.createGain();
    const now = audioContext.currentTime;
    oscillator.type = "triangle";
    oscillator.frequency.value = frequency;
    gain.gain.setValueAtTime(0.001, now);
    gain.gain.exponentialRampToValueAtTime(0.22, now + 0.008);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.22);
    oscillator.connect(gain).connect(audioContext.destination);
    oscillator.start(now);
    oscillator.stop(now + 0.23);
  }
  function stopHidden() {
    if (document.hidden) stopEffects();
    refresh();
  }
  document.addEventListener("visibilitychange", stopHidden);
  window.addEventListener("pagehide", () => { music.pause(); stopEffects(); });
  window.addEventListener("pageshow", refresh);
  window.DeskAudio = Object.freeze({
    get enabled() { return enabled; },
    enable, cue, note,
    setBase(value) { if (ambient !== value) { ambient = value; refresh(); } },
    scene(value) { override = value; refresh(); },
    restoreScene() { override = undefined; refresh(); }
  });
})();
