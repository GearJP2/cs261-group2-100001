-- Task78 independent, read-only oracle. Parameters: now, sport, venue, type,
-- starts_from, starts_to, state, q. Use a disposable/test database.
WITH args AS (
    SELECT %s::timestamptz AS at, %s::bigint AS sport_id, %s::bigint AS venue_id,
           %s::text AS venue_type, %s::timestamptz AS starts_from,
           %s::timestamptz AS starts_to, %s::text AS state, %s::text AS q
), counted AS (
    SELECT p.*, v.venue_type,
           (SELECT count(*) FROM parties_partymembership m
            WHERE m.party_id = p.id AND m.left_at IS NULL) AS active_count
    FROM parties_party p JOIN venues_venue v ON v.id = p.venue_id
), classified AS (
    SELECT p.*,
           CASE WHEN p.cancelled_at IS NOT NULL THEN 'Cancelled'
                WHEN p.ends_at <= a.at THEN 'Completed'
                WHEN p.starts_at <= a.at THEN 'InProgress'
                WHEN p.active_count >= p.capacity THEN 'Full'
                ELSE 'Open' END AS actual_state
    FROM counted p CROSS JOIN args a
)
SELECT p.id, p.actual_state, p.active_count
FROM classified p CROSS JOIN args a
WHERE (a.sport_id IS NULL OR p.sport_id = a.sport_id)
  AND (a.venue_id IS NULL OR p.venue_id = a.venue_id)
  AND (a.venue_type IS NULL OR p.venue_type = a.venue_type)
  AND (a.starts_from IS NULL OR p.starts_at >= a.starts_from)
  AND (a.starts_to IS NULL OR p.starts_at < a.starts_to)
  AND (a.state = 'all' OR p.actual_state = a.state)
  AND (a.q IS NULL OR strpos(upper(p.title), upper(a.q)) > 0)
ORDER BY p.starts_at, p.id;
