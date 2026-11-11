from datetime import UTC, datetime

import pytest

from oam_eoapi_stats.aggregate import build_snapshot, gsd_class

CLASSES = ("under_10cm", "10_50cm", "over_50cm")
NOW = datetime(2026, 11, 12, tzinfo=UTC)


def d(year: int) -> datetime:
    return datetime(year, 1, 1, tzinfo=UTC)


def fact(**overrides) -> dict:
    row = {
        "collection": "openaerialmap",
        "grp": "hosted",
        "platform": "uav",
        "gsd_bucket": 0,
        "licence": "CC-BY-4.0",
        "year_captured": 2020,
        "invalid_date": False,
        "set_aside": False,
        "items": 1,
        "duplicates": 0,
        "area_m2": 1e6,
        "set_aside_area_m2": 0.0,
        "earliest": d(2020),
        "latest": d(2020),
    }
    return {**row, **overrides}


FACTS = [
    fact(items=2, duplicates=1, area_m2=3e6),
    fact(
        platform="aircraft",
        gsd_bucket=1,
        licence="various",
        year_captured=2021,
        area_m2=2e6,
        earliest=d(2021),
        latest=d(2021),
    ),
    fact(year_captured=None, invalid_date=True, earliest=None, latest=None, licence="CC-BY-SA-4.0"),
    fact(
        platform="satellite",
        gsd_bucket=2,
        set_aside=True,
        area_m2=0.0,
        set_aside_area_m2=5e12,
        year_captured=2019,
        earliest=d(2019),
        latest=d(2019),
    ),
    fact(
        collection="maxar-opendata",
        grp="federated",
        platform="satellite",
        gsd_bucket=1,
        items=3,
        area_m2=30e6,
        year_captured=2023,
        licence="CC-BY-NC-4.0",
        earliest=d(2023),
        latest=d(2023),
    ),
    fact(
        collection="noaa-emergency-response",
        grp="federated",
        platform="aircraft",
        gsd_bucket=None,
        area_m2=4e6,
        year_captured=2024,
        licence="CC0-1.0",
        earliest=d(2024),
        latest=d(2024),
    ),
]


def scene(dim, grp, key, n):
    return {"dim": dim, "grp": grp, "key": key, "scenes": n}


SCENES = [
    scene("group", "hosted", None, 5),
    scene("group", "federated", None, 2),
    scene("platform", "hosted", "uav", 3),
    scene("platform", "hosted", "aircraft", 1),
    scene("platform", "hosted", "satellite", 1),
    scene("platform", "federated", "satellite", 1),
    scene("platform", "federated", "aircraft", 1),
    scene("year", "hosted", "2020", 2),
    scene("year", "hosted", "2021", 1),
    scene("year", "hosted", "2019", 1),
    scene("year", "hosted", None, 1),
    scene("year", "federated", "2023", 1),
    scene("year", "federated", "2024", 1),
    scene("licence", "hosted", "CC-BY-4.0", 3),
    scene("licence", "hosted", "various", 1),
    scene("licence", "hosted", "CC-BY-SA-4.0", 1),
    scene("collection", "hosted", "openaerialmap", 5),
    scene("collection", "federated", "maxar-opendata", 1),
    scene("collection", "federated", "noaa-emergency-response", 1),
]


@pytest.fixture
def snap():
    return build_snapshot(FACTS, SCENES, CLASSES, NOW)


@pytest.mark.parametrize("bucket,label", [(0, "under_10cm"), (1, "10_50cm"), (2, "over_50cm"), (None, "unknown")])
def test_gsd_class(bucket, label):
    assert gsd_class(bucket, CLASSES) == label


def test_totals(snap):
    hosted = snap.totals.hosted
    assert hosted.images == 5
    assert hosted.entries == 5
    assert hosted.area_km2 == {"under_10cm": 4.0, "10_50cm": 2.0, "over_50cm": 0.0, "unknown": 0.0}
    assert hosted.earliest_capture == d(2019)
    assert hosted.latest_capture == d(2021)
    assert hosted.invalid_dates == 1
    assert hosted.duplicates == 1
    assert hosted.set_aside.items == 1
    assert hosted.set_aside.area_km2 == 5e6

    federated = snap.totals.federated
    assert (federated.images, federated.entries) == (2, 4)
    assert federated.area_km2 == {"under_10cm": 0.0, "10_50cm": 30.0, "over_50cm": 0.0, "unknown": 4.0}


def test_platforms_sorted_by_images(snap):
    hosted = snap.platforms.hosted
    assert [r.platform for r in hosted] == ["uav", "aircraft", "satellite"]
    assert hosted[0].entries == 3
    assert hosted[0].area_km2["under_10cm"] == 4.0


def test_by_year_skips_invalid_dates(snap):
    assert [(r.year, r.images) for r in snap.by_year.hosted] == [(2019, 1), (2020, 2), (2021, 1)]
    assert [r.year for r in snap.by_year.federated] == [2023, 2024]


def test_licences(snap):
    assert [(r.licence, r.images) for r in snap.licences.hosted] == [("CC-BY-4.0", 3), ("CC-BY-SA-4.0", 1), ("various", 1)]


def test_collections(snap):
    maxar, noaa = snap.collections.federated
    assert (maxar.collection, maxar.images, maxar.entries) == ("maxar-opendata", 1, 3)
    assert maxar.earliest_capture == d(2023)
    assert noaa.area_km2["unknown"] == 4.0


def test_empty_catalog_still_reports_both_groups():
    snap = build_snapshot([], [], CLASSES, NOW)
    assert snap.totals.federated.images == 0
    assert snap.totals.federated.area_km2 == {c: 0.0 for c in (*CLASSES, "unknown")}
    assert snap.platforms.hosted == []
