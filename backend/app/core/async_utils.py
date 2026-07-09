"""
Bridges sync call sites (Celery tasks, LangGraph's sync node functions) to
async infrastructure clients (Neo4j driver, Qdrant client) safely.

Why this exists: those clients are cached as module-level singletons for
performance, but their internal connections bind to whichever asyncio event
loop was running the first time they were used. Calling `asyncio.run(...)`
fresh at each call site creates and destroys a new loop every time — so the
*second* call (e.g. a Celery task retry, or a second chat request) fails with
"Event loop is closed", because the cached client is still pointing at the
first, now-destroyed loop.

The fix is a single persistent event loop, run forever in one background
thread for the lifetime of the process, that every sync call site submits
work to via `run_async`. The cached clients then only ever see one loop.
"""
from __future__ import annotations

import asyncio
import threading
from typing import Any, Coroutine, TypeVar

T = TypeVar("T")

_loop: asyncio.AbstractEventLoop | None = None
_thread: threading.Thread | None = None
_lock = threading.Lock()


def _ensure_loop() -> asyncio.AbstractEventLoop:
    global _loop, _thread
    with _lock:
        if _loop is None or _loop.is_closed():
            _loop = asyncio.new_event_loop()
            _thread = threading.Thread(target=_loop.run_forever, daemon=True, name="async-bridge-loop")
            _thread.start()
    return _loop


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    """Run a coroutine to completion on the shared background loop and block
    the calling (sync) thread for the result. Safe to call repeatedly, from
    any thread, including from within code that's itself running inside a
    *different* event loop (e.g. a LangGraph sync node called from a FastAPI
    async handler) — this never nests or re-enters that loop."""
    loop = _ensure_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()
