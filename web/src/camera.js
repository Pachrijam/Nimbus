export function createHandTracking({ cameraVideo, cameraPreview, getInputMode, setInputMode, setStatus, showToast }) {
  const MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task";
  const MEDIAPIPE_VERSION = "1.2.2";

  let handLandmarker = null;
  let cameraStream = null;
  let lastVideoTime = -1;
  let lastHandLandmarks = null;
  let cameraRequest = 0;
  let handTrackingLoad = null;
  let handTrackingStarting = false;
  let cameraError = "";

  function stopCamera() {
    lastVideoTime = -1;
    lastHandLandmarks = null;
    cameraRequest += 1;
    handTrackingStarting = false;
    if (cameraStream) cameraStream.getTracks().forEach((track) => track.stop());
    cameraStream = null;
    cameraVideo.pause();
    cameraVideo.srcObject = null;
    cameraPreview.classList.add("hidden");
  }

  async function enableCamera(request) {
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error("Camera access requires HTTPS or localhost and a browser that supports webcam input.");
    }
    if (!cameraStream) {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } },
      });
      // A permission prompt can finish after the user has switched back to mouse.
      if (request !== cameraRequest) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      cameraStream = stream;
      cameraVideo.srcObject = cameraStream;
      await cameraVideo.play();
      if (request !== cameraRequest) return;
      cameraPreview.classList.remove("hidden");
    }
  }

  async function enableHandTracking() {
    if (getInputMode() === "HAND" || handTrackingStarting) return;
    const request = ++cameraRequest;
    handTrackingStarting = true;
    setStatus("Requesting camera access…");
    try {
      await enableCamera(request);
      if (request !== cameraRequest) return;
      if (!handLandmarker) {
        setStatus("Loading hand-tracking model…");
        if (!handTrackingLoad) {
          handTrackingLoad = (async () => {
            const vision = await import(`https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${MEDIAPIPE_VERSION}`);
            const fileset = await vision.FilesetResolver.forVisionTasks(
              `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${MEDIAPIPE_VERSION}/wasm`,
            );
            const options = {
              baseOptions: { modelAssetPath: MODEL_URL, delegate: "GPU" },
              runningMode: "VIDEO",
              numHands: 1,
            };
            try {
              handLandmarker = await vision.HandLandmarker.createFromOptions(fileset, options);
            } catch {
              handLandmarker = await vision.HandLandmarker.createFromOptions(fileset, {
                ...options,
                baseOptions: { modelAssetPath: MODEL_URL, delegate: "CPU" },
              });
            }
          })().finally(() => {
            handTrackingLoad = null;
          });
        }
        await handTrackingLoad;
      }
      if (request !== cameraRequest) return;
      handTrackingStarting = false;
      cameraError = "";
      setInputMode("HAND");
      setStatus("Draw to the gold destination with one finger, then hold up two fingers to launch. Tracking gaps pause your route.");
    } catch (error) {
      if (request !== cameraRequest) return;
      cameraError = error instanceof Error ? error.message : String(error);
      setInputMode("MOUSE");
      setStatus("Hand tracking could not start. Mouse drawing is ready.");
      showToast(`Camera/hand tracking unavailable: ${cameraError}`);
    }
  }

  function handLandmarks() {
    if (!cameraStream || !handLandmarker || cameraVideo.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) return null;
    // Display refresh can be faster than the camera; infer only on new video frames.
    if (cameraVideo.currentTime === lastVideoTime) return lastHandLandmarks;
    const result = handLandmarker.detectForVideo(cameraVideo, performance.now());
    lastVideoTime = cameraVideo.currentTime;
    lastHandLandmarks = result.landmarks?.[0]?.map(({ x, y }) => ({ x, y })) ?? null;
    return lastHandLandmarks;
  }

  return {
    stopCamera,
    enableHandTracking,
    handLandmarks,
    get active() { return Boolean(cameraStream); },
  };
}
