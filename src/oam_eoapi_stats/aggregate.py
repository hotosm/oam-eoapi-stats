"""Roll the rows of base_facts.sql and scenes.sql up into the published figures. No database access."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from oam_eoapi_stats.config import GROUPS
from oam_eoapi_stats.models import (
    Breakdown,
    CollectionRow,
    GroupTotals,
    LicenceRow,
    PlatformRow,
    SetAside,
    Snapshot,
    Totals,
    YearRow,
)

Row = dict[str, Any]
UNKNOWN_CLASS = "unknown"


def gsd_class(bucket: int | None, classes: tuple[str, ...]) -> str:
    """Label for a width_bucket() index: 0 is below the first bound, len(classes)-1 at or above the last."""
    return UNKNOWN_CLASS if bucket is None else classes[bucket]


def _km2(m2: float) -> float:
    return round(m2 / 1e6, 2)


def _earliest(a: datetime | None, b: datetime | None) -> datetime | None:
    return b if a is None else a if b is None else min(a, b)


def _latest(a: datetime | None, b: datetime | None) -> datetime | None:
    return b if a is None else a if b is None else max(a, b)


@dataclass
class _Acc:
    area_m2: dict[str, float]
    entries: int = 0
    earliest: datetime | None = None
    latest: datetime | None = None
    invalid_dates: int = 0
    duplicates: int = 0
    set_aside_items: int = 0
    set_aside_area_m2: float = 0.0

    def add(self, row: Row, classes: tuple[str, ...]) -> None:
        self.entries += row["items"]
        self.area_m2[gsd_class(row["gsd_bucket"], classes)] += row["area_m2"]
        self.earliest = _earliest(self.earliest, row["earliest"])
        self.latest = _latest(self.latest, row["latest"])
        self.duplicates += row["duplicates"]
        self.set_aside_area_m2 += row["set_aside_area_m2"]
        if row["invalid_date"]:
            self.invalid_dates += row["items"]
        if row["set_aside"]:
            self.set_aside_items += row["items"]

    def area_km2(self) -> dict[str, float]:
        return {cls: _km2(m2) for cls, m2 in self.area_m2.items()}


@dataclass
class _Rollup:
    """Facts summed per (group, dimension value), plus the matching distinct scene counts."""

    classes: tuple[str, ...]
    scenes: dict[tuple[str, str, str | None], int]
    by_group: dict[str, dict[Any, _Acc]] = field(default_factory=lambda: {g: {} for g in GROUPS})

    def fill(self, facts: Iterable[Row], key: Callable[[Row], Any]) -> "_Rollup":
        for row in facts:
            acc = self.by_group[row["grp"]].get(key(row))
            if acc is None:
                acc = _Acc(area_m2={cls: 0.0 for cls in (*self.classes, UNKNOWN_CLASS)})
                self.by_group[row["grp"]][key(row)] = acc
            acc.add(row, self.classes)
        return self

    def images(self, dim: str, grp: str, value: Any) -> int:
        return self.scenes.get((dim, grp, None if value is None else str(value)), 0)


def _index_scenes(scene_rows: Iterable[Row]) -> dict[tuple[str, str, str | None], int]:
    return {(r["dim"], r["grp"], r["key"]): r["scenes"] for r in scene_rows}


def build_snapshot(facts: list[Row], scene_rows: list[Row], classes: tuple[str, ...], generated_at: datetime) -> Snapshot:
    scenes = _index_scenes(scene_rows)

    def rollup(key: Callable[[Row], Any]) -> _Rollup:
        return _Rollup(classes, scenes).fill(facts, key)

    totals_r = rollup(lambda r: None)
    empty = _Acc(area_m2={cls: 0.0 for cls in (*classes, UNKNOWN_CLASS)})

    def group_totals(grp: str) -> GroupTotals:
        acc = totals_r.by_group[grp].get(None, empty)
        return GroupTotals(
            images=totals_r.images("group", grp, None),
            entries=acc.entries,
            area_km2=acc.area_km2(),
            earliest_capture=acc.earliest,
            latest_capture=acc.latest,
            invalid_dates=acc.invalid_dates,
            duplicates=acc.duplicates,
            set_aside=SetAside(items=acc.set_aside_items, area_km2=_km2(acc.set_aside_area_m2)),
        )

    def breakdown(dim: str, key: Callable[[Row], Any], make_row: Callable[[Any, int, _Acc], Any], sort_key) -> Breakdown:
        r = rollup(key)
        out = {}
        for grp in GROUPS:
            rows = [make_row(value, r.images(dim, grp, value), acc) for value, acc in r.by_group[grp].items()]
            out[grp] = sorted((row for row in rows if row is not None), key=sort_key)
        return Breakdown(generated_at=generated_at, **out)

    def by_images(name: str):
        return lambda row: (-row.images, getattr(row, name))

    return Snapshot(
        generated_at=generated_at,
        totals=Totals(generated_at=generated_at, **{grp: group_totals(grp) for grp in GROUPS}),
        platforms=breakdown(
            "platform",
            lambda r: r["platform"],
            lambda v, n, a: PlatformRow(platform=v, images=n, entries=a.entries, area_km2=a.area_km2()),
            by_images("platform"),
        ),
        by_year=breakdown(
            "year",
            lambda r: r["year_captured"],
            # Invalid dates have no year; they are reported in the totals instead.
            lambda v, n, a: None if v is None else YearRow(year=v, images=n, entries=a.entries, area_km2=a.area_km2()),
            lambda row: row.year,
        ),
        licences=breakdown(
            "licence",
            lambda r: r["licence"],
            lambda v, n, a: LicenceRow(licence=v, images=n, entries=a.entries, area_km2=a.area_km2()),
            by_images("licence"),
        ),
        collections=breakdown(
            "collection",
            lambda r: r["collection"],
            lambda v, n, a: CollectionRow(
                collection=v,
                images=n,
                entries=a.entries,
                area_km2=a.area_km2(),
                earliest_capture=a.earliest,
                latest_capture=a.latest,
            ),
            lambda row: row.collection,
        ),
    )
