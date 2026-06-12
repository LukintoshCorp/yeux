import time
import platform
import ctypes
from ctypes import wintypes
from typing import Tuple

from yeux_input_contract import YeuxMouseEvent


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


class YeuxInputBackend:
    def move_relative(self, dx: int, dy: int) -> None:
        raise NotImplementedError

    def left_down(self) -> None:
        raise NotImplementedError

    def left_up(self) -> None:
        raise NotImplementedError

    def left_click(self) -> None:
        self.left_down()
        time.sleep(0.045)
        self.left_up()

    def send_event(self, event: YeuxMouseEvent) -> None:
        if event.dx != 0 or event.dy != 0:
            self.move_relative(event.dx, event.dy)

        if event.left:
            self.left_click()


class WindowsSendInputBackend(YeuxInputBackend):
    INPUT_MOUSE = 0

    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004

    def __init__(self) -> None:
        if platform.system().lower() != "windows":
            raise RuntimeError("WindowsSendInputBackend only works on Windows.")

        self.user32 = ctypes.windll.user32

    def _send_mouse_event(self, dx: int, dy: int, flags: int) -> None:
        extra = ctypes.c_ulong(0)

        mouse_input = MOUSEINPUT(
            dx=int(dx),
            dy=int(dy),
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

    def move_relative(self, dx: int, dy: int) -> None:
        self._send_mouse_event(
            dx=dx,
            dy=dy,
            flags=self.MOUSEEVENTF_MOVE,
        )

    def left_down(self) -> None:
        self._send_mouse_event(
            dx=0,
            dy=0,
            flags=self.MOUSEEVENTF_LEFTDOWN,
        )

    def left_up(self) -> None:
        self._send_mouse_event(
            dx=0,
            dy=0,
            flags=self.MOUSEEVENTF_LEFTUP,
        )


class YeuxHIDPipeBackend(YeuxInputBackend):
    """
    Futuro backend do produto.

    Aqui depois vamos mandar o evento para:
    \\\\.\\pipe\\LukintoshYeuxInput

    O YeuxInputService recebe e encaminha para o driver:
    Lukintosh Yeux Virtual Mouse.
    """

    def __init__(self) -> None:
        self.pipe_name = r"\\.\pipe\LukintoshYeuxInput"

    def move_relative(self, dx: int, dy: int) -> None:
        event = YeuxMouseEvent(dx=dx, dy=dy, left=False)
        self._send_to_pipe(event)

    def left_down(self) -> None:
        event = YeuxMouseEvent(dx=0, dy=0, left=True)
        self._send_to_pipe(event)

    def left_up(self) -> None:
        event = YeuxMouseEvent(dx=0, dy=0, left=False)
        self._send_to_pipe(event)

    def _send_to_pipe(self, event: YeuxMouseEvent) -> None:
        # Placeholder.
        # Depois vamos implementar Named Pipe real aqui.
        print(event.to_json())


def create_backend(mode: str = "sendinput") -> YeuxInputBackend:
    if mode == "sendinput":
        return WindowsSendInputBackend()

    if mode == "hidpipe":
        return YeuxHIDPipeBackend()

    raise ValueError(f"Unknown backend mode: {mode}")