import cv2
import sys

HEADLESS_MODE = "--headless" in sys.argv

if HEADLESS_MODE:
    cv2.namedWindow = lambda *args, **kwargs: None
    cv2.imshow = lambda *args, **kwargs: None
    cv2.waitKey = lambda *args, **kwargs: -1
    cv2.destroyAllWindows = lambda *args, **kwargs: None
import time
import math
import json
import onnxruntime as ort
import queue
import threading
import traceback
import os
import platform
import ctypes
from ctypes import wintypes
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict, Any
from yeux_input_contract import YeuxMouseEvent
from yeux_input_backend import create_backend
import numpy as np
import pyautogui
from screeninfo import get_monitors



import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

YEUX_NATIVE_AVAILABLE = False
yeux_native = None

try:
    yeux_native = ctypes.CDLL(r"C:\Users\lucas\Videos\mouse-invisível\YeuxNativeCore.dll")

    yeux_native.yeux_update_cursor.argtypes = [
        ctypes.c_double,
        ctypes.c_double,
        ctypes.c_double,
        ctypes.c_double,
        ctypes.c_double,
        ctypes.c_double,
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
    ]

    yeux_native.yeux_update_cursor.restype = None

    YEUX_NATIVE_AVAILABLE = True
    print("YeuxNativeCore carregado")
except Exception as e:
    print("YeuxNativeCore não carregou:", e)
# ============================================================
# YEUX HYPERPRODUCT DEMO
# ============================================================
#
# Controle:
# - rosto/cabeça = movimento base
# - pupila/íris = intenção fina
# - olhar para baixo = taskbar intent
# - SendInput/SetCursorPos = input mais parecido com mouse real
# - Taskbar Hover Freeze = hover funciona melhor
# - Dwell Click = clicar olhando
# - Blink Click = clicar piscando
#
# Comandos:
# Q / ESC -> sair
# P       -> pausar
# R       -> recalibrar
# S       -> salvar calibração
# L       -> carregar calibração
# C       -> blink click on/off
# D       -> dwell click on/off
# F       -> fast/balanced
# B       -> edge assist on/off
# U       -> taskbar hover freeze on/off
# A       -> auto-hide taskbar mode on/off
# M       -> métricas on/off
# H       -> ajuda on/off
# T       -> sobe linha da taskbar
# Y       -> desce linha da taskbar
#
# ============================================================


# ============================================================
# DPI AWARENESS
# ============================================================

def make_process_dpi_aware() -> None:
    if platform.system().lower() != "windows":
        return

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


make_process_dpi_aware()


# ============================================================
# PYAUTOGUI LOW LATENCY FALLBACK
# ============================================================

pyautogui.PAUSE = 0
pyautogui.MINIMUM_DURATION = 0
pyautogui.MINIMUM_SLEEP = 0
pyautogui.FAILSAFE = False


# ============================================================
# WINDOWS INPUT STRUCTS
# ============================================================

ULONG_PTR = ctypes.POINTER(ctypes.c_ulong)


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("union", INPUT_UNION),
    ]


# ============================================================
# WINDOWS MOUSE ENGINE
# ============================================================

class WindowsMouseEngine:
    INPUT_MOUSE = 0

    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    MOUSEEVENTF_RIGHTDOWN = 0x0008
    MOUSEEVENTF_RIGHTUP = 0x0010
    MOUSEEVENTF_WHEEL = 0x0800

    def __init__(self) -> None:
        self.is_windows = platform.system().lower() == "windows"

        if self.is_windows:
            self.user32 = ctypes.windll.user32
        else:
            self.user32 = None

    def move_to(self, x: int, y: int) -> None:
        x = int(x)
        y = int(y)

        if self.is_windows:
            self.user32.SetCursorPos(x, y)
        else:
            pyautogui.moveTo(x, y)

    def get_pos(self) -> Tuple[int, int]:
        if self.is_windows:
            pt = wintypes.POINT()
            self.user32.GetCursorPos(ctypes.byref(pt))
            return int(pt.x), int(pt.y)

        x, y = pyautogui.position()
        return int(x), int(y)

    def _send_mouse_event(self, flags: int) -> None:
        if not self.is_windows:
            return

        extra = ctypes.c_ulong(0)

        mouse_input = MOUSEINPUT(
            dx=0,
            dy=0,
            mouseData=0,
            dwFlags=flags,
            time=0,
            dwExtraInfo=ctypes.pointer(extra),
        )

        input_union = INPUT_UNION()
        input_union.mi = mouse_input

        command = INPUT(
            type=self.INPUT_MOUSE,
            union=input_union,
        )

        self.user32.SendInput(
            1,
            ctypes.byref(command),
            ctypes.sizeof(command),
        )

    def left_click(self) -> None:
        if self.is_windows:
            self._send_mouse_event(self.MOUSEEVENTF_LEFTDOWN)
            time.sleep(0.035)
            self._send_mouse_event(self.MOUSEEVENTF_LEFTUP)
        else:
            pyautogui.click()

    def right_click(self) -> None:
        if self.is_windows:
            self._send_mouse_event(self.MOUSEEVENTF_RIGHTDOWN)
            time.sleep(0.035)
            self._send_mouse_event(self.MOUSEEVENTF_RIGHTUP)
        else:
            pyautogui.rightClick()

def scroll(self, amount: int) -> None:
    if not self.is_windows:
        pyautogui.scroll(amount)
        return

    extra = ctypes.c_ulong(0)

    mouse_input = MOUSEINPUT(
        dx=0,
        dy=0,
        mouseData=amount,
        dwFlags=self.MOUSEEVENTF_WHEEL,
        time=0,
        dwExtraInfo=ctypes.pointer(extra),
    )

    input_union = INPUT_UNION()
    input_union.mi = mouse_input

    command = INPUT(
        type=self.INPUT_MOUSE,
        union=input_union,
    )

    self.user32.SendInput(
        1,
        ctypes.byref(command),
        ctypes.sizeof(command),
    )
# ============================================================
# CONFIG
# ============================================================

@dataclass
class CameraConfig:
    index: int = 0
    width: int = 320
    height: int = 240
    fps: int = 15
    mirror: bool = True
    use_dshow_on_windows: bool = True
    mirror: bool = True
    use_dshow_on_windows: bool = True


@dataclass
class ModelConfig:
    model_path: str = "face_landmarker.task"
    max_num_faces: int = 1
    output_face_blendshapes: bool = True
    output_facial_transformation_matrixes: bool = False


@dataclass
class FusionConfig:
    eye_gain_x: float = 0.110
    eye_gain_y: float = 0.185

    taskbar_gaze_threshold: float = 0.62
    taskbar_gaze_boost: float = 0.080

    top_gaze_threshold: float = 0.36
    top_gaze_boost: float = 0.045

    gaze_deadzone: float = 0.030
    allow_head_only_fallback: bool = True


@dataclass
class CursorConfig:
    margin: int = 0

    deadzone: float = 0.006

    slow_alpha: float = 0.10
    fast_alpha: float = 0.56

    accel: float = 0.108
    friction: float = 0.68
    max_velocity: float = 0.056

    sleep_seconds: float = 0.010

    edge_assist_enabled: bool = True
    edge_assist_zone: float = 0.032

    taskbar_boost_zone: float = 0.125
    taskbar_snap_zone: float = 0.085
    taskbar_hover_y: int = 48

    auto_hide_taskbar_mode: bool = False
    auto_hide_reveal_ms: float = 210.0

    taskbar_lock_enabled: bool = True
    taskbar_lock_min_ms: float = 420.0
    taskbar_lock_move_reset_px: int = 14

    move_epsilon_px: int = 3

    top_safe_y: int = 2
    left_safe_x: int = 2
    right_safe_padding: int = 3

    clamp_min: float = 0.0
    clamp_max: float = 1.0


@dataclass
class CalibrationConfig:
    duration_seconds: float = 9.0
    min_span_x: float = 0.020
    min_span_y: float = 0.020
    auto_finish: bool = True
    file_path: str = "yeux_hyper_calibration.json"


@dataclass
class BlinkConfig:
    enabled: bool = True
    blink_threshold: float = 0.45
    double_blink_max_gap: float = 0.42
    blink_cooldown: float = 0.75
    use_double_blink: bool = True


@dataclass
class DwellClickConfig:
    enabled: bool = False
    dwell_time_ms: float = 850.0
    cooldown_ms: float = 900.0
    radius_px: int = 18
    taskbar_dwell_time_ms: float = 650.0
    show_ring: bool = True


@dataclass
class OverlayConfig:
    window_name: str = "Yeux HyperProduct Demo"
    show_metrics: bool = True
    show_help: bool = True
    show_crosshair: bool = True
    show_edge_zones: bool = True
    show_pupil_debug: bool = True


@dataclass
class DemoConfig:
    camera: CameraConfig = field(default_factory=CameraConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    fusion: FusionConfig = field(default_factory=FusionConfig)
    cursor: CursorConfig = field(default_factory=CursorConfig)
    calibration: CalibrationConfig = field(default_factory=CalibrationConfig)
    blink: BlinkConfig = field(default_factory=BlinkConfig)
    dwell: DwellClickConfig = field(default_factory=DwellClickConfig)
    overlay: OverlayConfig = field(default_factory=OverlayConfig)
    headless: bool = "--headless" in sys.argv
    fast_mode: bool = True
    log_file: str = "yeux_hyper_metrics.jsonl"
    use_onnx: bool = "--onnx" in sys.argv
onnx_model_path: str = r"models\MediaPipeFaceLandmarkDetector.onnx"


# ============================================================
# UTILS
# ============================================================

def perf_ms() -> float:
    return time.perf_counter() * 1000.0


def epoch_s() -> float:
    return time.time()


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def lerp(a: float, b: float, t: float) -> float:
    return a * (1.0 - t) + b * t


def safe_div(a: float, b: float, default: float = 0.0) -> float:
    if abs(b) < 1e-9:
        return default
    return a / b


def put_text(
    frame: np.ndarray,
    text: str,
    xy: Tuple[int, int],
    scale: float = 0.55,
    color: Tuple[int, int, int] = (255, 255, 255),
    thickness: int = 1,
) -> None:
    cv2.putText(
        frame,
        text,
        xy,
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        color,
        thickness,
        cv2.LINE_AA,
    )


def draw_panel(
    frame: np.ndarray,
    x: int,
    y: int,
    w: int,
    h: int,
    alpha: float = 0.56,
) -> None:
    overlay = frame.copy()
    cv2.rectangle(overlay, (x, y), (x + w, y + h), (12, 12, 12), -1)
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
    cv2.rectangle(frame, (x, y), (x + w, y + h), (90, 90, 90), 1)


def draw_badge(
    frame: np.ndarray,
    text: str,
    x: int,
    y: int,
    color: Tuple[int, int, int],
) -> None:
    text_size, _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.48, 1)
    tw, th = text_size
    pad_x = 10
    pad_y = 7

    cv2.rectangle(
        frame,
        (x, y - th - pad_y),
        (x + tw + pad_x * 2, y + pad_y),
        color,
        -1,
    )

    put_text(
        frame,
        text,
        (x + pad_x, y),
        scale=0.48,
        color=(0, 0, 0),
        thickness=1,
    )


# ============================================================
# LATEST QUEUE
# ============================================================

class LatestQueue:
    def __init__(self) -> None:
        self.q: queue.Queue = queue.Queue(maxsize=1)

    def put(self, item: Any) -> None:
        try:
            while self.q.full():
                self.q.get_nowait()
            self.q.put_nowait(item)
        except Exception:
            pass

    def get(self, timeout: Optional[float] = None) -> Any:
        return self.q.get(timeout=timeout)

    def get_nowait(self) -> Any:
        return self.q.get_nowait()


# ============================================================
# METRICS
# ============================================================

class RollingMetric:
    def __init__(self, size: int = 90) -> None:
        self.size = size
        self.values: List[float] = []

    def add(self, value: float) -> None:
        self.values.append(float(value))
        if len(self.values) > self.size:
            self.values.pop(0)

    def avg(self) -> float:
        if not self.values:
            return 0.0
        return float(sum(self.values) / len(self.values))

    def latest(self) -> float:
        if not self.values:
            return 0.0
        return float(self.values[-1])


class FPSCounter:
    def __init__(self) -> None:
        self.last = perf_ms()
        self.metric = RollingMetric(60)

    def tick(self) -> float:
        now = perf_ms()
        dt = now - self.last
        self.last = now

        if dt > 0:
            self.metric.add(1000.0 / dt)

        return self.metric.avg()


# ============================================================
# STATE
# ============================================================

@dataclass
class SharedState:
    running: bool = True
    paused: bool = False

    has_face: bool = False
    has_iris: bool = False

    calibrated: bool = False
    calibrating: bool = True

    blink_click_enabled: bool = True
    dwell_click_enabled: bool = False

    fast_mode: bool = True
    edge_assist_enabled: bool = True
    taskbar_lock_enabled: bool = False
    auto_hide_taskbar_mode: bool = False

    show_metrics: bool = True
    show_help: bool = True

    fps_capture: float = 0.0
    fps_vision: float = 0.0
    fps_cursor: float = 0.0

    latency_total_ms: float = 0.0
    latency_vision_ms: float = 0.0
    latency_cursor_ms: float = 0.0

    confidence: float = 0.0

    cursor_norm_x: float = 0.5
    cursor_norm_y: float = 0.5

    target_norm_x: float = 0.5
    target_norm_y: float = 0.5

    raw_norm_x: float = 0.5
    raw_norm_y: float = 0.5

    head_x: float = 0.5
    head_y: float = 0.5

    iris_x: float = 0.5
    iris_y: float = 0.5

    gaze_x_norm: float = 0.5
    gaze_y_norm: float = 0.5

    blink_left: float = 0.0
    blink_right: float = 0.0

    click_count: int = 0

    dwell_progress: float = 0.0
    dwell_ready: bool = False

    taskbar_hover_y: int = 48
    taskbar_region: bool = False
    taskbar_frozen: bool = False

    last_screen_x: int = 0
    last_screen_y: int = 0

    status_message: str = "starting"
    error_message: str = ""
    user_message: str = "initializing"
    headless: bool = False
    calibration_progress: float = 0.0

    lock: threading.Lock = field(default_factory=threading.Lock)

    def snapshot(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "running": self.running,
                "paused": self.paused,
                "has_face": self.has_face,
                "has_iris": self.has_iris,
                "calibrated": self.calibrated,
                "calibrating": self.calibrating,
                "blink_click_enabled": self.blink_click_enabled,
                "dwell_click_enabled": self.dwell_click_enabled,
                "fast_mode": self.fast_mode,
                "edge_assist_enabled": self.edge_assist_enabled,
                "taskbar_lock_enabled": self.taskbar_lock_enabled,
                "auto_hide_taskbar_mode": self.auto_hide_taskbar_mode,
                "show_metrics": self.show_metrics,
                "show_help": self.show_help,
                "fps_capture": self.fps_capture,
                "fps_vision": self.fps_vision,
                "fps_cursor": self.fps_cursor,
                "latency_total_ms": self.latency_total_ms,
                "latency_vision_ms": self.latency_vision_ms,
                "latency_cursor_ms": self.latency_cursor_ms,
                "confidence": self.confidence,
                "cursor_norm_x": self.cursor_norm_x,
                "cursor_norm_y": self.cursor_norm_y,
                "target_norm_x": self.target_norm_x,
                "target_norm_y": self.target_norm_y,
                "raw_norm_x": self.raw_norm_x,
                "raw_norm_y": self.raw_norm_y,
                "head_x": self.head_x,
                "head_y": self.head_y,
                "iris_x": self.iris_x,
                "iris_y": self.iris_y,
                "gaze_x_norm": self.gaze_x_norm,
                "gaze_y_norm": self.gaze_y_norm,
                "blink_left": self.blink_left,
                "blink_right": self.blink_right,
                "click_count": self.click_count,
                "dwell_progress": self.dwell_progress,
                "dwell_ready": self.dwell_ready,
                "taskbar_hover_y": self.taskbar_hover_y,
                "taskbar_region": self.taskbar_region,
                "taskbar_frozen": self.taskbar_frozen,
                "last_screen_x": self.last_screen_x,
                "last_screen_y": self.last_screen_y,
                "status_message": self.status_message,
                "error_message": self.error_message,
                "user_message": self.user_message,
                "calibration_progress": self.calibration_progress,
            }

    def set(self, **kwargs: Any) -> None:
        with self.lock:
            for k, v in kwargs.items():
                if hasattr(self, k):
                    setattr(self, k, v)


# ============================================================
# SOUND FALLBACK
# ============================================================

class DemoSound:
    def __init__(self) -> None:
        self.available = False
        self.sound = None

        try:
            from sound_system import YeuxSoundSystem
            self.sound = YeuxSoundSystem()
            self.available = True
        except Exception:
            self.available = False
            self.sound = None

    def play(self, name: str) -> None:
        if not self.available:
            return
        try:
            self.sound.play(name)
        except Exception:
            pass

    def update(self) -> None:
        if not self.available:
            return
        try:
            self.sound.update()
        except Exception:
            pass

    def stop(self) -> None:
        if not self.available:
            return
        try:
            self.sound.stop()
        except Exception:
            pass


# ============================================================
# PACKETS
# ============================================================

@dataclass
class FramePacket:
    frame: np.ndarray
    capture_ms: float
    frame_index: int


@dataclass
class PosePacket:
    raw_x: float
    raw_y: float
    norm_x: float
    norm_y: float
    confidence: float

    head_x: float
    head_y: float

    iris_x: float
    iris_y: float

    gaze_x_norm: float
    gaze_y_norm: float

    has_iris: bool

    capture_ms: float
    vision_start_ms: float
    vision_end_ms: float

    blink_left: float
    blink_right: float

    face_points: List[Tuple[int, int]]
    iris_points: List[Tuple[int, int]]


# ============================================================
# CALIBRATION
# ============================================================

class CalibrationController:
    def __init__(self, config: CalibrationConfig) -> None:
        self.config = config
        self.reset()

    def reset(self) -> None:
        self.started_ms = perf_ms()

        self.min_x = 1.0
        self.max_x = 0.0
        self.min_y = 1.0
        self.max_y = 0.0

        self.done = False
        self.samples: List[Tuple[float, float]] = []

        self.points = [
            (0.10, 0.12),
            (0.50, 0.10),
            (0.90, 0.12),
            (0.12, 0.50),
            (0.50, 0.50),
            (0.88, 0.50),
            (0.10, 0.88),
            (0.50, 0.90),
            (0.90, 0.88),
        ]

    def save(self) -> bool:
        try:
            data = {
                "min_x": self.min_x,
                "max_x": self.max_x,
                "min_y": self.min_y,
                "max_y": self.max_y,
                "done": self.done,
                "saved_at": epoch_s(),
            }

            with open(self.config.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            return True
        except Exception:
            return False

    def load(self) -> bool:
        try:
            if not os.path.exists(self.config.file_path):
                return False

            with open(self.config.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.min_x = float(data["min_x"])
            self.max_x = float(data["max_x"])
            self.min_y = float(data["min_y"])
            self.max_y = float(data["max_y"])
            self.done = True

            return True
        except Exception:
            return False

    def progress(self) -> float:
        elapsed_s = (perf_ms() - self.started_ms) / 1000.0
        return clamp(elapsed_s / self.config.duration_seconds, 0.0, 1.0)

    def current_point_index(self) -> int:
        p = self.progress()
        idx = int(p * len(self.points))
        return int(clamp(idx, 0, len(self.points) - 1))

    def current_point(self) -> Tuple[float, float]:
        return self.points[self.current_point_index()]

    def update(self, raw_x: float, raw_y: float) -> Tuple[float, float, bool]:
        if not self.done:
            self.samples.append((raw_x, raw_y))

            self.min_x = min(self.min_x, raw_x)
            self.max_x = max(self.max_x, raw_x)
            self.min_y = min(self.min_y, raw_y)
            self.max_y = max(self.max_y, raw_y)

            span_x = self.max_x - self.min_x
            span_y = self.max_y - self.min_y

            enough_span = (
                span_x >= self.config.min_span_x and
                span_y >= self.config.min_span_y
            )

            if self.config.auto_finish:
                if self.progress() >= 1.0 and enough_span:
                    self.done = True

                if self.progress() >= 1.0 and not enough_span:
                    self.min_x = min(self.min_x, raw_x - 0.045)
                    self.max_x = max(self.max_x, raw_x + 0.045)
                    self.min_y = min(self.min_y, raw_y - 0.045)
                    self.max_y = max(self.max_y, raw_y + 0.045)
                    self.done = True

        nx = safe_div(raw_x - self.min_x, self.max_x - self.min_x + 1e-6, 0.5)
        ny = safe_div(raw_y - self.min_y, self.max_y - self.min_y + 1e-6, 0.5)

        nx = clamp(nx, 0.0, 1.0)
        ny = clamp(ny, 0.0, 1.0)

        return nx, ny, self.done


# ============================================================
# BLINK
# ============================================================

class BlinkDetector:
    def __init__(self, config: BlinkConfig) -> None:
        self.config = config
        self.was_blinking = False
        self.pending_first_blink_s = 0.0
        self.last_click_s = 0.0

    def update(self, blink_left: float, blink_right: float) -> bool:
        if not self.config.enabled:
            return False

        now = epoch_s()
        blink_strength = max(blink_left, blink_right)
        is_blinking = blink_strength >= self.config.blink_threshold

        clicked = False

        if is_blinking and not self.was_blinking:
            if now - self.last_click_s < self.config.blink_cooldown:
                self.was_blinking = is_blinking
                return False

            if not self.config.use_double_blink:
                clicked = True
                self.last_click_s = now
            else:
                if self.pending_first_blink_s <= 0:
                    self.pending_first_blink_s = now
                else:
                    gap = now - self.pending_first_blink_s

                    if gap <= self.config.double_blink_max_gap:
                        clicked = True
                        self.pending_first_blink_s = 0.0
                        self.last_click_s = now
                    else:
                        self.pending_first_blink_s = now

        if self.pending_first_blink_s > 0:
            if now - self.pending_first_blink_s > self.config.double_blink_max_gap:
                self.pending_first_blink_s = 0.0

        self.was_blinking = is_blinking
        return clicked


# ============================================================
# DWELL CLICK
# ============================================================

class DwellClickController:
    def __init__(self, config: DwellClickConfig) -> None:
        self.config = config

        self.anchor_x = -9999
        self.anchor_y = -9999
        self.started_ms = 0.0
        self.last_click_ms = 0.0

    def reset(self) -> None:
        self.anchor_x = -9999
        self.anchor_y = -9999
        self.started_ms = 0.0

    def update(
        self,
        x: int,
        y: int,
        enabled: bool,
        taskbar_region: bool,
    ) -> Tuple[bool, float, bool]:
        if not enabled:
            self.reset()
            return False, 0.0, False

        now = perf_ms()

        if now - self.last_click_ms < self.config.cooldown_ms:
            return False, 0.0, False

        if self.started_ms <= 0:
            self.anchor_x = x
            self.anchor_y = y
            self.started_ms = now
            return False, 0.0, False

        dist = math.hypot(x - self.anchor_x, y - self.anchor_y)

        if dist > self.config.radius_px:
            self.anchor_x = x
            self.anchor_y = y
            self.started_ms = now
            return False, 0.0, False

        dwell_time = (
            self.config.taskbar_dwell_time_ms
            if taskbar_region
            else self.config.dwell_time_ms
        )

        progress = clamp((now - self.started_ms) / dwell_time, 0.0, 1.0)

        if progress >= 1.0:
            self.last_click_ms = now
            self.reset()
            return True, 1.0, True

        return False, progress, False


# ============================================================
# CAMERA
# ============================================================

class CameraWorker:
    def __init__(
        self,
        config: CameraConfig,
        state: SharedState,
        frame_q_vision: LatestQueue,
        frame_q_overlay: LatestQueue,
    ) -> None:
        self.config = config
        self.state = state
        self.frame_q_vision = frame_q_vision
        self.frame_q_overlay = frame_q_overlay
        self.fps = FPSCounter()
        self.frame_index = 0

    def open(self) -> cv2.VideoCapture:
        if self.config.use_dshow_on_windows and platform.system().lower() == "windows":
            cap = cv2.VideoCapture(self.config.index, cv2.CAP_DSHOW)
            if cap.isOpened():
                return cap

        return cv2.VideoCapture(self.config.index)

    def configure(self, cap: cv2.VideoCapture) -> None:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
        cap.set(cv2.CAP_PROP_FPS, self.config.fps)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        try:
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        except Exception:
            pass

    def run(self) -> None:
        cap = self.open()

        if not cap.isOpened():
            self.state.set(
                running=False,
                error_message="camera not opened",
                status_message="camera error",
                user_message="Camera não abriu. Verifique permissões ou CAMERA_INDEX.",
            )
            return

        self.configure(cap)

        while self.state.snapshot()["running"]:
            ok, frame = cap.read()

            if not ok:
                time.sleep(0.003)
                continue

            if self.config.mirror:
                frame = cv2.flip(frame, 1)

            capture_ms = perf_ms()

            packet = FramePacket(
                frame=frame,
                capture_ms=capture_ms,
                frame_index=self.frame_index,
            )

            self.frame_index += 1

            self.frame_q_vision.put(packet)
            self.frame_q_overlay.put(packet)

            fps_value = self.fps.tick()
            self.state.set(fps_capture=fps_value)

        cap.release()


# ============================================================
# FACE + PUPIL VISION
# ============================================================

class FacePupilLandmarkerWorker:
    def __init__(
        self,
        model_config: ModelConfig,
        calibration_config: CalibrationConfig,
        fusion_config: FusionConfig,
        state: SharedState,
        frame_q: LatestQueue,
        pose_q: LatestQueue,
        sound: DemoSound,
    ) -> None:
        self.model_config = model_config
        self.fusion = fusion_config
        self.calibration = CalibrationController(calibration_config)
        self.state = state
        self.frame_q = frame_q
        self.pose_q = pose_q
        self.sound = sound

        self.fps = FPSCounter()
        self.last_had_face = False
        self.mp_timestamp_ms = 0

        self.face_point_indices = [
            1, 10, 152,
            33, 133, 159, 145,
            263, 362, 386, 374,
            61, 291,
        ]

        self.iris_indices_left = [468, 469, 470, 471, 472]
        self.iris_indices_right = [473, 474, 475, 476, 477]
        self.use_onnx = "--onnx" in sys.argv
        self.onnx_session = None
        self.onnx_input_name = None

        if self.use_onnx:
                   self.use_onnx = "--onnx" in sys.argv
        self.onnx_session = None
        self.onnx_input_name = None

        if self.use_onnx:
            self.onnx_session = ort.InferenceSession(
                r"models\MediaPipeFaceLandmarkDetector.onnx",
                providers=["DmlExecutionProvider", "CPUExecutionProvider"],
            )

            self.onnx_input_name = self.onnx_session.get_inputs()[0].name
            print("Yeux ONNX DirectML ativado")
    def create_detector(self) -> Any:
        base_options = python.BaseOptions(
            model_asset_path=self.model_config.model_path
        )

        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.IMAGE,
            num_faces=self.model_config.max_num_faces,
            output_face_blendshapes=self.model_config.output_face_blendshapes,
            output_facial_transformation_matrixes=(
                self.model_config.output_facial_transformation_matrixes
            ),
        )

        return vision.FaceLandmarker.create_from_options(options)

    def mean_landmarks(
        self,
        landmarks: Any,
        indices: List[int],
    ) -> Optional[Tuple[float, float]]:
        xs = []
        ys = []

        for idx in indices:
            if idx < len(landmarks):
                xs.append(float(landmarks[idx].x))
                ys.append(float(landmarks[idx].y))

        if not xs:
            return None

        return float(np.mean(xs)), float(np.mean(ys))

    def extract_head_anchor(self, landmarks: Any) -> Tuple[float, float]:
        head_points = [1, 33, 263, 133, 362, 10, 152]
        result = self.mean_landmarks(landmarks, head_points)

        if result is None:
            return 0.5, 0.5

        return result

    def extract_pupil_gaze(
        self,
        landmarks: Any,
    ) -> Tuple[bool, float, float, float, float]:
        has_iris = len(landmarks) > 477

        if not has_iris:
            return False, 0.5, 0.5, 0.5, 0.5

        left_iris = self.mean_landmarks(landmarks, self.iris_indices_left)
        right_iris = self.mean_landmarks(landmarks, self.iris_indices_right)

        if left_iris is None or right_iris is None:
            return False, 0.5, 0.5, 0.5, 0.5

        iris_x = (left_iris[0] + right_iris[0]) / 2.0
        iris_y = (left_iris[1] + right_iris[1]) / 2.0

        required = [33, 133, 159, 145, 263, 362, 386, 374]

        if any(i >= len(landmarks) for i in required):
            return True, iris_x, iris_y, 0.5, 0.5

        lx1 = float(landmarks[33].x)
        lx2 = float(landmarks[133].x)
        ly_top = float(landmarks[159].y)
        ly_bottom = float(landmarks[145].y)

        rx1 = float(landmarks[362].x)
        rx2 = float(landmarks[263].x)
        ry_top = float(landmarks[386].y)
        ry_bottom = float(landmarks[374].y)

        eye_min_x = min(lx1, lx2, rx1, rx2)
        eye_max_x = max(lx1, lx2, rx1, rx2)

        eye_top_y = min(ly_top, ry_top)
        eye_bottom_y = max(ly_bottom, ry_bottom)

        eye_w = max(eye_max_x - eye_min_x, 1e-6)
        eye_h = max(eye_bottom_y - eye_top_y, 1e-6)

        gaze_x_norm = (iris_x - eye_min_x) / eye_w
        gaze_y_norm = (iris_y - eye_top_y) / eye_h

        gaze_x_norm = clamp(gaze_x_norm, 0.0, 1.0)
        gaze_y_norm = clamp(gaze_y_norm, 0.0, 1.0)

        return True, iris_x, iris_y, gaze_x_norm, gaze_y_norm

    def apply_gaze_deadzone(self, value: float) -> float:
        centered = value - 0.5
        dz = self.fusion.gaze_deadzone

        if abs(centered) < dz:
            return 0.0

        sign = 1.0 if centered > 0 else -1.0
        adjusted = (abs(centered) - dz) / max(0.5 - dz, 1e-6)

        return sign * clamp(adjusted, 0.0, 1.0) * 0.5

    def fuse_head_and_pupil(
        self,
        head_x: float,
        head_y: float,
        has_iris: bool,
        gaze_x_norm: float,
        gaze_y_norm: float,
    ) -> Tuple[float, float]:
        if not has_iris:
            if self.fusion.allow_head_only_fallback:
                return head_x, head_y
            return 0.5, 0.5

        gaze_dx = self.apply_gaze_deadzone(gaze_x_norm)
        gaze_dy = self.apply_gaze_deadzone(gaze_y_norm)

        fused_x = head_x + gaze_dx * self.fusion.eye_gain_x
        fused_y = head_y + gaze_dy * self.fusion.eye_gain_y

        if gaze_y_norm > self.fusion.taskbar_gaze_threshold:
            down_strength = (
                gaze_y_norm - self.fusion.taskbar_gaze_threshold
            ) / max(1.0 - self.fusion.taskbar_gaze_threshold, 1e-6)

            fused_y += self.fusion.taskbar_gaze_boost * clamp(down_strength, 0.0, 1.0)

        if gaze_y_norm < self.fusion.top_gaze_threshold:
            up_strength = (
                self.fusion.top_gaze_threshold - gaze_y_norm
            ) / max(self.fusion.top_gaze_threshold, 1e-6)

            fused_y -= self.fusion.top_gaze_boost * clamp(up_strength, 0.0, 1.0)

        fused_x = clamp(fused_x, 0.0, 1.0)
        fused_y = clamp(fused_y, 0.0, 1.0)

        return fused_x, fused_y

    def extract_confidence(self, result: Any, has_iris: bool) -> float:
        if not result.face_landmarks:
            return 0.0

        score = 0.76

        if has_iris:
            score += 0.14

        try:
            if result.face_blendshapes:
                score += 0.08
        except Exception:
            pass

        return clamp(score, 0.0, 1.0)

    def extract_blinks(self, result: Any) -> Tuple[float, float]:
        left = 0.0
        right = 0.0

        try:
            if not result.face_blendshapes:
                return left, right

            categories = result.face_blendshapes[0]

            for cat in categories:
                name = cat.category_name
                score = float(cat.score)

                if name == "eyeBlinkLeft":
                    left = score
                elif name == "eyeBlinkRight":
                    right = score

        except Exception:
            pass

        return left, right

    def make_points(
        self,
        landmarks: Any,
        indices: List[int],
        frame_w: int,
        frame_h: int,
    ) -> List[Tuple[int, int]]:
        points = []

        for idx in indices:
            if idx >= len(landmarks):
                continue

            lm = landmarks[idx]
            x = int(clamp(float(lm.x), 0.0, 1.0) * frame_w)
            y = int(clamp(float(lm.y), 0.0, 1.0) * frame_h)
            points.append((x, y))

        return points
    def run_onnx_landmarks(self, frame):
        img = cv2.resize(frame, (192, 192))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = img.astype(np.float32) / 255.0
        img = np.transpose(img, (2, 0, 1))
        img = np.expand_dims(img, axis=0)

        scores, landmarks = self.onnx_session.run(
            None,
            {self.onnx_input_name: img},
        )

        score = float(scores[0])
        pts = landmarks[0]

        if score < 0.001:
            return None

        left_eye = pts[33]
        right_eye = pts[263]
        nose = pts[1]

        cx = float((left_eye[0] + right_eye[0] + nose[0]) / 3.0)
        cy = float((left_eye[1] + right_eye[1] + nose[1]) / 3.0)

        return cx, cy
    def run(self) -> None:
        try:
            detector = self.create_detector()
        except Exception as e:
            self.state.set(
                running=False,
                error_message=f"model error: {e}",
                status_message="model error",
                user_message="Erro ao carregar face_landmarker.task.",
            )
            return

        while self.state.snapshot()["running"]:
            snap = self.state.snapshot()

            try:
                packet: FramePacket = self.frame_q.get(timeout=0.05)
            except queue.Empty:
                continue

            if snap["paused"]:
                continue

            vision_start = perf_ms()
            if self.use_onnx and self.onnx_session is not None:
                gaze = self.run_onnx_landmarks(packet.frame)

                if gaze is not None:
                    gx, gy = gaze

                    packet_pose = PosePacket(
                        raw_x=gx,
                        raw_y=gy,
                        norm_x=gx,
                        norm_y=gy,
                        blink_left=0.0,
                        blink_right=0.0,
                        confidence=0.8,
                        capture_ms=packet.capture_ms,
                    )

                    self.pose_q.put(packet_pose)
                    continue
            try:
                rgb = cv2.cvtColor(packet.frame, cv2.COLOR_BGR2RGB)

                mp_image = mp.Image(
                    image_format=mp.ImageFormat.SRGB,
                    data=np.ascontiguousarray(rgb),
                )
                timestamp_ms = packet.frame_index * 1000

                self.mp_timestamp_ms += 1
                timestamp_ms = self.mp_timestamp_ms

                self.mp_timestamp_ms = 0

                result = detector.detect(mp_image)

                vision_end = perf_ms()

                if result.face_landmarks:
                    if not self.last_had_face:
                        self.sound.play("tracking_found")

                    self.last_had_face = True

                    landmarks = result.face_landmarks[0]

                    head_x, head_y = self.extract_head_anchor(landmarks)

                    (
                        has_iris,
                        iris_x,
                        iris_y,
                        gaze_x_norm,
                        gaze_y_norm,
                    ) = self.extract_pupil_gaze(landmarks)

                    fused_x, fused_y = self.fuse_head_and_pupil(
                        head_x=head_x,
                        head_y=head_y,
                        has_iris=has_iris,
                        gaze_x_norm=gaze_x_norm,
                        gaze_y_norm=gaze_y_norm,
                    )

                    nx, ny, done = self.calibration.update(fused_x, fused_y)

                    blink_left, blink_right = self.extract_blinks(result)

                    h, w = packet.frame.shape[:2]

                    face_points = self.make_points(
                        landmarks,
                        self.face_point_indices,
                        w,
                        h,
                    )

                    iris_points = []

                    if has_iris:
                        iris_points.extend(
                            self.make_points(
                                landmarks,
                                self.iris_indices_left,
                                w,
                                h,
                            )
                        )

                        iris_points.extend(
                            self.make_points(
                                landmarks,
                                self.iris_indices_right,
                                w,
                                h,
                            )
                        )

                    confidence = self.extract_confidence(result, has_iris)

                    pose = PosePacket(
                        raw_x=fused_x,
                        raw_y=fused_y,
                        norm_x=nx,
                        norm_y=ny,
                        confidence=confidence,
                        head_x=head_x,
                        head_y=head_y,
                        iris_x=iris_x,
                        iris_y=iris_y,
                        gaze_x_norm=gaze_x_norm,
                        gaze_y_norm=gaze_y_norm,
                        has_iris=has_iris,
                        capture_ms=packet.capture_ms,
                        vision_start_ms=vision_start,
                        vision_end_ms=vision_end,
                        blink_left=blink_left,
                        blink_right=blink_right,
                        face_points=face_points,
                        iris_points=iris_points,
                    )

                    self.pose_q.put(pose)

                    fps_value = self.fps.tick()

                    if done:
                        status = "tracking"
                        msg = "Face + pupil tracking active" if has_iris else "Head tracking fallback"
                    else:
                        status = "calibrating"
                        msg = "Calibrating face + pupil control"

                    self.state.set(
                        has_face=True,
                        has_iris=has_iris,
                        calibrated=done,
                        calibrating=not done,
                        fps_vision=fps_value,
                        latency_vision_ms=vision_end - vision_start,
                        confidence=confidence,
                        raw_norm_x=fused_x,
                        raw_norm_y=fused_y,
                        target_norm_x=nx,
                        target_norm_y=ny,
                        head_x=head_x,
                        head_y=head_y,
                        iris_x=iris_x,
                        iris_y=iris_y,
                        gaze_x_norm=gaze_x_norm,
                        gaze_y_norm=gaze_y_norm,
                        blink_left=blink_left,
                        blink_right=blink_right,
                        calibration_progress=self.calibration.progress(),
                        status_message=status,
                        user_message=msg,
                    )

                else:
                    if self.last_had_face:
                        self.sound.play("tracking_lost")

                    self.last_had_face = False

                    self.state.set(
                        has_face=False,
                        has_iris=False,
                        confidence=0.0,
                        status_message="face lost",
                        user_message="Face not detected",
                    )

            except Exception as e:
                self.state.set(
                    error_message=str(e),
                    status_message="vision error",
                    user_message="Vision pipeline error",
                )
                traceback.print_exc()
                time.sleep(0.01)


# ============================================================
# CURSOR
# ============================================================

class CursorWorker:
    def __init__(
        self,
        config: CursorConfig,
        blink_config: BlinkConfig,
        dwell_config: DwellClickConfig,
        state: SharedState,
        pose_q: LatestQueue,
        sound: DemoSound,
    ) -> None:
        self.config = config
        self.blink_config = blink_config
        self.dwell_config = dwell_config
        self.state = state
        self.pose_q = pose_q
        self.sound = sound
        self.last_right_click_ms = 0.0
        self.last_scroll_ms = 0.0

        try:
            self.input_backend = create_backend("sendinput")
        except Exception as e:
            print("Erro ao iniciar input backend:", e)
            self.input_backend = None

        self.last_backend_x = -9999
        self.last_backend_y = -9999

        self.screen_w, self.screen_h = pyautogui.size()

        self.cx = 0.5
        self.cy = 0.5
        self.vx = 0.0
        self.vy = 0.0
        self.smooth_x = 0.5
        self.smooth_y = 0.5
        self.target_x = 0.5
        self.target_y = 0.5
        self.last_pose: Optional[PosePacket] = None

        self.hover_freeze_started_ms = 0.0
        self.hover_freeze_px = -9999
        self.hover_freeze_py = -9999
        self.hover_frozen = False
        self.auto_hide_reveal_until_ms = 0.0
        self.last_click_ms = 0.0

        self.fps = FPSCounter()
        self.blink = BlinkDetector(blink_config)
        self.dwell = DwellClickController(dwell_config)

    def native_update_cursor(self) -> bool:
        if not YEUX_NATIVE_AVAILABLE or yeux_native is None:
            return False

        if not hasattr(self, "native_log_done"):
            self.native_log_done = True
            print("USANDO YeuxNativeCore.dll")

        out_x = ctypes.c_double(self.cx)
        out_y = ctypes.c_double(self.cy)

        out_vx = ctypes.c_double(self.vx)
        out_vy = ctypes.c_double(self.vy)

        yeux_native.yeux_update_cursor(
            float(self.target_x),
            float(self.target_y),
            float(self.cx),
            float(self.cy),
            float(self.vx),
            float(self.vy),
            ctypes.byref(out_x),
            ctypes.byref(out_y),
            ctypes.byref(out_vx),
            ctypes.byref(out_vy),
        )

        self.cx = float(out_x.value)
        self.cy = float(out_y.value)

        self.vx = float(out_vx.value)
        self.vy = float(out_vy.value)

        return True
    def update_target(self, pose: PosePacket, fast_mode: bool) -> None:
        dx = pose.norm_x - self.smooth_x
        dy = pose.norm_y - self.smooth_y
        movement = math.hypot(dx, dy)

        slow_alpha = self.config.slow_alpha
        fast_alpha = self.config.fast_alpha

        if not fast_mode:
            slow_alpha *= 0.72
            fast_alpha *= 0.68

        t = clamp(movement * 10.0, 0.0, 1.0)
        alpha = lerp(slow_alpha, fast_alpha, t)

        self.smooth_x = lerp(self.smooth_x, pose.norm_x, alpha)
        self.smooth_y = lerp(self.smooth_y, pose.norm_y, alpha)

        self.target_x = self.smooth_x
        self.target_y = self.smooth_y

    def norm_to_screen(
        self,
        nx: float,
        ny: float,
        edge_enabled: bool,
        taskbar_hover_y: int,
        auto_hide_mode: bool,
    ) -> Tuple[int, int]:
        nx = clamp(nx, 0.0, 1.0)
        ny = clamp(ny, 0.0, 1.0)

        px = int(nx * (self.screen_w - 1))
        py = int(ny * (self.screen_h - 1))

        if edge_enabled:
            edge_zone = self.config.edge_assist_zone

            if nx <= edge_zone:
                px = self.config.left_safe_x
            elif nx >= 1.0 - edge_zone:
                px = self.screen_w - self.config.right_safe_padding

            if ny <= edge_zone:
                py = self.config.top_safe_y

        if auto_hide_mode and ny >= 1.0 - self.config.taskbar_snap_zone:
            now = perf_ms()

            if self.auto_hide_reveal_until_ms <= 0:
                self.auto_hide_reveal_until_ms = now + self.config.auto_hide_reveal_ms

            if now < self.auto_hide_reveal_until_ms:
                py = self.screen_h - 1
        else:
            if ny < 1.0 - self.config.taskbar_snap_zone:
                self.auto_hide_reveal_until_ms = 0.0

        return px, py

    def apply_taskbar_boost(self) -> None:
        return

    def apply_taskbar_stabilization(self, taskbar_region: bool) -> None:
        return

    def apply_hover_freeze(
        self,
        px: int,
        py: int,
        taskbar_region: bool,
        enabled: bool,
    ) -> Tuple[int, int, bool]:
        return px, py, False
    def maybe_hot_corner_actions(self, pose: PosePacket) -> None:
        now = perf_ms()

        # canto superior direito = clique direito
        if pose.norm_x > 0.88 and pose.norm_y < 0.18:
            if now - self.last_right_click_ms > 1000:
                try:
                    pyautogui.rightClick()
                    self.last_right_click_ms = now
                    self.sound.play("click")
                except Exception as e:
                    print("Erro no clique direito:", e)

        # borda direita + olhar para cima/baixo = scroll
        if now - self.last_scroll_ms < 130:
            return

        if pose.norm_x > 0.90 and pose.norm_y < 0.35:
            pyautogui.scroll(2)
            self.last_scroll_ms = now

        elif pose.norm_x > 0.90 and pose.norm_y > 0.65:
            pyautogui.scroll(-2)
            self.last_scroll_ms = now
    def send_mouse_move(self, px: int, py: int, frozen: bool) -> None:
        if frozen:
            return

        eps = self.config.move_epsilon_px

        if self.last_backend_x == -9999 or self.last_backend_y == -9999:
            self.last_backend_x = px
            self.last_backend_y = py
            pyautogui.moveTo(px, py)
            return

        dx = px - self.last_backend_x
        dy = py - self.last_backend_y

        if abs(dx) < eps and abs(dy) < eps:
            return

        dx = int(clamp(dx, -60, 60))
        dy = int(clamp(dy, -60, 60))

        try:
            if self.input_backend is not None:
                self.input_backend.send_event(
                    YeuxMouseEvent(dx=dx, dy=dy, left=False)
                )
            else:
                pyautogui.moveRel(dx, dy)
        except Exception as e:
            print("Erro ao mover mouse:", e)
            try:
                pyautogui.moveRel(dx, dy)
            except Exception:
                pass

        self.last_backend_x += dx
        self.last_backend_y += dy

    def click_now(self) -> bool:
        now = perf_ms()

        if now - self.last_click_ms < 500:
            return False

        try:
            if self.input_backend is not None:
                self.input_backend.send_event(
                    YeuxMouseEvent(dx=0, dy=0, left=True)
                )
            else:
                pyautogui.click(button="left")

            self.last_click_ms = now
            self.sound.play("click")
            return True

        except Exception as e:
            print("Erro ao clicar:", e)

            try:
                pyautogui.click(button="left")
                self.last_click_ms = now
                return True
            except Exception:
                return False

    def maybe_blink_click(self, pose: PosePacket, blink_enabled: bool) -> bool:
        self.blink.config.enabled = blink_enabled

        clicked = self.blink.update(
            blink_left=pose.blink_left,
            blink_right=pose.blink_right,
        )

        if clicked:
            return self.click_now()

        return False

    def maybe_dwell_click(
        self,
        px: int,
        py: int,
        dwell_enabled: bool,
        taskbar_region: bool,
    ) -> Tuple[bool, float, bool]:
        clicked, progress, ready = self.dwell.update(
            x=px,
            y=py,
            enabled=dwell_enabled,
            taskbar_region=taskbar_region,
        )

        if clicked:
            ok = self.click_now()
            return ok, progress, ready

        return False, progress, ready

    def move_cursor(
        self,
        edge_enabled: bool,
        taskbar_hover_y: int,
        taskbar_lock_enabled: bool,
        auto_hide_mode: bool,
    ) -> Tuple[float, bool, bool, int, int]:
        start = perf_ms()
        if self.native_update_cursor():
            px, py = self.norm_to_screen(
                self.cx,
                self.cy,
                edge_enabled,
                taskbar_hover_y,
                auto_hide_mode,
            )

            self.send_mouse_move(px, py, False)

            end = perf_ms()
            taskbar_region = self.cy >= 1.0 - self.config.taskbar_snap_zone
            return end - start, taskbar_region, False, px, py
        dx = self.target_x - self.cx
        dy = self.target_y - self.cy
        dist = math.hypot(dx, dy)

        if dist < self.config.deadzone:
            dx = 0.0
            dy = 0.0
            self.vx *= 0.45
            self.vy *= 0.45
        else:
            scale = (dist - self.config.deadzone) / max(dist, 1e-6)
            dx *= scale
            dy *= scale

        speed_curve = clamp(dist * 4.15, 0.12, 1.32)

        self.vx += dx * self.config.accel * speed_curve
        self.vy += dy * self.config.accel * speed_curve

        self.vx *= self.config.friction
        self.vy *= self.config.friction

        self.vx = clamp(self.vx, -self.config.max_velocity, self.config.max_velocity)
        self.vy = clamp(self.vy, -self.config.max_velocity, self.config.max_velocity)

        self.cx += self.vx
        self.cy += self.vy

        self.cx = clamp(self.cx, self.config.clamp_min, self.config.clamp_max)
        self.cy = clamp(self.cy, self.config.clamp_min, self.config.clamp_max)

        taskbar_region = self.cy >= 1.0 - self.config.taskbar_snap_zone

        px, py = self.norm_to_screen(
            self.cx,
            self.cy,
            edge_enabled,
            taskbar_hover_y,
            auto_hide_mode,
        )

        px, py, frozen = self.apply_hover_freeze(
            px,
            py,
            taskbar_region,
            taskbar_lock_enabled,
        )

        self.send_mouse_move(px, py, frozen)

        end = perf_ms()
        return end - start, taskbar_region, frozen, px, py

    def run(self) -> None:
        print("CursorWorker.run iniciado")

        while self.state.snapshot()["running"]:
            snap = self.state.snapshot()

            if snap["paused"]:
                self.sound.update()
                time.sleep(0.01)
                continue

            pose = None

            try:
                pose = self.pose_q.get_nowait()
            except queue.Empty:
                pose = None

            if pose is not None:
                self.last_pose = pose

                if snap["calibrated"]:
                    self.update_target(pose, snap["fast_mode"])

                blink_clicked = self.maybe_blink_click(
                    pose,
                    snap["blink_click_enabled"],
                )
                self.maybe_hot_corner_actions(pose)

                if blink_clicked:
                    self.state.set(click_count=snap["click_count"] + 1)

            cursor_ms, taskbar_region, frozen, px, py = self.move_cursor(
                snap["edge_assist_enabled"],
                snap["taskbar_hover_y"],
                snap["taskbar_lock_enabled"],
                snap["auto_hide_taskbar_mode"],
            )

            dwell_clicked, dwell_progress, dwell_ready = self.maybe_dwell_click(
                px=px,
                py=py,
                dwell_enabled=snap["dwell_click_enabled"],
                taskbar_region=taskbar_region,
            )

            if dwell_clicked:
                self.state.set(click_count=snap["click_count"] + 1)

            fps_value = self.fps.tick()

            total_latency = 0.0
            if self.last_pose is not None:
                total_latency = perf_ms() - self.last_pose.capture_ms

            self.state.set(
                cursor_norm_x=self.cx,
                cursor_norm_y=self.cy,
                fps_cursor=fps_value,
                latency_cursor_ms=cursor_ms,
                latency_total_ms=total_latency,
                taskbar_region=taskbar_region,
                taskbar_frozen=frozen,
                last_screen_x=px,
                last_screen_y=py,
                dwell_progress=dwell_progress,
                dwell_ready=dwell_ready,
            )

            self.sound.update()
            time.sleep(self.config.sleep_seconds)
            
# ============================================================
# LOGGER
# ============================================================

class MetricsLogger:
    def __init__(self, path: str, state: SharedState) -> None:
        self.path = path
        self.state = state
        self.last_log_s = 0.0

    def maybe_log(self) -> None:
        now = epoch_s()

        if now - self.last_log_s < 1.0:
            return

        self.last_log_s = now
        snap = self.state.snapshot()

        row = {
            "time": now,
            "has_face": snap["has_face"],
            "has_iris": snap["has_iris"],
            "calibrated": snap["calibrated"],
            "paused": snap["paused"],
            "fast_mode": snap["fast_mode"],
            "edge_assist_enabled": snap["edge_assist_enabled"],
            "taskbar_lock_enabled": snap["taskbar_lock_enabled"],
            "taskbar_region": snap["taskbar_region"],
            "taskbar_frozen": snap["taskbar_frozen"],
            "blink_click_enabled": snap["blink_click_enabled"],
            "dwell_click_enabled": snap["dwell_click_enabled"],
            "dwell_progress": snap["dwell_progress"],
            "taskbar_hover_y": snap["taskbar_hover_y"],
            "last_screen_x": snap["last_screen_x"],
            "last_screen_y": snap["last_screen_y"],
            "head_x": snap["head_x"],
            "head_y": snap["head_y"],
            "iris_x": snap["iris_x"],
            "iris_y": snap["iris_y"],
            "gaze_x_norm": snap["gaze_x_norm"],
            "gaze_y_norm": snap["gaze_y_norm"],
            "fps_capture": snap["fps_capture"],
            "fps_vision": snap["fps_vision"],
            "fps_cursor": snap["fps_cursor"],
            "latency_total_ms": snap["latency_total_ms"],
            "latency_vision_ms": snap["latency_vision_ms"],
            "latency_cursor_ms": snap["latency_cursor_ms"],
            "confidence": snap["confidence"],
            "click_count": snap["click_count"],
            "status": snap["status_message"],
            "error": snap["error_message"],
        }

        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        except Exception:
            pass


# ============================================================
# OVERLAY
# ============================================================

class OverlayWorker:
    def __init__(
        self,
        config: OverlayConfig,
        calibration: CalibrationController,
        dwell_config: DwellClickConfig,
        state: SharedState,
        frame_q: LatestQueue,
        sound: DemoSound,
    ) -> None:
        self.config = config
        self.calibration = calibration
        self.dwell_config = dwell_config
        self.state = state
        self.frame_q = frame_q
        self.sound = sound
        self.latest_frame: Optional[np.ndarray] = None

    def draw_header(self, frame: np.ndarray, snap: Dict[str, Any]) -> None:
        draw_panel(frame, 12, 12, 455, 210, alpha=0.56)

        put_text(
            frame,
            "YEUX",
            (28, 54),
            scale=1.13,
            color=(255, 255, 255),
            thickness=2,
        )

        put_text(
            frame,
            "HYPERPRODUCT DEMO",
            (125, 52),
            scale=0.50,
            color=(215, 215, 215),
            thickness=1,
        )

        if snap["paused"]:
            badge_text = "PAUSED"
            badge_color = (0, 200, 255)
        elif not snap["has_face"]:
            badge_text = "FACE LOST"
            badge_color = (0, 0, 255)
        elif not snap["calibrated"]:
            badge_text = "CALIBRATING"
            badge_color = (0, 255, 255)
        else:
            badge_text = "TRACKING"
            badge_color = (0, 255, 100)

        draw_badge(frame, badge_text, 28, 94, badge_color)

        mode_text = "FAST" if snap["fast_mode"] else "BALANCED"
        draw_badge(frame, mode_text, 158, 94, (255, 255, 255))

        iris_text = "PUPIL ON" if snap["has_iris"] else "HEAD ONLY"
        iris_color = (0, 255, 255) if snap["has_iris"] else (120, 120, 120)
        draw_badge(frame, iris_text, 238, 94, iris_color)

        lock_text = "HOVER FREEZE" if snap["taskbar_lock_enabled"] else "NO FREEZE"
        lock_color = (0, 255, 255) if snap["taskbar_lock_enabled"] else (120, 120, 120)
        draw_badge(frame, lock_text, 28, 128, lock_color)

        dwell_text = "DWELL ON" if snap["dwell_click_enabled"] else "DWELL OFF"
        dwell_color = (0, 255, 100) if snap["dwell_click_enabled"] else (120, 120, 120)
        draw_badge(frame, dwell_text, 183, 128, dwell_color)

        blink_text = "BLINK ON" if snap["blink_click_enabled"] else "BLINK OFF"
        blink_color = (255, 230, 160) if snap["blink_click_enabled"] else (120, 120, 120)
        draw_badge(frame, blink_text, 298, 128, blink_color)

        msg = snap["user_message"]

        put_text(
            frame,
            msg[:52],
            (28, 166),
            scale=0.46,
            color=(215, 215, 215),
            thickness=1,
        )

        input_layer = "Windows SendInput" if platform.system().lower() == "windows" else "PyAutoGUI fallback"

        put_text(
            frame,
            f"Input layer: {input_layer}",
            (28, 190),
            scale=0.42,
            color=(170, 170, 170),
            thickness=1,
        )

    def draw_metrics(self, frame: np.ndarray, snap: Dict[str, Any]) -> None:
        if not snap["show_metrics"]:
            return

        h, w = frame.shape[:2]

        panel_w = 390
        panel_h = 382
        x = w - panel_w - 12
        y = 12

        draw_panel(frame, x, y, panel_w, panel_h, alpha=0.58)

        put_text(
            frame,
            "LIVE PRODUCT METRICS",
            (x + 16, y + 30),
            scale=0.55,
            color=(255, 255, 255),
            thickness=2,
        )

        latency = snap["latency_total_ms"]

        if latency < 100:
            latency_color = (0, 255, 100)
            latency_label = "sub-100"
        elif latency < 140:
            latency_color = (0, 255, 255)
            latency_label = "ok"
        else:
            latency_color = (0, 90, 255)
            latency_label = "high"

        tb_status = (
            "frozen"
            if snap["taskbar_frozen"]
            else ("region" if snap["taskbar_region"] else "off")
        )

        pupil_status = "on" if snap["has_iris"] else "fallback"

        lines = [
            ("Latency", f"{latency:6.1f} ms  {latency_label}", latency_color),
            ("Vision", f"{snap['latency_vision_ms']:6.1f} ms", (230, 230, 230)),
            ("Cursor", f"{snap['latency_cursor_ms']:6.1f} ms", (230, 230, 230)),
            ("FPS camera", f"{snap['fps_capture']:6.1f}", (230, 230, 230)),
            ("FPS vision", f"{snap['fps_vision']:6.1f}", (230, 230, 230)),
            ("FPS cursor", f"{snap['fps_cursor']:6.1f}", (230, 230, 230)),
            ("Confidence", f"{snap['confidence'] * 100:5.0f}%", (230, 230, 230)),
            ("Pupil", pupil_status, (0, 255, 255) if snap["has_iris"] else (230, 230, 230)),
            ("Gaze X/Y", f"{snap['gaze_x_norm']:.2f} / {snap['gaze_y_norm']:.2f}", (230, 230, 230)),
            ("Head X/Y", f"{snap['head_x']:.2f} / {snap['head_y']:.2f}", (230, 230, 230)),
            ("Iris X/Y", f"{snap['iris_x']:.2f} / {snap['iris_y']:.2f}", (230, 230, 230)),
            ("Blink L/R", f"{snap['blink_left']:.2f} / {snap['blink_right']:.2f}", (230, 230, 230)),
            ("Taskbar", tb_status, (0, 255, 255) if snap["taskbar_region"] else (230, 230, 230)),
            ("Taskbar Y", f"{snap['taskbar_hover_y']} px", (230, 230, 230)),
            ("Dwell", f"{snap['dwell_progress'] * 100:5.0f}%", (0, 255, 100) if snap["dwell_click_enabled"] else (170, 170, 170)),
            ("Screen pos", f"{snap['last_screen_x']}, {snap['last_screen_y']}", (230, 230, 230)),
            ("Clicks", f"{snap['click_count']}", (230, 230, 230)),
        ]

        yy = y + 62

        for label, value, color in lines:
            put_text(
                frame,
                label,
                (x + 16, yy),
                scale=0.43,
                color=(175, 175, 175),
                thickness=1,
            )

            put_text(
                frame,
                value,
                (x + 155, yy),
                scale=0.45,
                color=color,
                thickness=1,
            )

            yy += 18

    def draw_help(self, frame: np.ndarray, snap: Dict[str, Any]) -> None:
        if not snap["show_help"]:
            return

        h, w = frame.shape[:2]

        panel_w = 700
        panel_h = 174
        x = 12
        y = h - panel_h - 12

        draw_panel(frame, x, y, panel_w, panel_h, alpha=0.50)

        put_text(
            frame,
            "CONTROLS",
            (x + 16, y + 30),
            scale=0.55,
            color=(255, 255, 255),
            thickness=2,
        )

        controls = [
            "Q/ESC exit   P pause   R recalibrate   S save calibration   L load calibration",
            "D dwell click   C blink click   F fast/balanced   B edge assist",
            "U taskbar hover freeze   A auto-hide taskbar   T taskbar line up   Y down",
            "M metrics   H help",
        ]

        yy = y + 62

        for line in controls:
            put_text(
                frame,
                line,
                (x + 16, yy),
                scale=0.44,
                color=(220, 220, 220),
                thickness=1,
            )
            yy += 23

    def draw_calibration(self, frame: np.ndarray, snap: Dict[str, Any]) -> None:
        if snap["calibrated"]:
            return

        h, w = frame.shape[:2]
        progress = snap["calibration_progress"]

        cv2.rectangle(
            frame,
            (0, h - 7),
            (int(w * progress), h),
            (0, 255, 255),
            -1,
        )

        draw_panel(
            frame,
            int(w * 0.5) - 310,
            int(h * 0.5) - 94,
            620,
            165,
            alpha=0.54,
        )

        put_text(
            frame,
            "Calibrating Yeux HyperProduct",
            (int(w * 0.5) - 230, int(h * 0.5) - 45),
            scale=0.65,
            color=(255, 255, 255),
            thickness=2,
        )

        put_text(
            frame,
            "Move your head and look with your pupils to all corners",
            (int(w * 0.5) - 245, int(h * 0.5) - 6),
            scale=0.48,
            color=(0, 255, 255),
            thickness=1,
        )

        put_text(
            frame,
            "Look down hard to train taskbar access",
            (int(w * 0.5) - 154, int(h * 0.5) + 25),
            scale=0.43,
            color=(210, 210, 210),
            thickness=1,
        )

        try:
            px, py = self.calibration.current_point()
            cx = int(px * w)
            cy = int(py * h)

            cv2.circle(frame, (cx, cy), 22, (0, 255, 255), 2)
            cv2.circle(frame, (cx, cy), 5, (0, 255, 255), -1)
        except Exception:
            pass

    def draw_crosshair(self, frame: np.ndarray, snap: Dict[str, Any]) -> None:
        if not self.config.show_crosshair:
            return

        h, w = frame.shape[:2]

        x = int(snap["cursor_norm_x"] * w)
        y = int(snap["cursor_norm_y"] * h)

        if snap["taskbar_frozen"]:
            cross_color = (0, 255, 255)
        elif snap["dwell_progress"] > 0:
            cross_color = (0, 255, 100)
        else:
            cross_color = (255, 255, 255)

        cv2.circle(frame, (x, y), 16, cross_color, 1)
        cv2.circle(frame, (x, y), 3, cross_color, -1)

        if snap["dwell_click_enabled"] and self.dwell_config.show_ring:
            progress = snap["dwell_progress"]

            if progress > 0:
                radius = 22
                end_angle = int(360 * progress)
                cv2.ellipse(
                    frame,
                    (x, y),
                    (radius, radius),
                    0,
                    0,
                    end_angle,
                    (0, 255, 100),
                    2,
                )

        tx = int(snap["target_norm_x"] * w)
        ty = int(snap["target_norm_y"] * h)

        cv2.circle(frame, (tx, ty), 8, (0, 255, 255), 1)

    def draw_edge_zones(self, frame: np.ndarray, snap: Dict[str, Any]) -> None:
        if not self.config.show_edge_zones:
            return

        if not snap["edge_assist_enabled"]:
            return

        h, w = frame.shape[:2]

        zone = 10

        cv2.rectangle(frame, (0, 0), (w - 1, zone), (55, 55, 55), 1)
        cv2.rectangle(frame, (0, h - zone), (w - 1, h - 1), (0, 255, 255), 1)
        cv2.rectangle(frame, (0, 0), (zone, h - 1), (55, 55, 55), 1)
        cv2.rectangle(frame, (w - zone, 0), (w - 1, h - 1), (55, 55, 55), 1)

        taskbar_y = h - int(snap["taskbar_hover_y"])
        cv2.line(frame, (0, taskbar_y), (w - 1, taskbar_y), (0, 255, 255), 1)

        label = "taskbar hover/click line"

        put_text(
            frame,
            label,
            (w // 2 - 95, taskbar_y - 6),
            scale=0.42,
            color=(0, 255, 255),
            thickness=1,
        )

    def draw_pupil_debug(self, frame: np.ndarray, snap: Dict[str, Any]) -> None:
        if not self.config.show_pupil_debug:
            return

        if not snap["has_face"]:
            return

        h, w = frame.shape[:2]

        head_x = int(snap["head_x"] * w)
        head_y = int(snap["head_y"] * h)

        iris_x = int(snap["iris_x"] * w)
        iris_y = int(snap["iris_y"] * h)

        raw_x = int(snap["raw_norm_x"] * w)
        raw_y = int(snap["raw_norm_y"] * h)

        cv2.circle(frame, (head_x, head_y), 6, (255, 255, 255), 1)
        cv2.circle(frame, (iris_x, iris_y), 6, (0, 255, 255), 1)
        cv2.circle(frame, (raw_x, raw_y), 8, (0, 255, 100), 1)

        put_text(frame, "head", (head_x + 8, head_y), 0.35, (255, 255, 255), 1)
        put_text(frame, "pupil", (iris_x + 8, iris_y), 0.35, (0, 255, 255), 1)
        put_text(frame, "fusion", (raw_x + 8, raw_y), 0.35, (0, 255, 100), 1)

    def handle_key(self, key: int) -> None:
        if key == -1:
            return

        snap = self.state.snapshot()

        if key in (27, ord("q"), ord("Q")):
            self.state.set(running=False)
            return

        if key in (ord("p"), ord("P")):
            self.state.set(paused=not snap["paused"])
            self.sound.play("click")
            return

        if key in (ord("c"), ord("C")):
            self.state.set(blink_click_enabled=not snap["blink_click_enabled"])
            self.sound.play("click")
            return

        if key in (ord("d"), ord("D")):
            self.state.set(dwell_click_enabled=not snap["dwell_click_enabled"])
            self.sound.play("click")
            return

        if key in (ord("f"), ord("F")):
            self.state.set(fast_mode=not snap["fast_mode"])
            self.sound.play("click")
            return

        if key in (ord("b"), ord("B")):
            self.state.set(edge_assist_enabled=not snap["edge_assist_enabled"])
            self.sound.play("click")
            return

        if key in (ord("u"), ord("U")):
            self.state.set(taskbar_lock_enabled=not snap["taskbar_lock_enabled"])
            self.sound.play("click")
            return

        if key in (ord("a"), ord("A")):
            self.state.set(auto_hide_taskbar_mode=not snap["auto_hide_taskbar_mode"])
            self.sound.play("click")
            return

        if key in (ord("m"), ord("M")):
            self.state.set(show_metrics=not snap["show_metrics"])
            return

        if key in (ord("h"), ord("H")):
            self.state.set(show_help=not snap["show_help"])
            return

        if key in (ord("t"), ord("T")):
            new_y = int(clamp(snap["taskbar_hover_y"] + 4, 18, 100))
            self.state.set(
                taskbar_hover_y=new_y,
                user_message=f"Taskbar hover Y: {new_y}px",
            )
            return

        if key in (ord("y"), ord("Y")):
            new_y = int(clamp(snap["taskbar_hover_y"] - 4, 18, 100))
            self.state.set(
                taskbar_hover_y=new_y,
                user_message=f"Taskbar hover Y: {new_y}px",
            )
            return

        if key in (ord("r"), ord("R")):
            self.calibration.reset()
            self.state.set(
                calibrated=False,
                calibrating=True,
                calibration_progress=0.0,
                status_message="recalibrating",
                user_message="Recalibrating HyperProduct...",
            )
            self.sound.play("calibration")
            return

        if key in (ord("s"), ord("S")):
            ok = self.calibration.save()
            self.state.set(
                user_message="Calibration saved" if ok else "Could not save calibration"
            )
            return

        if key in (ord("l"), ord("L")):
            ok = self.calibration.load()
            self.state.set(
                calibrated=ok,
                calibrating=not ok,
                calibration_progress=1.0 if ok else 0.0,
                user_message="Calibration loaded" if ok else "No calibration file found",
            )
            return

    def run(self) -> None:
       if self.state.snapshot().get("headless", False):
        return

       cv2.namedWindow(self.config.window_name, cv2.WINDOW_NORMAL)

       while self.state.snapshot()["running"]:
            try:
                packet: FramePacket = self.frame_q.get(timeout=0.04)
                self.latest_frame = packet.frame.copy()
            except queue.Empty:
                if self.latest_frame is None:
                    time.sleep(0.01)
                    continue

            frame = self.latest_frame.copy()
            snap = self.state.snapshot()

            self.draw_edge_zones(frame, snap)
            self.draw_header(frame, snap)
            self.draw_metrics(frame, snap)
            self.draw_help(frame, snap)
            self.draw_calibration(frame, snap)
            self.draw_crosshair(frame, snap)
            self.draw_pupil_debug(frame, snap)

            if snap["error_message"]:
                h, w = frame.shape[:2]
                put_text(
                    frame,
                    f"ERR: {snap['error_message'][:95]}",
                    (18, h - 16),
                    scale=0.45,
                    color=(0, 0, 255),
                    thickness=1,
                )
                if not self.state.snapshot().get("headless", False):
                 cv2.imshow(self.config.window_name, frame)

                key = cv2.waitKey(1) & 0xFF
                self.handle_key(key)
   

    cv2.destroyAllWindows()


# ============================================================
# APP
# ============================================================

class YeuxHyperProductApp:
    def __init__(self) -> None:
        self.config = DemoConfig()

        self.state = SharedState(
            fast_mode=self.config.fast_mode,
            blink_click_enabled=self.config.blink.enabled,
            dwell_click_enabled=self.config.dwell.enabled,
            edge_assist_enabled=self.config.cursor.edge_assist_enabled,
            taskbar_lock_enabled=self.config.cursor.taskbar_lock_enabled,
            auto_hide_taskbar_mode=self.config.cursor.auto_hide_taskbar_mode,
            show_metrics=self.config.overlay.show_metrics,
            show_help=self.config.overlay.show_help,
            taskbar_hover_y=self.config.cursor.taskbar_hover_y,


            headless=self.config.headless,
        )

        self.sound = DemoSound()

        self.frame_q_vision = LatestQueue()
        self.frame_q_overlay = LatestQueue()
        self.pose_q = LatestQueue()

        self.camera = CameraWorker(
            config=self.config.camera,
            state=self.state,
            frame_q_vision=self.frame_q_vision,
            frame_q_overlay=self.frame_q_overlay,
        )

        self.vision = FacePupilLandmarkerWorker(
            model_config=self.config.model,
            calibration_config=self.config.calibration,
            fusion_config=self.config.fusion,
            state=self.state,
            frame_q=self.frame_q_vision,
            pose_q=self.pose_q,
            sound=self.sound,
        )

        self.cursor = CursorWorker(
            config=self.config.cursor,
            blink_config=self.config.blink,
            dwell_config=self.config.dwell,
            state=self.state,
            pose_q=self.pose_q,
            sound=self.sound,
        )

        self.overlay = OverlayWorker(
            config=self.config.overlay,
            calibration=self.vision.calibration,
            dwell_config=self.config.dwell,
            state=self.state,
            frame_q=self.frame_q_overlay,
            sound=self.sound,
        )

        self.logger = MetricsLogger(
            path=self.config.log_file,
            state=self.state,
        )

        self.threads: List[threading.Thread] = []

    def start_thread(self, target: Any, name: str) -> None:
        t = threading.Thread(
            target=target,
            name=name,
            daemon=True,
        )
        t.start()
        self.threads.append(t)

    def run_logger_loop(self) -> None:
        while self.state.snapshot()["running"]:
            self.logger.maybe_log()
            time.sleep(0.1)

    def try_load_calibration_on_start(self) -> None:
        ok = self.vision.calibration.load()

        if ok:
            self.state.set(
                calibrated=True,
                calibrating=False,
                calibration_progress=1.0,
                user_message="Hyper calibration loaded",
            )
        else:
            self.state.set(
                calibrated=False,
                calibrating=True,
                calibration_progress=0.0,
                user_message="Starting HyperProduct calibration",
            )

    def run(self) -> None:
        self.sound.play("startup")

        self.try_load_calibration_on_start()

        self.start_thread(self.camera.run, "camera")
        self.start_thread(self.vision.run, "vision")
        self.start_thread(self.cursor.run, "cursor")
        self.start_thread(self.run_logger_loop, "logger")

        if not self.config.headless:
            try:
                self.overlay.run()
            except KeyboardInterrupt:
                pass
            except Exception:
                traceback.print_exc()
            finally:
                self.shutdown()
        else:
            try:
                while self.state.snapshot()["running"]:
                    time.sleep(0.2)
            except KeyboardInterrupt:
                pass
            finally:
                self.shutdown()

    def shutdown(self) -> None:
        self.state.set(running=False)
        time.sleep(0.2)
        self.sound.stop()


# ============================================================
# ENTRYPOINT
# ============================================================

def main() -> None:
    app = YeuxHyperProductApp()
    app.run()


if __name__ == "__main__":
    main()