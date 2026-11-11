import logging
import threading
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from oam_eoapi_stats import __version__, scheduler
from oam_eoapi_stats.cache import cache
from oam_eoapi_stats.config import settings
from oam_eoapi_stats.models import Breakdown, CollectionRow, LicenceRow, PlatformRow, Snapshot, Totals, YearRow

logging.basicConfig(level=logging.INFO)

CACHE_CONTROL = "public, max-age=3600"
UNCACHED_PATHS = {"/stats/healthz", "/stats/readyz"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # The first refresh can take minutes, so it runs in the background; readyz reports 503 until it completes.
    threading.Thread(target=cache.refresh, daemon=True).start()
    scheduler.start()
    yield
    scheduler.stop()


# Everything, docs included, lives under /stats, so the service can share the OAM API hostname.
app = FastAPI(
    title="oam-eoapi-stats",
    version=__version__,
    lifespan=lifespan,
    docs_url="/stats/docs",
    redoc_url="/stats/redoc",
    openapi_url="/stats/openapi.json",
)
app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_methods=["GET"])


@app.middleware("http")
async def cache_control(request: Request, call_next):
    response = await call_next(request)
    if response.status_code == 200 and request.url.path not in UNCACHED_PATHS:
        response.headers["Cache-Control"] = CACHE_CONTROL
    return response


def require_snapshot() -> Snapshot:
    snapshot = cache.snapshot()
    if snapshot is None:
        raise HTTPException(status_code=503, detail="stats not yet available, initial refresh still in progress")
    return snapshot


CachedSnapshot = Annotated[Snapshot, Depends(require_snapshot)]


@app.get("/stats/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/stats/readyz")
def readyz(response: Response):
    if not cache.ready:
        response.status_code = 503
        return {"status": "not ready"}
    return {"status": "ready"}


@app.get("/stats", response_model=Totals)
def totals(snapshot: CachedSnapshot):
    """Headline totals (STATS.md #1), hosted and federated reported separately."""
    return snapshot.totals


@app.get("/stats/platforms", response_model=Breakdown[PlatformRow])
def platforms(snapshot: CachedSnapshot):
    """Images and area by platform (#3)."""
    return snapshot.platforms


@app.get("/stats/by-year", response_model=Breakdown[YearRow])
def by_year(snapshot: CachedSnapshot):
    """Images and area by year captured (#4). Invalid capture dates are counted in /stats instead."""
    return snapshot.by_year


@app.get("/stats/collections", response_model=Breakdown[CollectionRow])
def collections(snapshot: CachedSnapshot):
    """Images, entries, area and capture range per collection (#6)."""
    return snapshot.collections


@app.get("/stats/licenses", response_model=Breakdown[LicenceRow])
def licenses(snapshot: CachedSnapshot):
    """Images and area by licence (#7)."""
    return snapshot.licences
