-- Task84 read-only business snapshot. Bind one aware reference timestamp.
-- Does not use the API's ORM query/helper to compute state or active count.
WITH facts AS (
    SELECT p.*, v.venue_type,
           (SELECT count(*) FROM parties_partymembership m
            WHERE m.party_id=p.id AND m.left_at IS NULL) AS active_count,
           (SELECT jsonb_agg(jsonb_build_object('id',m.id,'user_id',m.user_id,
                       'joined_at',m.joined_at,'left_at',m.left_at) ORDER BY m.id)
            FROM parties_partymembership m WHERE m.party_id=p.id) AS memberships,
           (SELECT jsonb_agg(jsonb_build_object('id',r.id,'user_id',r.user_id,
                       'status',r.status,'decided_at',r.decided_at) ORDER BY r.id)
            FROM parties_joinrequest r WHERE r.party_id=p.id) AS requests
    FROM parties_party p JOIN venues_venue v ON v.id=p.venue_id
), clock AS (SELECT %s::timestamptz AS at)
SELECT f.id, f.title, f.sport_id, f.venue_id, f.venue_type,
       f.starts_at, f.ends_at, f.capacity, f.cancelled_at, f.updated_at,
       f.active_count, f.memberships, f.requests,
       CASE WHEN f.cancelled_at IS NOT NULL THEN 'Cancelled'
            WHEN f.ends_at <= c.at THEN 'Completed'
            WHEN f.starts_at <= c.at THEN 'InProgress'
            WHEN f.active_count >= f.capacity THEN 'Full'
            ELSE 'Open' END AS state
FROM facts f CROSS JOIN clock c ORDER BY f.starts_at, f.id;
