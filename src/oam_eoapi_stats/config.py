"""Settings read from environment variables and validated at import time."""

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from itertools import pairwise

from apscheduler.triggers.cron import CronTrigger

GROUPS = ("hosted", "federated")
STATEMENT_TIMEOUT_RE = re.compile(r"^\d+(ms|s|min|h|d)?$")


@dataclass(frozen=True)
class Settings:
    db_host: str
    db_port: str
    db_user: str
    db_password: str
    db_name: str
    cron_schedule: str
    query_statement_timeout: str
    hosted_collections: tuple[str, ...]
    federated_collections: tuple[str, ...]
    excluded_collections: tuple[str, ...]
    gsd_class_bounds: tuple[float, ...]
    max_gsd_m: dict[str, float]
    max_item_area_km2: dict[str, float]
    default_platform: dict[str, str]
    cors_origins: tuple[str, ...]

    @property
    def gsd_classes(self) -> tuple[str, ...]:
        """Class labels, in the order of the buckets: below the first bound, between bounds, from the last bound up."""
        cm = [_cm(bound) for bound in self.gsd_class_bounds]
        between = [f"{low}_{high}cm" for low, high in pairwise(cm)]
        return (f"under_{cm[0]}cm", *between, f"over_{cm[-1]}cm")

    @property
    def connect_kwargs(self) -> dict[str, str]:
        # Keyword arguments rather than a conninfo string, so passwords with spaces or quotes need no escaping.
        return {
            "host": self.db_host,
            "port": self.db_port,
            "user": self.db_user,
            "password": self.db_password,
            "dbname": self.db_name,
        }


def _cm(metres: float) -> str:
    return f"{metres * 100:g}"


def _list(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _pairs(name: str, value: str) -> dict[str, str]:
    pairs = {}
    for part in _list(value):
        key, sep, val = part.partition("=")
        if not sep or not key.strip() or not val.strip():
            raise ValueError(f"Invalid {name}: expected key=value pairs, got {part!r}")
        pairs[key.strip()] = val.strip()
    return pairs


def _group_floats(name: str, value: str) -> dict[str, float]:
    pairs = _pairs(name, value)
    if set(pairs) != set(GROUPS):
        raise ValueError(f"Invalid {name}: needs exactly the groups {', '.join(GROUPS)}, got {', '.join(pairs)}")
    try:
        parsed = {group: float(pairs[group]) for group in GROUPS}
    except ValueError as exc:
        raise ValueError(f"Invalid {name}: {exc}") from None
    if any(v <= 0 for v in parsed.values()):
        raise ValueError(f"Invalid {name}: values must be positive")
    return parsed


def load_settings(env: Mapping[str, str]) -> Settings:
    timeout = env.get("QUERY_STATEMENT_TIMEOUT", "10min")
    if not STATEMENT_TIMEOUT_RE.match(timeout):
        raise ValueError(f"Invalid QUERY_STATEMENT_TIMEOUT: {timeout!r}")

    cron = env.get("CRON_SCHEDULE", "0 2 * * *")
    try:
        CronTrigger.from_crontab(cron)
    except ValueError as exc:
        raise ValueError(f"Invalid CRON_SCHEDULE {cron!r}: {exc}") from None

    hosted = _list(env.get("HOSTED_COLLECTIONS", "openaerialmap"))
    federated = _list(env.get("FEDERATED_COLLECTIONS", "maxar-opendata,vantor-opendata,noaa-emergency-response"))
    excluded = _list(env.get("EXCLUDED_COLLECTIONS", "cop-dem-glo-30"))
    if not hosted:
        raise ValueError("HOSTED_COLLECTIONS must not be empty")
    seen: dict[str, str] = {}
    for name, collections in (("HOSTED", hosted), ("FEDERATED", federated), ("EXCLUDED", excluded)):
        for collection in collections:
            if collection in seen:
                raise ValueError(f"Collection {collection!r} is in both {seen[collection]} and {name}")
            seen[collection] = name

    try:
        bounds = tuple(float(b) for b in _list(env.get("GSD_CLASS_BOUNDS", "0.10,0.50")))
    except ValueError as exc:
        raise ValueError(f"Invalid GSD_CLASS_BOUNDS: {exc}") from None
    if not bounds or bounds[0] <= 0 or list(bounds) != sorted(set(bounds)):
        raise ValueError("GSD_CLASS_BOUNDS must be positive, strictly increasing metres")

    return Settings(
        db_host=env["DB_HOST"],
        db_port=env.get("DB_PORT", "5432"),
        db_user=env["DB_USER"],
        db_password=env["DB_PASSWORD"],
        db_name=env["DB_NAME"],
        cron_schedule=cron,
        query_statement_timeout=timeout,
        hosted_collections=hosted,
        federated_collections=federated,
        excluded_collections=excluded,
        gsd_class_bounds=bounds,
        max_gsd_m=_group_floats("MAX_GSD_M", env.get("MAX_GSD_M", "hosted=5,federated=50")),
        max_item_area_km2=_group_floats("MAX_ITEM_AREA_KM2", env.get("MAX_ITEM_AREA_KM2", "hosted=10000,federated=50000")),
        default_platform=_pairs(
            "DEFAULT_PLATFORM",
            env.get(
                "DEFAULT_PLATFORM",
                "maxar-opendata=satellite,vantor-opendata=satellite,noaa-emergency-response=aircraft",
            ),
        ),
        cors_origins=_list(env.get("CORS_ORIGINS", "https://imagery.hotosm.org")),
    )


settings = load_settings(os.environ)
