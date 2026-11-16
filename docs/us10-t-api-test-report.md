# S2-US10-T-API — Task56 API acceptance report

วันที่รัน: **16 พฤศจิกายน 2026 (Asia/Bangkok)**
งาน: [Issue #71](https://github.com/GearJP2/cs261-group2-100001/issues/71) / [Trello Task56](https://trello.com/c/sjmejBOJ)
คนหลัก: พี; คู่ช่วย: กอล์ฟ. ผู้ดำเนินการรอบนี้: Codex ตามคำขอพี; ไม่ใช่หลักฐาน peer review, CI หรือ human UAT

## ผลและขอบเขต

- เพิ่ม **18 unit tests** ครบ checklist `UT-US10-API-01`–`06`; ทั้งหมด Pass โดยไม่ใช้ฐานข้อมูลหรือ HTTP server
- รัน **47 HTTP case variants** กับแอปจริงและ PostgreSQL แยก: Pass 47, Fail 0; มี request/response และ SQL ก่อน–หลัง ไม่ใช้ Django test client ส่ง business API ในรอบ HTTP นี้
- `make verify`: พบ 691 tests, ผ่าน 690, skip 1, ไม่มี failure/error; Django checks, migration check, Ruff lint/format ผ่าน
- `make smoke`: Pass
- ไม่พบ bug ใหม่จากเคสที่รัน จึงไม่มี production fix หรือ bug/retest cycle ใหม่; ผลนี้ไม่ได้ยืนยันว่าครอบคลุมทุกกรณีของ Story

Source ที่ตรวจ: `05ce80ebcf25415e299452e1b061e7ef8545328a` บน baseline main `1b5c97b`; branch `test/s2-us10-t-api`. Unit tests อยู่ใน commit `50ab911`, HTTP runner/Compose overlay อยู่ `05ce80e`; commits ถัดมาเป็นเอกสารและหลักฐาน

ใช้ contract ปัจจุบันตาม [planning snapshot](sprint-2-planning-contract.md), [sequence](sprint-2-sequences/us10.mmd) และ [B-01](us10-b-01-test-report.md)/[B-02](us10-b-02-test-report.md)/[B-03](us10-b-03-test-report.md): GET `/join-requests/pending`, POST `/join-requests/{request_id}/decision` พร้อม Approved/Rejected. ข้อเสนอ `/approve`/`/reject` ใน Issue #55 ยังเป็นข้อแตกต่างที่ทีมต้องยืนยัน ไม่เปลี่ยน expected/route เพื่ออ้างว่าได้รับมติแล้ว

## ชิ้นงานและหลักฐาน

| ชิ้นงาน | หน้าที่ |
| --- | --- |
| [test_decision_unit.py](../backend/parties/test_decision_unit.py) | SimpleTestCase, RequestFactory และ mock ORM/clock แยก logic/guard/validation |
| [us10-api-evidence.py](../scripts/us10-api-evidence.py) | ตัวรัน HTTP + SQL; สร้างเฉพาะ synthetic fixtures ใหม่ ไม่ลบแถวเดิม |
| [compose.task56.yml](../scripts/compose.task56.yml) | Overlay ใช้ DB `s2_task56_api` และ DEBUG เฉพาะ Compose project ทดสอบ |
| [execution.csv](evidence/task56/execution.csv) | Expected/actual status/code, checks, result และเวลาครบ 47 variants |
| [http-results.json](evidence/task56/http-results.json) | Request method/path/body, response status/body, SQL ก่อน–หลัง, digest domain และผลตรวจแต่ละกรณี |
| [source-manifest.json](evidence/task56/source-manifest.json) | commit, environment, source SHA-256 และ checksum หลักฐาน |
| [unit-tests.log](evidence/task56/unit-tests.log) | 18 Pass พร้อม `Skipping setup of unused database(s): default` |
| [verify.log](evidence/task56/verify.log) / [smoke.log](evidence/task56/smoke.log) | ผลเต็มของ verify/smoke |
| [startup.log](evidence/task56/startup.log) / [guard-refusal.log](evidence/task56/guard-refusal.log) | เปิดแอปสำเร็จ และ runner ปฏิเสธ DB พัฒนาที่ชื่อไม่ใช่ `s2_task56_*` ก่อนสร้าง fixtures |

ไฟล์หลักฐานแปลงเป็น UTF-8/LF และ logs ตัด whitespace ท้ายบรรทัด/บรรทัดว่างท้ายไฟล์ก่อนคำนวณ checksum โดยไม่เปลี่ยนผลหรือข้อความทดสอบ; logs ต้นฉบับอยู่ `../output/us10-t-api/` นอก Git. กำหนด eol=lf เฉพาะโฟลเดอร์หลักฐานนี้เพื่อให้ checksum คงเดิมเมื่อ checkout บน Windows

## Unit Test — UT-US10-API-01 ถึง 06

ทุก test ใช้ `SimpleTestCase` ซึ่งห้าม database query. RequestFactory สร้าง request ในหน่วยความจำแล้วเรียก view/decorators จริง โดย mock identity lookup และ service ตามเคส; ไม่ใช่ HTTP client/server และไม่มี CSRF middleware ใน unit layer

Service tests เรียก `decide_join_request.__wrapped__` / `submit_join_request.__wrapped__` เพื่อทดสอบเฉพาะ logic โดยไม่เข้า atomic decorator; mock repository managers และ clock, ใช้ `get_party_state` จริงกับจำนวนสมาชิกที่ mock ไว้ **ผล unit ไม่ได้พิสูจน์ transaction/lock/rollback** ซึ่งตรวจด้วย integration suites เดิม

| Checklist | Expected / Actual ที่รันผ่าน | Test method suffix (ละ `test_`) |
| --- | --- | --- |
| UT-US10-API-01 | Anonymous 401; inactive direct guard 403 ACCOUNT_INACTIVE; identity หาย/ผิด 403; non-Host 403; ไม่เรียก mutation | `ut01_anonymous_never_calls_identity_or_mutation`, `ut01_inactive_actor_never_calls_identity_or_mutation`, `ut01_missing_or_invalid_university_evidence_never_calls_mutation`, `ut01_non_host_never_reads_request_or_mutates` |
| UT-US10-API-02 | lookup ระบุทั้ง request PK และ locked Party; ไม่พบตาม scope ได้ 404 และไม่เขียนข้อมูล | `ut02_request_lookup_is_scoped_to_locked_party` |
| UT-US10-API-03 | Approved/Rejected แล้วตัดสินซ้ำทั้งสองแบบได้ 409 REQUEST_DECIDED; ไม่มี save/create | `ut03_decided_request_does_not_write_again` |
| UT-US10-API-04 | Full ขัด Approve; Cancelled/เริ่มพอดี/InProgress/Completed ขัดทั้งสอง decision; ไม่มี save/create | `ut04_full_party_blocks_approve`, `ut04_cancelled_started_completed_and_exact_start_block_decisions` |
| UT-US10-API-05 | Approved สร้าง member หรือ reactivate แถวเดิมและบันทึก Host/time; active member ได้ 409; view ส่ง actor จาก session | `ut05_approve_creates_member_and_records_host_and_time`, `ut05_approve_reactivates_existing_membership`, `ut05_active_member_cannot_be_approved`, `ut05_ut06_view_passes_session_actor_and_exact_decision` |
| UT-US10-API-06 | Reject ตอน Full ได้; ไม่เรียก membership repository; ขอใหม่ใช้แถวเดิม เปลี่ยน Pending/created_at และล้าง decision; ขอใหม่ตอน Full ไม่ได้ | `ut06_reject_full_party_changes_only_decision`, `ut06_reapplication_reuses_rejected_row_and_clears_decision`, `ut06_full_party_blocks_reapplication_before_request_write`, `ut05_ut06_view_passes_session_actor_and_exact_decision` |

เพิ่มอีก 3 methods: `invalid_payload_never_reaches_service`, `wrong_method_never_reaches_service`, `service_error_preserves_status_and_code`. Method ที่ตรวจร่วม UT05/06 นับเพียงครั้งเดียว รวมทั้งหมด 18; ไม่ใช้จำนวน subTest variants เพิ่มจำนวน methods

## HTTP / SQL execution

Environment: Python 3.12.15, Django 5.2.18, PostgreSQL 17.11, Docker Desktop/Linux containers บน Windows. Compose project `us10-task56`, DB `s2_task56_api`, host port 58056 (app) / 55456 (DB); runner ภายใน backend เรียก `http://127.0.0.1:8000`

รันจริง **16:50:49–16:50:51 +07:00** ตาม timestamps ใน JSON. Session หลายบทบาทเป็น fixtures จาก `force_university_login`/local force_login แล้วนำ cookie ไปใช้ผ่าน urllib HTTP จริง. CSRF token/cookie มาจาก HTTP `/auth/csrf`. ไม่เรียก TU provider และไม่เก็บ cookie/token ลงหลักฐาน

Fixture แต่ละ scenario เป็น Party แยกและ request Pending, มี Host membership 1 คน/capacity 2; Full เพิ่มสมาชิกอีกคน, state เริ่ม/จบ/ยกเลิกตั้งเวลาหรือ cancelled_at อย่างชัดเจน. ผู้ใช้/สนาม/กีฬาสร้างชื่อ prefix สุ่มเฉพาะรอบ. case เรียงตาม `execution.csv`; กลุ่ม reapply ต้องรันตามลำดับ

SQL oracle อ่านสามตาราง Party/JoinRequest/PartyMembership โดยตรง ไม่ใช้ serializer หรือ service เป็นตัวตรวจตัวเอง. Error/read cases เทียบทุกแถวทุก field ในสามตารางก่อน–หลัง และเก็บ digest; JSON แสดง raw rows เฉพาะ Party เป้าหมาย. Domain ในรายงานไม่รวม session table เพราะการใช้/ล้าง session เป็นพฤติกรรมที่คาดหวัง

| QA mapping / variants | Expected และ Actual | ผล |
| --- | --- | --- |
| QA-US10-API-01 host/nonhost | Host 200 + public Pending fields; non-Host 403; GET ไม่เขียน domain | Pass 2 |
| QA-US10-API-08 anonymous/unverified/inactive/expired/outsider/applicant × 2 decisions | 401 หรือ 403 ตาม session/สิทธิ์, no mutation | Pass 12 |
| QA-US10-API-05 cross-party × 2, missing Party/request | 404 NOT_FOUND, no mutation | Pass 4 |
| QA-US10-API-07 malformed JSON/status array/object/Pending/actor injection | 400 INVALID_INPUT, no mutation | Pass 5 |
| QA-US10-API-08 CSRF missing/wrong/Origin/method | 403 CSRF_FAILED หรือ 405 METHOD_NOT_ALLOWED, no mutation | Pass 4 |
| QA-US10-API-07 Full/InProgress/Completed/Cancelled × 2 decisions | Full: approve409/reject200; started/completed/cancelled: ทั้งสอง409; error ไม่เขียน และ Reject ไม่แก้สมาชิก | Pass 8 |
| QA-US10-API-02 และ 06 approve + ตัดสินซ้ำสองค่า | Approved/member เพิ่มหนึ่งใน capacity; สองคำสั่งซ้ำ409และคงข้อมูล | Pass 3 |
| QA-US10-API-04 และ 06 reject → ตัดสินซ้ำสองค่า → ขอใหม่ → approve → อ่าน Pending/Detail | Reject ไม่เพิ่ม member, ซ้ำ409, ขอใหม่201 IDเดิม/metadataล้าง, approve200, Pendingว่าง/detail count2 slots0 Full | Pass 7 |
| QA-US10-API-08 logout/stale-cookie | logout200, cookie เก่าใช้ตัดสินได้401 และ domain ไม่เปลี่ยน | Pass 2 |

ชื่อ variant `QA-US10-API-07/Full-Rejected` ใน JSON ใช้เป็นหลักฐานของ inventory `QA-US10-API-03` ด้วย; outsider/applicant variants ภายใต้ API08 เป็นหลักฐานสิทธิ์ของ API05 ด้วย ไม่มีการนับเพิ่มซ้ำ. ผล variants อยู่แยกกัน ไม่แก้ inventory ส่วนกลางให้เป็น Pass ทั้งแถว เพราะบางแถวมีขอบเขตกว้างกว่ารอบนี้

Inactive session ผ่าน ModelBackend กลายเป็น anonymous จึง HTTP401; direct guard unit ได้ ACCOUNT_INACTIVE403 เมื่อส่ง authenticated inactive actor ให้โดยตรง ทั้งสองผลเป็นคนละชั้น ไม่เปลี่ยน expected ให้เท่ากัน

## คำสั่งและการรันซ้ำ

Unit run รันได้โดยไม่เปิด DB:

```powershell
docker compose run --rm -T --no-deps backend python backend/manage.py test parties.test_decision_unit --noinput --verbosity 2
```

HTTP rehearsal ต้องเลือก project/volume ใหม่เฉพาะทดสอบและ port ว่าง ตัวอย่างรอบนี้:

```powershell
$env:APP_PORT='58056'
$env:POSTGRES_HOST_PORT='55456'
$task56Compose=@('-f','docker-compose.yml','-f','scripts/compose.task56.yml','-p','us10-task56')
docker compose @task56Compose up --build -d --wait
$task56Source=git rev-parse HEAD
docker compose @task56Compose exec -T backend python scripts/us10-api-evidence.py --confirm-test-database --source-commit $task56Source | Out-File -Encoding utf8 http-results.json
make 'COMPOSE=docker compose -f docker-compose.yml -f scripts/compose.task56.yml -p us10-task56' verify
make 'COMPOSE=docker compose -f docker-compose.yml -f scripts/compose.task56.yml -p us10-task56' smoke
```

ไม่ใช้ DB พัฒนาหรือ production. Runner ปฏิเสธหากไม่มี confirmation/DEBUG/DB prefix ที่กำหนด หรือ URL ไม่ใช่ loopback HTTP; ปฏิเสธ redirect. ไม่มีรหัสผ่าน TU ในคำสั่ง. ต้องตรวจ exit code ของ runner และ summary Fail ก่อนรับผล; PowerShell pipeline ไป Out-File ไม่ใช่ตัวตัดสิน Pass

เมื่อจบรอบนี้ตรวจ label ของ volume แล้วปิด `us10-task56` และลบเฉพาะ volume ทดสอบนั้น เก็บฐานพัฒนาไว้ ไม่แก้ `.env` และไม่เปิด app ค้างให้ผู้ใช้

## ข้อจำกัด / ส่งต่อ

- **Not run:** login กับ TU API จริง, human manual sign-off, browser UAT/กดปุ่ม/refresh/ป้องกัน double click ของ Task55 (#70). HTTP runner เป็น assistant-operated scripted acceptance ไม่อ้างว่ามนุษย์ทดสอบเอง
- **Exact starts_at ผ่าน HTTP: Not run.** รอบนี้ HTTP ใช้เวลาก่อนเริ่ม/ผ่านเริ่มแล้ว; ขอบ `now == starts_at` พิสูจน์ด้วย controlled-clock unit ใหม่และ integration tests เดิมใน full verify ไม่อ้างว่าทดสอบขอบนี้ด้วย network timing
- QA-US10-API-01 เรื่องลำดับรายการหลายแถว/privacy variants ใช้ integration suite เดิมใน verify; HTTP รอบนี้ตรวจแถวเดียว ไม่ใช้แทนทุก variant ของ inventory
- Skip 1 ตัวใน full verify คือ placeholder เดิม `conduct.test_reviews_unit.ReviewSerializerUnitTests.test_no_show_and_credit_formula_blocked_until_policy_is_confirmed`, ข้อความ decorator `Blocked: policy not confirmed in #100/#105`; ไม่ใช่ tests US10 และไม่ใช่การยืนยันว่ามติ policy ปัจจุบันยังค้าง
- Transaction/race/rollback ตรวจด้วย suites เดิมที่รันใหม่ใน verify และอ้างรายงาน [Task57](s2-us10-t-db-task57.md); ไม่สร้าง race ใหม่หรือใช้ HTTP sequential cases แทนหลักฐาน concurrent execution
- ไม่มี production logic, migration, env variable สำหรับแอป หรือ package dependency ใหม่. Overlay มีเฉพาะค่าฐานชั่วคราวเพื่อทดสอบ
- ใช้ ID เดิมเมื่อขอใหม่ตาม contract ไม่มี version/idempotency key ข้ามรอบ; client ต้อง refresh ก่อนตัดสินและไม่ retry คำสั่งเก่าข้ามรอบอัตโนมัติ ตามข้อจำกัดใน B-03
- รอ CI และกอล์ฟ/ทีม review หลักฐานและข้อแตกต่าง contract ก่อนปิด #71; ไม่ปิด Issue/ย้าย Trello หรือประกาศ Story US10 เสร็จแทนทีม
