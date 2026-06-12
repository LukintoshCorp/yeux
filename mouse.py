import cv2
import time
import math
import pyautogui
import mediapipe as mp

from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# ===== CONFIG =====
CAM_INDEX = 1

ZONE = (0.25, 0.25, 0.75, 0.75)

SMOOTH_ALPHA = 0.3
DEAD_ZONE = 8
LOW_SPEED = 0.25
HIGH_SPEED = 0.75
DIST_THRESHOLD = 20

# ===== INIT =====
pyautogui.FAILSAFE = False
screen_w, screen_h = pyautogui.size()

# ===== MediaPipe Tasks =====
BaseOptions = python.BaseOptions
HandLandmarker = vision.HandLandmarker
HandLandmarkerOptions = vision.HandLandmarkerOptions
VisionRunningMode = vision.RunningMode

options = HandLandmarkerOptions(
    base_options=BaseOptions(model_asset_path="hand_landmarker.task"),
    running_mode=VisionRunningMode.VIDEO,
    num_hands=1
)

landmarker = HandLandmarker.create_from_options(options)

# ===== CAMERA =====
cap = cv2.VideoCapture(CAM_INDEX, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

# ===== STATE =====
prev_x, prev_y = pyautogui.position()
pinching = False
pinch_start = 0
prev_scroll_y = None
timestamp = 0

# ===== LOOP =====
while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)
    h, w, _ = frame.shape

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

    timestamp += 1
    result = landmarker.detect_for_video(mp_image, timestamp)

    if result.hand_landmarks:
        hand = result.hand_landmarks[0]

        # ===== POSIÇÃO =====
        x = hand[8].x
        y = hand[8].y

        xmin, ymin, xmax, ymax = ZONE

        if xmin < x < xmax and ymin < y < ymax:
            nx = (x - xmin) / (xmax - xmin)
            ny = (y - ymin) / (ymax - ymin)

            ny = 1 - ny

            target_x = int(nx * screen_w)
            target_y = int(ny * screen_h)

            dx = target_x - prev_x
            dy = target_y - prev_y
            dist = math.hypot(dx, dy)

            speed = LOW_SPEED if dist < DIST_THRESHOLD else HIGH_SPEED

            sx = prev_x + dx * speed
            sy = prev_y + dy * speed

            # suavização
            sx = prev_x + (sx - prev_x) * SMOOTH_ALPHA
            sy = prev_y + (sy - prev_y) * SMOOTH_ALPHA

            # zona morta
            if abs(sx - prev_x) > DEAD_ZONE or abs(sy - prev_y) > DEAD_ZONE:
                pyautogui.moveTo(sx, sy)
                prev_x, prev_y = sx, sy

        # ===== PINCH =====
        d_pinch = math.hypot(
            hand[8].x - hand[4].x,
            hand[8].y - hand[4].y
        )

        if d_pinch < 0.05 and not pinching:
            pyautogui.mouseDown()
            pinching = True
            pinch_start = time.time()

        elif d_pinch >= 0.05 and pinching:
            pyautogui.mouseUp()
            if time.time() - pinch_start < 0.2:
                pyautogui.click()
            pinching = False

        # ===== SCROLL =====
        d_scroll = math.hypot(
            hand[8].x - hand[12].x,
            hand[8].y - hand[12].y
        )

        if prev_scroll_y is None:
            prev_scroll_y = y

        delta = y - prev_scroll_y

        if d_scroll < 0.05:
            pyautogui.scroll(int(-delta * 600))

        prev_scroll_y = y

    else:
        prev_x, prev_y = pyautogui.position()
        prev_scroll_y = None
        pinching = False

    # ===== DEBUG =====
    cv2.rectangle(
        frame,
        (int(w * ZONE[0]), int(h * ZONE[1])),
        (int(w * ZONE[2]), int(h * ZONE[3])),
        (0, 255, 0),
        2
    )

    cv2.imshow("Lukintosh Air v3", frame)

    if cv2.waitKey(1) & 0xFF == 27:
        break

    time.sleep(0.01)

cap.release()
cv2.destroyAllWindows()