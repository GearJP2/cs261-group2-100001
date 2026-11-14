# Task69 — Soft leave และ transaction สมาชิก

วันที่ตรวจ: 13 พฤศจิกายน 2026 (Asia/Bangkok) · Owner: Gold

- [Issue #84](https://github.com/GearJP2/cs261-group2-100001/issues/84) / S2-US4-DB-01 / US4 AC 1,3
- Branch: `feat/s2-us4-db-soft-leave`; base `65404fdf8b55e9885968f521cec7352dd75ce50e`
- Design: [policy](us4-leave-party-policy.md), [contract](us4-leave-party-api-contract.md), [test design](us4-leave-party-test-cases.md)
- Design PR [#136](https://github.com/GearJP2/cs261-group2-100001/pull/136) ได้ GearJP2 APPROVED และ merge วันที่ 13 พ.ย. 2026; checklist ผู้ตรวจ Austin ในเอกสารยังไม่ติ๊ก จึงไม่อ้างว่า Austin รับรองแล้ว

## สิ่งที่ส่งมอบและขอบเขต

เพิ่ม `leave_party(party_id=..., user=...)` ใน service เดิม คืน `PartyMembership` เมื่อสำเร็จ และใช้ `PartyError` เดิมเมื่อผิดกฎ ผู้เรียกต้องส่ง authenticated/verified user จาก guard ของระบบ ไม่รับ user ที่ client เลือกเอง

ล็อก Party ก่อน Membership ภายใน atomic transaction เช่นเดียวกับ approve/edit/cancel. ครั้งแรกเขียนเฉพาะ `left_at`; ครั้งซ้ำคืนเวลาถอนเดิมโดยไม่ UPDATE. ไม่ DELETE membership, ไม่แก้ capacity/JoinRequest และไม่อนุมัติผู้รออัตโนมัติ. เวลาอ่านหลังได้ lock; Host, nonmember, already-left, cancelled, started ตรวจตามลำดับใน Design

Task69 เป็นชั้น service/database ไม่เพิ่ม route/view หรือ UI. Task70 ต้องต่อ endpoint/guard/validation/response; Task75 ต้องส่งมอบ test matrix ของตัวเองหลังชิ้นงานพร้อม ไม่ถือว่าปิด Task75 จากผลชุดนี้

## ตรวจ query อะไร

1. Party lookup ใช้ primary key และ `SELECT ... FOR UPDATE` เป็น mutex ร่วม แม้สมาชิกเป้าหมายยังไม่มีแถว
2. Membership lookup ใช้ `(party_id,user_id)` พร้อม `FOR UPDATE`; ใช้ unique constraint `unique_party_membership` ที่มีอยู่ ไม่เพิ่มแถวใหม่เมื่อถอน
3. Write ใช้ `save(update_fields=["left_at"])`; retry ไม่เรียก save จึงคง timestamp เดิม
4. จำนวน active อ่านจาก `left_at IS NULL` รวม Host ผ่าน helper เดิม ไม่เพิ่ม counter แยก. มี index `(party,left_at)` เดิมอยู่แล้ว ไม่เพิ่ม index/migration ซ้ำ
5. [SQL snapshot](../database/seeds/us4_leave_snapshot.sql) อ่าน membership ทุกแถวและ count ด้วย subquery แยก ไม่ join กับ requests จน count คูณ. Test execute ไฟล์ SQL นี้จริงด้วย bound parameter (ไม่ได้ต่อค่าผู้ใช้เป็น SQL)

ตรวจความถูกต้องของ query/results และ lock จริง ไม่ได้ benchmark หรืออ้างประสิทธิภาพ production จาก fixture ขนาดเล็ก

## Environment และวิธีทดสอบ

ผู้ช่วยรัน automated service integration บน PostgreSQL จริง ตามคำขอโกล. ใช้ MOCK users/Party/JoinRequest ใน Django fixtures ไม่มี TU API หรือข้อมูลบัญชีจริง

- Compose project `s2-task69`; DB `s2_task69_leave`, test DB `test_s2_task69_leave`
- Host DB port `15469`; APP_PORT `18069` (ไม่ได้เปิด web server)
- Docker image เดิม `cs261-unisport-backend:dev`; ไม่เปลี่ยน dependency หรือ env ของโปรเจกต์
- Runtime: Python 3.12.15 / Django 5.2.18 / PostgreSQL 17.11 (ดู [runtime log](evidence/task69/runtime.log)); [source hashes](evidence/task69/source-manifest.json) ผูกไฟล์ที่ทดสอบกับหลักฐาน
- Targeted log มี migration/test names/SQL snapshots และ PID/blocker; full verification log มีผล Django/Ruff/regression

ตั้งค่าจาก repo ที่มี `.env` พร้อมใช้ แล้วรัน PowerShell:

```powershell
$env:POSTGRES_DB='s2_task69_leave'
$env:POSTGRES_HOST_PORT='15469'
$env:APP_PORT='18069'
docker compose -p s2-task69 up -d --wait database
docker compose -p s2-task69 run --rm -T -e POSTGRES_DB=s2_task69_leave backend python backend/manage.py test parties.test_leave --noinput --verbosity 2
docker compose -p s2-task69 run --rm -T -e POSTGRES_DB=s2_task69_leave backend sh -c 'python backend/manage.py check && python backend/manage.py makemigrations --check --dry-run && ruff check backend scripts && ruff format --check backend scripts && python backend/manage.py test backend --top-level-directory backend --noinput --verbosity 1'
```

Precondition มาตรฐาน: Party เริ่มพรุ่งนี้, cap2, Host+M active รวม2 (Full), M มี Approved request เดิม, N ยังไม่เป็นสมาชิก. ทุก test สร้าง fixture แยก ไม่พึ่งข้อมูลรอบก่อน

## Cases / ขั้นตอน / Expected–Actual

ผล Targeted: **13 tests ผ่าน ไม่มี skipped**. ชื่อ test แบบเต็มอยู่ใน [raw log](evidence/task69/targeted-tests.log)

Full verification: **573 discovered = 572 ผ่าน + 1 skipped** ใน 39.767s; skipped คือ US14 No-show policy `test_no_show_and_credit_formula_blocked_until_policy_is_confirmed` ที่รอยืนยัน #100/#105 ไม่ใช่ Task69. Django check / migration dry-run / Ruff ผ่านทั้งหมด

| Case / test suffix | ขั้นตอนเฉพาะ | Expected | Actual |
| --- | --- | --- | --- |
| 69-01 `soft_leave_and_retry_preserve_history_and_query_count` | SQLก่อน → M leave → SQLหลัง → เปลี่ยน Party เป็น cancelled/completed → retry โดยดัก save | active2→1, slots0→1, membership ID/joined_at/จำนวนแถว/Host/capacity/requestเดิม; retry timestampเดิมไม่มี write | PASS; SQL before/after และ retry_left_at ใน JSONL |
| 69-02 `open_party_allows_leave` | เปลี่ยน cap3 เป็น Open → M leave | active เหลือ1 | PASS |
| 69-03 `host_and_nonmember_rejected_before_state_checks` | Party cancelled → Host และ N leave | HOST_CANNOT_LEAVE403 / NOT_MEMBER403 ตามลำดับ; SQLไม่เปลี่ยน | PASS ทั้ง2กรณี |
| 69-04 `pending_and_rejected_applicants_are_not_members` | N มี Pending/Rejected request แต่ไม่มี membership → leave | NOT_MEMBER403 ทั้งคู่; SQLไม่เปลี่ยน | PASS ทั้ง2subcases |
| 69-05 `cancelled_precedes_started_and_preserves_membership` | cancelled และ clockเท่ากับends_at → M leave | PARTY_CANCELLED409 ก่อนเช็กเวลา; ไม่ถอน | PASS |
| 69-06 `start_boundary_and_completed_reject_first_leave` | แทน clock ที่ starts_at และ ends_at → leave | PARTY_STARTED409 ทั้งคู่; SQLไม่เปลี่ยน | PASS ทั้ง2subcases; clockจำลอง |
| 69-07 `unknown_party` | ส่ง IDที่ไม่มี | NOT_FOUND404 | PASS |
| 69-08 `database_error_after_write_rolls_back` | SQLก่อน → saveจริง → inject DatabaseErrorก่อนออกatomic → SQLหลัง | exceptionออกservice; SQLเหมือนเดิม active2/left_atNULL | PASS; errorเป็นการจำลองหลัง UPDATE จริง ไม่ใช่DBconstraintสร้างเอง |
| 69-09 `rejoin_requires_approval_then_allows_new_leave_cycle` | leave → US3ขอใหม่ → US10approve → leaveรอบใหม่ | ก่อนapproveยังactive1; หลังapprove2; reuse request/membership และเวลาถอนรอบใหม่ | PASS |
| 69-10 `two_leaves_update_once_after_real_lock_wait` | ถือPartylock, workerleaveรอจริง, coordinatorleaveแล้วcommit, workerทำต่อ | ทั้งคู่ timestampเดียว; active1/แถว2 | PASS; มีpg_blocking_pidsจริง |
| 69-11 `approve_waits_for_leave_then_reads_freed_slot` | ถือPartylock, workerapproveรอจริง, coordinatorleaveแล้วcommit | approveอ่านที่ว่างใหม่; Approved, active2ไม่เกินcap2 | PASS; SQLก่อน/หลังและPIDในJSONL |
| 69-12 `leave_rechecks_time_after_lock` | workerleaveรอPartylock; coordinatorเปลี่ยนstarts_atเป็นอดีตก่อนปล่อย | workerอ่านเวลาหลังlock ได้PARTY_STARTED; Mยังactive | PASS; เปลี่ยนเวลาPartyจริง ไม่ใช้sleepจนถึงเวลา |
| 69-13 `approve_before_waiting_leave_sees_full_party` | workerleaveรอจริง; coordinatorapproveขณะFull → ปล่อยleave | approvePARTY_FULL; requestPending/no Nmembership; หลังleaveactive1 | PASS; SQLก่อน/หลังและPIDในJSONL |

Concurrency ใช้ `TransactionTestCase`, connection แยกและ thread worker มี timeout5s/10s. Coordinator ถือ Party lock จน `pg_blocking_pids(worker_pid)` ยืนยันว่า worker รอ coordinator จริง แล้วจึงดำเนินการตามลำดับที่กำหนด ไม่ใช่ยิงสองคำสั่งเรียงแล้วเรียกว่า race

## หลักฐานและข้อจำกัด

- [Targeted raw log](evidence/task69/targeted-tests.log): ชื่อ13testsและผลจริง
- [JSONL SQL/PID observations](evidence/task69/observations.jsonl): ดึงบรรทัด `DB69_EVIDENCE` จาก targeted log โดยไม่เปลี่ยนค่า
- [Full verification](evidence/task69/verification.log): คำสั่ง check/makemigrations/Ruff และ regression (ดูผลท้ายไฟล์)
- [Test source](../backend/parties/test_leave.py): assertions และขั้นตอนที่ทำซ้ำได้

ไม่ใช่ human UAT, browser click test หรือ Manual API ผ่าน HTTP. ยังไม่พิสูจน์ endpoint เพราะ Task70 ยังไม่ต่อ. Task75 ยังต้องตรวจ matrix เพิ่ม เช่น cancel/editทั้งลำดับ, external API/SQL evidence ตามขอบเขตที่ทีมรับมอบ ไม่ติ๊ก Complete หรือ peer-review แทนผู้ตรวจ

Retry รับรองผลเดิมเฉพาะเมื่อแถวยังถอนอยู่ หากถูก approve กลับเป็น active แล้ว คำสั่งใหม่จะถอนรอบใหม่ ไม่มี idempotency key แยกรอบ ห้าม frontend retryคำสั่งเก่าอัตโนมัติข้ามรอบสมาชิก
