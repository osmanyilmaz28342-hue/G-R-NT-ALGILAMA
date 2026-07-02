"""
main.py  —  Shift + Sag Click Bot  v9.0
=========================================
Mimari:
  detector.py    -> mss + CLAHE + multi-scale + NMS
  clicker.py     -> Win32 SendInput, 7 mod
  humanizer.py   -> Bezier insan hareketi
  overlay.py     -> Neon ekran overlay
  config.py      -> JSON ayar kaliciligi
  session_log.py -> Log + CSV export
  profiler.py    -> Named profil sistemi
  region_selector.py -> Ekranda bolge ciz

Sekmeler:
  1. Temel      — template, pencere, güven, dongü
  2. Tiklama    — mod, insan hareketi, gecikmeler
  3. Tarama     — multi-scale, yöntem, bölge, önislem
  4. Zamanlayici— otomatik baslat/durdur, max tiklamalar
  5. Profiller  — kaydet/yukle/sil
  6. Istatistik — canli grafik, CSV export
"""

import datetime
import math
import os
import random
import sys
import threading
import time
import tkinter as tk
from queue import Empty, Queue
from tkinter import filedialog, messagebox, simpledialog, ttk

_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Bagimlılık kontrolü ───────────────────────────────────────────────────────
_missing = []
try:
    import cv2, numpy as np
except ImportError:
    _missing.append("opencv-python")
try:
    import pyautogui
except ImportError:
    _missing.append("pyautogui")
try:
    import pygetwindow as gw
except ImportError:
    _missing.append("pygetwindow")
try:
    from PIL import Image, ImageDraw, ImageTk, ImageGrab
except ImportError:
    _missing.append("Pillow")
try:
    import psutil; HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
try:
    import keyboard; HAS_KEYBOARD = True
except Exception:
    HAS_KEYBOARD = False
try:
    import mss as _mss; HAS_MSS = True
except ImportError:
    HAS_MSS = False

if _missing:
    import tkinter.messagebox as _mb
    _r = tk.Tk(); _r.withdraw()
    _mb.showerror("Eksik Kutuphane",
        "Eksikler: " + ", ".join(_missing) + "\n\n"
        "CMD'de su komutu calistir:\n"
        "pip install opencv-python pyautogui pygetwindow Pillow mss pystray psutil keyboard")
    sys.exit(1)

import detector    as det
import clicker     as clk
import overlay     as ovl
import config      as cfg
import session_log as slog
import profiler    as prf
import region_selector as rsel

pyautogui.FAILSAFE = True
pyautogui.PAUSE    = 0.0

# ── Palet (Catppuccin Mocha) ─────────────────────────────────────────────────
BG      = "#1e1e2e"
BG2     = "#313244"
BG3     = "#45475a"
BG4     = "#585b70"
FG      = "#cdd6f4"
SUB     = "#a6adc8"
ACCENT  = "#89b4fa"
GREEN   = "#a6e3a1"
RED     = "#f38ba8"
YELLOW  = "#f9e2af"
PURPLE  = "#cba6f7"
TEAL    = "#94e2d5"
PINK    = "#f5c2e7"
FONT    = ("Segoe UI", 10)
FONTB   = ("Segoe UI", 10, "bold")
FONTS   = ("Segoe UI", 9)
FONTM   = ("Consolas",  9)
FONTG   = ("Segoe UI", 9)


# ── Ses ──────────────────────────────────────────────────────────────────────
def _beep(freq=880, dur=120):
    try:
        import winsound
        winsound.Beep(freq, dur)
        time.sleep(0.04)
        winsound.Beep(int(freq * 1.25), 80)
    except Exception:
        pass


# ── Pencere listesi ───────────────────────────────────────────────────────────
def get_windows() -> list[tuple[str, str]]:
    pid_map: dict[int, str] = {}
    if HAS_PSUTIL:
        for p in psutil.process_iter(["pid", "name"]):
            try: pid_map[p.info["pid"]] = p.info["name"] or ""
            except Exception: pass

    seen, out = set(), []
    for win in gw.getAllWindows():
        t = (win.title or "").strip()
        if not t or t in seen:
            continue
        seen.add(t)
        label = t
        if HAS_PSUTIL:
            try:
                import ctypes
                pid = ctypes.c_ulong()
                ctypes.windll.user32.GetWindowThreadProcessId(
                    win._hWnd, ctypes.byref(pid))
                pname = pid_map.get(pid.value, "")
                if pname:
                    label = f"{pname}  —  {t}"
            except Exception:
                pass
        out.append((label, t))
    out.sort(key=lambda x: x[0].lower())
    return out


# ── Zaten tiklandi kontrolu ───────────────────────────────────────────────────
def _already_clicked(x, y, history: list, radius: int) -> bool:
    for cx, cy in history:
        if math.hypot(x - cx, y - cy) <= radius:
            return True
    return False


# ── Hedef siralama ────────────────────────────────────────────────────────────
def _sort_results(results, priority: str, ref_x=0, ref_y=0):
    if priority == "score":
        return sorted(results, key=lambda r: r.score, reverse=True)
    if priority == "nearest":
        return sorted(results,
                      key=lambda r: math.hypot(r.cx - ref_x, r.cy - ref_y))
    if priority == "left_right":
        return sorted(results, key=lambda r: (r.cy // 20, r.cx))
    # random
    r2 = list(results)
    random.shuffle(r2)
    return r2


# ── Preview numpy → PhotoImage ────────────────────────────────────────────────
def _make_preview(screen_bgr, results, offset, max_w=224, max_h=144):
    if screen_bgr is None:
        blank = Image.new("RGB", (max_w, max_h), "#313244")
        return ImageTk.PhotoImage(blank)
    img = screen_bgr.copy()
    ox, oy = offset
    for r in results:
        cv2.rectangle(img, (r.x, r.y), (r.x+r.w, r.y+r.h), (0, 255, 128), 2)
        cv2.circle(img, (r.cx, r.cy), 5, (64, 64, 255), -1)
    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    pil.thumbnail((max_w, max_h), Image.LANCZOS)
    return ImageTk.PhotoImage(pil)


# ════════════════════════════════════════════════════════════════════════════
# BOT WORKER
# ════════════════════════════════════════════════════════════════════════════
def run_bot(params: dict, log_q: Queue, preview_q: Queue,
            stop_event: threading.Event, slog_inst, session_stats: dict):

    def log(msg, tag=""):
        log_q.put(("msg", msg, tag))
        slog_inst.log(msg)

    # ── Pencere bölgesi ───────────────────────────────────────────────────────
    region  = params.get("capture_region")  # None veya [x1,y1,x2,y2]
    offset  = (0, 0)
    win_title = params.get("window_title", "")

    if win_title:
        wins = gw.getWindowsWithTitle(win_title)
        if not wins:
            log(f"[HATA] '{win_title}' penceresi bulunamadi.", "red"); return
        w = wins[0]
        try:
            if w.isMinimized: w.restore(); time.sleep(0.4)
            w.activate(); time.sleep(0.3)
        except Exception: pass
        rx, ry = max(0, w.left), max(0, w.top)
        rw, rh = max(1, w.width), max(1, w.height)
        if region is None:
            region = (rx, ry, rx + rw, ry + rh)
            offset = (rx, ry)
        # Kullanici bolge secmisse, offset 0,0 (mutlak koordinatlar)

    if region and not isinstance(region, tuple):
        region = tuple(region)

    # ── Template yükleme ──────────────────────────────────────────────────────
    templates = []
    for p in params.get("image_paths", []):
        try:
            tpl = det.load_template(p)
            templates.append((os.path.basename(p), tpl))
            log(f"  + Template: {os.path.basename(p)}  [{tpl.shape[1]}x{tpl.shape[0]}px]", "teal")
        except Exception as e:
            log(f"  x Template acilamadi: {os.path.basename(p)} - {e}", "yellow")

    if not templates:
        log("[HATA] Hic gecerli template yok.", "red"); return

    # ── Parametreler ──────────────────────────────────────────────────────────
    confidence    = params["confidence"]
    conf          = confidence
    multiscale    = params["multiscale"]
    scales        = cfg.build_scales(params)
    nms_iou       = params["nms_iou"] / 100.0
    use_clahe     = params.get("use_clahe", True)
    blur          = params.get("blur_kernel", 0)
    method_str    = params.get("match_method", "CCOEFF")
    method        = cv2.TM_CCOEFF_NORMED if method_str == "CCOEFF" else cv2.TM_SQDIFF_NORMED

    click_mode    = params["click_mode"]
    rand_offset   = params["rand_offset"]
    pre_move_ms   = params.get("pre_move_ms", 20)
    hold_ms       = params.get("hold_ms", 35)
    post_click_ms = params.get("post_click_ms", 60)
    human_move    = params.get("human_move", False)
    human_speed   = params.get("human_speed", 1.0)
    human_jitter  = params.get("human_jitter", 2)

    repeat        = params["repeat"]
    interval      = params["interval"]
    skip_radius   = params["skip_radius"]
    adaptive_conf = params.get("adaptive_conf", True)
    adaptive_min  = params.get("adaptive_min", 0.50)
    priority_mode = params.get("priority_mode", "score")
    sound_alert   = params["sound_alert"]
    overlay_dur   = params["overlay_duration"]
    pause_unfocus = params.get("pause_on_unfocus", False)
    ss_on_detect  = params.get("screenshot_on_detect", False)

    max_clicks    = int(params.get("max_clicks", 0))
    max_dur_min   = float(params.get("max_duration_min", 0))
    break_every   = float(params.get("break_every_min", 0))
    break_for     = float(params.get("break_for_sec", 30))

    clicked: list = []
    session_stats.update({
        "start_time": time.time(),
        "total_scans": 0, "total_found": 0, "total_clicks": 0,
        "rate": 0.0, "last_found": 0,
    })
    click_history: list[float] = []  # timestamps for rate calculation
    break_timer = time.time()

    log(f"[OK] Bot baslatildi | Mod: {clk.MODE_LABELS.get(click_mode,'?')} | "
        f"Tekrar: {repeat} | Aralik: {interval}s")
    if HAS_MSS:
        log("[OK] Ekran yakalama: mss (ultra hizli)", "teal")
    else:
        log("[UYARI] mss bulunamadi, PIL kullaniliyor (daha yavas)", "yellow")

    for i in range(repeat):
        if stop_event.is_set():
            log("Durduruldu.", "yellow"); break

        # Max sure kontrolü
        elapsed_total = time.time() - session_stats["start_time"]
        if max_dur_min > 0 and elapsed_total >= max_dur_min * 60:
            log(f"[ZAMANLAYICI] Max sure doldu ({max_dur_min} dk).", "yellow"); break

        # Max tiklama kontrolü
        if max_clicks > 0 and session_stats["total_clicks"] >= max_clicks:
            log(f"[ZAMANLAYICI] Max tiklama doldu ({max_clicks}).", "yellow"); break

        # Ara verme
        if break_every > 0:
            if time.time() - break_timer >= break_every * 60:
                log(f"[ARA] {break_for:.0f} saniye ara veriliyor...", "yellow")
                t0 = time.time()
                while time.time() - t0 < break_for:
                    if stop_event.is_set(): break
                    time.sleep(0.5)
                break_timer = time.time()
                log("[ARA] Devam ediliyor.", "green")

        # Bekleme (ilk turda yok)
        if i > 0:
            t0 = time.time()
            while time.time() - t0 < interval:
                if stop_event.is_set():
                    log("Durduruldu.", "yellow"); return
                time.sleep(0.05)

        # Pause on unfocus
        if pause_unfocus and win_title:
            try:
                active = gw.getActiveWindow()
                if active and win_title not in (active.title or ""):
                    log(f"[{i+1}] Pencere odaklanmadi, bekleniyor...", "yellow")
                    while True:
                        if stop_event.is_set(): return
                        active = gw.getActiveWindow()
                        if active and win_title in (active.title or ""): break
                        time.sleep(0.5)
            except Exception:
                pass

        # Ekran yakala
        try:
            screen = det.grab_screen(region)
        except Exception as e:
            log(f"[{i+1}/{repeat}] Ekran yakalanamadi: {e}", "red")
            continue

        session_stats["total_scans"] += 1

        # Tespit
        results = det.detect_all(
            templates, screen, conf, multiscale,
            nms_iou, scales, use_clahe, blur, method
        )

        # Preview gönder
        preview_q.put((screen.copy(), results, offset))

        # Adaptive confidence
        if adaptive_conf and not results and conf > adaptive_min:
            conf = max(adaptive_min, conf - 0.03)
            log(f"[{i+1}/{repeat}] Bulunamadi, güven dusuruldu: {conf:.2f}", "yellow")
            continue
        elif results:
            conf = max(conf, confidence - 0.05)  # Bulununca hafif geri yuksel

        if not results:
            log(f"[{i+1}/{repeat}] Esleme yok (güven={conf:.2f})", "yellow")
            continue

        # Overlay tetikle
        log_q.put(("overlay", results, offset, overlay_dur))

        # Ekran görüntüsü (istenmisse)
        if ss_on_detect:
            try:
                ss_dir = os.path.join(_DIR, "screenshots")
                os.makedirs(ss_dir, exist_ok=True)
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                ss_path = os.path.join(ss_dir, f"detect_{ts}.png")
                from PIL import Image as _PILImg
                _PILImg.fromarray(
                    cv2.cvtColor(screen, cv2.COLOR_BGR2RGB)
                ).save(ss_path)
            except Exception:
                pass

        session_stats["total_found"] += len(results)
        session_stats["last_found"]   = len(results)
        clicked_round = 0

        # Siralama
        try:
            import ctypes as _ct
            pt = _ct.wintypes.POINT()
            _ct.windll.user32.GetCursorPos(_ct.byref(pt))
            ref_x, ref_y = pt.x, pt.y
        except Exception:
            ref_x = ref_y = 0
        sorted_results = _sort_results(results, priority_mode, ref_x, ref_y)

        for r in sorted_results:
            if stop_event.is_set():
                log("Durduruldu.", "yellow"); return
            if max_clicks > 0 and session_stats["total_clicks"] >= max_clicks:
                break

            sx, sy = r.screen_coords(offset if region is None else (0, 0))
            if region:
                sx, sy = r.cx + region[0], r.cy + region[1]

            if skip_radius > 0 and _already_clicked(sx, sy, clicked, skip_radius):
                log(f"[{i+1}/{repeat}] Atlandi ({sx},{sy})  [{r.template_name} {r.score:.2f}]", "yellow")
                continue

            ok = clk.do_click(
                click_mode, sx, sy,
                rand_offset=rand_offset,
                pre_move_ms=pre_move_ms,
                hold_ms=hold_ms,
                human=human_move,
                human_speed=human_speed,
                jitter=human_jitter,
            )
            clicked.append((sx, sy))
            session_stats["total_clicks"] += 1
            clicked_round += 1
            click_history.append(time.time())
            # Son 60 saniyedeki tiklamalari say
            now = time.time()
            click_history = [t for t in click_history if now - t <= 60]
            session_stats["rate"] = len(click_history)

            engine = "SendInput" if ok else "pyautogui"
            log(f"[{i+1}/{repeat}] OK ({sx},{sy}) skor={r.score:.2f} "
                f"[{r.template_name}] [{engine}]", "green")

            slog_inst.record_click(sx, sy, r.score, r.template_name, engine, i+1)

            if sound_alert:
                threading.Thread(target=_beep, daemon=True).start()

            time.sleep(post_click_ms / 1000.0)

        if clicked_round == 0:
            log(f"[{i+1}/{repeat}] Hepsi zaten tiklandi.", "yellow")

        log_q.put(("stats", dict(session_stats)))

    log(f"--- Tamamlandi --- ({session_stats['total_clicks']} tiklama, "
        f"{session_stats['total_scans']} tarama)", "accent")


# ════════════════════════════════════════════════════════════════════════════
# GUI
# ════════════════════════════════════════════════════════════════════════════
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Shift + Sag Click Bot  v9.0")
        self.configure(bg=BG)
        self.resizable(True, False)
        self.minsize(720, 0)

        # DPI
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                import ctypes
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

        self._cfg     = cfg.load(_DIR)
        self._wins:   list[tuple[str, str]] = []
        self._clkd:   list[tuple[int, int]] = []
        self._stop    = threading.Event()
        self._alive   = False
        self._log_q:     Queue = Queue()
        self._preview_q: Queue = Queue()
        self._stats:  dict = {}
        self._preview_img = None
        self._overlay: "ovl.Overlay | None" = None
        self._slog:   "slog.SessionLog | None" = None
        self._capture_region = (
            tuple(self._cfg["capture_region"])
            if self._cfg.get("capture_region") else None
        )
        self._click_times: list[float] = []  # grafik icin
        self._scan_times:  list[float] = []

        self._build_styles()
        self._build_ui()

        if self._cfg.get("overlay_enabled", True):
            try: self._overlay = ovl.Overlay(self)
            except Exception: self._overlay = None

        self._refresh_windows()
        self._load_cfg_to_ui()
        self._poll_log()
        self._poll_preview()
        self._poll_stats_graph()

        if HAS_KEYBOARD:
            try:
                keyboard.add_hotkey("f9",  self._start)
                keyboard.add_hotkey("f10", self._stop_bot)
                keyboard.add_hotkey("f8",  self._toggle_overlay)
            except Exception:
                pass

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Stiller ──────────────────────────────────────────────────────────────
    def _build_styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        base = dict(background=BG, foreground=FG, font=FONT)
        s.configure(".", **base)
        s.configure("TFrame",       background=BG)
        s.configure("TLabel",       **base)
        s.configure("TEntry",       fieldbackground=BG2, foreground=FG, insertcolor=FG)
        s.configure("TCombobox",    fieldbackground=BG2, foreground=FG,
                    selectbackground=BG3, selectforeground=FG)
        s.map("TCombobox",          fieldbackground=[("readonly", BG2)],
                                    foreground=[("readonly", FG)])
        s.configure("TSpinbox",     fieldbackground=BG2, foreground=FG,
                    insertcolor=FG, arrowcolor=FG)
        s.configure("TButton",      background=ACCENT, foreground=BG,
                    font=FONTB, relief="flat", padding=(8, 4))
        s.map("TButton",            background=[("active", "#74c7ec"), ("disabled", BG3)],
                                    foreground=[("disabled", BG4)])
        s.configure("Red.TButton",  background=RED, foreground=BG,
                    font=FONTB, relief="flat", padding=(8, 4))
        s.map("Red.TButton",        background=[("active", "#eba0ac")])
        s.configure("Green.TButton",background=GREEN, foreground=BG,
                    font=FONTB, relief="flat", padding=(8, 4))
        s.map("Green.TButton",      background=[("active", "#89dcab")])
        s.configure("Sm.TButton",   background=BG3, foreground=FG,
                    font=FONTS, padding=(4, 2), relief="flat")
        s.map("Sm.TButton",         background=[("active", BG2)])
        s.configure("Del.TButton",  background=BG4, foreground=RED,
                    font=FONTS, padding=(4, 2), relief="flat")
        s.map("Del.TButton",        background=[("active", BG3)])
        s.configure("Teal.TButton", background=TEAL, foreground=BG,
                    font=FONTS, padding=(4, 2), relief="flat")
        s.map("Teal.TButton",       background=[("active", "#7dd6c5")])
        s.configure("TScale",       background=BG, troughcolor=BG2, sliderlength=14)
        s.configure("TCheckbutton", background=BG, foreground=FG, font=FONT)
        s.map("TCheckbutton",       background=[("active", BG)])
        s.configure("TSeparator",   background=BG3)
        s.configure("TNotebook",    background=BG, tabmargins=0)
        s.configure("TNotebook.Tab",background=BG2, foreground=SUB,
                    padding=(12, 5), font=FONTS)
        s.map("TNotebook.Tab",      background=[("selected", BG3)],
                                    foreground=[("selected", FG)])

    # ── Ana UI ───────────────────────────────────────────────────────────────
    def _build_ui(self):
        band = tk.Frame(self, bg=BG2)
        band.pack(fill="x")
        tk.Label(band, text="  Shift + Sag Click Bot  v9.0",
                 bg=BG2, fg=ACCENT, font=("Segoe UI", 11, "bold")).pack(side="left", pady=8)
        hk = "F9=Baslat  F10=Durdur  F8=Overlay" if HAS_KEYBOARD else "Hotkey: Yonetici gerekli"
        tk.Label(band, text=hk + "  ", bg=BG2, fg=BG4, font=FONTS).pack(side="right")
        mss_lbl = "mss OK" if HAS_MSS else "mss YOK"
        mss_col  = TEAL if HAS_MSS else YELLOW
        tk.Label(band, text=f"[{mss_lbl}]  ", bg=BG2, fg=mss_col, font=FONTS).pack(side="right")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=12, pady=(8, 0))

        t1 = ttk.Frame(nb); nb.add(t1, text="  Temel  ")
        t2 = ttk.Frame(nb); nb.add(t2, text="  Tiklama  ")
        t3 = ttk.Frame(nb); nb.add(t3, text="  Tarama  ")
        t4 = ttk.Frame(nb); nb.add(t4, text="  Zamanlayici  ")
        t5 = ttk.Frame(nb); nb.add(t5, text="  Profiller  ")
        t6 = ttk.Frame(nb); nb.add(t6, text="  Istatistik  ")

        self._build_tab_temel(t1)
        self._build_tab_tiklama(t2)
        self._build_tab_tarama(t3)
        self._build_tab_zamanlayici(t4)
        self._build_tab_profiller(t5)
        self._build_tab_istatistik(t6)

        # Start / Stop
        fb = tk.Frame(self, bg=BG)
        fb.pack(fill="x", padx=12, pady=6)
        self._bgo  = ttk.Button(fb, text="▶  Baslat (F9)", command=self._start)
        self._bgo.pack(side="left", padx=(0, 8))
        self._bstp = ttk.Button(fb, text="■  Durdur (F10)", style="Red.TButton",
                                command=self._stop_bot, state="disabled")
        self._bstp.pack(side="left")
        self._status_lbl = tk.Label(fb, text="Hazir", bg=BG, fg=SUB, font=FONTS)
        self._status_lbl.pack(side="right")

        ttk.Separator(self).pack(fill="x", padx=12, pady=(4, 0))

        # Log + Preview
        bot = tk.Frame(self, bg=BG)
        bot.pack(fill="both", expand=True, padx=12, pady=(4, 12))

        lf = tk.Frame(bot, bg=BG)
        lf.pack(side="left", fill="both", expand=True)
        hdr = tk.Frame(lf, bg=BG)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Cikti:", bg=BG, fg=SUB, font=FONTS).pack(side="left")
        ttk.Button(hdr, text="Temizle", style="Sm.TButton",
                   command=self._clear_log).pack(side="right")
        self._log = tk.Text(lf, height=10, bg=BG2, fg=FG, font=FONTM,
                            relief="flat", state="disabled", wrap="word",
                            selectbackground=BG3, insertbackground=FG)
        self._log.pack(fill="both", expand=True, pady=(3, 0))
        for tag, col in [("green", GREEN), ("red", RED), ("yellow", YELLOW),
                          ("accent", ACCENT), ("teal", TEAL), ("purple", PURPLE)]:
            self._log.tag_configure(tag, foreground=col)

        pf = tk.Frame(bot, bg=BG2, width=232, highlightthickness=1,
                      highlightbackground=BG3)
        pf.pack(side="right", fill="y", padx=(10, 0))
        pf.pack_propagate(False)
        tk.Label(pf, text="Son Tarama", bg=BG2, fg=SUB, font=FONTS).pack(pady=(6, 2))
        self._preview_lbl = tk.Label(pf, bg=BG2, cursor="crosshair")
        self._preview_lbl.pack(fill="both", expand=True, padx=4, pady=(0, 4))

    # ── Tab 1: Temel ─────────────────────────────────────────────────────────
    def _build_tab_temel(self, parent):
        P = dict(padx=12, pady=5)

        # Görseller
        f1 = ttk.Frame(parent); f1.pack(fill="x", **P)
        hr = ttk.Frame(f1); hr.pack(fill="x")
        ttk.Label(hr, text="Referans Görseller:", font=FONTB).pack(side="left")
        ttk.Button(hr, text="+ Ekle", style="Sm.TButton",
                   command=self._add_imgs).pack(side="right")
        lf = tk.Frame(f1, bg=BG2, highlightthickness=1, highlightbackground=BG3)
        lf.pack(fill="x", pady=(4, 0))
        self._lb = tk.Listbox(lf, bg=BG2, fg=FG, font=FONTM,
                              selectbackground=BG3, activestyle="none",
                              relief="flat", bd=0, height=4, highlightthickness=0)
        self._lb.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(lf, orient="vertical", command=self._lb.yview)
        sb.pack(side="right", fill="y")
        self._lb.configure(yscrollcommand=sb.set)
        br = ttk.Frame(f1); br.pack(fill="x", pady=(4, 0))
        ttk.Button(br, text="x Secili Sil", style="Del.TButton",
                   command=self._rm_img).pack(side="left", padx=(0, 6))
        ttk.Button(br, text="Tumünü Temizle", style="Del.TButton",
                   command=self._clr_imgs).pack(side="left")
        ttk.Label(br, text="2-5 gorsel onerilir (farkli aci/isik)",
                  foreground=SUB, font=FONTS).pack(side="right")

        ttk.Separator(parent).pack(fill="x", padx=12, pady=3)

        # Pencere
        f2 = ttk.Frame(parent); f2.pack(fill="x", **P)
        ttk.Label(f2, text="Hedef Pencere:", font=FONTB).pack(anchor="w")
        wr = ttk.Frame(f2); wr.pack(fill="x", pady=(3, 0))
        self._wvar  = tk.StringVar()
        self._combo = ttk.Combobox(wr, textvariable=self._wvar,
                                   state="readonly", font=FONT)
        self._combo.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ttk.Button(wr, text="Yenile", style="Sm.TButton",
                   command=self._refresh_windows).pack(side="left")
        ttk.Label(f2, text="Bos = tum ekran",
                  foreground=SUB, font=FONTS).pack(anchor="w", pady=(2, 0))

        ttk.Separator(parent).pack(fill="x", padx=12, pady=3)

        # Güven + Tekrar + Aralik
        f3 = ttk.Frame(parent); f3.pack(fill="x", **P)
        r1 = ttk.Frame(f3); r1.pack(fill="x")
        ttk.Label(r1, text="Güven esigi:", width=16).pack(side="left")
        self._conf = tk.DoubleVar(value=0.80)
        ttk.Scale(r1, from_=0.30, to=1.0, variable=self._conf,
                  orient="horizontal", length=180).pack(side="left", padx=(0, 6))
        self._clbl = ttk.Label(r1, text="0.80", width=5); self._clbl.pack(side="left")
        self._conf.trace_add("write",
            lambda *_: self._clbl.config(text=f"{self._conf.get():.2f}"))
        ttk.Label(r1, text="0.60-0.70 dene bulamazsan",
                  foreground=SUB, font=FONTS).pack(side="left", padx=6)

        r2 = ttk.Frame(f3); r2.pack(fill="x", pady=(5, 0))
        ttk.Label(r2, text="Tekrar:", width=16).pack(side="left")
        self._rep = tk.IntVar(value=9999)
        ttk.Spinbox(r2, from_=1, to=9999999, textvariable=self._rep,
                    width=8, font=FONT).pack(side="left", padx=(0, 20))
        ttk.Label(r2, text="Aralik (sn):").pack(side="left")
        self._ivl = tk.DoubleVar(value=1.0)
        ttk.Spinbox(r2, from_=0.05, to=600, increment=0.1,
                    textvariable=self._ivl, width=6, font=FONT,
                    format="%.2f").pack(side="left", padx=(4, 20))
        ttk.Label(r2, text="Atla yarıcapi:").pack(side="left")
        self._skip = tk.IntVar(value=40)
        ttk.Spinbox(r2, from_=0, to=500, textvariable=self._skip,
                    width=5, font=FONT).pack(side="left", padx=(4, 0))

        r3 = ttk.Frame(f3); r3.pack(fill="x", pady=(5, 0))
        self._adaptive_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(r3, text="Adaptive güven (bulamazsa otomatik düsür)",
                        variable=self._adaptive_var).pack(side="left")

    # ── Tab 2: Tiklama ────────────────────────────────────────────────────────
    def _build_tab_tiklama(self, parent):
        P = dict(padx=12, pady=6)
        modes = list(clk.MODE_LABELS.values())
        mode_keys = list(clk.MODE_LABELS.keys())

        f1 = ttk.Frame(parent); f1.pack(fill="x", **P)
        ttk.Label(f1, text="Tiklama Modu:", font=FONTB).pack(anchor="w")
        self._mode_var = tk.StringVar()
        self._mode_cb  = ttk.Combobox(f1, textvariable=self._mode_var,
                                       values=modes, state="readonly", width=30)
        self._mode_cb.pack(anchor="w", pady=(4, 0))
        self._mode_cb.bind("<<ComboboxSelected>>", lambda e: None)

        ttk.Separator(parent).pack(fill="x", padx=12, pady=4)

        f2 = ttk.Frame(parent); f2.pack(fill="x", **P)
        ttk.Label(f2, text="Insan Hareketi (Anti-Detection):", font=FONTB).pack(anchor="w")
        self._human_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(f2, text="Bezier egri + overshoot hareketi",
                        variable=self._human_var).pack(anchor="w", pady=(3, 0))
        hr = ttk.Frame(f2); hr.pack(fill="x", pady=(4, 0))
        ttk.Label(hr, text="Hiz:", width=10).pack(side="left")
        self._hspeed = tk.DoubleVar(value=1.0)
        ttk.Scale(hr, from_=0.3, to=4.0, variable=self._hspeed,
                  orient="horizontal", length=150).pack(side="left", padx=(0, 6))
        self._hslbl = ttk.Label(hr, text="1.0", width=4); self._hslbl.pack(side="left")
        self._hspeed.trace_add("write",
            lambda *_: self._hslbl.config(text=f"{self._hspeed.get():.1f}"))
        ttk.Label(hr, text="(0.3=cok yavas, 4.0=cok hizli)",
                  foreground=SUB, font=FONTS).pack(side="left", padx=4)

        jr = ttk.Frame(f2); jr.pack(fill="x", pady=(3, 0))
        ttk.Label(jr, text="Jitter (px):", width=10).pack(side="left")
        self._hjitter = tk.IntVar(value=2)
        ttk.Spinbox(jr, from_=0, to=20, textvariable=self._hjitter, width=4).pack(side="left")

        ttk.Separator(parent).pack(fill="x", padx=12, pady=4)

        f3 = ttk.Frame(parent); f3.pack(fill="x", **P)
        ttk.Label(f3, text="Tiklama Zamalamalari (ms):", font=FONTB).pack(anchor="w")
        rows = [
            ("Rastgele sapma (px):", "rand_offset", tk.IntVar, 3, 0, 50),
            ("Hareket oncesi bekleme:", "pre_move", tk.IntVar, 20, 5, 200),
            ("Tus basili tutma:", "hold_ms", tk.IntVar, 35, 10, 300),
            ("Tiklama sonrasi bekleme:", "post_click", tk.IntVar, 60, 10, 1000),
        ]
        for lbl, attr, vtype, default, lo, hi in rows:
            r = ttk.Frame(f3); r.pack(fill="x", pady=2)
            ttk.Label(r, text=lbl, width=26).pack(side="left")
            v = vtype(value=default)
            setattr(self, f"_{attr}_var", v)
            ttk.Spinbox(r, from_=lo, to=hi, textvariable=v,
                        width=6, font=FONT).pack(side="left")

        ttk.Separator(parent).pack(fill="x", padx=12, pady=4)

        f4 = ttk.Frame(parent); f4.pack(fill="x", **P)
        self._sound_var   = tk.BooleanVar(value=True)
        self._overlay_var = tk.BooleanVar(value=True)
        self._ss_detect_var = tk.BooleanVar(value=False)
        self._pause_uf_var  = tk.BooleanVar(value=False)
        ttk.Checkbutton(f4, text="Ses alarmı (Beep)",
                        variable=self._sound_var).pack(anchor="w")
        ttk.Checkbutton(f4, text="Ekran overlay (tiklanan yerleri goster)",
                        variable=self._overlay_var).pack(anchor="w")
        ttk.Checkbutton(f4, text="Eslesme bulunca ekran goruntusu kaydet",
                        variable=self._ss_detect_var).pack(anchor="w")
        ttk.Checkbutton(f4, text="Pencere odak kaybedince bekle (Pause on unfocus)",
                        variable=self._pause_uf_var).pack(anchor="w")

    # ── Tab 3: Tarama ─────────────────────────────────────────────────────────
    def _build_tab_tarama(self, parent):
        P = dict(padx=12, pady=6)

        f1 = ttk.Frame(parent); f1.pack(fill="x", **P)
        ttk.Label(f1, text="Olcek (Multi-Scale):", font=FONTB).pack(anchor="w")
        self._ms_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(f1, text="Multi-scale etkin",
                        variable=self._ms_var).pack(anchor="w", pady=(3, 0))
        sr = ttk.Frame(f1); sr.pack(fill="x", pady=(4, 0))
        ttk.Label(sr, text="Min:", width=6).pack(side="left")
        self._sc_min = tk.DoubleVar(value=0.50)
        ttk.Spinbox(sr, from_=0.1, to=1.0, increment=0.05,
                    textvariable=self._sc_min, width=5,
                    format="%.2f", font=FONT).pack(side="left", padx=(0, 12))
        ttk.Label(sr, text="Max:").pack(side="left")
        self._sc_max = tk.DoubleVar(value=2.00)
        ttk.Spinbox(sr, from_=0.5, to=5.0, increment=0.1,
                    textvariable=self._sc_max, width=5,
                    format="%.2f", font=FONT).pack(side="left", padx=(0, 12))
        ttk.Label(sr, text="Adim:").pack(side="left")
        self._sc_steps = tk.IntVar(value=12)
        ttk.Spinbox(sr, from_=2, to=30, textvariable=self._sc_steps,
                    width=4, font=FONT).pack(side="left")

        ttk.Separator(parent).pack(fill="x", padx=12, pady=4)

        f2 = ttk.Frame(parent); f2.pack(fill="x", **P)
        ttk.Label(f2, text="Eslesme Yontemi:", font=FONTB).pack(anchor="w")
        self._method_var = tk.StringVar(value="CCOEFF")
        fr = ttk.Frame(f2); fr.pack(anchor="w", pady=(3, 0))
        ttk.Radiobutton(fr, text="TM_CCOEFF_NORMED  (onerilen)",
                        variable=self._method_var, value="CCOEFF").pack(side="left", padx=(0, 20))
        ttk.Radiobutton(fr, text="TM_SQDIFF_NORMED  (aydinlatmadan bagimsiz)",
                        variable=self._method_var, value="SQDIFF").pack(side="left")

        nr = ttk.Frame(f2); nr.pack(fill="x", pady=(4, 0))
        ttk.Label(nr, text="NMS IoU esigi (%):", width=20).pack(side="left")
        self._nms_var = tk.IntVar(value=30)
        ttk.Spinbox(nr, from_=5, to=95, textvariable=self._nms_var, width=4).pack(side="left")
        ttk.Label(nr, text="  Hedef siralama:", foreground=SUB).pack(side="left")
        self._priority_var = tk.StringVar(value="score")
        ttk.Combobox(nr, textvariable=self._priority_var,
                     values=["score","nearest","left_right","random"],
                     state="readonly", width=12).pack(side="left", padx=(4, 0))

        ttk.Separator(parent).pack(fill="x", padx=12, pady=4)

        f3 = ttk.Frame(parent); f3.pack(fill="x", **P)
        ttk.Label(f3, text="On-isleme:", font=FONTB).pack(anchor="w")
        self._clahe_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(f3, text="CLAHE normalizasyon (isiga karsi dayanikli)",
                        variable=self._clahe_var).pack(anchor="w", pady=(3, 0))
        br2 = ttk.Frame(f3); br2.pack(fill="x", pady=(3, 0))
        ttk.Label(br2, text="Gaussian blur (0=kapali, tek sayi):").pack(side="left")
        self._blur_var = tk.IntVar(value=0)
        ttk.Spinbox(br2, from_=0, to=11, increment=2,
                    textvariable=self._blur_var, width=3).pack(side="left", padx=4)

        ttk.Separator(parent).pack(fill="x", padx=12, pady=4)

        f4 = ttk.Frame(parent); f4.pack(fill="x", **P)
        ttk.Label(f4, text="Yakalama Bolgesi:", font=FONTB).pack(anchor="w")
        rr = ttk.Frame(f4); rr.pack(fill="x", pady=(4, 0))
        self._region_lbl = tk.Label(rr, text="Tum ekran", bg=BG, fg=SUB, font=FONTM)
        self._region_lbl.pack(side="left", expand=True, anchor="w")
        ttk.Button(rr, text="Bolge Sec", style="Teal.TButton",
                   command=self._select_region).pack(side="right", padx=(6, 0))
        ttk.Button(rr, text="Temizle", style="Del.TButton",
                   command=self._clear_region).pack(side="right")
        ttk.Label(f4, text="Pencere secilmisse bolge pencere icerisinde alinir",
                  foreground=SUB, font=FONTS).pack(anchor="w", pady=(2, 0))

        # Log
        f5 = ttk.Frame(parent); f5.pack(fill="x", **P)
        self._log_file_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(f5, text="Log dosyasina yaz (logs/ klasoru)",
                        variable=self._log_file_var).pack(side="left")

    # ── Tab 4: Zamanlayici ────────────────────────────────────────────────────
    def _build_tab_zamanlayici(self, parent):
        P = dict(padx=12, pady=6)

        f1 = ttk.Frame(parent); f1.pack(fill="x", **P)
        ttk.Label(f1, text="Otomatik Baslat/Durdur:", font=FONTB).pack(anchor="w")
        self._sched_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(f1, text="Zamanlayici etkin",
                        variable=self._sched_var).pack(anchor="w", pady=(3, 0))
        gr = ttk.Frame(f1); gr.pack(fill="x", pady=(4, 0))
        ttk.Label(gr, text="Baslat saati (SS:DD):", width=22).pack(side="left")
        self._sched_start = tk.StringVar(value="")
        ttk.Entry(gr, textvariable=self._sched_start, width=8).pack(side="left")
        ttk.Label(gr, text="  Durdur saati:", foreground=SUB).pack(side="left")
        self._sched_stop = tk.StringVar(value="")
        ttk.Entry(gr, textvariable=self._sched_stop, width=8).pack(side="left")

        ttk.Separator(parent).pack(fill="x", padx=12, pady=4)

        f2 = ttk.Frame(parent); f2.pack(fill="x", **P)
        ttk.Label(f2, text="Otomatik Durdurma Koşulları:", font=FONTB).pack(anchor="w")
        rows2 = [
            ("Max tiklama (0=sinirsiz):", "_max_clicks_var", 0),
            ("Max sure (dk, 0=sinirsiz):", "_max_dur_var", 0),
        ]
        for lbl, attr, default in rows2:
            r = ttk.Frame(f2); r.pack(fill="x", pady=3)
            ttk.Label(r, text=lbl, width=28).pack(side="left")
            v = tk.IntVar(value=default)
            setattr(self, attr, v)
            ttk.Spinbox(r, from_=0, to=9999999, textvariable=v, width=8).pack(side="left")

        ttk.Separator(parent).pack(fill="x", padx=12, pady=4)

        f3 = ttk.Frame(parent); f3.pack(fill="x", **P)
        ttk.Label(f3, text="Molalar:", font=FONTB).pack(anchor="w")
        mr = ttk.Frame(f3); mr.pack(fill="x", pady=(4, 0))
        ttk.Label(mr, text="Her X dakikada bir:", width=20).pack(side="left")
        self._break_every_var = tk.IntVar(value=0)
        ttk.Spinbox(mr, from_=0, to=600, textvariable=self._break_every_var,
                    width=5).pack(side="left")
        ttk.Label(mr, text="  Y saniye mola ver:").pack(side="left")
        self._break_for_var = tk.IntVar(value=30)
        ttk.Spinbox(mr, from_=5, to=3600, textvariable=self._break_for_var,
                    width=5).pack(side="left")
        ttk.Label(f3, text="0 = mola yok",
                  foreground=SUB, font=FONTS).pack(anchor="w", pady=(2, 0))

    # ── Tab 5: Profiller ──────────────────────────────────────────────────────
    def _build_tab_profiller(self, parent):
        P = dict(padx=12, pady=8)

        f1 = ttk.Frame(parent); f1.pack(fill="both", expand=True, **P)
        ttk.Label(f1, text="Kayitli Profiller:", font=FONTB).pack(anchor="w")

        lf = tk.Frame(f1, bg=BG2, highlightthickness=1, highlightbackground=BG3)
        lf.pack(fill="both", expand=True, pady=(4, 0))
        self._prof_lb = tk.Listbox(lf, bg=BG2, fg=FG, font=FONTM,
                                    selectbackground=BG3, activestyle="none",
                                    relief="flat", bd=0, height=8, highlightthickness=0)
        self._prof_lb.pack(side="left", fill="both", expand=True)
        sb2 = ttk.Scrollbar(lf, orient="vertical", command=self._prof_lb.yview)
        sb2.pack(side="right", fill="y")
        self._prof_lb.configure(yscrollcommand=sb2.set)

        br = ttk.Frame(f1); br.pack(fill="x", pady=(8, 0))
        ttk.Button(br, text="Kaydet", style="Green.TButton",
                   command=self._save_profile).pack(side="left", padx=(0, 6))
        ttk.Button(br, text="Yukle", command=self._load_profile).pack(side="left", padx=(0, 6))
        ttk.Button(br, text="Sil", style="Del.TButton",
                   command=self._del_profile).pack(side="left", padx=(0, 20))
        ttk.Button(br, text="Disari Aktar", style="Sm.TButton",
                   command=self._export_profile).pack(side="left", padx=(0, 6))
        ttk.Button(br, text="Iceri Aktar", style="Sm.TButton",
                   command=self._import_profile).pack(side="left")

        self._refresh_profiles()

    # ── Tab 6: Istatistik ─────────────────────────────────────────────────────
    def _build_tab_istatistik(self, parent):
        P = dict(padx=12, pady=6)

        # Sayaçlar
        f1 = ttk.Frame(parent); f1.pack(fill="x", **P)
        self._stat_labels: dict[str, tk.Label] = {}
        stat_defs = [
            ("Tiklama/dk:", "rate"),
            ("Toplam tiklama:", "total_clicks"),
            ("Toplam tarama:", "total_scans"),
            ("Toplam eslesme:", "total_found"),
            ("Gecen sure:", "elapsed"),
        ]
        for i, (lbl, key) in enumerate(stat_defs):
            r = ttk.Frame(f1); r.pack(fill="x", pady=2)
            ttk.Label(r, text=lbl, width=20).pack(side="left")
            lw = tk.Label(r, text="0", bg=BG, fg=ACCENT, font=FONTB)
            lw.pack(side="left")
            self._stat_labels[key] = lw

        ttk.Separator(parent).pack(fill="x", padx=12, pady=4)

        # Mini grafik (canvas)
        f2 = ttk.Frame(parent); f2.pack(fill="x", **P)
        ttk.Label(f2, text="Tiklama Gecmisi (son 60 saniye):", font=FONTB).pack(anchor="w")
        self._graph = tk.Canvas(f2, bg=BG2, height=80, highlightthickness=0)
        self._graph.pack(fill="x", pady=(4, 0))

        ttk.Separator(parent).pack(fill="x", padx=12, pady=4)

        f3 = ttk.Frame(parent); f3.pack(fill="x", **P)
        ttk.Button(f3, text="CSV Export", style="Teal.TButton",
                   command=self._export_csv).pack(side="left", padx=(0, 8))
        ttk.Button(f3, text="Logs Klasorunu Ac", style="Sm.TButton",
                   command=self._open_logs).pack(side="left", padx=(0, 8))
        ttk.Button(f3, text="Istatistikleri Sifirla", style="Del.TButton",
                   command=self._reset_stats).pack(side="left")

    # ────────────────────────────────────────────────────────────────────────
    # Görsel yardımcıları
    # ────────────────────────────────────────────────────────────────────────
    def _set_status(self, text, color=None):
        self._status_lbl.config(text=text, fg=color or SUB)

    def _append_log(self, msg, tag=""):
        self._log.config(state="normal")
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._log.insert("end", f"[{ts}] {msg}\n", tag or "")
        self._log.see("end")
        self._log.config(state="disabled")

    def _clear_log(self):
        self._log.config(state="normal")
        self._log.delete("1.0", "end")
        self._log.config(state="disabled")

    def _draw_graph(self):
        g = self._graph
        g.delete("all")
        w = g.winfo_width() or 400
        h = 80
        now = time.time()
        # Son 60 saniye, 6 saniyesel dilim
        bins = [0] * 10
        for t in self._click_times:
            age = now - t
            if age <= 60:
                idx = min(9, int(age / 6))
                bins[9 - idx] += 1
        if not any(bins):
            g.create_text(w//2, h//2, text="Henuz veri yok",
                          fill=BG4, font=FONTS)
            return
        mx = max(bins) or 1
        bw = w / 10
        for i, val in enumerate(bins):
            bh = int((val / mx) * (h - 10))
            x0 = i * bw + 2
            x1 = (i + 1) * bw - 2
            y0 = h - bh - 2
            y1 = h - 2
            col = ACCENT if val == mx else BG3
            g.create_rectangle(x0, y0, x1, y1, fill=col, outline="")
            if val > 0:
                g.create_text((x0+x1)//2, y0-6, text=str(val),
                              fill=FG, font=("Consolas", 7))
        g.create_text(4, 4, text="←60sn önce", fill=BG4, font=("Consolas", 7), anchor="nw")
        g.create_text(w-4, 4, text="şimdi→", fill=BG4, font=("Consolas", 7), anchor="ne")

    # ────────────────────────────────────────────────────────────────────────
    # Pencere + bölge
    # ────────────────────────────────────────────────────────────────────────
    def _refresh_windows(self):
        self._wins = get_windows()
        labels = ["(Tum Ekran)"] + [l for l, _ in self._wins]
        self._combo["values"] = labels
        cur = self._wvar.get()
        if cur not in labels:
            self._combo.current(0)

    def _select_region(self):
        self.withdraw()
        time.sleep(0.15)
        r = rsel.select_region()
        self.deiconify()
        if r:
            self._capture_region = r
            self._region_lbl.config(text=rsel.region_to_str(r), fg=TEAL)
        else:
            self._region_lbl.config(text="Iptal edildi", fg=YELLOW)

    def _clear_region(self):
        self._capture_region = None
        self._region_lbl.config(text="Tum ekran", fg=SUB)

    # ────────────────────────────────────────────────────────────────────────
    # Template listesi
    # ────────────────────────────────────────────────────────────────────────
    def _add_imgs(self):
        paths = filedialog.askopenfilenames(
            title="Referans gorsel sec",
            filetypes=[("Gorsel", "*.png *.jpg *.jpeg *.bmp *.webp"),
                       ("Tumu", "*.*")])
        for p in paths:
            if p not in list(self._lb.get(0, "end")):
                self._lb.insert("end", p)

    def _rm_img(self):
        sel = list(self._lb.curselection())
        for i in reversed(sel):
            self._lb.delete(i)

    def _clr_imgs(self):
        self._lb.delete(0, "end")

    # ────────────────────────────────────────────────────────────────────────
    # Profil sistemi
    # ────────────────────────────────────────────────────────────────────────
    def _refresh_profiles(self):
        self._prof_lb.delete(0, "end")
        for name in prf.list_profiles(_DIR):
            self._prof_lb.insert("end", name)

    def _collect_cfg(self) -> dict:
        c = dict(self._cfg)
        c["image_paths"]     = list(self._lb.get(0, "end"))
        wsel = self._wvar.get()
        c["window_title"]    = "" if wsel == "(Tum Ekran)" else next(
            (t for l, t in self._wins if l == wsel), "")
        c["confidence"]      = round(self._conf.get(), 2)
        c["repeat"]          = self._rep.get()
        c["interval"]        = round(self._ivl.get(), 2)
        c["skip_radius"]     = self._skip.get()
        c["adaptive_conf"]   = self._adaptive_var.get()
        c["click_mode"]      = next(
            (k for k, v in clk.MODE_LABELS.items() if v == self._mode_var.get()),
            "shift_right")
        c["human_move"]      = self._human_var.get()
        c["human_speed"]     = round(self._hspeed.get(), 1)
        c["human_jitter"]    = self._hjitter.get()
        c["rand_offset"]     = self._rand_offset_var.get()
        c["pre_move_ms"]     = self._pre_move_var.get()
        c["hold_ms"]         = self._hold_ms_var.get()
        c["post_click_ms"]   = self._post_click_var.get()
        c["sound_alert"]     = self._sound_var.get()
        c["overlay_enabled"] = self._overlay_var.get()
        c["screenshot_on_detect"] = self._ss_detect_var.get()
        c["pause_on_unfocus"]= self._pause_uf_var.get()
        c["multiscale"]      = self._ms_var.get()
        c["scales_min"]      = round(self._sc_min.get(), 2)
        c["scales_max"]      = round(self._sc_max.get(), 2)
        c["scales_steps"]    = self._sc_steps.get()
        c["match_method"]    = self._method_var.get()
        c["nms_iou"]         = self._nms_var.get()
        c["priority_mode"]   = self._priority_var.get()
        c["use_clahe"]       = self._clahe_var.get()
        c["blur_kernel"]     = self._blur_var.get()
        c["log_to_file"]     = self._log_file_var.get()
        c["scheduler_enabled"] = self._sched_var.get()
        c["scheduler_start"] = self._sched_start.get()
        c["scheduler_stop"]  = self._sched_stop.get()
        c["max_clicks"]      = self._max_clicks_var.get()
        c["max_duration_min"]= self._max_dur_var.get()
        c["break_every_min"] = self._break_every_var.get()
        c["break_for_sec"]   = self._break_for_var.get()
        c["capture_region"]  = list(self._capture_region) if self._capture_region else None
        return c

    def _load_cfg_to_ui(self):
        c = self._cfg
        for p in c.get("image_paths", []):
            self._lb.insert("end", p)
        win = c.get("window_title", "")
        if win:
            labels = [l for l, t in self._wins if t == win]
            if labels:
                self._wvar.set(labels[0])
        else:
            if self._combo["values"]:
                self._combo.current(0)
        self._conf.set(c.get("confidence", 0.80))
        self._rep.set(c.get("repeat", 9999))
        self._ivl.set(c.get("interval", 1.0))
        self._skip.set(c.get("skip_radius", 40))
        self._adaptive_var.set(c.get("adaptive_conf", True))
        mode_lbl = clk.MODE_LABELS.get(c.get("click_mode", "shift_right"), "Shift + Sag Tik")
        self._mode_var.set(mode_lbl)
        self._mode_cb["values"] = list(clk.MODE_LABELS.values())
        self._human_var.set(c.get("human_move", False))
        self._hspeed.set(c.get("human_speed", 1.0))
        self._hjitter.set(c.get("human_jitter", 2))
        self._rand_offset_var.set(c.get("rand_offset", 3))
        self._pre_move_var.set(c.get("pre_move_ms", 20))
        self._hold_ms_var.set(c.get("hold_ms", 35))
        self._post_click_var.set(c.get("post_click_ms", 60))
        self._sound_var.set(c.get("sound_alert", True))
        self._overlay_var.set(c.get("overlay_enabled", True))
        self._ss_detect_var.set(c.get("screenshot_on_detect", False))
        self._pause_uf_var.set(c.get("pause_on_unfocus", False))
        self._ms_var.set(c.get("multiscale", True))
        self._sc_min.set(c.get("scales_min", 0.50))
        self._sc_max.set(c.get("scales_max", 2.00))
        self._sc_steps.set(c.get("scales_steps", 12))
        self._method_var.set(c.get("match_method", "CCOEFF"))
        self._nms_var.set(c.get("nms_iou", 30))
        self._priority_var.set(c.get("priority_mode", "score"))
        self._clahe_var.set(c.get("use_clahe", True))
        self._blur_var.set(c.get("blur_kernel", 0))
        self._log_file_var.set(c.get("log_to_file", True))
        self._sched_var.set(c.get("scheduler_enabled", False))
        self._sched_start.set(c.get("scheduler_start", ""))
        self._sched_stop.set(c.get("scheduler_stop", ""))
        self._max_clicks_var.set(c.get("max_clicks", 0))
        self._max_dur_var.set(c.get("max_duration_min", 0))
        self._break_every_var.set(c.get("break_every_min", 0))
        self._break_for_var.set(c.get("break_for_sec", 30))
        r = c.get("capture_region")
        if r:
            self._capture_region = tuple(r)
            self._region_lbl.config(text=rsel.region_to_str(self._capture_region), fg=TEAL)

    def _save_profile(self):
        name = simpledialog.askstring("Profil Kaydet", "Profil adı:", parent=self)
        if not name:
            return
        c = self._collect_cfg()
        if prf.save_profile(_DIR, name, c):
            self._append_log(f"Profil kaydedildi: {name}", "green")
            self._refresh_profiles()
        else:
            messagebox.showerror("Hata", "Profil kaydedilemedi.")

    def _load_profile(self):
        sel = self._prof_lb.curselection()
        if not sel:
            messagebox.showinfo("Bilgi", "Bir profil seciniz.")
            return
        name = self._prof_lb.get(sel[0])
        data = prf.load_profile(_DIR, name)
        if data is None:
            messagebox.showerror("Hata", "Profil yuklenemedi.")
            return
        self._cfg = data
        self._lb.delete(0, "end")
        self._load_cfg_to_ui()
        self._append_log(f"Profil yuklendi: {name}", "teal")

    def _del_profile(self):
        sel = self._prof_lb.curselection()
        if not sel:
            return
        name = self._prof_lb.get(sel[0])
        if messagebox.askyesno("Sil", f"'{name}' profilini sil?"):
            prf.delete_profile(_DIR, name)
            self._refresh_profiles()

    def _export_profile(self):
        sel = self._prof_lb.curselection()
        if not sel:
            messagebox.showinfo("Bilgi", "Bir profil seciniz.")
            return
        name = self._prof_lb.get(sel[0])
        path = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("JSON", "*.json")],
            initialfile=name)
        if path:
            prf.export_profile(_DIR, name, path)
            self._append_log(f"Profil aktarildi: {path}", "teal")

    def _import_profile(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if path:
            name = prf.import_profile(_DIR, path)
            if name:
                self._append_log(f"Profil iceri aktarildi: {name}", "green")
                self._refresh_profiles()

    # ────────────────────────────────────────────────────────────────────────
    # İstatistik yardımcıları
    # ────────────────────────────────────────────────────────────────────────
    def _export_csv(self):
        if self._slog:
            p = self._slog.export_csv()
            if p:
                messagebox.showinfo("CSV Export", f"Dosya kaydedildi:\n{p}")
            else:
                messagebox.showinfo("CSV Export", "Henüz kayit yok.")
        else:
            messagebox.showinfo("CSV Export", "Aktif oturum yok.")

    def _open_logs(self):
        log_dir = os.path.join(_DIR, "logs")
        os.makedirs(log_dir, exist_ok=True)
        os.startfile(log_dir)

    def _reset_stats(self):
        self._click_times.clear()
        self._scan_times.clear()
        for k in self._stat_labels:
            self._stat_labels[k].config(text="0")
        self._draw_graph()

    def _toggle_overlay(self):
        if self._overlay:
            self._overlay.hide() if self._overlay_var.get() else None

    # ────────────────────────────────────────────────────────────────────────
    # Bot kontrol
    # ────────────────────────────────────────────────────────────────────────
    def _start(self):
        if self._alive:
            return
        params = self._collect_cfg()
        if not params["image_paths"]:
            messagebox.showwarning("Uyari", "En az bir referans gorsel ekleyin.")
            return

        self._cfg = params
        cfg.save(_DIR, params)
        self._clkd.clear()
        self._stop.clear()
        self._stats = {}
        self._click_times.clear()
        self._slog = slog.SessionLog(_DIR, enabled=params.get("log_to_file", True))
        self._alive = True

        if self._overlay and params.get("overlay_enabled"):
            pass
        elif self._overlay:
            self._overlay.hide()

        self._bgo.config(state="disabled")
        self._bstp.config(state="normal")
        self._set_status("Calisıyor...", GREEN)

        def worker():
            run_bot(params, self._log_q, self._preview_q,
                    self._stop, self._slog, self._stats)
            self._alive = False
            self.after(0, self._on_bot_done)

        threading.Thread(target=worker, daemon=True).start()

    def _stop_bot(self):
        self._stop.set()
        self._set_status("Durduruluyor...", YELLOW)

    def _on_bot_done(self):
        self._bgo.config(state="normal")
        self._bstp.config(state="disabled")
        self._set_status("Durduruldu / Bitti", SUB)
        if self._slog:
            self._slog.close()

    # ────────────────────────────────────────────────────────────────────────
    # Polling
    # ────────────────────────────────────────────────────────────────────────
    def _poll_log(self):
        try:
            while True:
                item = self._log_q.get_nowait()
                kind = item[0]
                if kind == "msg":
                    _, msg, tag = item
                    self._append_log(msg, tag)
                elif kind == "overlay":
                    _, results, offset, dur = item
                    if self._overlay and self._overlay_var.get():
                        self._overlay.show(results, offset, dur)
                elif kind == "stats":
                    _, stats = item
                    self._stats = stats
                    self._update_stat_labels(stats)
        except Empty:
            pass
        self.after(80, self._poll_log)

    def _poll_preview(self):
        try:
            while True:
                item = self._preview_q.get_nowait()
        except Empty:
            item = None
        if item:
            screen, results, offset = item
            try:
                img = _make_preview(screen, results, offset)
                self._preview_img = img
                self._preview_lbl.config(image=img)
            except Exception:
                pass
        self.after(120, self._poll_preview)

    def _poll_stats_graph(self):
        if self._alive and self._stats:
            # click_times güncelle (stats'tan)
            tc = self._stats.get("total_clicks", 0)
            # Grafik için kendi listimizi kullanıyoruz (log_q'dan gelmiyor)
            pass
        self._draw_graph()
        self._update_stat_labels(self._stats)
        self.after(1000, self._poll_stats_graph)

    def _update_stat_labels(self, stats: dict):
        if not stats:
            return
        rate  = stats.get("rate", 0)
        tc    = stats.get("total_clicks", 0)
        ts_   = stats.get("total_scans", 0)
        tf    = stats.get("total_found", 0)
        st    = stats.get("start_time", 0)
        elapsed = time.time() - st if st else 0
        m, s  = divmod(int(elapsed), 60)
        h, m2 = divmod(m, 60)
        elapsed_str = f"{h:02d}:{m2:02d}:{s:02d}"

        updates = {
            "rate":         f"{rate:.1f}",
            "total_clicks": str(tc),
            "total_scans":  str(ts_),
            "total_found":  str(tf),
            "elapsed":      elapsed_str,
        }
        for k, v in updates.items():
            if k in self._stat_labels:
                self._stat_labels[k].config(text=v)

        # Click times grafik listesine ekle (yaklasık)
        if tc > len(self._click_times):
            diff = tc - len(self._click_times)
            now  = time.time()
            for _ in range(diff):
                self._click_times.append(now)

    # ────────────────────────────────────────────────────────────────────────
    # Kapatma
    # ────────────────────────────────────────────────────────────────────────
    def _on_close(self):
        self._stop.set()
        if self._slog:
            self._slog.close()
        try:
            cfg.save(_DIR, self._collect_cfg())
        except Exception:
            pass
        if self._overlay:
            try: self._overlay.destroy()
            except Exception: pass
        if HAS_KEYBOARD:
            try: keyboard.unhook_all_hotkeys()
            except Exception: pass
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
