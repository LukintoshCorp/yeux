import cv2
import time
import pyautogui
import mediapipe as mp
import math

from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# ===== CONFIG =====
CAM_INDEX = 0

SMOOTH_BASE = 0.1
COOLDOWN = 0.7
GESTURE_HOLD = 0.5
DWELL_TIME = 1.0

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

screen_w, screen_h = pyautogui.size()

# ===== POSE =====
options = vision.PoseLandmarkerOptions(
    base_options=python.BaseOptions(model_asset_path="pose_landmarker_heavy.task"),
    running_mode=vision.RunningMode.VIDEO
)

pose = vision.PoseLandmarker.create_from_options(options)

cap = cv2.VideoCapture(CAM_INDEX, cv2.CAP_DSHOW)
cap.set(3, 320)
cap.set(4, 240)

prev_x, prev_y = pyautogui.position()

last_click = 0
last_action = 0

anchor = pyautogui.position()
anchor_time = time.time()

# ===== TIMERS =====
click_start = None
scroll_up_start = None
scroll_down_start = None
cross_start = None
alt_start = None

timestamp = 0

# ===== UTILS =====
def dist(a, b):
    return math.sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2)

def valid(p):
    return p.visibility > 0.5

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        timestamp += 1
        result = pose.detect_for_video(mp_image, timestamp)

        if result.pose_landmarks:
            lm = result.pose_landmarks[0]

            rw, lw = lm[16], lm[15]
            rs, ls = lm[12], lm[11]

            if not (valid(rw) and valid(rs) and valid(ls)):
                continue

            now = time.time()

            # ===== NORMALIZAÇÃO =====
            shoulder_height = abs(rs.y - ls.y)

            # ===== ATIVAÇÃO MELHOR =====
            active = rw.y < rs.y and abs(rw.x - rs.x) > 0.08

            if active:

                # ===== MOUSE (SMOOTH ADAPTATIVO) =====
                x = int(rw.x * screen_w)
                y = int((1 - rw.y) * screen_h)

                dx = abs(x - prev_x)
                dy = abs(y - prev_y)
                speed = min((dx + dy) / 50, 1)

                alpha = SMOOTH_BASE + 0.4 * speed

                x = int(prev_x + (x - prev_x) * alpha)
                y = int(prev_y + (y - prev_y) * alpha)

                pyautogui.moveTo(x, y)
                prev_x, prev_y = x, y

                # ===== CLICK (MÃO ACIMA DO OMBRO) =====
                if rw.y < rs.y - shoulder_height * 0.3:
                    if click_start is None:
                        click_start = now
                    else:
                        progress = (now - click_start) / GESTURE_HOLD
                        cv2.rectangle(frame, (20, 200),
                                      (int(20 + 200 * min(progress,1)), 220),
                                      (0,255,0), -1)

                        if now - click_start > GESTURE_HOLD:
                            if now - last_click > COOLDOWN:
                                pyautogui.click()
                                last_click = now
                                click_start = None
                else:
                    click_start = None

                # ===== SCROLL PROPORCIONAL =====
                scroll_power = int((ls.y - lw.y) * 1200)

                if abs(scroll_power) > 50:
                    pyautogui.scroll(scroll_power)

                # ===== DWELL CLICK MELHORADO =====
                cx, cy = pyautogui.position()

                threshold = max(15, int(shoulder_height * screen_h * 0.02))

                if dist((cx, cy), anchor) < threshold:
                    if now - anchor_time > DWELL_TIME:
                        if now - last_click > COOLDOWN:
                            pyautogui.click()
                            last_click = now
                            anchor_time = now
                else:
                    anchor = (cx, cy)
                    anchor_time = now

                # ===== ALT TAB =====
                if rs.x - ls.x > 0.3:
                    if alt_start is None:
                        alt_start = now
                    elif now - alt_start > 0.6:
                        if now - last_action > 1.5:
                            pyautogui.hotkey("alt", "tab")
                            last_action = now
                            alt_start = None
                else:
                    alt_start = None

                # ===== BRAÇOS CRUZADOS (ESC) =====
                crossed = (
                    rw.x < ls.x - 0.05 and
                    lw.x > rs.x + 0.05 and
                    abs(rw.y - lw.y) < shoulder_height * 0.4
                )

                if crossed:
                    if cross_start is None:
                        cross_start = now
                    elif now - cross_start > 0.8:
                        pyautogui.press("esc")
                        cross_start = None
                else:
                    cross_start = None

                # ===== INDICADOR ATIVO =====
                cv2.putText(frame, "ACTIVE", (20, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)

        cv2.imshow("Windows Body OS v4 🔥", frame)

        if cv2.waitKey(1) & 0xFF == 27:
            break

finally:
    cap.release()
    cv2.destroyAllWindows()
    pose.close()