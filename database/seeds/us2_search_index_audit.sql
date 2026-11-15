-- Read-only inventory; FK indexes are already created by Django.
SELECT tablename, indexname, indexdef
FROM pg_indexes
WHERE schemaname = current_schema()
  AND tablename IN ('parties_party', 'parties_partymembership',
                   'parties_joinrequest', 'venues_venue', 'venues_venuesport')
ORDER BY tablename, indexname;
