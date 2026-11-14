-- Manual psql SQL rehearsal only; service/API and concurrency need the tests.
-- Requires seed_sprint2 on the disposable Task75 DB. All writes roll back.
\set ON_ERROR_STOP on
DO $$ BEGIN
    IF NOT starts_with(current_database(), 's2_task75_') THEN
        RAISE EXCEPTION 'Use only a disposable s2_task75_ database';
    END IF;
END $$;
SELECT p.id AS party_id FROM parties_party p
JOIN accounts_user u ON u.id = p.host_id
WHERE p.title = '[S2-DATA] Last slot' AND u.username = 's2data_h'
  AND p.description = 'Synthetic S2-DATA fixture; rerunning seed_sprint2 resets this party.'
\gset
\echo BEFORE_EXPECT_ACTIVE_2_SLOTS_1_HISTORY_3
\ir us4_leave_snapshot.sql
BEGIN;
SELECT id FROM parties_party WHERE id = :party_id FOR UPDATE;
DO $$
DECLARE target bigint; member bigint; changed integer;
BEGIN
    SELECT p.id INTO STRICT target FROM parties_party p
    JOIN accounts_user u ON u.id=p.host_id
    WHERE p.title='[S2-DATA] Last slot' AND u.username='s2data_h'
      AND p.description='Synthetic S2-DATA fixture; rerunning seed_sprint2 resets this party.';
    SELECT m.id INTO STRICT member FROM parties_partymembership m
    JOIN accounts_user u ON u.id=m.user_id
    WHERE m.party_id=target AND u.username='s2data_m' AND m.left_at IS NULL
    FOR UPDATE OF m;
    IF (SELECT count(*) FROM parties_partymembership WHERE party_id=target AND left_at IS NULL) <> 2
       OR (SELECT count(*) FROM parties_partymembership WHERE party_id=target) <> 3 THEN
        RAISE EXCEPTION 'Reset Sprint2 fixture: expected active2/history3';
    END IF;
    UPDATE parties_partymembership SET left_at=CURRENT_TIMESTAMP
    WHERE id=member AND left_at IS NULL;
    GET DIAGNOSTICS changed = ROW_COUNT;
    IF changed <> 1 THEN RAISE EXCEPTION 'First leave must change one row'; END IF;
    UPDATE parties_partymembership SET left_at=CURRENT_TIMESTAMP
    WHERE id=member AND left_at IS NULL;
    GET DIAGNOSTICS changed = ROW_COUNT;
    IF changed <> 0 THEN RAISE EXCEPTION 'Repeat leave must not change a row'; END IF;
    IF (SELECT count(*) FROM parties_partymembership WHERE party_id=target AND left_at IS NULL) <> 1
       OR (SELECT count(*) FROM parties_partymembership WHERE party_id=target) <> 3
       OR (SELECT capacity FROM parties_party WHERE id=target) <> 3 THEN
        RAISE EXCEPTION 'Expected active1/history3/capacity3';
    END IF;
    RAISE NOTICE 'PASS first UPDATE=1, repeat UPDATE=0, active=1, history=3, capacity=3';
END $$;
\echo AFTER_LEAVE_EXPECT_ACTIVE_1_SLOTS_2_HISTORY_3
\ir us4_leave_snapshot.sql
ROLLBACK;
\echo AFTER_ROLLBACK_EXPECT_ORIGINAL_ACTIVE_2_SLOTS_1_HISTORY_3
\ir us4_leave_snapshot.sql
