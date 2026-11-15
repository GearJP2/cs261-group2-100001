# S2-US10-B-03 — Reject request API / test report

วันที่ตรวจ: 14 พฤศจิกายน 2026 (Asia/Bangkok)
Task52: [Issue #67](https://github.com/GearJP2/cs261-group2-100001/issues/67) / [Trello](https://trello.com/c/EoWxwxzS)
คนหลัก: พี; คู่ช่วย review: กอล์ฟ
ผู้รัน: Codex ในเครื่องพัฒนาตามคำขอพี; เป็นผล local checks ไม่ใช่ CI/review หรือ browser UAT

## ขอบเขตและสิ่งที่ส่งมอบ

ตรวจรับ AC 2 และ 3 ของ US10 โดย reuse implementation ใน main `8657ae0` ตาม [sequence](sprint-2-sequences/us10.mmd) และ [schema contract](base-02-schema-contract.md) เรื่องใช้คำขอเดิมกลับเป็น Pending เมื่อขอใหม่หลังถูกปฏิเสธ

Reject มี implementation ที่รองรับเงื่อนไขอยู่แล้ว รอบนี้ไม่พบความจำเป็นต้องเปลี่ยน runtime logic จึงเพิ่มหลักฐานตรวจรับและอธิบาย contract:

- [services.py](../backend/parties/services.py): เพิ่ม docstring ว่า Reject ต้องเป็น Pending/ยังไม่เริ่ม/ไม่ยกเลิก แต่ Full ปฏิเสธได้ และไม่แก้ membership/capacity
- [test_rejection.py](../backend/parties/test_rejection.py): เพิ่ม 14 Backend integration tests ผ่าน Django HTTP client กับ PostgreSQL; ครอบคลุมผลตัดสิน, สิทธิ์, session/CSRF, read APIs, rollback และขอใหม่
- [test_rejection_concurrency.py](../backend/parties/test_rejection_concurrency.py): เพิ่ม 5 concurrency integration tests ผ่าน HTTP client บน connections แยกกัน และยืนยันการรอ Party lock ด้วย `pg_blocking_pids`
- ใช้ decision endpoint, guard, constraints และการ lock Party → JoinRequest เดิม; ไม่มี route/schema ใหม่

## Contract สำหรับ Frontend

```http
POST /api/v1/parties/{party_id}/join-requests/{request_id}/decision
Content-Type: application/json
X-CSRFToken: <token>
Cookie: <session และ csrf cookies>
```

```json
{"status": "Rejected"}
```

`request_id` คือ JoinRequest ID จาก GET Pending ไม่ใช่ user ID; actor ใช้ Host จาก university session ไม่รับ user_id/host_id/decided_by หรือ field อื่นเพิ่มใน body

สำเร็จตอบ 200:

```json
{"data": {"id": 123, "status": "Rejected"}}
```

บันทึก `status`, `decided_at`, `decided_by` เท่านั้น; เก็บ request และ created_at เดิม จำนวนสมาชิก, left_at/joined_at ของ membership, capacity และที่ว่างไม่เปลี่ยน หลังสำเร็จให้โหลด Pending/Party detail ใหม่ คำขอที่ถูกปฏิเสธจะหายจาก Pending และผู้ขอเห็น Rejected จาก `/join-requests/me` เทสต์รอบนี้ตรวจ read APIs รวมรายชื่อสมาชิก US6 แต่ยังไม่ตรวจปุ่ม/refresh ใน browser

| เงื่อนไข | ผล |
| --- | --- |
| Host + Pending + Party Open | 200 Rejected |
| Host + Pending + Party Full | 200 Rejected; ที่ว่างยังเป็น 0 |
| ไม่ login / session หมดอายุ / cookie หลัง logout | 401 `AUTH_REQUIRED` เมื่อ CSRF ผ่าน |
| ไม่ผ่าน university guard / ไม่ใช่ Host แม้เป็น staff หรือสมาชิก | 403 `FORBIDDEN` |
| CSRF หาย/ผิด หรือ Origin ไม่ผ่าน | 403 `CSRF_FAILED` |
| JSON/content type/status ไม่ถูกต้อง หรือ body มี field เกิน | 400 `INVALID_INPUT` (validator เดียวกับ B-02) |
| Party/request ไม่มี หรือ request ไม่อยู่ใน Party ตาม URL | 404 `NOT_FOUND` |
| method ไม่ใช่ POST | 405 `METHOD_NOT_ALLOWED`, `Allow: POST` |
| request Approved/Rejected แล้วและยังไม่ได้ขอใหม่ | 409 `REQUEST_DECIDED`; คง decision และ membership เดิม |
| Party Cancelled | 409 `PARTY_CANCELLED` |
| ถึงเวลาเริ่มพอดี, InProgress หรือ Completed | 409 `PARTY_STARTED` |

CSRF middleware ทำงานก่อน view; service ตรวจ Host และ Pending ก่อน state จึงอาจตอบ error ก่อนหน้าเมื่อผิดหลายเงื่อนไขพร้อมกัน ไม่บังคับว่าต้องตอบ error สถานะ Party เสมอ

ผู้ถูกปฏิเสธส่ง `POST /api/v1/parties/{party_id}/join-requests` ด้วย `{}` ได้ตามเงื่อนไข US3 เดิม: Party ยังเปิด/มีที่ว่าง/ไม่ใช่สมาชิก ระบบ reuse ID เดิม, เปลี่ยนเป็น Pending, อัปเดต created_at และล้าง decided_at/by โดยไม่สร้างสมาชิก ต้องรอ Host ตัดสินใหม่ จึงไม่ใช่การแบนถาวร

ใช้ `/decision` เดิมให้ตรงกับ caller ปัจจุบัน ข้อเสนอ URL `/reject` ใน Issue #55 ยังไม่ถูกเพิ่มในงานนี้ หากทีมจะเปลี่ยน URL ต้องยืนยัน contract และปรับ callers ร่วมกัน

## ผลทดสอบจริง

- Branch: `feat/s2-us10-b-03-reject-request`; source/tests ที่ตรวจคือ `8b7d1db` รวม `34f9117` บน baseline `8657ae0`
- Python 3.12.15, Django 5.2.18, PostgreSQL 17.11; Docker Desktop/Linux containers บน Windows
- ชุดใหม่ 19 test methods: API 14 และ concurrency 5, ไม่มี skip; subTest variants ไม่นับเป็น methods เพิ่ม
- Session/identity สร้างด้วย `force_university_login` ใน test database; ไม่เรียก TU provider จริง; unsafe HTTP ใช้ `enforce_csrf_checks=True`

| คำสั่ง | ผลจริง |
| --- | --- |
| `docker compose run --rm -T backend python backend/manage.py test parties.test_rejection --noinput --verbosity 2` | ผ่าน 14 tests, ไม่มี skip |
| `docker compose run --rm -T backend python backend/manage.py test parties.test_rejection_concurrency --noinput --verbosity 2` | ผ่าน 5 tests, ไม่มี skip |
| `make verify` | Django checks, migration check (`No changes detected`), Ruff lint/format ผ่าน; พบ 608 tests: ผ่าน 607, skip 1, ไม่มี failure/error |
| `make "COMPOSE=docker compose -p us10-b03-smoke" up` | build/start สำเร็จ backend/database healthy |
| `make "COMPOSE=docker compose -p us10-b03-smoke" smoke` | ผ่าน HTTP, PostgreSQL readiness, Django template และ static CSS |

Skip เดิมอยู่ `conduct.test_reviews_unit.ReviewSerializerUnitTests.test_no_show_and_credit_formula_blocked_until_policy_is_confirmed` มี decorator ระบุ `Blocked: policy not confirmed in #100/#105` เป็น placeholder US14 ที่อยู่ใน baseline ไม่ใช่ tests Reject และไม่ใช่การยืนยันว่ามติ policy ปัจจุบันยังค้างอยู่

Smoke ใช้ project/volume แยก `us10-b03-smoke`, process environment `APP_PORT=58030`, `POSTGRES_HOST_PORT=55430` ไม่แก้ `.env`; migrate/seed catalog ตอน startup อยู่ในฐาน smoke ใหม่ เมื่อจบลบเฉพาะ project/volume smoke รอบนี้ และปิด container ฐานทดสอบของ project หลักโดยเก็บ volume ฐานพัฒนาไว้

Logs local อยู่นอก Git ที่ `../output/us10-b-03/`: `reject-api-2026-11-14.log`, `reject-concurrency-2026-11-14.log`, `verify-2026-11-14.log`, `smoke-start-2026-11-14.log`, `smoke-2026-11-14.log`

## เคสตรวจรับและผล

ชื่อ methods ด้านล่างละ prefix `test_`; ทุกแถว Pass ในรอบ local นี้

| Case / AC | Test method | ผลที่ยืนยัน |
| --- | --- | --- |
| REJ-01 / AC2 | `reject_records_decision_and_refreshes_reads_without_changing_members` | 200, ผู้ตัดสิน/เวลาถูกต้อง, คง created_at; Pending ตัดเฉพาะรายการเป้าหมาย; own request Rejected; detail/members เท่าเดิม |
| REJ-02 / AC2 | `full_party_can_reject_without_freeing_a_slot` | Full ยัง Reject ได้ และผู้ขอยังขอใหม่ไม่ได้จนกว่าจะมีที่ว่าง |
| REJ-03 / AC2 | `reject_preserves_withdrawn_membership_history` | Reject และการขอใหม่ไม่เปิดใช้หรือแก้ประวัติ membership ที่ถอนแล้ว |
| REJ-04 / AC2 | `rejected_applicant_can_reapply_and_then_be_approved` | HTTP Reject → ขอใหม่ ID เดิม → Pending metadata ว่าง → Approved; ขอซ้ำตอน Pending ได้ 409 |
| REJ-05 / AC3 | `non_host_roles_and_anonymous_cannot_reject` | ผู้สมัคร/คนอื่น/สมาชิกที่เป็น staff+superuser ไม่มีสิทธิ์; anonymous 401 |
| REJ-06 / AC3 | `unverified_and_expired_sessions_cannot_reject` | ไม่มี university evidence 403, session หมดอายุ 401 |
| REJ-07 / AC3 | `logout_revokes_old_cookie_for_reject` | เรียก logout จริงแล้วใช้ cookie เก่า Reject ได้ 401 |
| REJ-08 / AC3 | `missing_or_wrong_party_request_cannot_be_rejected` | missing Party/request และ request ต่าง Party ของ Host เดียวกันได้ 404 |
| REJ-09 / AC3 | `repeated_reject_and_approve_preserve_rejection` | Reject แล้วตัดสินซ้ำทั้งสองค่าได้ 409, คงข้อมูลเดิม |
| REJ-10 / AC3 | `reject_cannot_overturn_approval_or_remove_member` | Approved แล้ว Reject ไม่ได้และไม่ถอนสมาชิก |
| REJ-11 / AC3 | `cancelled_started_completed_and_exact_start_deny_reject` | ตรวจ cancelled/started/completed/เวลาเริ่มพอดี; ไม่มี domain writes |
| REJ-12 / AC3 | `extra_body_fields_cannot_override_actor_or_target` | field เกิน 400; query ไม่เปลี่ยน actor/request/decision |
| REJ-13 / AC3 | `reject_requires_csrf_and_post` | token/Origin ผิด 403, methods อื่น 405; domain snapshot เท่าเดิม |
| REJ-14 / AC2 | `failure_after_decision_write_rolls_back_all_domain_data` | หลัง SQL บันทึก Rejected แล้วทำให้ constraint ล้มเหลวจริง; rollback เหลือ Pending เดิมและ retry ได้ |
| REJ-C01 / AC2,3 | `two_rejects_decide_once_without_changing_members_or_slots` | worker HTTP สอง connections ติด lock จริง; หนึ่ง 200 อีกหนึ่ง 409 REQUEST_DECIDED |
| REJ-C02 / AC3 | `rejection_committed_first_prevents_waiting_approval` | Reject commit ก่อนทำให้ Approve ที่รอได้ 409 และคง metadata เดิม |
| REJ-C03 / AC3 | `cancellation_committed_first_prevents_waiting_rejection` | cancel service commit ก่อนปล่อย lock; Reject ที่รอได้ 409 PARTY_CANCELLED |
| REJ-C04 / AC3 | `new_start_time_is_rechecked_after_waiting_for_lock` | เปลี่ยนเวลาเริ่มใน transaction ที่ถือ lock; worker อ่านค่าใหม่และตอบ 409 PARTY_STARTED |
| REJ-C05 / AC2 | `party_becoming_full_while_waiting_still_allows_reject` | capacity เปลี่ยนจน Full ระหว่างรอ; worker ยัง Reject ได้ ที่ว่างคง 0 |

Full suite ยังรันหลักฐานเดิมของ B-02/Task49/Task57 รวม approve-versus-reject และการตรวจ SQL ว่า Reject ไม่เขียน membership; ไม่เพิ่มเทสต์สำเนาของเคสเหล่านี้

## ผลกระทบและข้อจำกัด

- ไม่มี migration, env variable, dependency หรือ runtime behavior ใหม่ และไม่ต้องรอ schema เพิ่มสำหรับ patch นี้
- ไม่เพิ่ม endpoint, reason field, notification หรือประวัติ decision หลายรอบ; บันทึกเฉพาะสถานะล่าสุดตาม schema เดิม
- Request ใช้ ID เดิมเมื่อขอใหม่ ไม่มี version/idempotency key ผูกแต่ละรอบ; 409 REQUEST_DECIDED ป้องกันการตัดสินซ้ำขณะที่ยังเป็นสถานะตัดสินแล้ว ไม่รับประกันคำสั่งเก่าที่ถูก retry ข้ามรอบขอใหม่ Frontend ควรโหลด Pending ใหม่ก่อนตัดสิน ไม่ retry คำสั่งเก่าอัตโนมัติข้ามรอบ
- Unexpected DB failure ยัง propagate เป็น server error หลัง rollback ตามระบบเดิม; tests ใช้ Django client ยืนยัน exception/DB state ไม่ได้เพิ่ม JSON error contract ใหม่
- ไม่ได้รัน TU login จริง, browser E2E, การปิดปุ่มซ้ำ หรือ UAT ร่วม Frontend; ผล read API ไม่แทนการ refresh บนหน้าจอ
- รอ push/CI/review ก่อนปิด Task52 และไม่ใช้ผล local ปิด Story US10 ทั้งหมด

Commits ก่อนเอกสารรายงาน:

1. `34f9117` — API/rollback/reapplication tests 14 methods และ docstring เงื่อนไข Reject
2. `8b7d1db` — HTTP concurrency/state-recheck tests 5 methods
