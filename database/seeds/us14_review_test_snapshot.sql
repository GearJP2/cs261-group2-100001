-- Read-only per-reviewee evidence; review rows and summary share one snapshot.
-- psql -v reviewee_id=123 -f database/seeds/us14_review_test_snapshot.sql
WITH target AS (SELECT :reviewee_id::bigint AS user_id), actual AS (
    SELECT count(*) AS actual_count, coalesce(sum(rating), 0) AS actual_sum,
           avg(rating::numeric) AS actual_average
    FROM conduct_partyreview WHERE reviewee_id = (SELECT user_id FROM target)
)
SELECT t.user_id AS reviewee_id, p.rating_sum, p.rating_count, p.credit_score,
       a.actual_count, a.actual_sum, a.actual_average,
       (SELECT count(*) FROM conduct_conductcreditevent e WHERE e.user_id=t.user_id) AS credit_events,
       r.id AS review_id, r.party_id, r.reviewer_id, r.rating, r.created_at
FROM target t CROSS JOIN actual a
LEFT JOIN accounts_userprofile p ON p.user_id=t.user_id
LEFT JOIN conduct_partyreview r ON r.reviewee_id=t.user_id
ORDER BY r.id;
