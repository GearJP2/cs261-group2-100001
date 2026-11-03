-- Task60: independent read-only oracle for the S2 fixture's actual active rows.
-- No inferred Host membership and no join to requests (Pending never grants membership).
SELECT p.id AS party_id, p.title, m.id AS membership_id, u.id AS user_id,
       COALESCE(profile.display_name,
                CASE WHEN u.id = p.host_id THEN 'ผู้จัดกิจกรรม' ELSE 'ผู้ใช้' END) AS display_name,
       CASE WHEN u.id = p.host_id THEN 'Host' ELSE 'Member' END AS role,
       m.joined_at,
       COUNT(*) OVER (PARTITION BY p.id) AS active_member_count
FROM parties_party p
JOIN accounts_user h ON h.id = p.host_id
JOIN parties_partymembership m ON m.party_id = p.id AND m.left_at IS NULL
JOIN accounts_user u ON u.id = m.user_id
LEFT JOIN accounts_userprofile profile ON profile.user_id = u.id
WHERE p.description = 'Synthetic S2-DATA fixture; rerunning seed_sprint2 resets this party.'
  AND h.username = 's2data_h'
ORDER BY p.title, m.joined_at, m.id;
