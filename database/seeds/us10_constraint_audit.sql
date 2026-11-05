-- Task49: read-only PostgreSQL catalog evidence, independent of Django model declarations.
SELECT c.conrelid::regclass AS table_name, c.conname, c.contype,
       c.convalidated, pg_get_constraintdef(c.oid) AS definition
FROM pg_constraint c
WHERE c.conrelid IN ('parties_party'::regclass,
                    'parties_joinrequest'::regclass,
                    'parties_partymembership'::regclass)
ORDER BY c.conrelid::regclass::text, c.conname;

SELECT tablename, indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename IN ('parties_party', 'parties_joinrequest', 'parties_partymembership')
ORDER BY tablename, indexname;
