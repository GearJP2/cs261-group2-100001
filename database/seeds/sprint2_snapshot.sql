-- Read-only snapshot, restricted to owned synthetic S2 parties. No fixed primary keys.
SELECT p.id, p.title, s.name AS sport, v.name AS venue,
       p.starts_at AT TIME ZONE 'Asia/Bangkok' AS starts_bangkok,
       p.ends_at AT TIME ZONE 'Asia/Bangkok' AS ends_bangkok,
       p.cancelled_at, p.capacity,
       COUNT(DISTINCT m.id) FILTER (WHERE m.left_at IS NULL) AS active_members,
       COUNT(DISTINCT m.id) FILTER (WHERE m.left_at IS NOT NULL) AS left_members,
       p.capacity - COUNT(DISTINCT m.id) FILTER (WHERE m.left_at IS NULL) AS remaining,
       COUNT(DISTINCT r.id) FILTER (WHERE r.status = 'Pending') AS pending,
       COUNT(DISTINCT r.id) FILTER (WHERE r.status = 'Approved') AS approved,
       COUNT(DISTINCT r.id) FILTER (WHERE r.status = 'Rejected') AS rejected
FROM parties_party p
JOIN accounts_user h ON h.id = p.host_id
JOIN venues_sport s ON s.id = p.sport_id
JOIN venues_venue v ON v.id = p.venue_id
LEFT JOIN parties_partymembership m ON m.party_id = p.id
LEFT JOIN parties_joinrequest r ON r.party_id = p.id
WHERE p.description = 'Synthetic S2-DATA fixture; rerunning seed_sprint2 resets this party.'
  AND h.username = 's2data_h'
GROUP BY p.id, s.name, v.name
ORDER BY p.title;
