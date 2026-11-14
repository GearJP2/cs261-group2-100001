-- Read-only: psql -v party_id=123 -f database/seeds/us4_leave_snapshot.sql
-- Count independently of history/requests to avoid join multiplication.
SELECT p.id AS party_id, p.capacity, p.cancelled_at,
       (SELECT count(*) FROM parties_partymembership a
        WHERE a.party_id = p.id AND a.left_at IS NULL) AS active_count,
       p.capacity - (SELECT count(*) FROM parties_partymembership a
                     WHERE a.party_id = p.id AND a.left_at IS NULL) AS remaining_slots,
       m.id AS membership_id, m.user_id, m.joined_at, m.left_at
FROM parties_party p
LEFT JOIN parties_partymembership m ON m.party_id = p.id
WHERE p.id = :party_id
ORDER BY m.id;
