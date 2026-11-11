"""Holds the latest Snapshot in memory; requests never touch the database."""

import logging
import threading
from collections.abc import Callable

from oam_eoapi_stats.config import settings
from oam_eoapi_stats.models import Snapshot
from oam_eoapi_stats.refresh import load_snapshot

logger = logging.getLogger(__name__)


class StatsCache:
    def __init__(self, loader: Callable[[], Snapshot]):
        self._loader = loader
        self._snapshot: Snapshot | None = None
        self._lock = threading.Lock()

    @property
    def ready(self) -> bool:
        return self.snapshot() is not None

    def snapshot(self) -> Snapshot | None:
        with self._lock:
            return self._snapshot

    def refresh(self) -> None:
        """Replace the snapshot. On failure the previous one keeps being served."""
        try:
            snapshot = self._loader()
        except Exception:
            logger.exception("Stats refresh failed; keeping the previous snapshot")
            return
        with self._lock:
            self._snapshot = snapshot


cache = StatsCache(lambda: load_snapshot(settings))
