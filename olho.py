import cv2
import time
import pyautogui
import mediapipe as mp

from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# ===== CONFIG =====
CAM_INDEX = 0

BASE_SENS = 800
ACCEL = 2.0
SMOOTH = 0.1
DEAD = 0.0015

DWELL_RADIUS = 15
DWELL_TIME = 0.9
COOLDOWN = 0.7

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

# ===== MEDIAPIPE =====
FaceOptions = vision.FaceLandmarkerOptions(
    base_options=python.BaseOptions(model_asset_path="face_landmarker.task"),
    running_mode=vision.RunningMode.VIDEO,
    num_faces=1
)

face = vision.FaceLandmarker.create_from_options(FaceOptions)

# ===== CAMERA =====
cap = cv2.VideoCapture(CAM_INDEX, cv2.CAP_DSHOW)
cap.set(3, 320)
cap.set(4, 240)

# ===== ESTADO =====
prev_nx, prev_ny = None, None
prev_dx, prev_dy = 0, 0

anchor_x, anchor_y = pyautogui.position()
anchor_time = time.time()

last_click_time = 0
timestamp = 0

def dist(a, b):
    return ((a[0]-b[0])**2 + (a[1]-b[1])**2) ** 0.5

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        timestamp += 1
        result = face.detect_for_video(mp_image, timestamp)

        if result.face_landmarks:
            lm = result.face_landmarks[0]
            nose = lm[1]

            nx, ny = nose.x, nose.y

            if prev_nx is not None:
                dx = nx - prev_nx
                dy = ny - prev_ny

                # zona morta
                if abs(dx) < DEAD:
                    dx = 0
                if abs(dy) < DEAD:
                    dy = 0

                # velocidade + aceleração
                speed = (dx*dx + dy*dy)**0.5
                sens = BASE_SENS + speed * ACCEL * 5000

                move_x = dx * sens
                move_y = dy * sens   # 🔥 DIREÇÃO CORRIGIDA

                # suavização
                move_x = prev_dx + (move_x - prev_dx) * SMOOTH
                move_y = prev_dy + (move_y - prev_dy) * SMOOTH

                # limite (anti salto)
                move_x = max(min(move_x, 50), -50)
                move_y = max(min(move_y, 50), -50)

                pyautogui.moveRel(move_x, move_y)

                prev_dx, prev_dy = move_x, move_y

            prev_nx, prev_ny = nx, ny

            # ===== CLICK POR PARAR =====
            cx, cy = pyautogui.position()

            if dist((cx, cy), (anchor_x, anchor_y)) < DWELL_RADIUS:
                if time.time() - anchor_time > DWELL_TIME:
                    if time.time() - last_click_time > COOLDOWN:
                        pyautogui.click()
                        last_click_time = time.time()
                        anchor_time = time.time()
            else:
                anchor_x, anchor_y = cx, cy
                anchor_time = time.time()

        cv2.imshow("Face Mouse 😏", frame)

        if cv2.waitKey(1) & 0xFF == 27:
            break

finally:
    cap.release()
    cv2.destroyAllWindows()
    face.close()