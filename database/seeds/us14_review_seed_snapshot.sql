-- Read-only manual snapshot of the synthetic Task95 seed reviewee.
\set ON_ERROR_STOP on
DO $$ BEGIN
    IF NOT starts_with(current_database(), 's2_task95_') THEN
        RAISE EXCEPTION 'Use only a disposable s2_task95_ database';
    END IF;
END $$;
SELECT id AS reviewee_id FROM accounts_user WHERE username='s2data_m'
\gset
\ir us14_review_test_snapshot.sql
