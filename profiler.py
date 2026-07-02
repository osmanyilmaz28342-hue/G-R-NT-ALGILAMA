"""
profiler.py  —  Profil yonetimi  v9.0
======================================
Birden fazla config profili kaydet/yukle/sil.
profiles/  klasorunde her profil ayri bir JSON dosyasi.
"""

import json
import os
from typing import Optional


PROFILES_DIR = "profiles"


def _dir(script_dir: str) -> str:
    return os.path.join(script_dir, PROFILES_DIR)


def list_profiles(script_dir: str) -> list[str]:
    d = _dir(script_dir)
    if not os.path.isdir(d):
        return []
    names = [
        f[:-5] for f in os.listdir(d)
        if f.endswith(".json")
    ]
    names.sort()
    return names


def save_profile(script_dir: str, name: str, cfg: dict) -> bool:
    d = _dir(script_dir)
    os.makedirs(d, exist_ok=True)
    safe = "".join(c for c in name if c.isalnum() or c in " _-").strip() or "profil"
    path = os.path.join(d, safe + ".json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def load_profile(script_dir: str, name: str) -> Optional[dict]:
    path = os.path.join(_dir(script_dir), name + ".json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def delete_profile(script_dir: str, name: str) -> bool:
    path = os.path.join(_dir(script_dir), name + ".json")
    try:
        os.remove(path)
        return True
    except Exception:
        return False


def export_profile(script_dir: str, name: str, dest_path: str) -> bool:
    data = load_profile(script_dir, name)
    if data is None:
        return False
    try:
        with open(dest_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def import_profile(script_dir: str, src_path: str) -> Optional[str]:
    try:
        with open(src_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        name = os.path.splitext(os.path.basename(src_path))[0]
        if save_profile(script_dir, name, data):
            return name
    except Exception:
        pass
    return None
