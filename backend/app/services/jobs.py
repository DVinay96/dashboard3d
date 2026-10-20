from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

_pool: ThreadPoolExecutor | None = None
_lock = threading.Lock()


def configure(workers: int) -> None:
    global _pool
    with _lock:
        if _pool is not None:
            _pool.shutdown(wait=False, cancel_futures=True)
        _pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="job") if workers > 0 else None


def submit(fn: Callable, *args) -> None:
    pool = _pool
    if pool is None:
        fn(*args)
    else:
        pool.submit(fn, *args)


def shutdown() -> None:
    global _pool
    with _lock:
        if _pool is not None:
            _pool.shutdown(wait=False, cancel_futures=True)
        _pool = None
