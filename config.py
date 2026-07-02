"""
config.py  —  Ayar kaliciligi  v9.0
=====================================
• config.json  ile JSON-tabanlı kayit
• DEFAULT ile güvenli birleştirme (yeni anahtarlar kaybolmaz)
• import/export yardimcilari
"""

import json
import os

DEFAULT: dict = {
    # Eslestirme
    "confidence":       0.80,
    "multiscale":       True,
    "scales_min":       0.50,
    "scales_max":       2.00,
    "scales_steps":     12,
    "nms_iou":          30,         # %
    "use_clahe":        True,
    "blur_kernel":      0,          # 0=kapali, 3/5=acik
    "match_method":     "CCOEFF",   # CCOEFF | SQDIFF

    # Tiklama
    "click_mode":       "shift_right",
    "rand_offset":      3,
    "pre_move_ms":      20,
    "hold_ms":          35,
    "post_click_ms":    60,

    # Insan gibi hareket
    "human_move":       False,
    "human_speed":      1.0,        # 0.5=cok yavas, 3.0=cok hizli
    "human_jitter":     2,

    # Dongü
    "repeat":           9999,
    "interval":         1.0,
    "skip_radius":      40,
    "adaptive_conf":    True,
    "adaptive_min":     0.50,

    # Zamanlayici
    "scheduler_enabled":    False,
    "scheduler_start":      "",     # "HH:MM"
    "scheduler_stop":       "",     # "HH:MM"
    "max_clicks":           0,      # 0=sinirsiz
    "max_duration_min":     0,      # 0=sinirsiz
    "break_every_min":      0,      # 0=kapali
    "break_for_sec":        30,

    # Ozellikler
    "sound_alert":          True,
    "overlay_enabled":      True,
    "overlay_duration":     1500,
    "log_to_file":          True,
    "pause_on_unfocus":     False,
    "screenshot_on_detect": False,  # eslesme bulununca ekran goruntusu kaydet
    "priority_mode":        "score",# score | nearest | random | left_right

    # Durum
    "image_paths":      [],
    "window_title":     "",
    "capture_region":   None,       # [x1,y1,x2,y2] veya null
}


def cfg_path(script_dir: str) -> str:
    return os.path.join(script_dir, "config.json")


def load(script_dir: str) -> dict:
    cfg = dict(DEFAULT)
    p   = cfg_path(script_dir)
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                saved = json.load(f)
            for k in DEFAULT:
                if k in saved:
                    cfg[k] = saved[k]
        except Exception:
            pass
    return cfg


def save(script_dir: str, cfg: dict) -> None:
    p = cfg_path(script_dir)
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def build_scales(cfg: dict) -> list[float]:
    """config'den scale listesi olustur."""
    lo    = float(cfg.get("scales_min", 0.50))
    hi    = float(cfg.get("scales_max", 2.00))
    steps = int(cfg.get("scales_steps", 12))
    if steps < 1:
        return [1.0]
    if steps == 1:
        return [1.0]
    step  = (hi - lo) / (steps - 1)
    return [round(lo + i * step, 3) for i in range(steps)]
