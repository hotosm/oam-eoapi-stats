from contextlib import ExitStack
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from oam_eoapi_stats.aggregate import build_snapshot
from oam_eoapi_stats.cache import StatsCache
from oam_eoapi_stats.main import app

from .test_aggregate import CLASSES, FACTS, SCENES

DATA_PATHS = ("/stats", "/stats/platforms", "/stats/by-year", "/stats/collections", "/stats/licenses")


def snapshot():
    return build_snapshot(FACTS, SCENES, CLASSES, datetime(2026, 11, 12, tzinfo=UTC))


@pytest.fixture
def client_for():
    with ExitStack() as stack:

        def make(loaded: bool) -> TestClient:
            stats_cache = StatsCache(snapshot)
            if loaded:
                stats_cache.refresh()
            stack.enter_context(patch("oam_eoapi_stats.main.cache", stats_cache))
            # Keep the startup refresh and the scheduler away from the (absent) database.
            stack.enter_context(patch("oam_eoapi_stats.main.threading.Thread"))
            stack.enter_context(patch("oam_eoapi_stats.main.scheduler"))
            return stack.enter_context(TestClient(app))

        yield make


def test_healthz_always_ok(client_for):
    assert client_for(loaded=False).get("/stats/healthz").status_code == 200


def test_not_ready_before_first_refresh(client_for):
    client = client_for(loaded=False)
    assert client.get("/stats/readyz").status_code == 503
    for path in DATA_PATHS:
        response = client.get(path)
        assert response.status_code == 503
        assert "cache-control" not in response.headers


def test_served_from_snapshot(client_for):
    client = client_for(loaded=True)
    assert client.get("/stats/readyz").status_code == 200

    totals = client.get("/stats").json()
    assert totals["generated_at"] == "2026-11-12T00:00:00Z"
    assert totals["hosted"]["images"] == 5
    assert totals["hosted"]["area_km2"]["under_10cm"] == 4.0
    assert totals["hosted"]["set_aside"] == {"items": 1, "area_km2": 5e6}
    assert totals["federated"]["entries"] == 4

    assert client.get("/stats/platforms").json()["hosted"][0]["platform"] == "uav"
    assert [r["year"] for r in client.get("/stats/by-year").json()["hosted"]] == [2019, 2020, 2021]
    assert client.get("/stats/collections").json()["federated"][0]["collection"] == "maxar-opendata"
    assert client.get("/stats/licenses").json()["hosted"][0] == {
        "licence": "CC-BY-4.0",
        "images": 3,
        "entries": 3,
        "area_km2": {"under_10cm": 3.0, "10_50cm": 0.0, "over_50cm": 0.0, "unknown": 0.0},
    }


def test_cache_and_cors_headers(client_for):
    client = client_for(loaded=True)
    for path in DATA_PATHS:
        response = client.get(path, headers={"Origin": "https://imagery.hotosm.org"})
        assert response.headers["cache-control"] == "public, max-age=3600"
        assert response.headers["access-control-allow-origin"] == "https://imagery.hotosm.org"
    assert "cache-control" not in client.get("/stats/readyz").headers
    other = client.get("/stats", headers={"Origin": "https://example.com"})
    assert "access-control-allow-origin" not in other.headers


def test_failed_refresh_keeps_previous_snapshot():
    loads = iter([snapshot()])

    def loader():
        return next(loads)  # second call raises StopIteration

    stats_cache = StatsCache(loader)
    stats_cache.refresh()
    first = stats_cache.snapshot()
    stats_cache.refresh()
    assert stats_cache.snapshot() is first
