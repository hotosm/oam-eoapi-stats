-- Distinct scenes (images) per group and per dimension. Distinct counts can't be summed
-- across base_facts rows, so each breakdown gets its own count. `key` is the dimension value as text.
WITH /* facts */
SELECT 'group' AS dim, grp, NULL::text AS key, count(DISTINCT scene) AS scenes FROM f GROUP BY grp
UNION ALL
SELECT 'gsd_class', grp, gsd_bucket::text, count(DISTINCT scene) FROM f GROUP BY grp, gsd_bucket
UNION ALL
SELECT 'platform', grp, platform, count(DISTINCT scene) FROM f GROUP BY grp, platform
UNION ALL
SELECT 'year', grp, year_captured::text, count(DISTINCT scene) FROM f GROUP BY grp, year_captured
UNION ALL
SELECT 'licence', grp, licence, count(DISTINCT scene) FROM f GROUP BY grp, licence
UNION ALL
SELECT 'collection', grp, collection, count(DISTINCT scene) FROM f GROUP BY grp, collection
