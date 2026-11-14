# Task75 — ตรวจ SQL / Transaction / Race ของการถอนสมาชิก

วันที่: 14 พฤศจิกายน 2026 (Asia/Bangkok) · Owner: Gold (`gold555555`)

- [Issue #90](https://github.com/GearJP2/cs261-group2-100001/issues/90) · S2-US4-T-DB · US4 AC1,3
- Branch `test/s2-us4-db-race-evidence`; base `f8eb427f9ad546d380afc805929af00cb85e0e19`
- Dependency: Task69 [PR139](https://github.com/GearJP2/cs261-group2-100001/pull/139) และ Task70 [PR158](https://github.com/GearJP2/cs261-group2-100001/pull/158) merge แล้ว
- อ้าง [policy](us4-leave-party-policy.md), [API contract](us4-leave-party-api-contract.md), [Test Design](us4-leave-party-test-cases.md)

## Scope และการแบ่งประเภทหลักฐาน

ตรวจฐานข้อมูลจริงหลังเรียก leave API: `left_at`, membership history, active/slots, retry, request ไม่เปลี่ยน, rollback และ concurrent writers. เพิ่ม tests ต่อจาก Task69/70 โดยไม่แก้ production service/API/schema/dependency

1. **Automated API/SQL integration:** Django test client เปิด CSRF checks, session fixtures ที่ verified ในฐานทดสอบ, เรียก view/guard/service/ORM/PostgreSQLจริง ไม่ใช่ mockทั้งระบบ. ไม่มี external network HTTP หรือ TU API และไม่ใช่ human UAT
2. **Automated PostgreSQL race:** workerคนละconnection, coordinatorถือPartylock, barrierเริ่มworkerพร้อมกัน และใช้ `pg_blocking_pids` ยืนยันว่ารอlockจริงก่อนปล่อย. APIworkerจับPIDจากconnectionที่กำลัง `FOR UPDATE` ภายในrequestจริง เพราะ Djangoอาจ reconnect ตอนเริ่มrequest. Testsไม่เก็บ cookie/session/CSRF token ในหลักฐาน
3. **Manual SQL rehearsal:** ผู้ช่วยรัน `psql` บนDBเฉพาะงาน สังเกต SQLก่อน/หลัง/หลังROLLBACK และมี assertionsในSQL. แยกจากการพิสูจน์ service/API atomicity และไม่ใช้แทนrace

## Environment และ Precondition

ผู้ช่วยรันตามคำขอโกล ใช้ข้อมูล MOCK เท่านั้น. Compose `s2-task75`, DB `s2_task75_leave`, testDB `test_s2_task75_leave`, hostDBport15475, APP_PORT18075 (ไม่ได้เปิดwebserver)

Python3.12.15 / Django5.2.18 / PostgreSQL17.11; Python/Djangoในsetup.log และPostgreSQLในruntime.log. [Source manifest](evidence/task75/source-manifest.json) เก็บbasecommitและSHA256ของไฟล์ที่รัน

Automated fixture: cap2, Host+M active2 (Full), M มี Approved requestเดิม, Aไม่มีmembership. Partyเริ่มอีก2วัน10:00 มีเวลาเปิดสนาม09:00–18:00สำหรับตรวจcapacityedit. Testแต่ละตัวสร้างข้อมูลแยกและล้างหลังจบ

Manual fixture `seed_sprint2`: Last slot **cap3/active2/history3** (Host, M และสมาชิกเก่าที่มีleft_at). ต่างจากautomatedcap2โดยตั้งใจ ห้ามเทียบจำนวนจากคนละfixtureเป็นbefore/afterเดียวกัน

## ขั้นตอนตรวจและ Expected–Actual

| Case / trace | ขั้นตอน | Expected | Actual / หลักฐาน |
| --- | --- | --- | --- |
| DB75-01 / IT-US4-DB-01 | SQLก่อน → POST leave `{}` เป็น M → SQLหลัง → POSTซ้ำ → SQLอีกครั้ง | HTTP200ทั้งคู่/left_atเดียว; active2→1 slots0→1; ID/user/joined_at/capacity/request/Hostเดิม | PASS; `test_api_leave_retry_sql_history_and_count` เก็บresponses+SQLในJSONL |
| DB75-02 / IT-US4-DB-02 | worker2คน POST leaveของMเดียวกัน รอPartylockจริงแล้วปล่อย | HTTP200+200/left_atเดียว; active1/history2 ไม่เพิ่มแถว | PASS; `test_two_api_leaves_return_same_timestamp_and_free_one_slot` มีPID2ตัวและblockerchain |
| DB75-03 / IT-US4-DB-03 | M POSTleave แข่งHost POSTapproveA จากFull | leave200; ถ้าapproveก่อนleave409PARTY_FULL/Pending/no membership; ถ้าleaveก่อนapprove200/Approved/memberactive. activeไม่เกิน2 | PASS; raceยอมรับผลที่ถูกต้องตามลำดับlockจริง ดูผลรอบนี้ในJSONL |
| DB75-04 / Design DB03 | รันเคสเดิม Task69 บังคับapproveก่อนleave และleaveก่อนapprove โดยworkerรอlockจริง | ทดสอบทั้ง2ลำดับ ไม่พึ่งว่าraceสุ่มได้winnerไหน | PASS; `LeaveLockTests.test_approve_before_waiting_leave_sees_full_party` และ `test_approve_waits_for_leave_then_reads_freed_slot` |
| DB75-05 / Design DB01 | SQLก่อน → APIleave → saveจริงแล้วinjectDatabaseError → SQLหลัง | HTTP500 ไม่ส่งsuccess; atomicrollback; left_atNULL/active2/request/historyเท่าก่อน | PASS; `test_api_write_failure_returns_500_and_rolls_back_sql`; errorจำลองหลังUPDATEจริง ไม่ใช่DBconstraintสร้างเอง |
| DB75-06 / Design DB04 | workerleaveรอ; coordinatorcancelก่อนcommit | leavePARTY_CANCELLED; Mยังactive/historyเดิม | PASS; `test_cancel_before_waiting_leave_preserves_membership` |
| DB75-07 / Design DB04 | workercancelรอ; coordinatorleaveก่อนcommit | leaveคงอยู่และcancelled_atถูกบันทึก ไม่ย้อนผลถอน | PASS; `test_leave_before_waiting_cancel_keeps_leave_history` |
| DB75-08 / Design DB05 | workereditcap1รอ; coordinatorleaveก่อนcommit | editอ่านactiveใหม่=1 จึงcap1ได้; ไม่มีlostupdate | PASS; `test_leave_before_waiting_edit_allows_capacity_one` |
| DB75-09 / Design DB05 | workerleaveรอ; coordinatoreditcap1ก่อน | editCAPACITY_TOO_SMALL ขณะactive2; leaveภายหลังactive1/capยัง2 | PASS; `test_edit_before_waiting_leave_cannot_shrink_below_active` |
| DB75-10 / Design DB06 | รันTask69เดิม: workerleaveรอ; coordinatorเปลี่ยนstarts_atเป็นอดีตก่อนปล่อยlock | leaveอ่านเวลาใหม่ PARTY_STARTED ไม่ถอน | PASS; `test_leave_rechecks_time_after_lock`; เปลี่ยนPartytimeแทนการsleepรอขอบเวลา |
| DB75-11 / Design DB07 | รันTask69เดิม: leave→US3ขอใหม่→US10approve→leaveรอบใหม่ | ก่อนapproveไม่active; reuse request/membership; รอบใหม่ต้องตรวจใหม่ | PASS; `test_rejoin_requires_approval_then_allows_new_leave_cycle` |
| DB75-12 / Design DB08 | Mถอนสำเร็จ → HostapproveA → Mrefresh detail/members | detail is_member=false/count2/slots0/Full แม้เพิ่งถอน; members403 | PASS; `test_detail_refresh_after_replacement_approval_uses_current_count` มีdetailและSQLในJSONL |
| DB75-SQL01 / query | migrate+seed → psqlอ่านsnapshot → BEGIN/Partylock/memberlock → UPDATEleft_at → snapshot | cap3/active2/history3 → active1/slots2/history3; updateแรก1แถว/ซ้ำ0แถว | PASS; `manual-sql.log` มีNOTICEและตารางจริง |
| DB75-SQL02 / isolation | SQLrehearsalROLLBACK แล้วอ่านอีกครั้ง | cap3/active2/slots1/history3 คืนbaseline | PASS; ท้าย `manual-sql.log` |
| DB75-G01 / guard | รันrehearsalบนDBชื่อ `postgres` ในprojectทดสอบ | ปฏิเสธก่อนwrite/exit3 | PASS; `sql-guard.log` |

Targetedรันซ้ำ testsเดิมทั้งหมดใน `parties.test_leave` และ `parties.test_leave_api` ด้วย จึงครอบคลุมhost/nonmember/Pending/Rejected, cancelled/start/end, JSON/body/method/auth/CSRF, read-detail/membersสิทธิ์หลังถอน. Testชื่อเต็ม/ผลอยู่rawlog ไม่อ้างเคสที่ไม่ได้รันเป็นPASS

Targeted **29 tests ผ่าน ไม่มี skipped** (6.235s): 9ใหม่ + 13เดิมTask69 + 7เดิมTask70. JSONLมี9observationsจากtestใหม่; เคสเดิมTask69มี `DB69_EVIDENCE` ในrawlogด้วย. ไม่จำเป็นต้องมีจำนวนobservationเท่าจำนวนtests เพราะแต่ละtestมีหลายassertions/subcases

Full verification **589 discovered = 588 ผ่าน + 1 skipped** (46.630s). Skippedคือ US14 `test_no_show_and_credit_formula_blocked_until_policy_is_confirmed` รอกติกา #100/#105 ไม่ใช่Task75. Django check, migration dry-run, Ruff check/formatผ่านทั้งหมด. ไม่รันmake smokeเพราะไม่เปลี่ยนruntime/routeหรือหน้าเว็บ

ตัวอย่างค่าจริงรอบtargeted: สองleaveใช้PID908และ907, blockerchain907→908→906(observer). ทั้งคู่HTTP200และleft_atเดียวกัน. ส่วนleaveแข่งapproveรอบนี้approveได้409PARTY_FULL/Pending แล้วleaveสำเร็จ; ลำดับleaveก่อนapproveพิสูจน์แบบบังคับแยกในtestsเดิมTask69 จึงไม่ได้อ้างว่าการraceสุ่มรอบเดียวพิสูจน์ทั้ง2winner

## วิธีรันซ้ำ

ต้องมีDockerและ `.env` สำหรับlocalพร้อมใช้ ไม่แนบค่าลับลงlog. PowerShellจากrepo:

```powershell
$env:POSTGRES_DB='s2_task75_leave'
$env:POSTGRES_HOST_PORT='15475'
$env:APP_PORT='18075'
docker compose -p s2-task75 up -d --wait database
docker compose -p s2-task75 run --rm -T -e POSTGRES_DB=s2_task75_leave backend python backend/manage.py test parties.test_leave_database parties.test_leave parties.test_leave_api --noinput --verbosity 2
docker compose -p s2-task75 run --rm -T -e POSTGRES_DB=s2_task75_leave backend sh -c 'python backend/manage.py migrate --noinput && python backend/manage.py seed_sprint2 --confirm-test-data'
docker cp database/seeds/us4_leave_rehearsal.sql s2-task75-database-1:/tmp/us4_leave_rehearsal.sql
docker cp database/seeds/us4_leave_snapshot.sql s2-task75-database-1:/tmp/us4_leave_snapshot.sql
docker compose -p s2-task75 exec -T database sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /tmp/us4_leave_rehearsal.sql'
# Negative guard: expected exit3, do not treat this expected error as a suite failure.
docker compose -p s2-task75 exec -T database sh -c 'psql -U "$POSTGRES_USER" -d postgres -f /tmp/us4_leave_rehearsal.sql'
docker compose -p s2-task75 run --rm -T -e POSTGRES_DB=s2_task75_leave backend sh -c 'python backend/manage.py check && python backend/manage.py makemigrations --check --dry-run && ruff check backend scripts && ruff format --check backend scripts && python backend/manage.py test backend --top-level-directory backend --noinput --verbosity 1'
docker compose -p s2-task75 down
```

SQLsnapshotเลือกPartyด้วยboundparameterในtest; psqlใช้เลขIDจากseedที่ตรวจmarker/Hostแล้ว. Rehearsalguardจำกัดชื่อDB `s2_task75_...`, ตรวจfixtureก่อนwrite และROLLBACKทุกwrite ไม่มีการแก้ข้อมูลผู้ใช้หรือvolumeเดิม

## หลักฐาน / ข้อจำกัด / bug-retest

- [Test sourceใหม่](../backend/parties/test_leave_database.py) / [SQL rehearsal](../database/seeds/us4_leave_rehearsal.sql)
- [Targeted log](evidence/task75/targeted-tests.log) / [JSONL SQL+response+PID](evidence/task75/observations.jsonl)
- [Setup](evidence/task75/setup.log) / [Manual psql](evidence/task75/manual-sql.log) / [Guard rejection](evidence/task75/sql-guard.log)
- [Full verification](evidence/task75/verification.log)

ไม่พบproductionbugจากเคสที่รัน จึงไม่มีproductionfix/retestของbugใหม่. ไม่อ้างUI/UAT/loadtest/productionbenchmark หรือunitmockจากผลintegration. Rollbackerrorในtestเป็นfaultinjection มีactualUPDATEจริงก่อนexception. PeerreviewยังรอGearJP2 ไม่ติ๊กอนุมัติแทนผู้ตรวจ; Doneหมายถึงส่งมอบรอreview/merge ยังไม่ใช่Complete
