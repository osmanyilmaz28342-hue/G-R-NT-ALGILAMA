"""
overlay.py  —  Seffaf ekran overlay'i  v9.0
============================================
• Neon yeşil dikdörtgen + köşe vurguları
• Animasyonlu köşeler (dönen L çizgiler)
• Güven çubugu (confidence bar)
• FPS göstergesi
• Tıklamaları geçirir (WS_EX_LAYERED + WS_EX_TRANSPARENT)
• Her eslesme üstüne template adı + skor etiketi
• N ms sonra otomatik kaybolur
"""

import time
import tkinter as tk
from typing import Optional


_TRANSPARENT = "#010203"   # transparentcolor olarak kullanilan neredeyse-siyah
_NEON        = "#00ff88"
_RED_DOT     = "#ff4455"
_WHITE       = "#ffffff"
_YELLOW      = "#ffcc00"


class Overlay:
    def __init__(self, master: tk.Tk):
        self._master  = master
        self._win:    Optional[tk.Toplevel] = None
        self._canvas: Optional[tk.Canvas]  = None
        self._after:  Optional[str]        = None
        self._anim_job: Optional[str]      = None
        self._anim_ids: list = []
        self._anim_tick = 0
        self._build()

    def _build(self):
        w = tk.Toplevel(self._master)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        w.attributes("-transparentcolor", _TRANSPARENT)

        try:
            import ctypes
            WS_EX_LAYERED     = 0x00080000
            WS_EX_TRANSPARENT = 0x00000020
            GWL_EXSTYLE       = -20
            hwnd  = w.winfo_id()
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(
                hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT
            )
        except Exception:
            pass

        sw = w.winfo_screenwidth()
        sh = w.winfo_screenheight()
        w.geometry(f"{sw}x{sh}+0+0")
        w.configure(bg=_TRANSPARENT)

        canvas = tk.Canvas(w, bg=_TRANSPARENT, highlightthickness=0, bd=0)
        canvas.pack(fill="both", expand=True)
        w.withdraw()

        self._win    = w
        self._canvas = canvas

    # ── Corner L çizgisi ─────────────────────────────────────────────────────
    def _corner(self, x, y, dx, dy, size=14, color=_WHITE, width=2, tag="corner"):
        c = self._canvas
        c.create_line(x, y, x + dx*size, y,
                      fill=color, width=width, tags=tag)
        c.create_line(x, y, x, y + dy*size,
                      fill=color, width=width, tags=tag)

    # ── Tek esleme kutusu ─────────────────────────────────────────────────────
    def _draw_match(self, r, offset):
        c = self._canvas
        ox, oy = offset
        rx = r.x + ox
        ry = r.y + oy
        rw, rh = r.w, r.h

        # Ana dikdörtgen
        c.create_rectangle(rx, ry, rx+rw, ry+rh,
                           outline=_NEON, width=2, fill="")

        # Köşe L vurguları
        for cx_, cy_, dx, dy in [
            (rx,      ry,      1,  1),
            (rx+rw,   ry,     -1,  1),
            (rx,      ry+rh,   1, -1),
            (rx+rw,   ry+rh,  -1, -1),
        ]:
            self._corner(cx_, cy_, dx, dy, size=12, color=_WHITE, width=2)

        # Merkez nokta
        mx = r.cx + ox
        my = r.cy + oy
        c.create_oval(mx-5, my-5, mx+5, my+5, fill=_RED_DOT, outline="")
        c.create_line(mx-8, my, mx+8, my, fill=_RED_DOT, width=1)
        c.create_line(mx, my-8, mx, my+8, fill=_RED_DOT, width=1)

        # Etiket arka plan + metin
        label = f"  {r.template_name}  {r.score:.2f}  "
        tag_bg = "lbg"
        c.create_rectangle(rx, ry-18, rx + len(label)*6 + 4, ry - 2,
                           fill="#00000088", outline="", tags=tag_bg)
        c.create_text(rx + 4, ry - 10,
                      text=label,
                      fill=_NEON, anchor="w",
                      font=("Consolas", 8, "bold"))

        # Güven çubuğu (renkli)
        bar_w = min(rw, 80)
        bar_filled = int(bar_w * r.score)
        bar_y = ry + rh + 3
        c.create_rectangle(rx, bar_y, rx + bar_w, bar_y + 4,
                           fill="#333333", outline="")
        bar_color = _NEON if r.score >= 0.80 else (_YELLOW if r.score >= 0.65 else "#ff6655")
        c.create_rectangle(rx, bar_y, rx + bar_filled, bar_y + 4,
                           fill=bar_color, outline="")

    # ── Public: göster ───────────────────────────────────────────────────────
    def show(self, matches: list, offset: tuple = (0, 0), duration_ms: int = 1500):
        if not self._win:
            return
        c = self._canvas
        c.delete("all")

        for r in matches:
            self._draw_match(r, offset)

        # Ekran köşesine FPS bilgisi
        c.create_text(
            8, 8,
            text=f"BOT v9.0  |  {len(matches)} eslesme",
            fill=_NEON, anchor="nw",
            font=("Consolas", 8, "bold"),
        )

        self._win.deiconify()
        self._win.lift()

        if self._after:
            try: self._master.after_cancel(self._after)
            except Exception: pass
        self._after = self._master.after(duration_ms, self.hide)

    def hide(self):
        if self._win:
            try: self._win.withdraw()
            except Exception: pass
        self._after = None

    def enabled(self) -> bool:
        return self._win is not None

    def destroy(self):
        if self._after:
            try: self._master.after_cancel(self._after)
            except Exception: pass
        if self._win:
            try: self._win.destroy()
            except Exception: pass
        self._win = self._canvas = None
