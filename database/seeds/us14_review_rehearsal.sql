-- Disposable Task87 DB only. Manual SQL rehearsal, not service/API proof.
\set ON_ERROR_STOP on
DO $$ BEGIN
    IF NOT starts_with(current_database(), 's2_task87_') THEN
        RAISE EXCEPTION 'Use only a disposable s2_task87_ database';
    END IF;
END $$;
\echo BASELINE_EXPECT_ZERO_RATINGS_AND_NULL_AVERAGE
\ir us14_review_cache_audit.sql
BEGIN;
DO $$
DECLARE p bigint; h bigint; m bigint; duplicate_constraint text;
BEGIN
    SELECT id INTO STRICT h FROM accounts_user WHERE username='s2data_h';
    SELECT id INTO STRICT m FROM accounts_user WHERE username='s2data_m';
    SELECT id INTO STRICT p FROM parties_party
    WHERE title='[S2-DATA] Completed' AND host_id=h
      AND description='Synthetic S2-DATA fixture; rerunning seed_sprint2 resets this party.'
    FOR UPDATE;
    IF EXISTS (SELECT 1 FROM conduct_partyreview WHERE reviewee_id=m)
       OR NOT EXISTS (SELECT 1 FROM accounts_userprofile
                      WHERE user_id=m AND rating_count=0 AND rating_sum=0) THEN
        RAISE EXCEPTION 'Expected a fresh Task87 review fixture';
    END IF;
    INSERT INTO conduct_partyreview(party_id,reviewer_id,reviewee_id,rating,comment,created_at)
    VALUES(p,h,m,5,'Synthetic Task87 SQL rehearsal',CURRENT_TIMESTAMP);
    UPDATE accounts_userprofile SET rating_sum=rating_sum+5,rating_count=rating_count+1
    WHERE user_id=m;
    BEGIN
        INSERT INTO conduct_partyreview(party_id,reviewer_id,reviewee_id,rating,comment,created_at)
        VALUES(p,h,m,4,'Synthetic duplicate',CURRENT_TIMESTAMP);
        RAISE EXCEPTION 'Duplicate unexpectedly accepted';
    EXCEPTION WHEN unique_violation THEN
        GET STACKED DIAGNOSTICS duplicate_constraint=CONSTRAINT_NAME;
        IF duplicate_constraint <> 'unique_party_review' THEN RAISE; END IF;
        RAISE NOTICE 'PASS duplicate SQLSTATE23505 constraint=%',duplicate_constraint;
    END;
END $$;
\echo AFTER_VALID_INSERT_EXPECT_ACTUAL_5_1_AND_CACHE_MATCHES_TRUE
\ir us14_review_cache_audit.sql
-- Deliberately corrupt only synthetic cache to verify the detector, not auto-repair.
UPDATE accounts_userprofile SET rating_sum=rating_sum+1
WHERE user_id=(SELECT id FROM accounts_user WHERE username='s2data_m');
\echo INJECTED_DRIFT_EXPECT_CACHED_6_ACTUAL_5_MATCHES_FALSE
\ir us14_review_cache_audit.sql
ROLLBACK;
\echo AFTER_ROLLBACK_EXPECT_ORIGINAL_ZERO_CACHE_MATCHES_TRUE
\ir us14_review_cache_audit.sql
