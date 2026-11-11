# S2-US10-B-02 — Approve request API / test report

วันที่ตรวจ: 2 พฤศจิกายน 2026 (Asia/Bangkok)
Task51: [Issue #66](https://github.com/GearJP2/cs261-group2-100001/issues/66) / [Trello](https://trello.com/c/7TSMc2YY)
คนหลัก: พี; คู่ช่วย review: กอล์ฟ
ผู้รัน automated checks: Codex ในเครื่องพัฒนา ตามคำขอพี; ผลด้านล่างเป็น local checks ไม่ใช่ CI หรือผล review

## ขอบเขตและสิ่งที่เปลี่ยน

Reuse decision endpoint และ transaction/Party lock เดิมตาม [US10 sequence](sprint-2-sequences/README.md#us10--อนุมัติ--ปฏิเสธ) โดยตรวจรับส่วนอนุมัติของ Task51 (AC 1, 3, 4 และส่วน Backend ของ AC 5)

- [views.py](../backend/parties/views.py): ตรวจว่า `status` เป็น string ก่อนเทียบค่าที่อนุญาต แก้กรณีส่ง array/object แล้วเกิด TypeError/500 ให้ตอบ 400 `INVALID_INPUT`
- [services.py](../backend/parties/services.py): ปฏิเสธ Pending ที่อ้างผู้ขอซึ่งเป็น Host หรือสมาชิก active อยู่แล้วด้วย 409 `ALREADY_MEMBER`; ใช้ state ที่คำนวณหลัง Party lock ตรวจ Full และ lock membership เดิมก่อนเปิดใช้อีกครั้ง
- คงการอนุมัติผู้เคยถอนตัวโดยใช้ membership แถวเดิม ตั้ง `left_at=null` และเก็บ `joined_at` เดิม; ไม่เพิ่มแถวซ้ำ
- [test_approval.py](../backend/parties/test_approval.py): เพิ่ม 17 methods ตรวจ contract, สิทธิ์, state, CSRF, rollback และผลต่อ read APIs
- [test_approval_concurrency.py](../backend/parties/test_approval_concurrency.py): เพิ่ม 6 methods ตรวจการอนุมัติพร้อมกันและการอ่าน state ใหม่หลังรอ lock บน PostgreSQL จริง

ก่อนแก้ พบเทสต์ล้มเหลวจริงเมื่อ `status` เป็น array/object และเมื่ออนุมัติ Pending ของสมาชิก active/Host; หลังแก้ผ่านทั้งหมด ส่วน atomic rollback และ Party lock มีอยู่ก่อนแล้ว รอบนี้เพิ่มหลักฐานตรวจพฤติกรรม ไม่ได้อ้างว่าสร้างกลไกเหล่านี้ใหม่

## API สำหรับ Frontend

```http
POST /api/v1/parties/{party_id}/join-requests/{request_id}/decision
Content-Type: application/json
X-CSRFToken: <token จาก API csrf>
Cookie: <session และ csrf cookies ของผู้ใช้>
```

```json
{"status": "Approved"}
```

- ใช้ session ของ Host ที่ผ่าน university guard; ห้ามส่ง `user_id`, `host_id`, `party_id` หรือ `decided_by` ใน body
- `request_id` คือ ID ของ JoinRequest จาก Pending API ไม่ใช่ user ID
- Response 200 มีเฉพาะผลตัดสิน เช่น:

```json
{"data": {"id": 123, "status": "Approved"}}
```

หลังสำเร็จให้โหลด Pending และ Party detail ใหม่: Pending รายการนั้นหายไป, สมาชิก active เพิ่มหนึ่ง, ที่ว่างลดหนึ่ง และสถานะเป็น Full เมื่อเต็ม ผู้ขอดู `/join-requests/me` แล้วเห็น Approved การ refresh ผ่าน browser ต้องทดสอบในงาน Frontend/integration ต่อ

เลือกใช้ `/decision` เดิมเพื่อให้ตรงกับ caller ปัจจุบัน ไม่เพิ่ม `/approve` alias ในงานนี้ ข้อเสนอแยก `/approve` กับ `/reject` ใน Issue #55 ยังต้องให้ทีมยืนยันก่อน migrate URL/callers ร่วมกัน เอกสารนี้ไม่ใช่มติแทนทีม

| HTTP | Error code | กรณี |
| --- | --- | --- |
| 400 | `INVALID_INPUT` | JSON/content type/ชนิด status ไม่ถูกต้อง หรือมี field เกิน |
| 401 | `AUTH_REQUIRED` | ไม่มี session หรือ session หมดอายุ |
| 403 | `FORBIDDEN` | ไม่ผ่าน university guard หรือไม่ใช่ Host ของ Party |
| 403 | `CSRF_FAILED` | token หาย/ผิด หรือ Origin ไม่ผ่าน |
| 404 | `NOT_FOUND` | Party/request ไม่มี หรือ request ไม่อยู่ใน Party ตาม URL |
| 405 | `METHOD_NOT_ALLOWED` | method ไม่ใช่ POST; `Allow: POST` |
| 409 | `REQUEST_DECIDED` | request ไม่ใช่ Pending รวมการกดอนุมัติซ้ำ |
| 409 | `PARTY_CANCELLED` | กิจกรรมยกเลิกแล้ว |
| 409 | `PARTY_STARTED` | ถึงเวลาเริ่มแล้วหรือจบแล้ว |
| 409 | `PARTY_FULL` | สมาชิก active ถึง capacity แล้ว |
| 409 | `ALREADY_MEMBER` | ผู้ขอเป็น Host หรือสมาชิก active อยู่แล้ว |

Guard ใช้ของ BASE-04/US1-B เดิม รวม policy บัญชี inactive ตามระบบเดิม; ตารางนี้สรุปกรณีหลักของ approval ไม่แทน contract guard ทั้งระบบ CSRF middleware ตรวจ unsafe request ก่อน view จึงอาจได้ `CSRF_FAILED` ก่อน error สิทธิ์เมื่อไม่มี token

ลำดับ service: lock Party → ตรวจ Host → lock request ที่อยู่ใน Party → ตรวจ Pending → คำนวณ state จากเวลาปัจจุบัน → ตรวจ Cancelled/Started/Full → ตรวจสมาชิก → เขียน membership และ decision ใน transaction เดียวกัน ดังนั้นถ้าทั้งเต็มและเป็นสมาชิกอยู่แล้ว จะได้ `PARTY_FULL` ก่อน `ALREADY_MEMBER`

ที่ว่างคำนวณจาก capacity ลบสมาชิก active ไม่ได้ลด capacity หรือเขียน counter อีกชุด หากบันทึกไม่สำเร็จ transaction ย้อนทั้ง membership และ decision; unexpected database failure ยัง propagate เป็น server error ตามพฤติกรรมเดิม ไม่แปลงเป็น business 409 หรือรับประกัน retry อัตโนมัติ

## Environment และผลรันจริง

- Runtime/tests ที่ตรวจ: commit `50d9a0d` รวม `4c5ca50`, branch `feat/s2-us10-b-02-approve-request`, เริ่มจาก main `d2f1893`
- Python 3.12.15, Django 5.2.18, PostgreSQL 17.11; Docker Desktop / Linux containers บน Windows
- ชุดใหม่รวม 23 methods: 17 Backend API/service integration และ 6 concurrency integration; ใช้ DB จริงและ Django test client ไม่ใช่ browser E2E
- สร้าง identity/session ด้วย `force_university_login` ใน test database; ไม่ส่ง credentials ไป TU provider จริง
- Concurrency ใช้ connections แยกกัน; race ใช้ Barrier ส่วนการรอ edit/cancel/start ตรวจ `pg_blocking_pids` เพื่อยืนยันว่าติด Party lock จริงก่อนปล่อย transaction

| คำสั่ง | ผลจริง |
| --- | --- |
| `docker compose run --rm -T backend python backend/manage.py test parties.test_approval parties.test_approval_concurrency --noinput --verbosity 2` | ผ่าน 23 tests, ไม่มี skip |
| `make verify` | ผ่าน Django checks, migration drift check (`No changes detected`), Ruff lint/format และ 336 tests, ไม่มี skip |
| `make "COMPOSE=docker compose -p us10-b02-smoke" up` | build/start สำเร็จ; backend/database healthy |
| `make "COMPOSE=docker compose -p us10-b02-smoke" smoke` | ผ่าน HTTP, PostgreSQL readiness, Django template และ static CSS |

Smoke ใช้ project `us10-b02-smoke` กับ volume ใหม่ และ process environment `APP_PORT=58020`, `POSTGRES_HOST_PORT=55420`; ไม่แก้ `.env` หรือ reset ฐานพัฒนา Startup migrate/seed catalog เกิดในฐาน smoke แยก เมื่อจบลบเฉพาะ project/volume smoke ที่สร้างรอบนี้ และปิด database container ที่เปิดสำหรับ tests โดยเก็บ volume ฐานพัฒนาไว้

Logs local อยู่ `../output/us10-b-02/verify-2026-11-02.log` และ `smoke-2026-11-02.log` นอก Git; ให้แนบผล CI ของ PR เพิ่มเมื่อส่ง review

## หลักฐานตาม Acceptance Criteria

ชื่อ method ด้านล่างละ prefix `test_`; subTest variants ไม่เพิ่มจำนวน test methods

| AC / สิ่งที่ตรวจ | Test methods | ผลจริง |
| --- | --- | --- |
| 1: Approved + สมาชิก + read APIs | `approval_adds_one_member_and_refreshes_pending_own_request_and_detail` | 200, decided_by/time ถูกต้อง, สมาชิก 2/ที่ว่าง 0/Full, Pending ว่าง, ผู้ขอเห็น Approved |
| 1: เคยถอนตัว | `reapproval_reuses_withdrawn_membership_and_preserves_join_history` | reuse แถวเดิมและ joined_at เดิม, left_at null |
| 1: rollback | `membership_write_failure_leaves_request_pending`, `decision_constraint_failure_rolls_back_new_or_reactivated_membership` | snapshot domain ก่อน/หลังเท่ากัน; กรณีหลังทำให้ DB constraint ล้มเหลวจริงหลังเขียน membership ทั้ง create/reactivate |
| 3: Host/session/ขอบเขต request | `non_host_and_anonymous_cannot_approve`, `missing_university_evidence_or_expired_session_cannot_approve`, `request_must_exist_and_belong_to_url_party` | 401/403/404 ตามกรณีและไม่มี domain writes |
| 3: ตัดสินแล้ว/สมาชิกเดิม | `repeated_decision_preserves_first_result_and_membership`, `rejected_request_cannot_be_approved_without_new_application`, `existing_active_member_cannot_be_approved_again`, `host_cannot_be_approved_even_without_host_membership` | 409, คงผลเดิมและไม่เพิ่มสมาชิก |
| 3: input/method/CSRF/ปลอม actor | `invalid_payloads_are_400_not_server_errors`, `wrong_content_type_and_methods_are_rejected`, `csrf_missing_invalid_and_wrong_origin_do_not_write`, `query_cannot_change_actor_target_or_decision` | invalid 400/403/405; query ไม่เปลี่ยน Host/ผู้ขอ/decision |
| 4: Party state และขอบเวลาเริ่ม | `full_started_completed_and_cancelled_party_reject_approval`, `exact_start_boundary_rejects_approval` | 409 และไม่มี domain writes |
| 5: ที่นั่งสุดท้าย | `two_approvals_for_last_slot_add_only_one_member` | สำเร็จหนึ่งคำขอ อีกคำขอ 409 PARTY_FULL และยัง Pending; ไม่เกิน capacity |
| 3/5: request เดียวพร้อมกัน | `same_request_approved_concurrently_is_decided_once`, `approve_racing_reject_has_one_consistent_decision` | หนึ่ง 200 อีกหนึ่ง 409 REQUEST_DECIDED; สมาชิกตรงกับ decision ที่ชนะ |
| 4/5: state เปลี่ยนระหว่างรอ lock | `cancel_committed_while_approval_waits_blocks_approval`, `capacity_edit_committed_while_approval_waits_is_rechecked`, `clock_is_read_after_party_lock_at_exact_start` | อ่าน cancel/capacity/เวลาหลัง lock; 409 โดยคำขอและสมาชิกไม่เปลี่ยน |

## ผลกระทบและสิ่งที่ยังต้องทำ

- ไม่มี migration, env variable, package dependency หรือ route ใหม่; ใช้ constraints/session/Party lock ที่มีใน main อยู่แล้ว
- ไม่มี schema งานใหม่ที่ต้องรอ Database สำหรับ patch นี้ แต่ทุก service ที่แก้สมาชิก/ความจุในอนาคตต้องใช้ Party lock ตามลำดับเดียวกันจึงจะรักษาเงื่อนไข concurrency นี้ได้
- การรักษา joined_at เดิมเป็นพฤติกรรมเดิม ไม่ใช่ประวัติทุกช่วงเข้า–ออก; ถ้าต้องเก็บแต่ละช่วงให้ตกลงกับ Database ในงานแยก
- การปฏิเสธใช้ endpoint/service ร่วมกันจึงมี regression approve-versus-reject แต่ยังไม่ถือว่าตรวจรับ S2-US10-B-03 ทั้งหมด
- ยังไม่ได้ทดสอบบัญชี TU จริง, ปุ่มใน browser, การปิดปุ่มซ้ำ, การ refresh รายชื่อสมาชิก US6 หรือ UAT กับ Frontend; smoke ไม่แทนการทดสอบเหล่านี้
- รอ push/CI/review และการยืนยัน contract กับทีมก่อนปิด Task51; ไม่ใช้ผล local ปิด Story US10 ทั้งหมด

Commits งาน runtime/tests:

1. `4c5ca50` — validation/member guard และ API/rollback tests 17 methods
2. `50d9a0d` — concurrency/state-recheck tests 6 methods
