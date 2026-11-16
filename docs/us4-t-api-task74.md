# Task74 — US4 API testing

งาน `S2-US4-T-API` / [Issue #89](https://github.com/GearJP2/cs261-group2-100001/issues/89)
คนหลัก Golf (@Seamui); ผู้ตรวจที่รอ Austin (@Siestashi)
วันที่รัน unit tests: 16 พฤศจิกายน 2026 (Asia/Bangkok)
สถานะส่งมอบ: เสร็จเฉพาะ unit tests; Manual API ยัง **Not run** ไม่ถือว่าปิด Task74 แล้ว

## Unit tests แบบ mock

ไฟล์ [test_leave_unit.py](../backend/parties/test_leave_unit.py) ใช้ SimpleTestCase ซึ่งห้าม DB access, RequestFactory เรียก handler โดยตรง และ mock identity lookup, ORM managers, service หรือ clock ตามระดับที่ทดสอบ
ไม่มี HTTP server, PostgreSQL หรือ TU provider จริงในการทดสอบชุดนี้
Service tests เรียก `leave_party.__wrapped__` เพื่อทดสอบ business logic โดยไม่เปิด atomic transaction; transaction/row locks/rollback เป็นหลักฐาน integration ของ Task69/Task75 ไม่ใช่ข้อพิสูจน์จากชุด unit นี้

| Checklist | Expected | Actual | ผล |
| --- | --- | --- | --- |
| UT-US4-API-01 | anonymous ไม่เรียก service; actor จาก client ถูกปฏิเสธ; nonmember ไม่ save | anonymous 401, identity ไม่ผ่าน 403, client-selected actor 400; mocks ยืนยัน no service/save และ query membership ของ session actor เท่านั้น | Pass |
| UT-US4-API-02 | สมาชิก active ก่อนเริ่มส่ง session actor ไป service แล้ว soft leave | handler ส่ง party_id/user ถูกตัว; service บันทึก left_at จาก clock ด้วย save(update_fields=[left_at]) ครั้งเดียว | Pass |
| UT-US4-API-03 | ถอนแล้วไม่เขียนหรือคืนที่ว่างเพิ่ม | left_at เดิมคงอยู่, save ไม่ถูกเรียก แม้ Party เริ่ม/ยกเลิกภายหลัง; ไม่มี counter ที่ว่างแยกให้เพิ่ม | Pass |
| UT-US4-API-04 | Host ถอนไม่ได้ตาม policy | HOST_CANNOT_LEAVE 403 ก่อน query membership/clock; ไม่มี save | Pass |
| UT-US4-API-05 | ตรงเวลาเริ่ม/หลังเริ่มหรือยกเลิกต้องไม่เขียน | PARTY_STARTED 409, PARTY_CANCELLED 409; cancelled ชนะเวลา; ก่อนเริ่ม 1 microsecond ถอนได้ | Pass |

คำสั่งรัน:

```bash
docker compose run --rm -T --no-deps backend python backend/manage.py test parties.test_leave_unit --noinput --verbosity 2
```

ผลจริง: **11 tests ผ่าน ไม่มี skipped** และ output ระบุ `Skipping setup of unused database(s): default.` ดู [raw log](evidence/task74/unit-tests.log)
Ruff check/format และ `git diff --check` ผ่าน ไม่มีการเปลี่ยน runtime code
Raw log ชุดนี้เป็นผล local ของ working tree ที่เพิ่มไฟล์ test นี้ รอแนบ commit/PR จริงหลังผู้ใช้ commit; ไม่ใช่ผล GitHub CI

## งานถัดไป

- [ ] เตรียม fixtures/session และทำ Manual HTTP API: success, anonymous, client-selected actor, nonmember, Host, retry และ started/cancelled
- [ ] เก็บ request/status/response ที่ไม่มี cookie/token พร้อม DB snapshot ก่อน–หลัง เพื่อยืนยัน no mutation เมื่อไม่อนุญาต
- [ ] อ้างและรัน concurrent integration tests ที่เกี่ยวข้องแยกจาก unit; ไม่ใช้ SQL snapshot อย่างเดียวอ้าง race ผ่าน
- [ ] บันทึก expected/actual และ Pass/Fail/Blocked/Not run, bug/retest เมื่อมี
- [ ] รัน checks ทั้งชุด แนบ commit/PR/CI และให้ Austin review ก่อนปิด #89
