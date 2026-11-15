-- Read-only reconciliation. Does not repair caches or change conduct credit.
-- Aggregate reviews BEFORE joining profiles: membership/ledger joins multiply rows.
WITH actual AS (
    SELECT reviewee_id AS user_id, count(*) AS actual_count,
           sum(rating) AS actual_sum, avg(rating::numeric) AS actual_average
    FROM conduct_partyreview GROUP BY reviewee_id
)
SELECT coalesce(p.user_id, a.user_id) AS user_id,
       p.user_id IS NOT NULL AS profile_exists,
       p.rating_sum AS cached_sum, p.rating_count AS cached_count,
       coalesce(a.actual_sum, 0) AS actual_sum,
       coalesce(a.actual_count, 0) AS actual_count,
       a.actual_average,
       p.user_id IS NOT NULL
           AND p.rating_sum = coalesce(a.actual_sum, 0)
           AND p.rating_count = coalesce(a.actual_count, 0) AS cache_matches,
       p.credit_score
FROM accounts_userprofile p FULL OUTER JOIN actual a ON a.user_id = p.user_id
ORDER BY user_id;
