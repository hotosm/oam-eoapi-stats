-- Summable facts per combination of dimensions; rolled up in aggregate.py.
-- Area leaves out set-aside items and the extra copies of exact duplicates.
WITH /* facts */
SELECT collection,
       grp,
       platform,
       gsd_bucket,
       licence,
       year_captured,
       invalid_date,
       set_aside,
       count(*) AS items,
       count(*) FILTER (WHERE duplicate) AS duplicates,
       coalesce(sum(area_m2) FILTER (WHERE NOT set_aside AND NOT duplicate), 0) AS area_m2,
       coalesce(sum(area_m2) FILTER (WHERE set_aside AND NOT duplicate), 0) AS set_aside_area_m2,
       min(captured) AS earliest,
       max(captured) AS latest
FROM f
GROUP BY collection, grp, platform, gsd_bucket, licence, year_captured, invalid_date, set_aside
