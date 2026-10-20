from __future__ import annotations

import re
import shutil
import threading
import time
from pathlib import Path

from ..config import get_settings

_log_lock = threading.RLock()


def product_dir(pid: str) -> Path:
    return get_settings().products_dir / pid


def safe_file(pid: str, rel: str) -> Path | None:
    base = product_dir(pid).resolve()
    full = (base / rel).resolve()
    if base not in full.parents or not full.is_file():
        return None
    return full


def slugify(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", name or "producto").strip("_").lower()
    return s[:60] or "producto"


def log(pid: str, msg: str) -> None:
    line = time.strftime("%H:%M:%S") + "  " + str(msg)
    with _log_lock:
        d = product_dir(pid)
        d.mkdir(parents=True, exist_ok=True)
        with open(d / "log.txt", "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    print("[" + pid[:8] + "] " + str(msg), flush=True)


def append_log(pid: str, text: str) -> None:
    with _log_lock:
        with open(product_dir(pid) / "log.txt", "a", encoding="utf-8") as fh:
            fh.write(text)


def read_log(pid: str, limit: int = 20000) -> str:
    p = product_dir(pid) / "log.txt"
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="replace")[-limit:]


def remove_product_files(pid: str) -> None:
    d = product_dir(pid).resolve()
    if get_settings().products_dir.resolve() in d.parents and d.is_dir():
        shutil.rmtree(d, ignore_errors=True)
