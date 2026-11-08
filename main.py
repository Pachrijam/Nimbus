import cv2
import numpy as np

from game import Session
from gotypes import event


def main():
    session = Session()
    free_draw = cv2.namedWindow("Nimbus", cv2.WINDOW_NORMAL)
    free_draw_mode = False

    while True:
        key = cv2.waitKey(30) & 0xFF
        if key == ord("q"):
            break
        if key == ord("p"):
            free_draw_mode = not free_draw_mode
            free_draw.end_stroke()
            session.game.reset_gesture_state()
        elif key == 27 and free_draw_mode:
            free_draw_mode = False
            free_draw.end_stroke()
            session.game.reset_gesture_state()
        elif key == ord("f"):
            fullscreen = not fullscreen
            cv2.setWindowProperty("Nimbus", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL if not fullscreen else cv2.WINDOW_FULLSCREEN)

        frame = session.render()
        if free_draw_mode:
            frame = free_draw.draw(frame)
        cv2.imshow("Nimbus", frame)


if __name__ == "__main__":
    main()
