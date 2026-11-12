/* Local camera input. The game requests access only after a player selects camera play. */
(() => {
  "use strict";
  const files = new URL("vendor/mediapipe/", document.currentScript.src);
  const file = name => new URL(name, files).href;
  const joints = [0, 11, 12, 13, 14, 15, 16];
  let activeStop = null;
  let modelQueue = Promise.resolve();

  function poseFrame(landmarks, aspect, time) {
    const points = Array(25).fill(null);
    for (const i of joints) {
      const p = landmarks?.[i];
      if (p && p.visibility >= 0.5 && p.x >= 0 && p.x <= 1 && p.y >= 0 && p.y <= 1) {
        points[i] = [1 - p.x, p.y];
      }
    }
    const tracked = Boolean(points[11] && points[12] && Math.abs(points[11][0] - points[12][0]) > 0.035);
    if (tracked && points[11][0] > points[12][0]) {
      for (const left of [11, 13, 15]) {
        [points[left], points[left + 1]] = [points[left + 1], points[left]];
      }
    }
    return {pose_points: tracked ? points : [], pose_aspect: aspect, tracked, time};
  }

  const cancelError = () => new DOMException("已关闭体感摄像头。", "AbortError");
  const cameraErrors = {
    NotAllowedError: "摄像头权限未获准。请在浏览器的站点权限中允许摄像头后重试。",
    NotFoundError: "未找到可用摄像头，请接入设备后重试。",
    NotReadableError: "摄像头当前无法读取，请关闭占用它的应用后重试。",
    SecurityError: "当前页面没有摄像头权限。请在 localhost 或 HTTPS 页面中打开。",
  };

  async function start({video, onFrame, onStatus, onError, signal, getAction=()=>""}) {
    if (signal?.aborted) throw cancelError();
    if (location.protocol === "file:" || !window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      throw new Error("摄像头体感需要 localhost 或 HTTPS。请从本机试玩地址打开，再启动摄像头。");
    }
    activeStop?.();
    let stopped = false, stream = null, request = 0;
    const detectors = new Map();
    let rejectPending;
    const cancelled = new Promise((_, reject) => { rejectPending = reject; });
    // The signal can arrive after startup or while the user is choosing a camera.
    cancelled.catch(() => {});
    function stop() {
      if (stopped) return;
      stopped = true;
      rejectPending(cancelError());
      signal?.removeEventListener("abort", stop);
      window.removeEventListener("pagehide", stop);
      document.removeEventListener("visibilitychange", visibility);
      cancelAnimationFrame(request);
      if (stream) {
        for (const track of stream.getTracks()) {
          track.removeEventListener("ended", disconnect);
          track.stop();
        }
        if (video.srcObject === stream) {
          video.pause();
          video.srcObject = null;
        }
      }
      for (const detector of detectors.values()) detector.close();
      detectors.clear();
      if (activeStop === stop) activeStop = null;
    }
    function fail(message) {
      if (stopped) return;
      stop();
      onError?.(new Error(message));
    }
    function disconnect() { fail("摄像头已断开，请重新接入并开启体感。"); }
    function visibility() {
      if (document.hidden) fail("摄像头已暂停，回到页面后可重新开启体感。");
    }
    activeStop = stop;
    signal?.addEventListener("abort", stop, {once:true});
    window.addEventListener("pagehide", stop, {once:true});
    document.addEventListener("visibilitychange", visibility);

    // Media permission prompts and WASM initialisation can finish after the dialog closes.
    // Dispose late arrivals instead of attaching them to a different game.
    async function acquire(promise, release) {
      return Promise.race([cancelled, promise.then(value => {
        if (stopped) { release(value); throw cancelError(); }
        return value;
      })]);
    }
    const kind = () => getAction()==="piano" ? "hands" : "pose";
    async function load(kind) {
      onStatus?.(kind==="hands" ? "正在启动十指骨骼识别…" : "正在启动本地姿态识别…");
      const loading=modelQueue.then(async () => {
        if (stopped) throw cancelError();
        const {PoseLandmarker,HandLandmarker}=await import(file("vision_bundle.mjs"));
        if (stopped) throw cancelError();
        const hands=kind==="hands", task=hands ? HandLandmarker : PoseLandmarker;
        return task.createFromOptions({
          wasmLoaderPath:file("vision_wasm_nosimd_internal.js"),wasmBinaryPath:file("vision_wasm_nosimd_internal.wasm")
        },{baseOptions:{modelAssetPath:file(hands?"hand_landmarker.task":"pose_landmarker_lite.task"),delegate:"CPU"},
          runningMode:"VIDEO",...(hands?{numHands:2}:{numPoses:1,outputSegmentationMasks:false})});
      });
      modelQueue=loading.catch(()=>{});
      const detector=await acquire(loading, model=>model.close());
      if (stopped) {detector.close();throw cancelError();}
      detectors.set(kind,detector);
    }
    let stage = "camera";
    try {
      onStatus?.("等待摄像头授权…");
      const camera = navigator.mediaDevices.getUserMedia({
        audio:false,
        video:{facingMode:{ideal:"user"},width:{ideal:640},height:{ideal:480},frameRate:{ideal:20,max:30}},
      });
      stream = await acquire(camera, s => s.getTracks().forEach(track => track.stop()));
      if (stopped) { stream.getTracks().forEach(track => track.stop()); throw cancelError(); }
      const track = stream.getVideoTracks()[0];
      if (!track || track.readyState === "ended") throw new Error("摄像头已断开。");
      track.addEventListener("ended", disconnect, {once:true});
      video.muted = true;
      video.playsInline = true;
      video.srcObject = stream;
      await Promise.race([video.play(), cancelled]);
      stage = "model";
      await load(kind());
      onStatus?.(kind()==="hands" ? "两掌朝向镜头，十指自然张开。" : "面向摄像头，让双肩和双手进入画面。");
      let lastMediaTime = -1, lastInference = -Infinity, lastFresh = performance.now(), lostReported = false;
      async function tick(now) {
        if (stopped) return;
        const aspect = video.videoWidth / video.videoHeight || 4 / 3;
        const fresh = !track.muted && video.readyState >= 2 && video.currentTime !== lastMediaTime;
        if (fresh && now - lastInference >= 65) {
          lastInference = now;
          lastMediaTime = video.currentTime;
          lastFresh = now;
          lostReported = false;
          const type=kind();
          try {
            if (!detectors.has(type)) await load(type);
            if (stopped) return;
            const result=detectors.get(type).detectForVideo(video,now);
            if (type==="hands") {
              const hand_points=result.landmarks.map(hand=>hand.map(p=>[1-p.x,p.y]));
              onFrame({hand_points,pose_points:[],pose_aspect:aspect,time:now});
            } else onFrame(poseFrame(result.landmarks[0],aspect,now));
          } catch {
            if (!stopped) fail(type==="hands" ? "手部识别中断，请重新开启摄像头或切换按键试玩。" : "本地姿态识别中断，请重新开启体感。");
            return;
          }
        } else if (!lostReported && now - lastFresh > 450) {
          lostReported = true;
          onFrame(poseFrame(null, aspect, now));
        }
        if (!stopped) request = requestAnimationFrame(tick);
      }
      request = requestAnimationFrame(tick);
      return {stop};
    } catch (error) {
      stop();
      if (error.name === "AbortError") throw error;
      if (stage === "model") throw new Error((kind()==="hands"?"手部":"姿态")+"模型未能启动。请从 localhost 或 HTTPS 打开，并保留完整的游戏资源。", {cause:error});
      throw new Error(cameraErrors[error.name] || "摄像头未能启动，请检查设备后再试。", {cause:error});
    }
  }
  window.DeskCamera = Object.freeze({start});
})();
