"""
session_log.py  —  Oturum loglama + CSV export  v9.0
=====================================================
• Her calistirma icin  logs/YYYY-MM-DD_HH-MM-SS.log
• CSV export: logs/YYYY-MM-DD_HH-MM-SS_stats.csv
• Thread-safe yazi
"""

import csv
import datetime
import os
import threading


class SessionLog:
    def __init__(self, script_dir: str, enabled: bool = True):
        self._enabled  = enabled
        self._file     = None
        self._csv_rows: list[dict] = []
        self._lock     = threading.Lock()
        self._log_path = ""
        self._csv_path = ""

        if not enabled:
            return

        log_dir = os.path.join(script_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self._log_path = os.path.join(log_dir, f"{ts}.log")
        self._csv_path = os.path.join(log_dir, f"{ts}_stats.csv")

        try:
            self._file = open(self._log_path, "w", encoding="utf-8", buffering=1)
            self._write(f"=== Oturum basladi: {ts} ===")
        except Exception:
            self._file = None

    # ── Dahili ────────────────────────────────────────────────────────────────
    def _write(self, msg: str):
        if self._file:
            ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
            try:
                self._file.write(f"[{ts}] {msg}\n")
            except Exception:
                pass

    # ── Public ────────────────────────────────────────────────────────────────
    def log(self, msg: str):
        if not self._enabled:
            return
        with self._lock:
            self._write(msg)

    def record_click(
        self,
        x: int, y: int,
        score: float,
        template: str,
        engine: str,
        scan_no: int,
    ):
        """CSV icin satirlik kayit."""
        if not self._enabled:
            return
        ts = datetime.datetime.now().isoformat(timespec="milliseconds")
        with self._lock:
            self._csv_rows.append({
                "timestamp": ts,
                "scan":      scan_no,
                "x":         x,
                "y":         y,
                "score":     f"{score:.4f}",
                "template":  template,
                "engine":    engine,
            })

    def export_csv(self) -> str:
        """CSV dosyasina yaz, yolu dondur."""
        if not self._csv_rows:
            return ""
        try:
            with open(self._csv_path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=[
                    "timestamp", "scan", "x", "y", "score", "template", "engine"
                ])
                w.writeheader()
                with self._lock:
                    w.writerows(self._csv_rows)
            return self._csv_path
        except Exception:
            return ""

    def log_dir(self) -> str:
        return os.path.dirname(self._log_path) if self._log_path else ""

    def close(self):
        with self._lock:
            if self._file:
                self._write("=== Oturum sona erdi ===")
                try:
                    self._file.close()
                except Exception:
                    pass
                self._file = None
        self.export_csv()
