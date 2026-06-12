import cv2
import numpy as np
import mediapipe as mp
import ctypes

from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# ===== CONFIG =====
ALPHA = 0.1       # suavidade
MAX_SPEED = 15    # limita movimento
CONTROL = True    # sempre ativo (simplificar)

# ===== WIN32 =====
user32 = ctypes.windll.user32
screen_w = user32.GetSystemMetrics(0)
screen_h = user32.GetSystemMetrics(1)

def move_mouse(x, y):
    user32.SetCursorPos(int(x), int(y))

# ===== SMOOTH =====
def smooth(new, prev):
    return prev * (1 - ALPHA) + new * ALPHA

def limit_speed(curr, prev):
    dx = curr[0] - prev[0]
    dy = curr[1] - prev[1]
    dist = (dx**2 + dy**2)**0.5

    if dist > MAX_SPEED:
        scale = MAX_SPEED / dist
        dx *= scale
        dy *= scale

    return prev[0] + dx, prev[1] + dy

# ===== MEDIAPIPE =====
face_detector = vision.FaceLandmarker.create_from_options(
    vision.FaceLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path="face_landmarker.task"),
        num_faces=1
    )
)

# ===== CAMERA =====
cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)

if not cam.isOpened():
    print("❌ câmera não abriu")
    exit()

prev_x, prev_y = screen_w//2, screen_h//2

while True:
    ret, frame = cam.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)
    h, w, _ = frame.shape

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

    result = face_detector.detect(mp_image)

    if result.face_landmarks:
        face = result.face_landmarks[0]

        # média da íris
        pts = [474,475,476,477]
        xs = [face[i].x for i in pts]
        ys = [face[i].y for i in pts]

        x = int(np.mean(xs) * w)
        y = int(np.mean(ys) * h)

        screen_x = np.interp(x, (0,w), (0,screen_w))
        screen_y = np.interp(y, (0,h), (0,screen_h))

        curr_x = smooth(screen_x, prev_x)
        curr_y = smooth(screen_y, prev_y)

        curr_x, curr_y = limit_speed((curr_x, curr_y), (prev_x, prev_y))

        if CONTROL:
            move_mouse(curr_x, curr_y)

        prev_x, prev_y = curr_x, curr_y

        cv2.circle(frame, (x, y), 5, (0,255,0), -1)

    cv2.imshow("YEUX V1 - CURSOR", frame)

    if cv2.waitKey(1) == 27:
        break

cam.release()
cv2.destroyAllWindows()