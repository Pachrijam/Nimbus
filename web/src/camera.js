export function createHandTracking({ cameraVideo, cameraPreview, getInputMode, setInputMode, setStatus, showToast, isFreeDraw = () => false }) {
  const MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task";
  const MEDIAPIPE_VERSION = "1.2.2";

  let handTrackingStarting = false;
  let cameraError = "";
  let currentRequest = 0;
  let sensor = null;
  let lastFrame = null;
  let handLandmarks = [];

  function startCamera() {
    if (!navigator.mediaDevices?.getUserMedia) {
      cameraError = "Camera access is unavailable in this browser.";
      setStatus(cameraError);
      return;
    }
    if (!cameraVideo) return;
    navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } }).then((stream) => {
      cameraVideo.srcObject = stream;
      cameraVideo.play();
      sensor = stream.getVideoTracks()[0];
      cameraError = "";
    }).catch((error) => {
      cameraError = error.message;
      setStatus(`Camera access failed: ${cameraError}`);
      showToast(cameraError, 8000);
    });
  }

  function stopCamera() {
    if (sensor) {
      sensor.stop();
      sensor = null;
    }
    if (cameraVideo?.srcObject) {
      cameraVideo.srcObject.getTracks().forEach((track) => track.stop());
      cameraVideo.srcObject = null;
    }
  }

  function enableHandTracking() {
    const request = ++currentRequest;
    handTrackingStarting = true;
    setInputMode("HAND");
    startCamera();
    setStatus(isFreeDraw()
      ? "Free draw: one finger draws; two or more change color. U undoes, C clears; Esc or P returns."
      : "Draw a route from the drone with one finger, then hold up two or more fingers to launch. Tracking gaps pause your route.");
  }

  function handLandmarksForFrame() {
    return handLandmarks;
  }

  return {
    active: !!cameraVideo?.srcObject,
    aspectRatio: 1,
    handLandmarks: handLandmarksForFrame,
    stopCamera,
    enableHandTracking,
  };
}
