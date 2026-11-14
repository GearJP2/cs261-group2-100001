# Task49 — JoinRequest / Membership constraints และ transaction

[Issue #64](https://github.com/GearJP2/cs261-group2-100001/issues/64) · [Trello](https://trello.com/c/BbPo8Xec) · US10 AC1,2,3,5

ผู้ทำ: Gold (`gold555555`) · ขอ GearJP2 review · ตรวจวันที่ 5 พฤศจิกายน 2026 (Asia/Bangkok)
Branch `chore/s2-us10-db-transactions` จาก main `e5a254e64324603cfb11e000e2cd6400d66c6f3e`.
ฐานข้อมูลทดสอบแยก `s2_task49_audit` / `test_s2_task49_audit`, Compose project `s2-task49`, host PG port15449.
Environment/source fingerprints: [manifest](evidence/task49/source-manifest.json), [runtime](evidence/task49/runtime.log).

## ผลตรวจและสิ่งที่เปลี่ยน

**ของเดิมบน main ทำ transaction/constraints ถูกต้องตาม scope ที่ตรวจ จึงไม่เพิ่ม schema หรือเขียน service ซ้ำ**
เพิ่มคำอธิบาย lock contract ใน service, 2 integration tests สังเกต SQL lock order จริง,
SQL catalog audit และ SQL rehearsal พร้อม raw logs/Expected–Actual ให้ตรวจซ้ำได้
ไม่มี migration, endpoint, env variable หรือ dependency ใหม่

### ข้อตกลงการเขียนข้อมูลร่วมกัน

1. `decide_join_request` อยู่ใน `transaction.atomic` ครอบคลุม membership และ decision
2. ล็อก **Party → JoinRequest ของ Party นั้น → Membership เดิม (ถ้ามี)** ตามลำดับ
3. อ่านเวลา/state/capacity หลังได้ Party lock; ปฏิเสธ Full/Started/Cancelled ตาม service เดิม
4. กรณียังไม่มี membership row การล็อก Party เป็น mutex ป้องกันช่องว่างนี้
   `UNIQUE(party,user)` ป้องกันคนเดิมซ้ำ แต่ไม่ป้องกันคนต่างกันแย่งที่นั่งสุดท้ายด้วยตัวมันเอง
5. บันทึก membership ใหม่หรือคืน `left_at=NULL` ใน row เดิม แล้วบันทึก Approved/เวลา/ผู้ตัดสิน
6. ถ้า DB error ต้องปล่อยให้ exception ออกจาก atomic boundary เพื่อ rollback ทั้งคู่
7. Reject ล็อก Party/Request เหมือนกัน แต่ไม่เขียน membership; การตัดสินซ้ำได้409

`submit_join_request`, `edit_party`, `cancel_party` ใช้ Party lock ก่อนอยู่แล้ว
ผู้พัฒนา leave ใน Task69/70 ต้องใช้ lock ตัวเดียวกันก่อนเปลี่ยนจำนวนสมาชิก;
งานนี้ยังไม่พิสูจน์การทำงานของ leave endpoint ที่ยังไม่มี

### ขอบเขตที่ DB บังคับได้จริง

ตรวจจาก `pg_constraint`/`pg_indexes` หลัง migrate จริง ไม่ใช่อ่านเฉพาะ model declarations:

| กฎ | ผล catalog จริง |
|---|---|
| Request หนึ่ง row ต่อ Party/User | `unique_party_join_request`: UNIQUE(party_id,user_id), validated |
| Membership หนึ่ง row ต่อ Party/User แม้เคย left | `unique_party_membership`: UNIQUE(party_id,user_id), validated |
| Pending ต้องไม่มี decided_at/decided_by; Approved/Rejected ต้องมี decided_at | `join_request_valid_decision`: CHECK, validated |
| capacity>=1 / ends_at>starts_at | CHECK ของ Party ทั้งสองข้อ, validated |
| อ่าน active memberships | index `(party_id,left_at)` เดิม |
| อ่านคำขอ Pending | index `(party_id,status,created_at)` เดิม |
| Foreign keys/PK | มี constraint validated ตาม [catalog log](evidence/task49/schema-audit.log) |

Catalog รอบนี้แสดง16constraints/16indexes ของ3tables รวม FK/PK/auto indexes;
ไม่แปลว่าต้องเพิ่ม16constraintsใหม่. FK PostgreSQL เป็น deferrableตามschemaเดิม
`decided_by` อนุญาต NULL หลังลบผู้ตัดสินตาม policy `SET_NULL` ไม่เปลี่ยนนโยบายนี้

**ข้อจำกัด**: DB CHECK ไม่บังคับ aggregate active count<=capacity ข้ามหลาย rows;
และไม่ได้บังคับความสัมพันธ์ Approved↔active membership ข้ามตารางตลอด lifecycle
(เช่นถอนตัวแล้ว Approved history ยังอยู่ได้). ต้องใช้ service/atomic/Party lock ร่วมกัน
raw SQL writer ที่ข้าม service อาจทำลาย business invariants ได้

## วิธีทดสอบและ Expected–Actual

ผู้ช่วยรันคำสั่งจริงตามคำขอ Gold ใช้ MOCK fixtures บน DB แยก ไม่ใช่ Gold กด UAT เอง
automated API tests ใช้ Django test client/session helper ไม่เรียก TU API;
SQL rehearsal ใช้ `psql` จริง แต่ไม่ได้เรียก Django service จึงไม่ใช้ผล SQL แทน service atomicity

| Case | Precondition / Steps | Expected | Actual / หลักฐาน |
|---|---|---|---|
| DB49-C01 catalog | migrate → รัน `us10_constraint_audit.sql` | unique/check/indexตามตารางข้างต้นติดตั้งจริง | PASS; validated=t, definitionsจริงใน `schema-audit.log` |
| DB49-L01 ใหม่ | ผู้ขอไม่มี membership → เรียก service approve พร้อม CaptureQueriesContext | FOR UPDATE Party→Request→Membership ก่อนwrite; atomic savepoint; Approved/member1row | PASS; SQL3คำสั่งจริงใน `verification.log`/`targeted-tests.log` |
| DB49-L02 ใหม่ | Pending → service reject พร้อม capture/snapshot | FOR UPDATE Party→Request; ไม่เขียนmembership; Rejected | PASS; SQL2คำสั่งและ snapshotเท่ากัน |
| DB49-S01 baseline | seed → SQL SELECT/lock Open กับA Pending | active2, ไม่มีสมาชิกA | PASS; NOTICE baselineใน `sql-rehearsal.log` |
| DB49-S02 constraint failure | INSERTสมาชิกA → UPDATE Approved แต่ decided_at=NULL ในsubtransaction | PostgreSQL23514 ที่ชื่อ `join_request_valid_decision` | PASS; SQLSTATE/constraintจริงในNOTICE |
| DB49-S03 rollback | หลังcatch check_violation → อ่านRequest/สมาชิก | Pending, Aไม่มีmembership, active2 | PASS; checksในDOผ่านและNOTICE |
| DB49-S04 success | INSERTA+UPDATEApprovedพร้อมเวลา/Host → นับ | Approved และactive3ในtransaction | PASS; NOTICEactive3 |
| DB49-S05 outer rollback | ROLLBACK transactionชุดทดลอง → SELECTอีกครั้ง | Pending / active2 / applicant_membership=false | PASS; final psql row `Pending | 2 | f` |
| DB49-A01 existing | `test_membership_write_failure_leaves_request_pending` inject membership DatabaseError | Request/Party/Membership snapshotไม่เปลี่ยน | PASS; realDB + injectedfailure ไม่ใช่ DBสร้างerrorเอง |
| DB49-A02 existing | `test_decision_constraint_failure_rolls_back_new_or_reactivated_membership`: ทำdecided_atNULLแล้วเรียกsaveจริง | DBIntegrityError; membershipใหม่/ที่reactivateและrequestกลับsnapshotเดิม | PASSทั้ง2subcases; PostgreSQL constraintจริง หลังmembershipwrite |
| DB49-A03 existing | schema tests INSERTduplicate/invaliddecisionจริง | IntegrityError; constraintsปฏิเสธข้อมูลผิด | PASS; `PartySchemaTests` ใน targeted log |
| DB49-A04 existing | HTTP test client approve, repeat, Full/Started/Cancelled, reapproveleft | success/409และstate/historyตามcontract | PASS;ชื่อtestsและผลในtargeted log |
| DB49-A05 existing | หลายPostgreSQLconnectionsแข่ง approveที่นั่งสุดท้าย/คำขอเดียว/approve-reject; observerตรวจ `pg_blocking_pids` | ผู้ชนะเดียว; countไม่เกินcapacity; readstateหลังlock | PASS 6 concurrency testsเดิม;ไม่ใช่การกดพร้อมกันด้วยมือ |
| DB49-G01 guard | เรียก rehearsalบนDBชื่อ `postgres` | ปฏิเสธก่อนเขียนข้อมูล | PASS; psql exit3/errorที่ตั้งใจใน `guard-refusal.log` |

Targeted suites **34 tests ผ่านทั้งหมด** (2.859s ในรอบเก็บหลักฐานสุดท้าย).
Full regression **345 tests ผ่านทั้งหมด**, ไม่มี skipped (20.802s);
Django check / migrations drift / Ruff lint+format ผ่าน. ผลfullsuiteเป็นregressionเพิ่มเติม
ไม่ใช้แทนผลmanualSQLรายcase. Task66อยู่คนละbranch จึงไม่มี7skippedของTask66ในงานนี้

## หลักฐาน / source

- [targeted tests](evidence/task49/targeted-tests.log): ชื่อทุกtest/ผลและ SQL lock จริง
- [full verification](evidence/task49/verification.log): check/migration/Ruff/345tests
- [schema audit](evidence/task49/schema-audit.log): actual constraint/index definitions
- [SQL rehearsal](evidence/task49/sql-rehearsal.log): SQLSTATE23514, rollback, success, finalbaseline
- [setup/fixture IDs](evidence/task49/setup.log), [runtime](evidence/task49/runtime.log), [guard](evidence/task49/guard-refusal.log)
- [source manifest](evidence/task49/source-manifest.json): basecommit และ SHA256 ของsourceจริง
- ใหม่: `backend/parties/test_decision_lock_order.py`, `database/seeds/us10_constraint_audit.sql`, `database/seeds/us10_transaction_rehearsal.sql`
- ใช้เดิม: `test_approval.py`, `test_approval_concurrency.py`, `tests.PartySchemaTests`, Task46 `seed_sprint2`

## ทำซ้ำ (PowerShell ที่ repository root)

เปิด Docker และเตรียม `.env`/imageของทีมตามREADME (`DEBUG=true`). ใช้ projectและDBแยกต่อไปนี้;
backendต้องมี `-e POSTGRES_DB=...` ด้วย เพราะ.envอาจยังระบุDBเดิม.

```powershell
$env:POSTGRES_DB='s2_task49_audit'
$env:POSTGRES_HOST_PORT='15449'
$env:APP_PORT='18049'
docker compose -p s2-task49 up -d --wait database
docker compose -p s2-task49 run --rm -T -e POSTGRES_DB=s2_task49_audit backend python backend/manage.py migrate --noinput
docker compose -p s2-task49 run --rm -T -e POSTGRES_DB=s2_task49_audit backend python backend/manage.py seed_sprint2 --confirm-test-data
Get-Content database/seeds/us10_constraint_audit.sql -Raw | docker compose -p s2-task49 exec -T database sh -c 'psql -X -P pager=off -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d s2_task49_audit'
Get-Content database/seeds/us10_transaction_rehearsal.sql -Raw | docker compose -p s2-task49 exec -T database sh -c 'psql -X -P pager=off -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d s2_task49_audit'
docker compose -p s2-task49 run --rm -T -e POSTGRES_DB=s2_task49_audit backend python backend/manage.py test parties.test_decision_lock_order parties.test_approval parties.test_approval_concurrency parties.tests.PartySchemaTests --noinput --verbosity 2

# เทียบเท่า make verify ในproject/DBแยก
docker compose -p s2-task49 run --rm -T -e POSTGRES_DB=s2_task49_audit backend sh -c 'python backend/manage.py check && python backend/manage.py makemigrations --check --dry-run && ruff check backend scripts && ruff format --check backend scripts && python backend/manage.py test backend --top-level-directory backend --noinput --verbosity 1'

# หยุดเฉพาะprojectทดสอบที่สร้างข้างบน เก็บvolume
docker compose -p s2-task49 down
Remove-Item Env:POSTGRES_DB, Env:POSTGRES_HOST_PORT, Env:APP_PORT
```

SQL rehearsalตั้งใจเขียนชั่วคราวแล้วROLLBACK ต้องเริ่มจากseedสะอาด (Open active2/A Pendingและไม่มีmembership)
ถ้าinputไม่ตรงจะRAISEแทนการเขียนต่อ. ตัวเลขIDเปลี่ยนได้ทุกเครื่องจึงหาจากmarkerและusernameMOCK
SQL auditเป็นread-only ส่วนrehearsal guardอนุญาตเฉพาะDBชื่อขึ้นต้น `s2_task49_`

## ส่งมอบและข้อจำกัด

ส่งชุดตรวจ/SQL/lock contractพร้อมPRให้GearJP2review แล้วย้ายDoneตามflowทีม;
ยังไม่ถือว่าreviewอนุมัติหรือCompleteจนมีหลักฐานreview/mergeจริง
งานนี้ไม่มีbehaviorfix เพราะผลตรวจไม่พบปัญหาในขอบเขตTask49
Task57ยังต้องส่งรายงานตรวจรับของตัวเอง แม้เราreuse/rerun tests raceเดิมเป็นregressionแล้ว;
ไม่ได้ปิดTask57/Task66/Task70 หรืออ้างผลเป็นhumanUAT/productionloadtest
