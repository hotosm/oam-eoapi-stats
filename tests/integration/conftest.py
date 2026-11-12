"""Load a small catalog into a pgstac database. Runs only when PGSTAC_TEST_DSN is set.

The database is wiped (pgstac items and collections) before loading, so never point this at a real catalog.
"""

import json
import os

import psycopg
import pytest

from oam_eoapi_stats.config import Settings, load_settings

DSN = os.environ.get("PGSTAC_TEST_DSN")


def collection(cid: str, license: str) -> dict:
    return {
        "type": "Collection",
        "stac_version": "1.0.0",
        "id": cid,
        "description": cid,
        "license": license,
        "extent": {"spatial": {"bbox": [[-180, -90, 180, 90]]}, "temporal": {"interval": [[None, None]]}},
        "links": [],
    }


def box(x: float, y: float, size: float) -> dict:
    ring = [[x, y], [x + size, y], [x + size, y + size], [x, y + size], [x, y]]
    return {"type": "Polygon", "coordinates": [ring]}


def item(iid: str, cid: str, dt: str, geometry: dict | None = None, **props) -> dict:
    geometry = geometry or box(0, 0, 0.01)
    coords = geometry["coordinates"][0]
    xs, ys = [c[0] for c in coords], [c[1] for c in coords]
    return {
        "type": "Feature",
        "stac_version": "1.0.0",
        "id": iid,
        "collection": cid,
        "geometry": geometry,
        "bbox": [min(xs), min(ys), max(xs), max(ys)],
        "properties": {"datetime": dt, **props},
        "links": [],
        "assets": {},
    }


COLLECTIONS = [
    collection("openaerialmap", "various"),
    collection("maxar-opendata", "CC-BY-NC-4.0"),
    collection("vantor-opendata", "CC-BY-NC-4.0"),
    collection("noaa-emergency-response", "CC0-1.0"),
    collection("cop-dem-glo-30", "proprietary"),
]

KM2 = 1_000_000

ITEMS = [
    # Hosted
    item(
        "oam-drone",
        "openaerialmap",
        "2020-03-01T00:00:00Z",
        gsd=0.05,
        license="CC-BY-4.0",
        **{"oam:platform_type": "UAV", "oam:footprint_area": 1 * KM2},
    ),
    # No licence of its own: falls back to the collection's.
    item(
        "oam-aircraft",
        "openaerialmap",
        "2021-06-01T00:00:00Z",
        gsd=0.2,
        **{"oam:platform_type": "aircraft", "oam:footprint_area": 2 * KM2},
    ),
    # Exact duplicates: two entries and two images, but the area counts once.
    *[
        item(
            f"oam-dup-{n}",
            "openaerialmap",
            "2022-01-01T00:00:00Z",
            box(10, 10, 0.02),
            gsd=0.03,
            title="same survey",
            license="CC-BY-4.0",
            **{"oam:platform_type": "uav", "oam:footprint_area": 3 * KM2},
        )
        for n in (1, 2)
    ],
    # Continent-sized with an absurd GSD: counted as an image, set aside from area.
    item(
        "oam-continent",
        "openaerialmap",
        "2019-01-01T00:00:00Z",
        box(-60, -30, 50),
        gsd=400_000,
        license="CC-BY-4.0",
        **{"oam:platform_type": "satellite"},
    ),
    # Year 0026: invalid date, left out of the year breakdown and the capture range.
    item(
        "oam-year-0026",
        "openaerialmap",
        "0026-05-01T00:00:00Z",
        gsd=0.05,
        license="CC-BY-SA-4.0",
        **{"oam:platform_type": "uav", "oam:footprint_area": 1 * KM2},
    ),
    # Federated: three Maxar tiles of one capture are one image.
    *[
        item(
            f"maxar-tile-{n}",
            "maxar-opendata",
            "2023-08-01T00:00:00Z",
            box(n, 20, 0.05),
            gsd=0.3,
            catalog_id="cat-1",
            **{"oam:footprint_area": 10 * KM2},
        )
        for n in (1, 2, 3)
    ],
    # 0.5 m sits on the upper bound, so it lands in the coarsest class.
    item("vantor-1", "vantor-opendata", "2024-02-01T00:00:00Z", gsd=0.5, **{"oam:footprint_area": 5 * KM2}),
    # NOAA: no gsd and no platform.
    item("noaa-1", "noaa-emergency-response", "2024-09-01T00:00:00Z", **{"oam:footprint_area": 4 * KM2}),
    # Excluded collection.
    item("dem-1", "cop-dem-glo-30", "2021-01-01T00:00:00Z", gsd=30),
]


@pytest.fixture(scope="session")
def pgstac_settings() -> Settings:
    if not DSN:
        pytest.skip("PGSTAC_TEST_DSN not set")
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("DELETE FROM pgstac.items")
        conn.execute("DELETE FROM pgstac.collections")
        for c in COLLECTIONS:
            conn.execute("SELECT pgstac.create_collection(%s::jsonb)", [json.dumps(c)])
        conn.execute("SELECT pgstac.create_items(%s::jsonb)", [json.dumps(ITEMS)])
    db = psycopg.conninfo.conninfo_to_dict(DSN)
    return load_settings(
        {
            "DB_HOST": db.get("host", "localhost"),
            "DB_PORT": str(db.get("port", "5432")),
            "DB_USER": db["user"],
            "DB_PASSWORD": db.get("password", ""),
            "DB_NAME": db["dbname"],
        }
    )
