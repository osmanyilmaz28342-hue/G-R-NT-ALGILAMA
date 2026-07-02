"""
detector.py  —  OpenCV eslestirme motoru  v9.0
================================================
Teknikler:
  • mss ile ultra hizli ekran yakalama  (PIL'den ~10x hizli)
  • PIL fallback  (mss yoksa)
  • CLAHE on-the-fly kontrast normalizasyonu  (isiga dayanikli)
  • TM_CCOEFF_NORMED  (en guvenilir metot)
  • TM_SQDIFF_NORMED  (alternatif — aydinlatmaya bağimsiz)
  • Multi-scale  (0.50→2.00×, 13 adim)
  • Grayscale matching
  • Gaussian blur on-option  (gurultulu ekranlar icin)
  • NMS  (cift tiklama yok)
  • ROI destegi  (sadece belirlenen bölgeyi tara)
"""

import math
from typing import Optional

import cv2
import numpy as np
from PIL import Image

# mss daha hizli — varsa kullan
try:
    import mss as _mss_lib
    _MSS = _mss_lib.mss()
    HAS_MSS = True
except Exception:
    _MSS    = None
    HAS_MSS = False

try:
    from PIL import ImageGrab as _ImageGrab
    HAS_PIL_GRAB = True
except Exception:
    HAS_PIL_GRAB = False


# ── Scale seti ────────────────────────────────────────────────────────────────
SCALES_DEFAULT = [0.50, 0.60, 0.70, 0.80, 0.90, 1.00,
                  1.10, 1.20, 1.30, 1.50, 1.75, 2.00]


# ── Ekran yakalama ────────────────────────────────────────────────────────────
def grab_screen(region: Optional[tuple] = None) -> np.ndarray:
    """
    Ekrani BGR numpy olarak yakala.
    region: (x1, y1, x2, y2)  None=tum ekran
    """
    if HAS_MSS and _MSS is not None:
        try:
            if region:
                x1, y1, x2, y2 = region
                mon = {"left": x1, "top": y1, "width": x2 - x1, "height": y2 - y1}
            else:
                mon = _MSS.monitors[0]  # tum ekranlar birlesi
            raw = _MSS.grab(mon)
            arr = np.array(raw, dtype=np.uint8)          # BGRA
            return cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)
        except Exception:
            pass  # fallback

    # PIL fallback
    if HAS_PIL_GRAB:
        bbox = None
        if region:
            x1, y1, x2, y2 = region
            bbox = (x1, y1, x2, y2)
        pil = _ImageGrab.grab(bbox=bbox, all_screens=True)
        arr = np.array(pil, dtype=np.uint8)              # RGB
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

    raise RuntimeError("Ekran yakalama basarisiz: mss ve PIL bulunamadi")


# ── Template yukleme ──────────────────────────────────────────────────────────
def load_template(path: str) -> np.ndarray:
    """PIL ile yukle → grayscale numpy  (Turkce yol guvenli)"""
    img = Image.open(path).convert("L")
    return np.array(img, dtype=np.uint8)


# ── Preprocessing ─────────────────────────────────────────────────────────────
def _preprocess(gray: np.ndarray, clahe: bool = True, blur: int = 0) -> np.ndarray:
    out = gray
    if blur > 0 and blur % 2 == 1:
        out = cv2.GaussianBlur(out, (blur, blur), 0)
    if clahe:
        cl = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        out = cl.apply(out)
    return out


# ── NMS ──────────────────────────────────────────────────────────────────────
def nms(
    boxes:  list[tuple[int, int, int, int]],
    scores: list[float],
    iou_thresh: float = 0.3,
) -> list[int]:
    if not boxes:
        return []
    order      = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    keep: list[int] = []
    suppressed  = set()

    for i in order:
        if i in suppressed:
            continue
        keep.append(i)
        x1, y1, w1, h1 = boxes[i]
        for j in order:
            if j in suppressed or j == i:
                continue
            x2, y2, w2, h2 = boxes[j]
            ix = max(0, min(x1+w1, x2+w2) - max(x1, x2))
            iy = max(0, min(y1+h1, y2+h2) - max(y1, y2))
            inter = ix * iy
            union = w1*h1 + w2*h2 - inter
            if union > 0 and inter / union > iou_thresh:
                suppressed.add(j)
    return keep


# ── Tek ölçek ─────────────────────────────────────────────────────────────────
def match_single(
    haystack_g: np.ndarray,
    template_g: np.ndarray,
    threshold:  float,
    method:     int = cv2.TM_CCOEFF_NORMED,
) -> list[tuple[int, int, int, int, float]]:
    th, tw = template_g.shape
    if tw > haystack_g.shape[1] or th > haystack_g.shape[0]:
        return []
    res  = cv2.matchTemplate(haystack_g, template_g, method)
    if method == cv2.TM_SQDIFF_NORMED:
        # SQDIFF: kucuk = iyi — dönüstür
        res  = 1.0 - res
    ys, xs = np.where(res >= threshold)
    return [(int(x), int(y), tw, th, float(res[y, x])) for x, y in zip(xs, ys)]


# ── Multi-scale ───────────────────────────────────────────────────────────────
def match_multiscale(
    haystack_g: np.ndarray,
    template_g: np.ndarray,
    threshold:  float,
    scales:     list[float] = SCALES_DEFAULT,
    method:     int         = cv2.TM_CCOEFF_NORMED,
) -> list[tuple[int, int, int, int, float]]:
    results = []
    oth, otw = template_g.shape

    for sc in scales:
        nw = max(4, int(otw * sc))
        nh = max(4, int(oth * sc))
        if nw > haystack_g.shape[1] or nh > haystack_g.shape[0]:
            continue
        tpl = cv2.resize(template_g, (nw, nh), interpolation=cv2.INTER_AREA)
        res = cv2.matchTemplate(haystack_g, tpl, method)
        if method == cv2.TM_SQDIFF_NORMED:
            res = 1.0 - res
        ys, xs = np.where(res >= threshold)
        for x, y in zip(xs, ys):
            results.append((int(x), int(y), nw, nh, float(res[y, x])))
    return results


# ── DetectionResult ───────────────────────────────────────────────────────────
class DetectionResult:
    __slots__ = ("x", "y", "w", "h", "score", "template_name", "cx", "cy")

    def __init__(self, x, y, w, h, score, template_name):
        self.x = x; self.y = y; self.w = w; self.h = h
        self.score         = score
        self.template_name = template_name
        self.cx = x + w // 2
        self.cy = y + h // 2

    def screen_coords(self, offset=(0, 0)):
        return self.cx + offset[0], self.cy + offset[1]

    def box_screen(self, offset=(0, 0)):
        return (self.x + offset[0], self.y + offset[1], self.w, self.h)

    def __repr__(self):
        return (f"Det({self.template_name}@({self.cx},{self.cy})"
                f" s={self.score:.3f})")


# ── Ana detektör ──────────────────────────────────────────────────────────────
def detect_all(
    templates:  list[tuple[str, np.ndarray]],
    screen_bgr: np.ndarray,
    threshold:  float,
    multiscale: bool,
    nms_iou:    float = 0.3,
    scales:     list[float] = SCALES_DEFAULT,
    use_clahe:  bool  = True,
    blur:       int   = 0,
    method:     int   = cv2.TM_CCOEFF_NORMED,
) -> list[DetectionResult]:
    screen_g = cv2.cvtColor(screen_bgr, cv2.COLOR_BGR2GRAY)
    screen_g = _preprocess(screen_g, clahe=use_clahe, blur=blur)

    raw: list[tuple[int, int, int, int, float, str]] = []

    for name, tpl in templates:
        tpl_p = _preprocess(tpl, clahe=use_clahe, blur=0)
        if multiscale:
            hits = match_multiscale(screen_g, tpl_p, threshold, scales, method)
        else:
            hits = match_single(screen_g, tpl_p, threshold, method)
        for (x, y, w, h, sc) in hits:
            raw.append((x, y, w, h, sc, name))

    if not raw:
        return []

    boxes  = [(r[0], r[1], r[2], r[3]) for r in raw]
    scores = [r[4]                      for r in raw]
    kept   = nms(boxes, scores, nms_iou)

    out = [
        DetectionResult(raw[i][0], raw[i][1], raw[i][2], raw[i][3],
                        raw[i][4], raw[i][5])
        for i in kept
    ]
    out.sort(key=lambda r: r.score, reverse=True)
    return out
