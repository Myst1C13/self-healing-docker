import threading
import time

from src import collector, detector, recovery, storage
from src.config import POLL_INTERVAL_SECONDS

_stop = threading.Event()
_last_tick = {"time": None, "incidents": 0}


def run_once():
    # one full pass: collect -> detect -> recover -> store
    collector.collect_once()
    windows = collector.get_all_windows()
    incidents = detector.detect_all(windows)

    for incident in incidents:
        recovery.recover(incident)
        storage.save_incident(incident)

    _last_tick["time"] = time.time()
    _last_tick["incidents"] = len(incidents)
    return incidents


def run_forever():
    print("[pipeline] starting, polling every", POLL_INTERVAL_SECONDS, "s")
    while not _stop.is_set():
        try:
            run_once()
        except Exception as e:
            # one bad tick shouldn't kill the whole loop
            print("[pipeline] tick error:", e)
        _stop.wait(POLL_INTERVAL_SECONDS)
    print("[pipeline] stopped")


def start_background():
    _stop.clear()
    t = threading.Thread(target=run_forever, daemon=True)
    t.start()
    return t


def stop():
    _stop.set()


def last_tick():
    return dict(_last_tick)


if __name__ == "__main__":
    run_forever()
