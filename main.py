"""Application entry point for the Nimbus flight-path game."""
from pathlib import Path
import time

import cv2

import freedraw
import game
import gestures


CAM_WIDTH = 640
CAM_HEIGHT = 480
WINDOW_NAME = "Nimbus: Flight Path"
MODEL_PATH = Path(__file__).with_name("hand_landmarker.task")


def main():
    """Run the camera, gesture-recognition, and game-rendering loop."""
    camera = None
    landmarker = None
    try:
        if MODEL_PATH.is_file():
            try:
                import mediapipe as mp
                from mediapipe.tasks import python as mp_python
                from mediapipe.tasks.python import vision
            except ImportError:
                print("MediaPipe Tasks is required for hand drawing. Install mediapipe and restart.")
                return
            else:
                options = vision.HandLandmarkerOptions(
                    base_options=mp_python.BaseOptions(model_asset_path=str(MODEL_PATH)),
                    running_mode=vision.RunningMode.VIDEO,
                    num_hands=1,
                )
                landmarker = vision.HandLandmarker.create_from_options(options)
        else:
            print(f"{MODEL_PATH.name} is required for hand drawing. Add it beside main.py and restart.")
            return

        free_draw_mode = False
        fullscreen = False
        debug = False
        previous_time = time.monotonic()
        previous_timestamp_ms = 0

        width, height = CAM_WIDTH, CAM_HEIGHT
        flight_game = game.Game(width, height)
        free_draw = freedraw.FreeDraw(width, height)

        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
        camera = cv2.VideoCapture(0)
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        while True:
            success, frame = camera.read()
            if not success:
                print("Webcam unavailable. Check camera access and restart to draw with your hand.")
                break
            frame = cv2.resize(cv2.flip(frame, 1), (width, height))
            now = time.monotonic()
            dt = min(now - previous_time, 0.05)
            previous_time = now

            timestamp_ms = max(int(now * 1000), previous_timestamp_ms + 1)
            previous_timestamp_ms = timestamp_ms
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = landmarker.detect_for_video(
                mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame),
                timestamp_ms,
            )
            landmarks = result.hand_landmarks[0] if result.hand_landmarks else None
            mode, point = gestures.get_gesture(landmarks, width, height, dt=dt)

            if free_draw_mode:
                free_draw.update(mode, point)
                output = free_draw.draw(frame)
            else:
                flight_game.update(mode, point, dt, gesture_input=True)
                output = flight_game.draw(frame)

            if debug:
                cv2.putText(
                    output,
                    f"mode={mode}",
                    (10, height - 15),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 0, 0),
                    2,
                    cv2.LINE_AA,
                )

            cv2.imshow(WINDOW_NAME, output)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("p"):
                free_draw_mode = not free_draw_mode
                free_draw.end_stroke()
                gestures.reset()
            elif key == 27 and free_draw_mode:
                free_draw_mode = False
                free_draw.end_stroke()
                gestures.reset()
            elif key == ord("f"):
                fullscreen = not fullscreen
                cv2.setWindowProperty(
                    WINDOW_NAME,
                    cv2.WND_PROP_FULLSCREEN,
                    cv2.WINDOW_FULLSCREEN if fullscreen else cv2.WINDOW_NORMAL,
                )
            elif key == ord("r") and not free_draw_mode:
                flight_game.retry()
            elif key == ord("n") and not free_draw_mode:
                flight_game.next_level()
            elif key == ord("v") and not free_draw_mode:
                flight_game.show_autopilot = not flight_game.show_autopilot
            elif key == ord("c") and free_draw_mode:
                free_draw.clear()
            elif key == ord("d"):
                debug = not debug
    finally:
        try:
            if landmarker is not None:
                landmarker.close()
        finally:
            if camera is not None:
                camera.release()
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
 
