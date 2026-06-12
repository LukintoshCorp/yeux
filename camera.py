import cv2
import numpy as np
import mediapipe as mp
import ctypes
import time

from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# CONFIG
ALPHA = 0.15
DEADZONE = 6
MAX_SPEED = 25
CLICK_DELAY = 0.8

CONTROL_ACTIVE = False

# WIN32
user32 = ctypes.windll.user32
screen_w = user32.GetSystemMetrics(0)
screen_h = user32.GetSystemMetrics(1)

def move_mouse(x, y):
    user32.SetCursorPos(int(x), int(y))

def click():
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.01)
    user32.mouse_event(0x0004, 0, 0, 0, 0)

# SMOOTH
def smooth(new, prev):
    return prev * (1 - ALPHA) + new * ALPHA

def deadzone(curr, prev):
    if abs(curr - prev) < DEADZONE:
        return prev
    return curr

def limit_speed(curr, prev):
    dx = curr[0] - prev[0]
    dy = curr[1] - prev[1]
    dist = (dx**2 + dy**2)**0.5

    if dist > MAX_SPEED:
        scale = MAX_SPEED / dist
        dx *= scale
        dy *= scale

    return prev[0] + dx, prev[1] + dy

# MEDIAPIPE
face_detector = vision.FaceLandmarker.create_from_options(
    vision.FaceLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path="face_landmarker.task"),
        num_faces=1
    )
)

hand_detector = vision.HandLandmarker.create_from_options(
    vision.HandLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path="hand_landmarker.task"),
        num_hands=1
    )
)

# CAMERA
cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)

if not cam.isOpened():
    print("❌ câmera não abriu")
    exit()

prev_x, prev_y = screen_w//2, screen_h//2
last_click_time = 0

print("Pressione E para ativar/desativar")
print("Pressione ESC para sair")

while True:
    ret, frame = cam.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)
    h, w, _ = frame.shape

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

    # FACE
    face_result = face_detector.detect(mp_image)

    if face_result.face_landmarks:
        face = face_result.face_landmarks[0]

        eye_pts = [474,475,476,477]
        xs = [face[i].x for i in eye_pts]
        ys = [face[i].y for i in eye_pts]

        x = int(np.mean(xs) * w)
        y = int(np.mean(ys) * h)

        screen_x = np.interp(x, (0,w), (0,screen_w))
        screen_y = np.interp(y, (0,h), (0,screen_h))

        curr_x = smooth(screen_x, prev_x)
        curr_y = smooth(screen_y, prev_y)

        curr_x = deadzone(curr_x, prev_x)
        curr_y = deadzone(curr_y, prev_y)

        curr_x, curr_y = limit_speed((curr_x, curr_y), (prev_x, prev_y))

        if CONTROL_ACTIVE:
            move_mouse(curr_x, curr_y)

        prev_x, prev_y = curr_x, curr_y

        cv2.circle(frame, (x, y), 5, (0,255,0), -1)

    # HAND CLICK
    hand_result = hand_detector.detect(mp_image)

    if hand_result.hand_landmarks:
        hand = hand_result.hand_landmarks[0]

        index = hand[8]
        thumb = hand[4]

        dist = ((index.x - thumb.x)**2 + (index.y - thumb.y)**2)**0.5

        if CONTROL_ACTIVE and dist < 0.03:
            if time.time() - last_click_time > CLICK_DELAY:
                click()
                last_click_time = time.time()

    # STATUS
    text = "ATIVO" if CONTROL_ACTIVE else "PAUSADO"
    color = (0,255,0) if CONTROL_ACTIVE else (0,0,255)

    cv2.putText(frame, text, (10,30),
                cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)

    cv2.imshow("YEUX CAMERA", frame)

    key = cv2.waitKey(1)

    if key == 27:
        break

    if key == ord('e'):
        CONTROL_ACTIVE = not CONTROL_ACTIVE

cam.release()
cv2.destroyAllWindows()