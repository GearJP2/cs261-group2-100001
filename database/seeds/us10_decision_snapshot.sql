-- Task57 read-only evidence. psql: \set party_id <fixture id>
-- Django supplies a bound parameter instead of the psql variable below.
SELECT p.id AS party_id, p.capacity,
       (SELECT count(*) FROM parties_partymembership active
        WHERE active.party_id=p.id AND active.left_at IS NULL) AS active_count,
       r.id AS request_id, r.user_id, r.status, r.decided_at, r.decided_by_id,
       m.id AS membership_id, m.joined_at, m.left_at
FROM parties_party p
LEFT JOIN parties_joinrequest r ON r.party_id=p.id
LEFT JOIN parties_partymembership m ON m.party_id=p.id AND m.user_id=r.user_id
WHERE p.id = :party_id
ORDER BY r.id;
