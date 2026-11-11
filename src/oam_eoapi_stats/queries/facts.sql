-- One row per catalog item in an included collection, with every derived field the figures need.
-- Shared by base_facts.sql and scenes.sql, so both always count the same items the same way.
-- Spatial functions are limited to ones DuckDB spatial also has, to keep the stac-geoparquet option open.
items AS (
    SELECT i.id,
           i.collection,
           i.datetime,  -- the pgstac column, not properties.datetime (missing on most hosted items)
           i.geometry,
           i.content -> 'properties' AS p,
           c.content ->> 'license' AS collection_license,
           CASE WHEN i.collection = ANY(%(hosted)s) THEN 'hosted' ELSE 'federated' END AS grp
    FROM pgstac.items i
    JOIN pgstac.collections c ON c.id = i.collection
    WHERE i.collection = ANY(%(hosted)s) OR i.collection = ANY(%(federated)s)
),
typed AS (
    SELECT *,
           CASE WHEN jsonb_typeof(p -> 'gsd') = 'number' THEN (p ->> 'gsd')::float8 END AS gsd,
           coalesce(
               CASE WHEN jsonb_typeof(p -> 'oam:footprint_area') = 'number' THEN (p ->> 'oam:footprint_area')::float8 END,
               ST_Area(geometry::geography)
           ) AS area_m2,
           coalesce(datetime >= '1990-01-01' AND datetime < now() + interval '1 day', false) AS valid_date
    FROM items
),
f AS (
    SELECT collection,
           grp,
           coalesce(p ->> 'catalog_id', id) AS scene,
           coalesce(lower(p ->> 'oam:platform_type'), %(default_platform)s::jsonb ->> collection, 'unknown') AS platform,
           -- 0 below the first bound, n at or above the n-th bound, NULL when gsd is missing
           width_bucket(gsd, %(gsd_bounds)s::float8[]) AS gsd_bucket,
           coalesce(p ->> 'license', collection_license, 'unspecified') AS licence,
           CASE WHEN valid_date THEN extract(year FROM datetime)::int END AS year_captured,
           NOT valid_date AS invalid_date,
           CASE WHEN valid_date THEN datetime END AS captured,
           area_m2,
           coalesce(gsd > CASE grp WHEN 'hosted' THEN %(max_gsd_hosted)s ELSE %(max_gsd_federated)s END, false)
               OR coalesce(
                   area_m2 > 1e6 * CASE grp WHEN 'hosted' THEN %(max_area_km2_hosted)s ELSE %(max_area_km2_federated)s END,
                   false
               ) AS set_aside,
           row_number() OVER (
               PARTITION BY collection,
                            md5(encode(ST_AsBinary(ST_SnapToGrid(geometry, 1e-6)), 'hex')
                                || coalesce(datetime::text, '') || coalesce(p ->> 'title', ''))
               ORDER BY id
           ) > 1 AS duplicate
    FROM typed
)
