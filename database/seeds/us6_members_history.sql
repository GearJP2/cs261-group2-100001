-- Task66 read-only evidence. Compare these retained rows with us6_active_members.sql.
-- Restricted to the synthetic Sprint 2 fixture, never a list of real users.
SELECT p.id AS party_id, p.title, m.id AS membership_id, m.user_id,
       m.joined_at, m.left_at, r.status AS request_status
FROM parties_party p
JOIN accounts_user h ON h.id = p.host_id
JOIN parties_partymembership m ON m.party_id = p.id
LEFT JOIN parties_joinrequest r ON r.party_id = p.id AND r.user_id = m.user_id
WHERE p.description = 'Synthetic S2-DATA fixture; rerunning seed_sprint2 resets this party.'
  AND h.username = 's2data_h'
ORDER BY p.title, m.joined_at, m.id;
