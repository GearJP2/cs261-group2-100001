# S2-US14-T-API — Unit tests และ Manual API test report

วันที่ตรวจ: 2 พฤศจิกายน 2026 (Asia/Bangkok)
Task: [Issue #109](https://github.com/GearJP2/cs261-group2-100001/issues/109)
ผู้รันการทดสอบ: Claude Code ในเครื่องพัฒนา ตามคำขอ Siesta; ผลด้านล่างเป็น local checks ไม่ใช่ CI หรือผล review

## สรุปผล

| ชุดทดสอบ | Pass | Fail | Blocked |
| --- | --- | --- | --- |
| Unit tests (`conduct.test_reviews_unit`, 32 methods) | 31 | 0 | 1 |
| Manual API ผ่าน HTTP จริง | 24 | 0 | 3 |

ไม่พบ bug ใน production code ของ US14 B-01/B-02 ทุก case ที่เกี่ยวกับ No-show และ credit ยังเป็น Blocked จึงยังไม่ถือว่าตรวจรับส่วนนั้นแล้ว

## Environment

- Branch: `test/s2-us14-t-api-unit-and-manual` (สร้างจาก `ab5072d`); ผลด้านล่างรันก่อน commit ของ test file และ report
- Python 3.12.15, Django 5.2.18, PostgreSQL 17.11; Docker 29.8.2 / Linux containers บน macOS
- `DEBUG=true`, app ที่ `http://127.0.0.1:8000` (runserver จาก `docker compose`, container เปิดอยู่แล้ว ไม่ต้องรัน `make up`)

| Commit | งาน | อยู่ใน branch นี้ |
| --- | --- | --- |
| `2ebb7d8` | S2-US14-B-01 submit review | ใช่ |
| `ab5072d` | S2-US14-B-02 read reviews and rating summary | ใช่ |
| `e1fde1f` | S2-US14-B-03 feature-flagged No-show และ credit ledger | **ไม่ใช่** อยู่เฉพาะ `feat/s2-us14-b-03-no-show` |

เพราะ `e1fde1f` ไม่อยู่ใน branch นี้ runtime ที่ทดสอบจึงไม่มี `conduct/policy.py`, setting `NO_SHOW_ENABLED` และ route ของ No-show

## Unit tests

ไฟล์: [test_reviews_unit.py](../backend/conduct/test_reviews_unit.py) ใช้ `SimpleTestCase` และ `unittest.mock` เท่านั้น: ไม่มี database, HTTP client หรือนาฬิกาจริง การรันเฉพาะไฟล์นี้ไม่สร้าง test database และ `SimpleTestCase` จะปฏิเสธ query ที่หลุด mock

| ID | สิ่งที่ตรวจ | Methods | ผล |
| --- | --- | --- | --- |
| UT-US14-API-01 | Open/Full/InProgress/Cancelled → 409 `PARTY_NOT_COMPLETED`; ไม่เคยเข้าร่วม → 403 `FORBIDDEN`; reviewee ไม่ใช่ผู้เข้าร่วมหรือไม่มี rating cache → 400 ที่ `reviewee_id`; Party ไม่มี → 404; อ่านเวลาหลัง lock; กรณีสำเร็จเรียก create และ cache update ครั้งเดียว | 7 | Pass |
| UT-US14-API-01 | `is_participant`: Host ไม่ query membership; ออกก่อนจบ → False; `left_at == ends_at` → True; ออกหลังจบ → True; `left_at` null → True; ไม่มีแถวของตนเอง → False | 6 | Pass |
| UT-US14-API-02 | รีวิวตัวเอง → 400 ที่ `reviewee_id`; ไม่เรียก create และ cache update | 1 | Pass |
| UT-US14-API-03 | `validate_review_payload` / `comment_error`: rating 1–5 ผ่าน; 0, 6, -1, `True`, `False`, `"5"`, `5.0`, `None`, `[5]` ไม่ผ่าน; comment หาย, ว่าง, whitespace, 501 ตัว, non-string, NUL, lone surrogate ไม่ผ่าน; 500 ตัวผ่าน (นับหลัง strip); view ไม่เรียก service เมื่อ input ผิด | 6 | Pass |
| UT-US14-API-04 | `IntegrityError` ที่มี `unique_party_review` → 409 `REVIEW_EXISTS` และไม่แตะ cache; constraint อื่น raise ตัวเดิมต่อ | 2 | Pass |
| UT-US14-API-05 | `average_rating`: 0 รีวิว → `None`; 5; 1; 5+4 → 4.5; 5+4+4 → 4.33; 5+5+4 → 4.67; ค่าใหญ่ในช่วง integer column; อ่าน summary และ submit ไม่แตะ `credit_score` | 5 | Pass |
| UT-US14-API-06 | Key ของ list/summary ตรง allowlist; ไม่มี email, username, student ID, reviewer ID, party ID แม้ source object จะมี; ไม่มี profile → `ผู้ใช้`; contract ของ response ตอนสร้างรีวิว | 4 | Pass |
| UT-US14-API-06 | `test_no_show_and_credit_formula_blocked_until_policy_is_confirmed` | 1 | **Blocked** (skip: policy not confirmed in #100/#105) |

วิธีทดสอบที่ควรรู้:

- Serializer ของ list และ create เขียน inline ใน view จึงทดสอบผ่าน view ด้วย `RequestFactory` และ mock service; ใช้ `inspect.unwrap` ข้าม decorator เพราะ university guard ต้อง query DB ส่วน access control ตรวจใน IT-US14-DB-33/34, IT-US14-READ-24/25 และ M-14/M-15
- `is_participant` สร้างเงื่อนไขเป็น `Q` ถ้า mock แค่ผลของ `.exists()` จะไม่ได้ตรวจเงื่อนไขจริง test จึงใช้ fake memberships ที่ประเมิน `Q` จริงกับข้อมูลในหน่วยความจำ
- `transaction.Atomic` ถูก patch rollback จริงจึงตรวจใน IT-US14-DB-18 ไม่ใช่ unit test ชุดนี้

ตรวจว่า test จับ bug ได้จริงด้วย mutation check: ใส่ bug ทีละจุด 31 แบบใน `services.py` และ `views.py` ของสำเนาใน container ชั่วคราว (เช่น ตัดการตรวจ state, `gte` → `gt`, rating max 6, ส่ง `reviewer_id` ใน list) ผล test ล้มเหลวครบ 31 แบบ ไม่มี production file ถูกแก้

## Manual API test

ใช้ Python `http.client` จาก host ยิง HTTP จริงไป app ที่กำลังรัน ทุก POST ใช้ token จาก `GET /api/v1/auth/csrf` พร้อม `Origin` ยกเว้น M-15

ข้อมูลทดสอบสร้างผ่าน `manage.py shell`: Session สร้างด้วย `force_university_login` ไม่ส่ง credentials ไป TU provider

| ข้อมูล | ID |
| --- | --- |
| Users `us14-manual-*` | host=1, member1=2, member2=3, member3=4, outsider=5, noprofile=6 (ไม่มี profile) |
| Parties | completed=1 (ย้าย `starts_at`/`ends_at` เป็นอดีตด้วย queryset update), open=2, cancelled=3 |

Path ด้านล่างละ prefix `/api/v1`; POST ไปที่ `/parties/{id}/reviews` และ body มี `reviewee_id`, `rating`, `comment` Actual ตัดข้อความให้สั้นลง

| ID | Request | Expected | Actual | ผล |
| --- | --- | --- | --- | --- |
| M-01 | POST party 1 โดย host, reviewee 2, rating 5 | 201 | 201 `{"review": {"id": 1, "party_id": 1, "reviewer": {"id": 1, "display_name": "ผู้ทดสอบหนึ่ง"}, "reviewee_id": 2, "rating": 5, ...}}` | Pass |
| M-02 | POST party 1 โดย member2, reviewee 2, rating 4 | 201 (member → member) | 201 `{"review": {"id": 2, "reviewer": {"id": 3, ...}, "reviewee_id": 2, "rating": 4, ...}}` | Pass |
| M-03 | ส่งซ้ำ M-01 ด้วย rating 1 | 409 `REVIEW_EXISTS` | 409 `REVIEW_EXISTS` | Pass |
| M-04 | POST party 1 โดย member1, reviewee 2 (ตัวเอง) | 400 ที่ `reviewee_id` | 400 `INVALID_INPUT`, `reviewee_id`: "ไม่สามารถรีวิวตัวเองได้" | Pass |
| M-05 | POST party 1 โดย outsider, reviewee 2 | 403 `FORBIDDEN` | 403 `FORBIDDEN` | Pass |
| M-06 | POST party 1 โดย host, reviewee 5 (outsider) | 400 ที่ `reviewee_id` | 400 `INVALID_INPUT`, `reviewee_id`: "ไม่สามารถรีวิวผู้ใช้นี้ได้" | Pass |
| M-07 | POST party 2 (Open) โดย host, reviewee 2 | 409 `PARTY_NOT_COMPLETED` | 409 `PARTY_NOT_COMPLETED` | Pass |
| M-08 | POST party 3 (Cancelled) โดย host, reviewee 2 | 409 `PARTY_NOT_COMPLETED` | 409 `PARTY_NOT_COMPLETED` | Pass |
| M-09 | POST party 1 โดย host, reviewee 3, rating `0` | 400 ที่ `rating` | 400 `INVALID_INPUT`, `rating` | Pass |
| M-10 | เหมือน M-09, rating `6` | 400 ที่ `rating` | 400 `INVALID_INPUT`, `rating` | Pass |
| M-11 | เหมือน M-09, rating `"5"` | 400 ที่ `rating` | 400 `INVALID_INPUT`, `rating` | Pass |
| M-12 | POST party 1 โดย host, reviewee 3, comment `""` | 400 ที่ `comment` | 400 `INVALID_INPUT`, `comment`: "กรุณาระบุความคิดเห็น" | Pass |
| M-13 | เหมือน M-12, comment 501 ตัวอักษร | 400 ที่ `comment` | 400 `INVALID_INPUT`, `comment`: "ความคิดเห็นต้องไม่เกิน 500 ตัวอักษร" | Pass |
| M-14 | POST party 1 มี CSRF ถูกต้องแต่ไม่มี session | 401 `AUTH_REQUIRED` | 401 `AUTH_REQUIRED` | Pass |
| M-15 | POST party 1 โดย member3, reviewee 3, ไม่มี CSRF cookie/header | 403 `CSRF_FAILED` | 403 `CSRF_FAILED` | Pass |
| M-16 | GET `/users/2/reviews` โดย outsider หลัง 2 รีวิว (5, 4) | 200, average 4.5, count 2, ใหม่สุดก่อน | 200, `average_rating` 4.5, `rating_count` 2, review ids [2, 1] | Pass |
| M-17 | POST party 1 โดย member3, reviewee 2, rating 4 | 201 | 201 `{"review": {"id": 4, "reviewer": {"id": 4, ...}, "rating": 4, ...}}` | Pass |
| M-18 | GET `/users/2/reviews` หลัง 3 รีวิว (5, 4, 4) | 200, average 4.33, count 3, ใหม่สุดก่อน | 200, `average_rating` 4.33, `rating_count` 3, review ids [4, 2, 1], `page` 1, `page_size` 20, `total` 3 | Pass |
| M-19 | GET `/users/2/reviews?page=1&page_size=2` | 200, 2 แถวใหม่สุด, total 3 | 200, review ids [4, 2], `page` 1, `page_size` 2, `total` 3 | Pass |
| M-20 | GET `/users/2/reviews?page=2&page_size=2` | 200, แถวเก่าสุด, total 3 | 200, review ids [1], `page` 2, `page_size` 2, `total` 3 | Pass |
| M-21 | GET `/users/2/reviews?page_size=101` | 400 ที่ `page_size` | 400 `INVALID_INPUT`, `page_size` | Pass |
| M-22 | ค้นใน raw body ของ M-18 | ตรง allowlist; ไม่มี `email`, `@example.test`, `username`, `us14-manual`, `student`, `test-user-`, `party`, `credit`, `reviewer_id` | ไม่พบคำเหล่านี้; key ตรง allowlist; `reviewer` มีเฉพาะ `display_name` | Pass |
| M-23 | GET `/users/3/reviews` (ยังไม่มีรีวิว) | 200, average null, count 0 | 200, `average_rating` null, `rating_count` 0, `reviews` [], `total` 0 | Pass |
| M-24 | GET `/users/6/reviews` (ไม่มี profile) | 404 `NOT_FOUND` | 404 `NOT_FOUND`: "ไม่พบผู้ใช้ที่ต้องการ" | Pass |

ตรวจ DB หลังรันทุก case: มีรีวิว 3 แถวตาม M-01, M-02, M-17 เท่านั้น; member1 มี `rating_sum`=13, `rating_count`=3; `credit_score` ที่ตั้งไว้ 75 ก่อนทดสอบยังเป็น 75; profile อื่น cache เป็น 0/0 จึงยืนยันว่า case ที่ถูกปฏิเสธไม่เขียนข้อมูล และ backend log ไม่มี traceback หรือ Internal Server Error ในช่วงทดสอบ

### Race

ไม่ได้ทดสอบ race ด้วยมือ และไม่อ้างผลแบบ manual หลักฐานคือ automated tests ใน [test_reviews_concurrency.py](../backend/conduct/test_reviews_concurrency.py) บน PostgreSQL จริง ซึ่งผ่านทั้ง 3 tests ทั้งใน `make verify` และเมื่อรันแยก

| Test ID | สิ่งที่ตรวจ | ผลจริง |
| --- | --- | --- |
| IT-US14-DB-41 | ส่งรีวิวเดียวกันพร้อมกัน เก็บเพียงแถวเดียว | ok |
| IT-US14-DB-42 | ผู้รีวิวต่างคนส่งพร้อมกัน rating cache ไม่หาย | ok |
| IT-US14-DB-43 | อ่าน state หลังได้ Party lock ที่เวลา `ends_at` พอดี | ok |

### No-show / credit (Blocked)

ไม่ได้ส่ง request และไม่ได้เปิด flag เหตุผล: policy ใน `conduct/policy.py` ของ `e1fde1f` ยังเป็น PROPOSAL ที่รอยืนยันใน #100/#105, ค่า default ของ `NO_SHOW_ENABLED` คือ false และ code ส่วนนี้ไม่อยู่ใน branch ที่ทดสอบ

| ID | Case | ผล |
| --- | --- | --- |
| M-B1 | ส่ง No-show report ผ่าน API | Blocked |
| M-B2 | เกณฑ์จำนวนผู้รายงานและช่วงเวลารายงาน | Blocked |
| M-B3 | สูตรหักและประวัติ conduct credit | Blocked |

Retest เมื่อ #100/#105 ยืนยัน policy และรวม B-03 แล้ว: แทน skipped test ด้วย unit tests ของค่าที่ยืนยัน แล้วรัน M-B1 ถึง M-B3 บน environment ที่ทีมตกลงให้เปิด flag

## การลบข้อมูลทดสอบ

ลบเฉพาะข้อมูลที่สร้างรอบนี้ หลังตรวจว่า ID ตรงกับตอนสร้าง: reviews 3, parties 3, memberships 12, venue 1, sport 1, sessions 5, identities 5, profiles 5, users 6

นับแถวทุก model (17 ตาราง) ก่อนสร้างและหลังลบ: **ไม่มีความต่าง**, ไม่เหลือ user prefix `us14-manual-` และ session เดิมตอบ 401 หลังลบ

สิ่งที่ค้างคือ sequence ของ PostgreSQL ที่เดินหน้าแล้ว ID ของข้อมูลใหม่จึงไม่เริ่มจากค่าเดิม ไม่กระทบข้อมูลอื่น

## Verify

| คำสั่ง | ผลจริง |
| --- | --- |
| `make format` | `1 file reformatted, 91 files left unchanged` (ไฟล์ test ใหม่เท่านั้น) |
| `make verify` | exit 0: Django check ผ่าน, `No changes detected`, Ruff `All checks passed!`, `92 files already formatted`, `Ran 438 tests`, `OK (skipped=1)` |
| `make smoke` | exit 0: `Smoke passed: HTTP, PostgreSQL readiness, Django template and static CSS.` |
| `manage.py test conduct.test_reviews_unit` | `Ran 32 tests`, `OK (skipped=1)` |
| `manage.py test conduct.test_reviews_concurrency` | `Ran 3 tests`, `OK` |

Test ที่ skip มีเพียงตัวเดียวคือ case Blocked ของ UT-US14-API-06

## Bugs และข้อสังเกต

**Bugs: ไม่พบ** จึงไม่มีรายการที่ต้อง retest นอกจาก case Blocked ด้านบน

ข้อสังเกต (ไม่ใช่ defect และไม่ได้แก้):

1. **Response ตอนสร้างรีวิวมี `party_id` และ `reviewer.id`** ส่วน list API ไม่มี พฤติกรรมนี้ตรงกับ IT-US14-DB-01 ดังนั้น allowlist ที่ห้าม reviewer ID/party ID ใช้กับ list/summary เท่านั้น ถ้าทีมต้องการกฎเดียวกันทั้งสอง API ต้องตัดสินใจและแก้ contract แยก
2. **Review ID เว้นช่วงได้** M-17 ได้ id 4 เพราะ insert ที่ชน unique ใน M-03 ใช้ค่า sequence ไปแล้ว ไม่กระทบลำดับหรือ cache แต่ client ไม่ควรถือว่า ID ต่อเนื่อง

## ข้อจำกัด

- ไม่ได้ทดสอบบัญชี TU จริง, browser/UI หรือ UAT; session มาจาก test helper
- Manual ทดสอบเฉพาะ state Open และ Cancelled; Full และ InProgress ตรวจใน UT-US14-API-01, IT-US14-DB-12 และ IT-US14-DB-13
- Manual รันบน app และ database สำหรับพัฒนาในเครื่อง ไม่ใช่ staging หรือ production
- Checklist มาจากรายละเอียดงานที่ได้รับ ไม่ได้เปิด Issue #109 โดยตรงเพราะเครื่องนี้ไม่มี `gh`; ควรเทียบกับ Issue อีกครั้งก่อนปิดงาน
- ยังไม่มีผล CI หรือ review; รอ commit/push ก่อนแนบผล
