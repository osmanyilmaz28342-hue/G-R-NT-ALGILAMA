"""
humanizer.py  —  Insan gibi fare hareketi  v9.0
=================================================
• Cubic Bezier eğrisi (dogrusal degil)
• Ease-in-out hiz profili (basta/sonda yavas, ortada hizli)
• Gaussian mikro titreme
• Overshoot + düzeltme
• Win32 SendInput ile (pyautogui'ye gerek yok)
"""

import ctypes
import math
import random
import time
from ctypes import wintypes


# ── Win32 ────────────────────────────────────────────────────────────────────
INPUT_MOUSE          = 0
MOUSEEVENTF_MOVE     = 0x0001
MOUSEEVENTF_ABSOLUTE = 0x8000


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx",          wintypes.LONG),
        ("dy",          wintypes.LONG),
        ("mouseData",   wintypes.DWORD),
        ("dwFlags",     wintypes.DWORD),
        ("time",        wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
    ]


class _UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("_input", _UNION)]


_u32      = ctypes.windll.user32
_INP_SIZE = ctypes.sizeof(INPUT)


def _screen_wh() -> tuple[int, int]:
    return _u32.GetSystemMetrics(0), _u32.GetSystemMetrics(1)


def _move_abs(x: int, y: int) -> None:
    sw, sh = _screen_wh()
    ax = int(x * 65535 / max(sw, 1))
    ay = int(y * 65535 / max(sh, 1))
    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp._input.mi.dx     = ax
    inp._input.mi.dy     = ay
    inp._input.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE
    inp._input.mi.dwExtraInfo = None
    _u32.SendInput(1, ctypes.byref(inp), _INP_SIZE)


# ── Bezier ────────────────────────────────────────────────────────────────────
def _cubic(t: float, p0, p1, p2, p3) -> tuple[float, float]:
    u = 1 - t
    return (
        u**3*p0[0] + 3*u**2*t*p1[0] + 3*u*t**2*p2[0] + t**3*p3[0],
        u**3*p0[1] + 3*u**2*t*p1[1] + 3*u*t**2*p2[1] + t**3*p3[1],
    )


def _ease_inout(t: float) -> float:
    """Smoothstep — ease in-out"""
    return t * t * (3 - 2 * t)


# ── Public ────────────────────────────────────────────────────────────────────
def human_move(
    x0: int, y0: int,
    x1: int, y1: int,
    speed: float  = 1.0,
    jitter: int   = 2,
    overshoot: bool = True,
) -> None:
    """
    (x0,y0) → (x1,y1) insan gibi Bezier hareketi.
    speed   : 0.5=cok yavas, 1.0=normal, 3.0=cok hizli
    jitter  : mikro titreme px (0=kapat)
    overshoot: hedefe biraz gecip geri gel (gercekci)
    """
    dist = math.hypot(x1 - x0, y1 - y0)
    if dist < 2:
        _move_abs(x1, y1)
        return

    # Kontrol noktasi sapmasi mesafeye gore
    spread = min(dist * 0.35, 60)
    p0 = (float(x0), float(y0))
    p3 = (float(x1), float(y1))
    p1 = (
        x0 + (x1 - x0) * 0.25 + random.uniform(-spread, spread),
        y0 + (y1 - y0) * 0.25 + random.uniform(-spread, spread),
    )
    p2 = (
        x0 + (x1 - x0) * 0.75 + random.uniform(-spread, spread),
        y0 + (y1 - y0) * 0.75 + random.uniform(-spread, spread),
    )

    # Overshoot: hedeft biraz gecik, geri don
    if overshoot and dist > 30 and random.random() < 0.6:
        dx = x1 - x0; dy = y1 - y0
        ovs = random.uniform(0.02, 0.07)
        px = float(x1 + dx * ovs + random.uniform(-3, 3))
        py = float(y1 + dy * ovs + random.uniform(-3, 3))
        # iki asama: x0→overshoot, overshoot→x1
        human_move(x0, y0, int(px), int(py), speed=speed * 1.1,
                   jitter=jitter, overshoot=False)
        time.sleep(random.uniform(0.01, 0.03))
        human_move(int(px), int(py), x1, y1, speed=speed * 0.8,
                   jitter=max(0, jitter - 1), overshoot=False)
        return

    steps = max(8, int(dist / speed * 0.35))
    dt    = max(0.0005, 0.004 / speed)

    px, py = x0, y0
    for i in range(steps + 1):
        t  = _ease_inout(i / steps)
        bx, by = _cubic(t, p0, p1, p2, p3)

        if jitter > 0 and 0 < i < steps:
            bx += random.gauss(0, jitter * 0.25)
            by += random.gauss(0, jitter * 0.25)

        nx, ny = int(bx), int(by)
        if nx != px or ny != py:
            _move_abs(nx, ny)
            px, py = nx, ny

        # ortada hizli, basta/sonda yavas
        phase = 1.0 - abs(t - 0.5) * 1.2
        time.sleep(dt / max(phase, 0.15))

    _move_abs(x1, y1)
