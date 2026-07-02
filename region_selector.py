"""
region_selector.py  —  Ekran üzerinde bölge seçici  v9.0
==========================================================
Tam ekran seffaf bir pencere açar, kullanıcı sol tus ile
dikdörtgen çizer. Pencere kapanınca (x1,y1,x2,y2) döner.
Iptal edilirse None döner.
"""

import tkinter as tk
from typing import Optional


def select_region() -> Optional[tuple[int, int, int, int]]:
    """
    Ekran üzerinde dikdörtgen çiz.
    Döner: (x1, y1, x2, y2) veya None (iptal)
    """
    result: list[Optional[tuple]] = [None]

    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-fullscreen", True)
    root.attributes("-alpha", 0.25)
    root.attributes("-topmost", True)
    root.configure(bg="black")

    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()

    canvas = tk.Canvas(root, bg="black", cursor="crosshair",
                       highlightthickness=0, bd=0)
    canvas.pack(fill="both", expand=True)

    # Talimat etiketi
    info = canvas.create_text(
        sw // 2, 30,
        text="Sol tus: çiz  |  Bırak: onayla  |  ESC / Sağ tus: iptal",
        fill="#00ff88", font=("Consolas", 13, "bold"),
    )

    state = {"x0": 0, "y0": 0, "rect": None, "drawing": False}

    def on_press(e):
        state["x0"] = e.x
        state["y0"] = e.y
        state["drawing"] = True
        if state["rect"]:
            canvas.delete(state["rect"])
        state["rect"] = canvas.create_rectangle(
            e.x, e.y, e.x, e.y,
            outline="#00ff88", width=2, fill="#00ff8822",
        )

    def on_drag(e):
        if state["drawing"] and state["rect"]:
            canvas.coords(state["rect"],
                          state["x0"], state["y0"], e.x, e.y)
            # Boyut etiketi
            canvas.delete("sizelbl")
            w = abs(e.x - state["x0"])
            h = abs(e.y - state["y0"])
            canvas.create_text(
                e.x + 6, e.y - 6,
                text=f"{w}×{h}",
                fill="#ffffff", font=("Consolas", 9),
                anchor="w", tags="sizelbl",
            )

    def on_release(e):
        state["drawing"] = False
        x0, y0 = state["x0"], state["y0"]
        x1_, y1_ = e.x, e.y
        if abs(x1_ - x0) > 5 and abs(y1_ - y0) > 5:
            result[0] = (
                min(x0, x1_), min(y0, y1_),
                max(x0, x1_), max(y0, y1_),
            )
        root.destroy()

    def on_cancel(e=None):
        result[0] = None
        root.destroy()

    canvas.bind("<ButtonPress-1>",   on_press)
    canvas.bind("<B1-Motion>",       on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)
    canvas.bind("<ButtonPress-3>",   on_cancel)
    root.bind("<Escape>",            on_cancel)

    root.mainloop()
    return result[0]


def region_to_str(r: Optional[tuple]) -> str:
    if r is None:
        return "Tum ekran"
    return f"({r[0]},{r[1]}) → ({r[2]},{r[3]})  [{r[2]-r[0]}×{r[3]-r[1]}px]"
