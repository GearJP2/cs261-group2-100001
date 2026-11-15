# Task57 — SQL / race / rollback ของ US10

[Issue #72](https://github.com/GearJP2/cs261-group2-100001/issues/72) · [Trello](https://trello.com/c/XbrzAl2L) · US10 AC1,2,3,5

ผู้รับผิดชอบ Gold (`gold555555`) · ขอ GearJP2 review · วันที่ตรวจ **13 พฤศจิกายน 2026** (Asia/Bangkok)
Branch `test/s2-us10-db-race-evidence` จาก main `6d0309770056ea0c9b8474354e39487a8c172578`.
Task49 / PR #134 เข้า main แล้ว; งานนี้ไม่รวม branch งานอื่นและไม่เปลี่ยน production API/schema

## 1. ขอบเขตและสิ่งส่งมอบ

ใช้ tests ของทีมต่อ โดยเพิ่มหลักฐานการรอ lock จริง, SQL ก่อน–หลัง,
request payload/response และ error จากฐานข้อมูล พร้อม test ใหม่ที่ยืนยัน Reject ไม่กินที่นั่ง
ไม่ได้สร้าง concurrency harness อีกชุดหรือใช้ SQL snapshot อย่างเดียวแทนการแข่งจริง

- **IT-US10-DB-01:** สอง approve แย่งที่นั่งสุดท้าย สมาชิกไม่เกิน capacity
- **IT-US10-DB-02:** approve ซ้ำ / approve แข่ง reject, คำขอกับสมาชิกต้องสอดคล้อง ไม่ซ้ำ; reject ไม่กินที่นั่ง
- **IT-US10-DB-03:** membership write failure และ decision constraint failure ต้อง rollback ทั้งคู่

## 2. Environment / ข้อมูลตั้งต้น / ชนิดการทดสอบ

ผู้ช่วยรันจริงตามคำขอ Gold ไม่อ้างว่าเป็นการกด UAT ของ Gold/ผู้ใช้
Python3.12.15 / Django5.2.18 / PostgreSQL17.11; ดู [runtime](evidence/task57/runtime.log)
และ [source manifest](evidence/task57/source-manifest.json) สำหรับเวลา/commit/hash ของไฟล์ที่ตรวจ

Compose project `s2-task57` มี network/volume แยก, DB `s2_task57_race`,
Django สร้างและลบ `test_s2_task57_race` เอง; host PG port15457.
ไม่ได้แก้ `.env` หรือหยุดบริการเดิม ไม่ใช้ข้อมูลจริง/รหัสผ่านมหาวิทยาลัย

**Automated race fixture:** capacity2 มี Host active1 คน + ผู้ขอ A/B Pending2คำขอ
เริ่มในอนาคต มี VenueSport/เวลาเปิดสนามที่รองรับ. แต่ละ test reset แยกกัน
session/identity เป็น local test fixtures จาก `force_university_login` ไม่เรียก TU API

**Manual SQL baseline:** ใช้ Task46 `seed_sprint2`; Last slot capacity3 มี H/M active2,
A/B Pending และ left Approved history. ต่างจาก automated fixtureแต่เหลือ1ที่นั่งเหมือนกัน
IDs/PIDs เปลี่ยนได้ทุกเครื่อง จึงไม่ hardcode ค่าใน assertions

Automated API requests ผ่าน **Django test client** + CSRF checks + PostgreSQL connections จริง
ไม่ใช่ external network HTTP และไม่ใช่ Unit Test แบบ mock ทั้งระบบ
มี fault injection เฉพาะจุดตามตาราง; SQL baseline คือผู้ช่วยสั่ง `psql` อ่านฐานจริงแยกต่างหาก

## 3. พิสูจน์ว่ามีการแข่ง/รอ lock จริงอย่างไร

1. Coordinator ถือ `SELECT ... FOR UPDATE` ของ Party ใน transaction ก่อน
2. Workers2ตัวมี clients/connections ของตัวเอง; ใช้ Barrier ให้ออกจากจุดรอพร้อมกัน
3. `execute_wrapper` จับ PID ตรง SQL Party `FOR UPDATE` จริงภายใน request
   (request lifecycle อาจ reconnect จึงไม่ใช้ PID ที่อ่านก่อนเข้า request)
4. Observer ตรวจ `pg_blocking_pids(worker_pid)` ทั้งสองตัว และยืนยันว่าคนละ PID
5. PostgreSQL อาจให้ workerที่2รอ workerที่1ในคิว แล้ว workerที่1รอ coordinator;
   หลักฐานจึงเก็บทั้ง direct blocker และ queue chain โดยต้องมีเส้นทางไป coordinator
6. หลังยืนยันทั้งคู่ blocked จึงปล่อย Party lock ให้ service ตัดสินจริง
7. รอ responses ทั้งคู่ แล้วรัน SQL snapshot อิสระจาก helper ของ service
   ตรวจ count<=capacity, request status, membership, decided_by/time และผลผู้แพ้

มี timeout สำหรับ Barrier/PID/lock/future เพื่อให้ test fail แทนค้างไม่จบ
worker ปิด connections ใน finally. วิธีนี้เป็น controlled contention ไม่ใช่ production throughput/load benchmark

## 4. Test cases: ขั้นตอน / Expected–Actual / หลักฐาน

ผล targeted รอบส่งมอบ: **9 tests ผ่านทั้งหมด** (2.474s), ไม่มี skipped.
มี7 JSON observations เพราะ rollback testเดียวมี2subcases และ observer regressions3testsใช้ assertion/logของtestrunner

| Case / Checklist | ขั้นตอน | Expected | Actual รอบ targeted / หลักฐาน |
|---|---|---|---|
| DB57-01 / IT-01 | Fixtureเหลือ1ที่นั่ง → 2workers POST approve คนละคำขอ → รอlockจริง → SQLก่อน/หลัง | หนึ่ง200, อีก409 PARTY_FULL; active1→2<=capacity2; ผู้แพ้Pending/ไม่มีmembership | **PASS**; winner request14=Approved, request15=Pending; PIDs1024/1025, chain1025→1024→observer1023 |
| DB57-02 / IT-02 | 2workers approve requestเดียวกัน → SQL | 200+409 REQUEST_DECIDED; membershipเพิ่มแถวเดียว ไม่ซ้ำ | **PASS**; Approved, active2; rawresponses/IDsในJSON |
| DB57-03 / IT-02 | approveแข่งreject requestเดียวกัน → SQL | ผู้ชนะหนึ่งคน/ผู้แพ้409 REQUEST_DECIDED; สมาชิกมีเฉพาะผลApproved | **PASS**; รอบtargetedนี้ **Rejectedชนะ**, activeยัง1 และไม่มีapplicantmembership; อีกฝ่าย409 |
| DB57-04 / IT-02 | POST Reject → SQL → POST Approve คำขอเดิม | Reject200, countไม่เพิ่ม/ไม่มีmembership; Approve409; decisionเดิมไม่เปลี่ยน | **PASS**; responses200/409, Rejected, active1คงเดิม |
| DB57-05 / IT-03 | inject DatabaseError ก่อน membership insert → เรียกservice → SQL/snapshotเทียบ | request Pending/decision fields NULL, ไม่มีmembershipเพิ่ม, ทุกdomainfieldเหมือนก่อน | **PASS**; SQLbefore=after. Errorนี้จำลองด้วยpatch ไม่ใช่PostgreSQLสร้างเอง |
| DB57-06 / IT-03 | ปล่อยmembershipwriteจริง → inject decided_atNULL → saveจริงให้DBปฏิเสธ; ทำทั้งnew/reactivate | SQLSTATE23514/check violation; rollback Request+membershipรวมleft_at/ประวัติ | **PASSทั้ง2subcases**; constraint `join_request_valid_decision`, SQLbefore=after; rowใหม่หาย/rowเดิมยังleft_atเดิม |
| DB57-07 / observer regression | approvalรอPartylock → coordinator cancelแล้วcommit → ปล่อยworker | 409 PARTY_CANCELLED; requests/membershipsไม่เปลี่ยน | **PASS** |
| DB57-08 / observer regression | approvalรอlock → ลดcapacityเป็น1แล้วcommit | workerอ่านstateใหม่ ได้409 PARTY_FULL; ไม่เพิ่มสมาชิก | **PASS** |
| DB57-09 / observer regression | ควบคุมclockที่เวลาเริ่มตรงขอบ; workerรอPartylock | ไม่อ่านclockก่อนlock; หลังlockได้409 PARTY_STARTED | **PASS**; เฉพาะclockจำลอง ฐานข้อมูล/locksเป็นของจริง |
| DB57-SQL01 / manual baseline | migrate+seed → psqlรัน snapshotของ Last slot | cap3/active2, A/B Pendingไม่มีmembership; left historyไม่นับactive | **PASS**; [psql output](evidence/task57/manual-baseline-sql.log), ไม่ใช่หลักฐานconcurrentในตัวมันเอง |

DB57-01..03 อ่านผลจาก tests เดิมที่เพิ่ม observer/SQL evidence;
DB57-04 เป็น test ใหม่; DB57-05..06 เพิ่ม SQL evidence ใน rollback tests เดิม
Racerผู้ชนะอาจสลับได้ในรอบอื่น เงื่อนไขผ่านตรวจ invariants ไม่บังคับคนใดชนะ
Full regression อาจได้winnerต่างจาก targeted จึงห้ามปะปน IDs จากคนละรอบ

Full verification รอบสุดท้าย: **560 discovered =559ผ่าน +1skipped** (39.223s).
ตัวที่skipคือ US14 `test_no_show_and_credit_formula_blocked_until_policy_is_confirmed`
ซึ่งยังรอpolicy #100/#105 ไม่ใช่Task57; ไม่เรียกว่า560ผ่าน.
Django check/migrations drift/Rufflint+formatผ่าน; Task57 targetedทั้ง9ไม่มีskipped

## 5. หลักฐานที่อาจารย์ตรวจได้

- [Targeted raw log](evidence/task57/targeted-tests.log): ชื่อ9tests/ผล และบรรทัด `DB57_EVIDENCE`
- [JSON observations](evidence/task57/observations.json): คัด JSON จาก rawlogโดยไม่เปลี่ยนค่า
  มี SQLbefore/after, เวลา, worker/blockerPIDs, payloadและresponse; ไม่มี auth headers/cookies/tokens
- [SQL source](../database/seeds/us10_decision_snapshot.sql): queryเดียวกันที่testsรันกับฐานจริง
- [Full verification](evidence/task57/verification.log): Django/migrations/Ruff/fulltests
- [Manual SQL baseline](evidence/task57/manual-baseline-sql.log), [fixture setup](evidence/task57/setup.log)
- [Runtime](evidence/task57/runtime.log), [source manifest](evidence/task57/source-manifest.json)
- Test source: `parties/test_approval_concurrency.py`, `parties/test_approval.py`,
  helperอ่านSQLใน `parties/test_join_requests.py` (pathsอยู่ใต้backend)

## 6. วิธีทำซ้ำ (PowerShell ที่ repository root)

เปิด Docker, เตรียม `.env` และ image ของทีมตาม README. ใช้ project/DBแยกนี้;
backendต้องมี `-e POSTGRES_DB=...` เพราะ env_file อาจยังระบุชื่อฐานเดิม

```powershell
$env:POSTGRES_DB='s2_task57_race'
$env:POSTGRES_HOST_PORT='15457'
$env:APP_PORT='18057'
docker compose -p s2-task57 up -d --wait database
docker compose -p s2-task57 run --rm -T -e POSTGRES_DB=s2_task57_race backend python backend/manage.py test parties.test_approval_concurrency parties.test_approval.ApproveRequestApiTests.test_membership_write_failure_leaves_request_pending parties.test_approval.ApproveRequestApiTests.test_decision_constraint_failure_rolls_back_new_or_reactivated_membership parties.test_approval.ApproveRequestApiTests.test_reject_keeps_seat_free_and_later_approve_cannot_overwrite_it --noinput --verbosity 2

# เทียบเท่า make verify ใน projectแยก
docker compose -p s2-task57 run --rm -T -e POSTGRES_DB=s2_task57_race backend sh -c 'python backend/manage.py check && python backend/manage.py makemigrations --check --dry-run && ruff check backend scripts && ruff format --check backend scripts && python backend/manage.py test backend --top-level-directory backend --noinput --verbosity 1'

# ส่วน manual SQL baseline; seedนี้เขียน MOCKลงDBทดสอบ ไม่เกี่ยวกับtestDBที่Djangoลบแล้ว
docker compose -p s2-task57 run --rm -T -e POSTGRES_DB=s2_task57_race backend python backend/manage.py migrate --noinput
docker compose -p s2-task57 run --rm -T -e POSTGRES_DB=s2_task57_race backend python backend/manage.py seed_sprint2 --confirm-test-data
$sql="SELECT id AS party_id FROM parties_party WHERE title='[S2-DATA] Last slot' AND description='Synthetic S2-DATA fixture; rerunning seed_sprint2 resets this party.' \gset"+[Environment]::NewLine+(Get-Content database/seeds/us10_decision_snapshot.sql -Raw)
$sql | docker compose -p s2-task57 exec -T database sh -c 'psql -X -P pager=off -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d s2_task57_race'

# หยุดเฉพาะprojectทดสอบนี้ เก็บvolume ไม่แตะcstuเดิม
docker compose -p s2-task57 down
Remove-Item Env:POSTGRES_DB, Env:POSTGRES_HOST_PORT, Env:APP_PORT
```

SQLmanualเป็นread-only; การเขียนในautomatedtestsอยู่ในฐานที่Djangoสร้าง/ลบเอง
ไม่ต้องสร้างรหัสผ่านfixtureหรือใช้TU keyจริง ไม่ใช้การกดสองbrowserด้วยมือแทนrace tests

## 7. ข้อจำกัดและการตรวจรับ

ส่งมอบรอ GearJP2 review/merge ก่อน Complete; ผลนี้ไม่ใช่humanUATหรือloadtestของระบบจริง
ไม่แก้ production API/schema และไม่ปิดงานUI/Task56/leave/Task66แทนคนอื่น
ถ้ารันซ้ำพบFailให้เก็บ rawlog/sourcecommit/environment และcaseเดิมเพื่อretest ไม่ติ๊กผ่านแทน
