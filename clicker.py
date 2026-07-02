"""
clicker.py  —  Win32 SendInput tiklama motoru  v9.0
=====================================================
Modlar:
  shift_right  — Shift + Sag Tik  (varsayilan)
  left         — Sol Tik
  right        — Sag Tik
  double_left  — Cift Sol Tik
  ctrl_click   — Ctrl + Sol Tik
  ctrl_right   — Ctrl + Sag Tik
  shift_left   — Shift + Sol Tik

Ozellikler:
  • Win32 SendInput  (en guvenilir, DirectInput uyumlu)
  • Scan kodu ile modifier tuslar  (anti-hook)
  • Human-like Bezier hareketi  (opsiyonel)
  • Degisken hold/pre-move suresi  (anti-detection)
  • pyautogui fallback
"""

import ctypes
import random
import time
from ctypes import wintypes
from typing import Optional


# ── Win32 sabitleri ───────────────────────────────────────────────────────────
INPUT_MOUSE         = 0
INPUT_KEYBOARD      = 1

MOUSEEVENTF_MOVE        = 0x0001
MOUSEEVENTF_LEFTDOWN    = 0x0002
MOUSEEVENTF_LEFTUP      = 0x0004
MOUSEEVENTF_RIGHTDOWN   = 0x0008
MOUSEEVENTF_RIGHTUP     = 0x0010
MOUSEEVENTF_ABSOLUTE    = 0x8000

KEYEVENTF_KEYUP         = 0x0002
KEYEVENTF_SCANCODE      = 0x0008

VK_LSHIFT   = 0xA0
VK_LCONTROL = 0xA2
SCAN_LSHIFT = 0x2A
SCAN_LCTRL  = 0x1D


# ── ctypes yapıları ───────────────────────────────────────────────────────────
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx",          wintypes.LONG),
        ("dy",          wintypes.LONG),
        ("mouseData",   wintypes.DWORD),
        ("dwFlags",     wintypes.DWORD),
        ("time",        wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk",         wintypes.WORD),
        ("wScan",       wintypes.WORD),
        ("dwFlags",     wintypes.DWORD),
        ("time",        wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("_input", _INPUT_UNION)]


_INPUT_SIZE = ctypes.sizeof(INPUT)
_user32     = ctypes.windll.user32


# ── Yardımcılar ───────────────────────────────────────────────────────────────
def _screen_size() -> tuple[int, int]:
    return _user32.GetSystemMetrics(0), _user32.GetSystemMetrics(1)


def _to_abs(x: int, y: int) -> tuple[int, int]:
    sw, sh = _screen_size()
    return int(x * 65535 / max(sw, 1)), int(y * 65535 / max(sh, 1))


def _mi(flags: int, x: int = 0, y: int = 0) -> INPUT:
    i = INPUT(); i.type = INPUT_MOUSE
    i._input.mi.dx = x; i._input.mi.dy = y
    i._input.mi.mouseData = 0; i._input.mi.dwFlags = flags
    i._input.mi.time = 0; i._input.mi.dwExtraInfo = None
    return i


def _ki(vk: int, scan: int, flags: int) -> INPUT:
    i = INPUT(); i.type = INPUT_KEYBOARD
    i._input.ki.wVk = vk; i._input.ki.wScan = scan
    i._input.ki.dwFlags = flags; i._input.ki.time = 0
    i._input.ki.dwExtraInfo = None
    return i


def _send(*inputs: INPUT) -> bool:
    n   = len(inputs)
    arr = (INPUT * n)(*inputs)
    return _user32.SendInput(n, arr, _INPUT_SIZE) == n


def _rnd_delay(base_ms: int, variance: float = 0.3) -> float:
    """base_ms etrafinda +/- variance oraninda rastgele gecikme."""
    lo = base_ms * (1 - variance)
    hi = base_ms * (1 + variance)
    return random.uniform(lo, hi) / 1000.0


def _jitter_coords(x: int, y: int, radius: int) -> tuple[int, int]:
    if radius <= 0:
        return x, y
    dx = random.randint(-radius, radius)
    dy = random.randint(-radius, radius)
    return x + dx, y + dy


# ── Hareket ───────────────────────────────────────────────────────────────────
def _move_to(x: int, y: int, human: bool, human_speed: float, jitter: int) -> None:
    if human:
        try:
            import humanizer
            cx = ctypes.windll.user32.GetCursorPos
            pt = ctypes.wintypes.POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
            humanizer.human_move(pt.x, pt.y, x, y,
                                  speed=human_speed, jitter=jitter)
            return
        except Exception:
            pass
    # Direkt mutlak hareket
    ax, ay = _to_abs(x, y)
    _send(_mi(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, ax, ay))


# ── Tıklama fonksiyonları ─────────────────────────────────────────────────────
def _base_click(
    x: int, y: int,
    down_flag: int, up_flag: int,
    rand_offset: int = 0,
    pre_move_ms: int = 20,
    hold_ms:     int = 30,
    human:       bool  = False,
    human_speed: float = 1.0,
    jitter:      int   = 2,
) -> bool:
    x, y = _jitter_coords(x, y, rand_offset)
    ax, ay = _to_abs(x, y)
    try:
        _move_to(x, y, human, human_speed, jitter)
        time.sleep(_rnd_delay(pre_move_ms))
        _send(_mi(down_flag | MOUSEEVENTF_ABSOLUTE, ax, ay))
        time.sleep(_rnd_delay(hold_ms))
        _send(_mi(up_flag  | MOUSEEVENTF_ABSOLUTE, ax, ay))
        return True
    except Exception:
        return False


def _modifier_click(
    x: int, y: int,
    mod_vk: int, mod_scan: int,
    btn_down: int, btn_up: int,
    rand_offset: int = 0,
    pre_move_ms: int = 20,
    hold_ms:     int = 35,
    human:       bool  = False,
    human_speed: float = 1.0,
    jitter:      int   = 2,
) -> bool:
    x, y = _jitter_coords(x, y, rand_offset)
    ax, ay = _to_abs(x, y)
    try:
        _move_to(x, y, human, human_speed, jitter)
        time.sleep(_rnd_delay(pre_move_ms))
        _send(_ki(mod_vk, mod_scan, KEYEVENTF_SCANCODE))
        time.sleep(_rnd_delay(hold_ms))
        _send(_mi(btn_down | MOUSEEVENTF_ABSOLUTE, ax, ay))
        time.sleep(_rnd_delay(hold_ms))
        _send(_mi(btn_up   | MOUSEEVENTF_ABSOLUTE, ax, ay))
        time.sleep(_rnd_delay(hold_ms))
        _send(_ki(mod_vk, mod_scan, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP))
        return True
    except Exception:
        return False


# ── Public mod fonksiyonları ──────────────────────────────────────────────────
def shift_right_click(x, y, rand_offset=0, pre_move_ms=20, hold_ms=35,
                      human=False, human_speed=1.0, jitter=2):
    ok = _modifier_click(x, y, VK_LSHIFT, SCAN_LSHIFT,
                         MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP,
                         rand_offset, pre_move_ms, hold_ms, human, human_speed, jitter)
    if ok:
        return True
    # pyautogui fallback
    try:
        import pyautogui
        pyautogui.keyDown("shift"); time.sleep(0.03)
        pyautogui.click(x, y, button="right"); time.sleep(0.03)
        pyautogui.keyUp("shift")
    except Exception:
        pass
    return False


def left_click(x, y, rand_offset=0, pre_move_ms=20, hold_ms=30,
               human=False, human_speed=1.0, jitter=2):
    return _base_click(x, y, MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP,
                       rand_offset, pre_move_ms, hold_ms, human, human_speed, jitter)


def right_click(x, y, rand_offset=0, pre_move_ms=20, hold_ms=30,
                human=False, human_speed=1.0, jitter=2):
    return _base_click(x, y, MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP,
                       rand_offset, pre_move_ms, hold_ms, human, human_speed, jitter)


def double_left_click(x, y, rand_offset=0, pre_move_ms=20, hold_ms=30,
                      human=False, human_speed=1.0, jitter=2):
    r = left_click(x, y, rand_offset, pre_move_ms, hold_ms, human, human_speed, jitter)
    time.sleep(random.uniform(0.06, 0.14))
    left_click(x, y, rand_offset // 2, 5, hold_ms, False, 1.0, 0)
    return r


def ctrl_click(x, y, rand_offset=0, pre_move_ms=20, hold_ms=35,
               human=False, human_speed=1.0, jitter=2):
    return _modifier_click(x, y, VK_LCONTROL, SCAN_LCTRL,
                           MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP,
                           rand_offset, pre_move_ms, hold_ms, human, human_speed, jitter)


def ctrl_right_click(x, y, rand_offset=0, pre_move_ms=20, hold_ms=35,
                     human=False, human_speed=1.0, jitter=2):
    return _modifier_click(x, y, VK_LCONTROL, SCAN_LCTRL,
                           MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP,
                           rand_offset, pre_move_ms, hold_ms, human, human_speed, jitter)


def shift_left_click(x, y, rand_offset=0, pre_move_ms=20, hold_ms=35,
                     human=False, human_speed=1.0, jitter=2):
    return _modifier_click(x, y, VK_LSHIFT, SCAN_LSHIFT,
                           MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP,
                           rand_offset, pre_move_ms, hold_ms, human, human_speed, jitter)


# ── Dispatcher ────────────────────────────────────────────────────────────────
MODES: dict[str, callable] = {
    "shift_right":  shift_right_click,
    "left":         left_click,
    "right":        right_click,
    "double_left":  double_left_click,
    "ctrl_click":   ctrl_click,
    "ctrl_right":   ctrl_right_click,
    "shift_left":   shift_left_click,
}

MODE_LABELS: dict[str, str] = {
    "shift_right":  "Shift + Sag Tik",
    "left":         "Sol Tik",
    "right":        "Sag Tik",
    "double_left":  "Cift Sol Tik",
    "ctrl_click":   "Ctrl + Sol Tik",
    "ctrl_right":   "Ctrl + Sag Tik",
    "shift_left":   "Shift + Sol Tik",
}


def do_click(
    mode:        str,
    x:           int,
    y:           int,
    rand_offset: int   = 0,
    pre_move_ms: int   = 20,
    hold_ms:     int   = 35,
    human:       bool  = False,
    human_speed: float = 1.0,
    jitter:      int   = 2,
) -> bool:
    fn = MODES.get(mode, shift_right_click)
    return fn(x, y, rand_offset, pre_move_ms, hold_ms, human, human_speed, jitter)
