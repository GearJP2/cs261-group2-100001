-- Read-only PostgreSQL catalog audit, including actual validated FK/CHECK/UNIQUE.
SELECT conrelid::regclass AS table_name, conname, contype, convalidated,
       pg_get_constraintdef(oid) AS definition
FROM pg_constraint
WHERE conrelid = 'conduct_partyreview'::regclass
   OR (conrelid = 'accounts_userprofile'::regclass AND conname LIKE '%rating%')
ORDER BY table_name, conname;
SELECT tablename, indexname, indexdef FROM pg_indexes
WHERE schemaname = current_schema() AND tablename = 'conduct_partyreview'
ORDER BY indexname;
