# S2-US10-B-01 — Host Pending API implementation / test report

วันที่ตรวจ: 1 พฤศจิกายน 2026 (Asia/Bangkok)
Task50: [Issue #65](https://github.com/GearJP2/cs261-group2-100001/issues/65) / [Trello](https://trello.com/c/mXq4fXQh)
คนหลัก: พี; คู่ช่วย review: กอล์ฟ
ผู้รัน automated checks ในรอบนี้: Codex ในเครื่องพัฒนา ตามคำขอพี; ยังไม่ใช่ผล review หรือ CI บน GitHub

## ขอบเขตและสิ่งที่เปลี่ยน

ใช้ `GET /api/v1/parties/{party_id}/join-requests/pending` เดิม พร้อม university session guard, Host check และ allowlist `id`, `display_name`, `created_at`
API นี้มี implementation มาก่อนแล้ว งานนี้ตรวจ reuse ตาม [Design](us10-pending-api-design.md) และเพิ่มหลักฐานตรวจรับตาม [PEND-01 ถึง PEND-18](us10-pending-api-test-cases.md)

- [views.py](../backend/parties/views.py): เพิ่ม `pk` เป็นลำดับรองจาก `created_at` เพื่อให้รายการที่เวลาเท่ากันเรียงแน่นอน และอธิบายว่าสถานะ Party จำกัดการตัดสิน ไม่ปิดสิทธิ์อ่านของ Host
- [test_pending_requests.py](../backend/parties/test_pending_requests.py): เพิ่ม 21 test methods แยกจากชุดส่ง/ตัดสินคำขอ ครอบคลุม 18 case IDs และ variants ของสิทธิ์/session/state
- ไม่แก้ routes, decision service, models, constraints หรือ migrations; ไม่มี env variable หรือ dependency ใหม่
- ไม่เพิ่ม alias GET `/join-requests`, pagination, API approve/reject ใหม่ หรือ Frontend

ก่อนแก้ query เทสต์ equal timestamps ล้มเหลวจริง: ได้ `[1003, 1001, 1002]` แทน `[1001, 1002, 1003]` หลังเพิ่ม `.order_by("created_at", "pk")` เทสต์ผ่าน

## Contract ที่ใช้ใน implementation นี้

อิง Design จาก PR #120 ที่ merge แล้ว โดยนำข้อเสนอ D01–D05 มาใช้เป็น implementation สำหรับ review:

| ข้อเสนอ | การใช้ใน Task50 |
| --- | --- |
| D01 | คง URL `/pending` และ reverse name `party-join-request-list` เดิม |
| D02 | คงสาม public fields; ไม่มี profile ใช้ `ผู้ใช้`; ไม่ใช้ username/email แทน |
| D03 | คงการอ่านได้โดย Host ใน Open/Full/InProgress/Completed/Cancelled; GET ไม่ตัดสินคำขอ |
| D04 | เพิ่ม tie-break ด้วย request PK เมื่อ `created_at` เท่ากัน |
| D05 | คงไม่มี pagination/query filters; query ไม่เปลี่ยน actor, Party หรือ Pending status |

การเลือกนี้ไม่ใช่หลักฐานว่ากอล์ฟ/Frontend ยืนยันมติครบทุกข้อแล้ว เอกสาร Design ยังเก็บสถานะข้อเสนอไว้ ต้องให้ reviewer ยืนยัน compatibility กับ #55 และ caller ใน PR ของ Task50 ก่อนปิดงาน
Issue #55 ยังเสนอ GET `/join-requests`; ถ้าทีมเลือกเปลี่ยน ต้องแก้ caller/route/tests/docs ร่วมกันโดยรักษา POST ส่งคำขอของ US3

## Environment และหลักฐานรัน

- Source runtime/tests ที่ตรวจ: commit `aabf151` (รวม commit `51053cd`), branch `feat/s2-us10-b-01-pending-requests`; commits หลังจากนี้ในรอบเดียวกันเป็นเอกสารรายงาน
- Python 3.12.15, Django 5.2.18, PostgreSQL 17.11; Docker Desktop / Linux containers บน Windows
- Fixtures ของชุดใหม่: สร้างใน test database ของ Django แล้วทำลายเมื่อจบ; ไม่ใช้ข้อมูลบัญชีมหาวิทยาลัยจริง
- ยืนยัน session ด้วย `force_university_login`; logout เรียก app endpoint จริงผ่าน Django test client พร้อม CSRF; ไม่เรียก TU provider จริง
- 21 methods แบ่งเป็น Backend integration 20 methods และ direct guard seam 1 method; `subTest` variants ไม่ถูกนับเป็น test methods เพิ่ม
- Full suite ใช้ PostgreSQL รวม concurrency tests เดิม; รอบนี้ไม่ได้เพิ่ม concurrency ของการอนุมัติ เพราะอยู่นอกขอบเขตการอ่าน Pending

| คำสั่ง | ผลจริง |
| --- | --- |
| `docker compose run --rm -T backend python backend/manage.py test parties.test_pending_requests --noinput --verbosity 2` | ผ่าน 21 tests, ไม่มี skip |
| `make verify` | ผ่าน Django checks, migration drift check (`No changes detected`), Ruff lint/format และ 305 tests, ไม่มี skip |
| `make "COMPOSE=docker compose -p us10-b01-smoke" up` | build/start สำเร็จ; backend/database healthy ใน Compose project แยก |
| `make "COMPOSE=docker compose -p us10-b01-smoke" smoke` | ผ่าน HTTP, PostgreSQL readiness, Django template และ static CSS |
| `curl --include http://localhost:58010/api/v1/parties/0/join-requests/pending` โดยไม่มี cookie | HTTP 401, JSON `AUTH_REQUIRED`, `Cache-Control` มี `no-store` |

Smoke ใช้ `APP_PORT=58010`, `POSTGRES_HOST_PORT=55410` ใน process environment ชั่วคราว และ project `us10-b01-smoke` ซึ่งมี volume ของตัวเอง ไม่แก้ `.env`
Startup migrate/seed catalog ทำกับฐาน smoke แยก ไม่ reset ข้อมูลสนามในฐานพัฒนา เมื่อจบลบเฉพาะ project/volume smoke ที่สร้างในรอบนี้ และปิด container database ที่เปิดสำหรับ tests โดยเก็บ volume ฐานพัฒนาไว้
Logs local เก็บแยกจาก Git ใน `../output/us10-b-01/`: `pending-tests-2026-11-01.log`, `verify-2026-11-01.log`, `smoke-2026-11-01.log`; ให้แนบ logs/CI ของ PR ตอนส่ง review ไม่ถือว่า logs local เป็นผล CI

## ผลตามเคส Design

Preconditions/steps ตาม test design; fixtures จริงอยู่ `PendingRequestApiTests.setUpTestData` โดยใช้ request IDs ต่างจาก user IDs และมี insertion order ต่างจาก PK order เพื่อจับปัญหาการเรียง
`read()` ถ่ายและเทียบ snapshot ทุกแถวของ Party/JoinRequest/PartyMembership ก่อน–หลัง GET; unsafe methods มี snapshot ตรวจแยก ส่วน direct guard ตรวจว่าไม่มี query
ชื่อ methods ในตารางทั้งหมดอยู่ใน [ชุดเทสต์ Task50](../backend/parties/test_pending_requests.py)

| Case | Test method (ไม่รวม prefix `test_`) | Actual เทียบ Expected | ผล |
| --- | --- | --- | --- |
| PEND-01 | `host_reads_only_own_pending_with_exact_public_fields` | 200, data array, request ID และสาม public fields ตรงข้อมูล | Pass |
| PEND-02 | `host_reads_only_own_pending_with_exact_public_fields` | มีเฉพาะสาม Pending ของ Party เป้าหมาย ไม่มี Approved/Rejected หรือคำขออีก Party | Pass |
| PEND-03 | `no_pending_returns_empty_array_even_when_decided_requests_exist` | 200 และ data เป็น `[]` เมื่อไม่มี Pending | Pass |
| PEND-04 | `non_hosts_cannot_read_even_if_member_applicant_or_staff` | Host อีก Party, ผู้สมัคร, สมาชิก, ผู้ถอนตัวถูกปฏิเสธ 403; staff/superuser ไม่ข้าม Host check | Pass |
| PEND-05 | `anonymous_denied_before_party_lookup` | 401 ทั้ง Party ที่มีและไม่มีจริง | Pass |
| PEND-06 | `missing_invalid_or_other_users_identity_is_forbidden`, `unverified_or_wrong_provider_identity_is_forbidden` | ไม่มี/ผิดชนิด/อ้าง identity คนอื่น, provider ผิด หรือขาด timestamp ยืนยันได้ 403 | Pass |
| PEND-07 | `missing_party_and_unmatched_routes_return_404` | numeric ID ไม่มีจริงได้ JSON 404; path abc/-1 ได้ routing 404 | Pass |
| PEND-08 | `query_cannot_change_actor_party_or_status` | query user_id/host_id/party_id/status ไม่เปลี่ยนผลจาก Pending ของ Party ตาม URL | Pass |
| PEND-09 | `other_host_cannot_impersonate_owner_with_query` | ปลอม ID Host ผ่าน query ยังได้ 403 | Pass |
| PEND-10 | `missing_profile_has_safe_fallback_without_private_identifiers` | ไม่มี profile ใช้ `ผู้ใช้`, ไม่สร้าง profile และไม่มี private identifiers/extra fields | Pass |
| PEND-11 | `oldest_first_and_equal_timestamps_use_request_id` | เก่าไปใหม่และเวลาเท่ากันเรียง PK เพิ่มขึ้น; regression ก่อนแก้ล้มเหลว หลังแก้ผ่าน | Pass |
| PEND-12 | `created_at_has_bangkok_offset_without_changing_instant` | offset +07:00 และ instant ตรง DB โดยไม่มีการแก้ timestamp | Pass |
| PEND-13 | `expired_session_cannot_read_previously_visible_requests`, `real_logout_revokes_copied_cookie_for_pending_reads` | expired/logout/cookie เก่าได้ 401; logout ลบ server session จริง | Pass |
| PEND-14 | `inactive_host_session_is_anonymous_under_model_backend`, `authenticated_inactive_guard_denies_without_database_query` | HTTP session ได้ 401; direct guard ได้ 403 ACCOUNT_INACTIVE โดยไม่มี query | Pass |
| PEND-15 | `unsupported_methods_and_csrf_failures_do_not_write` | HEAD/OPTIONS/unsafe methods ที่มี CSRF ได้ 405 + Allow: GET; HEAD body ว่าง; POST ไม่มี CSRF ได้ 403; domain ไม่เปลี่ยน | Pass |
| PEND-16 | `refresh_removes_decided_request_and_responses_are_not_cached` | หลังเปลี่ยน fixture เป็น Rejected ไม่ปรากฏใน GET ถัดไป; response มี no-store (error responses ตรวจใน assert_error ด้วย) | Pass |
| PEND-17 | `host_can_read_pending_in_every_party_state` | Open/Full/InProgress/Completed/Cancelled อ่านได้ 200 โดยคำขอไม่เปลี่ยน | Pass |
| PEND-18 | `repeated_reads_preserve_requests_memberships_and_slots` | snapshots เท่าเดิมทั้งสองครั้ง, สมาชิก 2 คนและที่ว่าง 2 ที่เท่าเดิม | Pass |

เพิ่มอีกหนึ่ง method `host_authorization_does_not_depend_on_membership_row`: ลบ Host membership จาก fixture แล้วยังอ่านได้ เพราะ ownership มาจาก Party.host ไม่ใช่ membership; ผ่าน
ผลทั้งหมดเป็น local automated checks ไม่ใช่การตรวจ flow อนุมัติ/ปฏิเสธใหม่ทั้งระบบหรือ browser UAT

## ข้อจำกัดและส่งต่อ review

- รายการ Manual UI ใน test design ยัง **Not run**; smoke ไม่ได้พิสูจน์ loading/error หรือการกดปุ่มผ่าน browser
- Manual HTTP รอบนี้ตรวจเฉพาะ anonymous 401; กรณี Host และสิทธิ์อื่นมีหลักฐานจาก Django client/DB tests ไม่ใช่บัญชี TU จริง
- ผล CI/review ของ PR Task50 ยังรอหลัง push; ไม่ปิด #65/#55 หรือย้าย Trello เป็น Complete จากผล local เพียงอย่างเดียว
- การอ่านทั้งหมดโดยไม่แบ่งหน้ายังเป็นข้อจำกัดเดิมตาม D05; ถ้าจะเพิ่ม pagination ให้ตกลง contract กับ Frontend แยก
- Task49/Database และ Task51/52 (approve/reject) ยังมีขอบเขตของตัวเอง ไม่รวมผล concurrency/rollback ของการตัดสินในรายงานนี้

ประวัติ commits ของงานโค้ด:

1. `51053cd` — แก้ลำดับกรณีเวลาเท่ากัน พร้อม public/read-only tests 8 methods
2. `aabf151` — เพิ่ม access/session/CSRF/state tests จนครบ 21 methods
