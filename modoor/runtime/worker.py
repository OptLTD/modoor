"""Job worker: poll Postgres queue. Used in-process (API) or `make worker`."""

from __future__ import annotations

import logging
import threading
import time

from modoor.core.settings import get_settings

log = logging.getLogger("modoor.worker")

_stop = threading.Event()
_thread: threading.Thread | None = None


def _ensure_handlers() -> None:
    from platform.doc.jobs import register as register_doc_jobs

    register_doc_jobs()


def run_forever(*, poll_seconds: float | None = None) -> None:
    from modoor.runtime.jobs import run_pending

    _ensure_handlers()
    settings = get_settings()
    interval = float(
        poll_seconds if poll_seconds is not None else settings.modoor_jobs_poll_seconds
    )
    interval = max(interval, 0.2)
    log.info("job worker polling every %.2fs", interval)
    while not _stop.is_set():
        try:
            n = run_pending(limit=8)
            if n:
                continue
        except Exception:  # noqa: BLE001
            log.exception("job worker loop error")
        _stop.wait(interval)


def start_inprocess() -> None:
    global _thread
    settings = get_settings()
    if not settings.modoor_jobs_inprocess:
        return
    if _thread is not None and _thread.is_alive():
        return
    _stop.clear()
    _ensure_handlers()
    _thread = threading.Thread(target=run_forever, name="modoor-jobs", daemon=True)
    _thread.start()
    log.info("in-process job worker started")


def stop_inprocess() -> None:
    global _thread
    _stop.set()
    t = _thread
    _thread = None
    if t is not None:
        t.join(timeout=3)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    from modoor.platform.bootstrap import bootstrap
    from modoor.core.db import init_db

    get_settings.cache_clear()
    init_db()
    bootstrap()
    _stop.clear()
    try:
        run_forever()
    except KeyboardInterrupt:
        _stop.set()


if __name__ == "__main__":
    main()
