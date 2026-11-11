"""SQL lives in .sql files next to this module, so Python only ever sees fixed-schema rows."""

import json
from importlib.resources import files

from oam_eoapi_stats.config import Settings

_FACTS_MARKER = "/* facts */"


def _read(name: str) -> str:
    return (files(__package__) / name).read_text()


def _with_facts(name: str) -> str:
    sql = _read(name)
    if _FACTS_MARKER not in sql:
        raise ValueError(f"{name} does not include {_FACTS_MARKER}")
    return sql.replace(_FACTS_MARKER, _read("facts.sql"))


BASE_FACTS = _with_facts("base_facts.sql")
SCENES = _with_facts("scenes.sql")


def params(settings: Settings) -> dict:
    return {
        "hosted": list(settings.hosted_collections),
        "federated": list(settings.federated_collections),
        "default_platform": json.dumps(settings.default_platform),
        "gsd_bounds": list(settings.gsd_class_bounds),
        "max_gsd_hosted": settings.max_gsd_m["hosted"],
        "max_gsd_federated": settings.max_gsd_m["federated"],
        "max_area_km2_hosted": settings.max_item_area_km2["hosted"],
        "max_area_km2_federated": settings.max_item_area_km2["federated"],
    }
