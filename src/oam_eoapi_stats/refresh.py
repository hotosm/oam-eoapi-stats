"""Query pgSTAC (read-only) and turn the rows into a Snapshot."""

import logging
import time
from datetime import UTC, datetime

import psycopg
from psycopg.rows import dict_row

from oam_eoapi_stats import queries
from oam_eoapi_stats.aggregate import build_snapshot
from oam_eoapi_stats.config import Settings
from oam_eoapi_stats.models import Snapshot

logger = logging.getLogger(__name__)

UNGROUPED_COLLECTIONS = "SELECT id FROM pgstac.collections WHERE NOT id = ANY(%s) ORDER BY id"


def load_snapshot(settings: Settings) -> Snapshot:
    started = time.monotonic()
    params = queries.params(settings)
    configured = [*settings.hosted_collections, *settings.federated_collections, *settings.excluded_collections]

    with psycopg.connect(**settings.connect_kwargs, row_factory=dict_row) as conn:
        conn.read_only = True
        # query_statement_timeout is validated against STATEMENT_TIMEOUT_RE when settings load.
        conn.execute(f"SET statement_timeout = '{settings.query_statement_timeout}'")

        ungrouped = [row["id"] for row in conn.execute(UNGROUPED_COLLECTIONS, [configured]).fetchall()]
        if ungrouped:
            logger.warning("Skipping collections in no group (hosted, federated or excluded): %s", ", ".join(ungrouped))

        facts = conn.execute(queries.BASE_FACTS, params).fetchall()
        scenes = conn.execute(queries.SCENES, params).fetchall()

    snapshot = build_snapshot(facts, scenes, settings.gsd_classes, datetime.now(UTC))
    logger.info(
        "Stats refreshed in %.1fs: hosted %s images / %s entries, federated %s images / %s entries",
        time.monotonic() - started,
        snapshot.totals.hosted.images,
        snapshot.totals.hosted.entries,
        snapshot.totals.federated.images,
        snapshot.totals.federated.entries,
    )
    return snapshot
