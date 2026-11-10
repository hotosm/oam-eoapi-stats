import pytest

from oam_eoapi_stats.config import load_settings

DB = {"DB_HOST": "db", "DB_USER": "u", "DB_PASSWORD": "p", "DB_NAME": "n"}


def test_defaults():
    s = load_settings(DB)
    assert s.hosted_collections == ("openaerialmap",)
    assert s.federated_collections == ("maxar-opendata", "vantor-opendata", "noaa-emergency-response")
    assert s.excluded_collections == ("cop-dem-glo-30",)
    assert s.gsd_class_bounds == (0.10, 0.50)
    assert s.gsd_classes == ("under_10cm", "10_50cm", "over_50cm")
    assert s.max_gsd_m == {"hosted": 5.0, "federated": 50.0}
    assert s.max_item_area_km2 == {"hosted": 10000.0, "federated": 50000.0}
    assert s.default_platform["noaa-emergency-response"] == "aircraft"
    assert s.cors_origins == ("https://imagery.hotosm.org",)


def test_custom_bounds_labels():
    s = load_settings({**DB, "GSD_CLASS_BOUNDS": "0.05, 0.3, 1.5"})
    assert s.gsd_classes == ("under_5cm", "5_30cm", "30_150cm", "over_150cm")


@pytest.mark.parametrize(
    "env",
    [
        {"QUERY_STATEMENT_TIMEOUT": "10 minutes; DROP TABLE x"},
        {"CRON_SCHEDULE": "every day"},
        {"FEDERATED_COLLECTIONS": "openaerialmap"},
        {"EXCLUDED_COLLECTIONS": "maxar-opendata"},
        {"HOSTED_COLLECTIONS": ""},
        {"GSD_CLASS_BOUNDS": "0.5,0.1"},
        {"GSD_CLASS_BOUNDS": "0,0.5"},
        {"GSD_CLASS_BOUNDS": "a,b"},
        {"MAX_GSD_M": "hosted=5"},
        {"MAX_GSD_M": "hosted=5,federated=x"},
        {"MAX_ITEM_AREA_KM2": "hosted=-1,federated=1"},
        {"DEFAULT_PLATFORM": "noaa"},
    ],
)
def test_rejects_invalid(env):
    with pytest.raises(ValueError):
        load_settings({**DB, **env})


def test_requires_db():
    with pytest.raises(KeyError):
        load_settings({})
