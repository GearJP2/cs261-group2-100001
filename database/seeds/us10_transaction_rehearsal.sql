-- Task49: SQL rehearsal, NOT proof that the Django service itself is atomic.
-- Reuse seed_sprint2 first. All writes are rolled back; never run against real data.
BEGIN;
DO $$
DECLARE
    party_key bigint;
    applicant_key bigint;
    request_key bigint;
    constraint_key text;
    request_status text;
    active_count integer;
BEGIN
    IF current_database() NOT LIKE 's2_task49_%' THEN
        RAISE EXCEPTION 'Only an isolated s2_task49_* test database is allowed';
    END IF;
    SELECT p.id INTO STRICT party_key
    FROM parties_party p JOIN accounts_user h ON h.id=p.host_id
    WHERE p.title='[S2-DATA] Open' AND h.username='s2data_h'
      AND p.description='Synthetic S2-DATA fixture; rerunning seed_sprint2 resets this party.'
    FOR UPDATE OF p;
    SELECT id INTO STRICT applicant_key FROM accounts_user WHERE username='s2data_a';
    SELECT id INTO STRICT request_key FROM parties_joinrequest
    WHERE party_id=party_key AND user_id=applicant_key AND status='Pending' FOR UPDATE;
    SELECT count(*) INTO active_count FROM parties_partymembership
    WHERE party_id=party_key AND left_at IS NULL;
    IF active_count<>2 OR EXISTS (SELECT 1 FROM parties_partymembership
                                  WHERE party_id=party_key AND user_id=applicant_key) THEN
        RAISE EXCEPTION 'Expected clean seed baseline: 2 active and applicant absent';
    END IF;
    RAISE NOTICE 'DB49-S01 baseline: Pending, applicant membership absent, active=2';

    BEGIN
        INSERT INTO parties_partymembership(party_id,user_id,joined_at,left_at)
        VALUES(party_key,applicant_key,now(),NULL);
        -- Real PostgreSQL constraint error AFTER the membership insert.
        UPDATE parties_joinrequest SET status='Approved',decided_at=NULL WHERE id=request_key;
        RAISE EXCEPTION 'Expected a check violation but the invalid decision was accepted';
    EXCEPTION WHEN check_violation THEN
        GET STACKED DIAGNOSTICS constraint_key = CONSTRAINT_NAME;
        IF constraint_key<>'join_request_valid_decision' THEN RAISE; END IF;
        RAISE NOTICE 'DB49-S02 actual SQLSTATE=23514 constraint=%',constraint_key;
    END;
    SELECT status INTO request_status FROM parties_joinrequest WHERE id=request_key;
    IF request_status<>'Pending' OR EXISTS (SELECT 1 FROM parties_partymembership
                                            WHERE party_id=party_key AND user_id=applicant_key) THEN
        RAISE EXCEPTION 'Rollback failed';
    END IF;
    RAISE NOTICE 'DB49-S03 after failure: Pending, applicant membership absent, active=2';

    INSERT INTO parties_partymembership(party_id,user_id,joined_at,left_at)
    VALUES(party_key,applicant_key,now(),NULL);
    UPDATE parties_joinrequest SET status='Approved',decided_at=now(),
           decided_by_id=(SELECT host_id FROM parties_party WHERE id=party_key)
    WHERE id=request_key;
    SELECT count(*) INTO active_count FROM parties_partymembership
    WHERE party_id=party_key AND left_at IS NULL;
    IF active_count<>3 THEN RAISE EXCEPTION 'Expected active=3 after approval'; END IF;
    RAISE NOTICE 'DB49-S04 successful pair inside transaction: Approved, active=3';
END $$;
ROLLBACK;

-- The outer rollback must leave the seeded state unchanged.
SELECT p.title,r.status,
       (SELECT count(*) FROM parties_partymembership m
        WHERE m.party_id=p.id AND m.left_at IS NULL) AS active_count,
       EXISTS(SELECT 1 FROM parties_partymembership m
              WHERE m.party_id=p.id AND m.user_id=r.user_id) AS applicant_membership
FROM parties_party p JOIN parties_joinrequest r ON r.party_id=p.id
JOIN accounts_user u ON u.id=r.user_id
WHERE p.title='[S2-DATA] Open' AND u.username='s2data_a'
  AND p.description='Synthetic S2-DATA fixture; rerunning seed_sprint2 resets this party.';
