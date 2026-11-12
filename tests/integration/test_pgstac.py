"""End-to-end refresh against a real pgstac database loaded with the fixtures in conftest.py."""

import logging
from dataclasses import replace

import pytest

from oam_eoapi_stats.refresh import load_snapshot


@pytest.fixture(scope="module")
def snapshot(pgstac_settings):
    return load_snapshot(pgstac_settings)


def by(rows, attr):
    return {getattr(row, attr): row for row in rows}


def test_hosted_totals(snapshot):
    hosted = snapshot.totals.hosted
    assert hosted.images == 6
    assert hosted.entries == 6
    # drone 1 + duplicates 3 (counted once) + year-0026 item 1; aircraft 2; continent set aside
    assert hosted.area_km2 == {"under_10cm": 5.0, "10_50cm": 2.0, "over_50cm": 0.0, "unknown": 0.0}
    assert hosted.duplicates == 1
    assert hosted.invalid_dates == 1
    assert hosted.set_aside.items == 1
    assert hosted.set_aside.area_km2 > 10_000_000
    assert hosted.earliest_capture.year == 2019
    assert hosted.latest_capture.year == 2022


def test_federated_totals(snapshot):
    federated = snapshot.totals.federated
    assert federated.images == 3  # three Maxar tiles share a catalog_id
    assert federated.entries == 5  # the DEM collection is excluded
    assert federated.area_km2 == {"under_10cm": 0.0, "10_50cm": 30.0, "over_50cm": 5.0, "unknown": 4.0}


def test_platform_defaults_and_case(snapshot):
    hosted = by(snapshot.platforms.hosted, "platform")
    assert hosted["uav"].images == 4  # "UAV" and "uav" merge
    federated = by(snapshot.platforms.federated, "platform")
    assert federated["aircraft"].images == 1  # NOAA default
    assert federated["satellite"].images == 2


def test_by_year_skips_invalid_dates(snapshot):
    assert [r.year for r in snapshot.by_year.hosted] == [2019, 2020, 2021, 2022]
    assert by(snapshot.by_year.hosted, "year")[2022].images == 2


def test_licence_falls_back_to_collection(snapshot):
    hosted = by(snapshot.licences.hosted, "licence")
    assert set(hosted) == {"CC-BY-4.0", "CC-BY-SA-4.0", "various"}
    assert hosted["various"].images == 1
    assert by(snapshot.licences.federated, "licence")["CC0-1.0"].images == 1


def test_collections(snapshot):
    federated = by(snapshot.collections.federated, "collection")
    assert set(federated) == {"maxar-opendata", "vantor-opendata", "noaa-emergency-response"}
    assert (federated["maxar-opendata"].images, federated["maxar-opendata"].entries) == (1, 3)
    assert [c.collection for c in snapshot.collections.hosted] == ["openaerialmap"]


def test_warns_about_ungrouped_collections(pgstac_settings, caplog):
    with caplog.at_level(logging.WARNING):
        load_snapshot(replace(pgstac_settings, excluded_collections=()))
    assert "cop-dem-glo-30" in caplog.text
