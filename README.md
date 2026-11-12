# oam-eoapi-stats

Lightweight statistics service for the OpenAerialMap eoAPI catalog: scene counts, deduplicated coverage and an aggregated footprint, served as a small read-only API.

> [!WARNING]
> This project is in early development. The API is not stable yet.

The service queries pgSTAC (read-only) on a schedule, keeps the results in memory and serves them under `/stats`. Requests never hit the database. See [STATS.md](STATS.md) for what is counted and [IMPLEMENTATION.md](IMPLEMENTATION.md) for the design.

## Endpoints

Hosted and federated imagery are always reported separately. An *image* is a scene, an *entry* a raw catalog item, and area is in km² split by resolution class.

| Endpoint | Contents |
|---|---|
| `GET /stats` | Headline totals: images, entries, area, capture range, set-aside and duplicate counts |
| `GET /stats/platforms` | By platform |
| `GET /stats/by-year` | By year captured |
| `GET /stats/collections` | By collection |
| `GET /stats/licenses` | By licence |
| `GET /stats/healthz`, `GET /stats/readyz` | Liveness, and readiness once the first refresh is done |
| `GET /stats/docs` | OpenAPI docs |

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` | port `5432`, others required | pgSTAC connection |
| `CRON_SCHEDULE` | `0 2 * * *` | When to refresh |
| `QUERY_STATEMENT_TIMEOUT` | `10min` | Postgres statement timeout for the refresh queries |
| `HOSTED_COLLECTIONS` | `openaerialmap` | |
| `FEDERATED_COLLECTIONS` | `maxar-opendata,vantor-opendata,noaa-emergency-response` | |
| `EXCLUDED_COLLECTIONS` | `cop-dem-glo-30` | Collections in no group are skipped with a warning |
| `GSD_CLASS_BOUNDS` | `0.10,0.50` | Resolution class boundaries in metres |
| `MAX_GSD_M` | `hosted=5,federated=50` | Coarser items are set aside from area |
| `MAX_ITEM_AREA_KM2` | `hosted=10000,federated=50000` | Larger items are set aside from area |
| `DEFAULT_PLATFORM` | `maxar-opendata=satellite,vantor-opendata=satellite,noaa-emergency-response=aircraft` | Platform for items that don't record one |
| `CORS_ORIGINS` | `https://imagery.hotosm.org` | |

## Development

```bash
uv sync
uv run pytest
uv run pre-commit install
```

Run the integration tests against a throwaway pgstac database (they wipe its items and collections):

```bash
docker run -d --name pgstac -p 5439:5432 \
  -e POSTGRES_USER=username -e POSTGRES_PASSWORD=password -e POSTGRES_DB=postgis \
  ghcr.io/stac-utils/pgstac:v0.10.1
PGSTAC_TEST_DSN=postgresql://username:password@localhost:5439/postgis uv run pytest tests/integration
```

Run the service:

```bash
DB_HOST=localhost DB_PORT=5439 DB_USER=username DB_PASSWORD=password DB_NAME=postgis \
  uv run uvicorn oam_eoapi_stats.main:app --reload
```

or with Docker: `docker build -t oam-eoapi-stats . && docker run -p 8000:8000 -e DB_HOST=... oam-eoapi-stats`.

## License

[MIT](LICENSE)
