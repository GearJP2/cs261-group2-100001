-- Run only on the disposable test DB immediately after seed_sprint2.
-- SQL data rehearsal, NOT proof that approve/leave APIs or concurrent writers work.
\set ON_ERROR_STOP on
\echo BEFORE
\ir sprint2_snapshot.sql
BEGIN;
DO $$
DECLARE
    target parties_party%ROWTYPE;
    applicant bigint;
    active_before integer;
BEGIN
    SELECT p.* INTO STRICT target FROM parties_party p
    JOIN accounts_user h ON h.id = p.host_id
    WHERE p.title = '[S2-DATA] Last slot' AND h.username = 's2data_h'
      AND p.description = 'Synthetic S2-DATA fixture; rerunning seed_sprint2 resets this party.'
    FOR UPDATE OF p;
    SELECT id INTO STRICT applicant FROM accounts_user WHERE username = 's2data_a';
    SELECT COUNT(*) INTO active_before FROM parties_partymembership
    WHERE party_id = target.id AND left_at IS NULL;
    IF active_before <> 2 OR target.capacity <> 3 THEN
        RAISE EXCEPTION 'Reset S2 fixtures first: Last slot must have 2/3 active members';
    END IF;
    UPDATE parties_joinrequest SET status = 'Approved', decided_at = CURRENT_TIMESTAMP,
        decided_by_id = target.host_id
    WHERE party_id = target.id AND user_id = applicant AND status = 'Pending';
    IF NOT FOUND THEN RAISE EXCEPTION 'Expected pending s2data_a request'; END IF;
    INSERT INTO parties_partymembership (party_id, user_id, joined_at, left_at)
    VALUES (target.id, applicant, CURRENT_TIMESTAMP, NULL);
    IF (SELECT COUNT(*) FROM parties_partymembership
        WHERE party_id = target.id AND left_at IS NULL) <> 3 THEN
        RAISE EXCEPTION 'Expected 3 active memberships after rehearsal';
    END IF;
END $$;
\echo DURING_TRANSACTION_EXPECT_LAST_SLOT_ACTIVE_3_REMAINING_0_PENDING_1
\ir sprint2_snapshot.sql
ROLLBACK;
\echo AFTER_ROLLBACK_EXPECT_ORIGINAL_2_ACTIVE_1_REMAINING_2_PENDING
\ir sprint2_snapshot.sql
