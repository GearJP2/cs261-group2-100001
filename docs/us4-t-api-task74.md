# Task74 — US4 API testing

งาน `S2-US4-T-API` / [Issue #89](https://github.com/GearJP2/cs261-group2-100001/issues/89)
คนหลัก Golf (@Seamui); ผู้ตรวจที่รอ Austin (@Siestashi)
วันที่รัน unit tests: 16 พฤศจิกายน 2026 (Asia/Bangkok)
สถานะส่งมอบ: unit และ HTTP rehearsal โดย agent ผ่านแล้ว; ยังไม่ใช่ human Manual API/UAT และยังรอ review/CI ก่อนปิด Task74

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
Raw log ชุดนี้เป็นผล local ของ working tree ที่เพิ่มไฟล์ test นี้ และผู้ใช้บันทึก unit tests ใน commit `dcf17c1` แล้ว; ไม่ใช่ผล GitHub CI

## HTTP + SQL rehearsal — 16 พฤศจิกายน 2026

ใช้ [script](../scripts/us4-api-evidence.py) ส่ง HTTP จริงผ่าน loopback WSGI server และ Django middleware ไป PostgreSQL แยก `s2_task74_http_retest` ใน Compose project `s2-task74`
Session เป็น synthetic verified fixture เก็บ cookie/CSRF ใน memory ไม่เรียก TU provider ไม่เพิ่ม login bypass ในแอป
ทุก request ใช้ path `/api/v1/parties/{id}/leave`; POST ส่ง JSON `{}` ยกเว้น HTTP04 ส่ง user_id ของผู้อื่น และ HTTP08 ใช้ GET

| Case | ขั้นตอน / Expected | Actual | ผล |
| --- | --- | --- | --- |
| HTTP01 | สมาชิก active ถอนก่อนเริ่ม → 200, active ลด1/ที่ว่างเพิ่ม1 | 200; active2→1, slots1→2; membership เดิม, request/capacity ไม่เปลี่ยน | Pass |
| HTTP02 | ส่งซ้ำ → 200 payload/left_at เดิม ไม่มี SQL mutation | 200 ตรงผลแรก; snapshot เท่าเดิม | Pass |
| HTTP03 | ไม่แนบ session แต่ CSRF ถูกต้อง → 401/no mutation | AUTH_REQUIRED 401; snapshot เท่าเดิม | Pass |
| HTTP04 | สมาชิกแนบ user_id คนอื่น → 400/no mutation | INVALID_INPUT 400; snapshot เท่าเดิม | Pass |
| HTTP05 | ผู้ไม่เป็นสมาชิกส่งคำขอ → 403/no mutation | NOT_MEMBER 403; snapshot เท่าเดิม | Pass |
| HTTP06 | Host ถอน → 403/no mutation | HOST_CANNOT_LEAVE 403; snapshot เท่าเดิม | Pass |
| HTTP07 | session ถูกต้องแต่ไม่ส่ง CSRF header → 403/no mutation | CSRF_FAILED 403; snapshot เท่าเดิม | Pass |
| HTTP08 | ใช้ GET → 405/no mutation | METHOD_NOT_ALLOWED 405; snapshot เท่าเดิม | Pass |
| HTTP09 | ตั้งกิจกรรมเริ่มแล้ว → 409/no mutation | PARTY_STARTED 409; snapshot เท่าเดิม | Pass |
| HTTP10 | ตั้งกิจกรรมจบแล้ว → 409/no mutation | PARTY_STARTED 409; snapshot เท่าเดิม | Pass |
| HTTP11 | ยกเลิกและเลยเวลาเริ่ม → 409/no mutation | PARTY_CANCELLED 409; snapshot เท่าเดิม | Pass |

ดู expected/actual, response และ SQL snapshots ทุกเคสใน [http-sql.json](evidence/task74/http-sql.json) พร้อม source commit/runtime/hash และ [runtime log](evidence/task74/http-runtime.log)
snapshot แต่ละเคสอ่านหลังการเตรียมสถานะแล้วและก่อนส่ง HTTP ไม่เอาการเปลี่ยนเวลา fixture ไปนับเป็น mutation ของ request
วันที่ตรง starts_at พอดีพิสูจน์ด้วย mock clock ใน unit tests ไม่อ้างว่ารอบ HTTP นี้จับเวลาตรง microsecond ได้

นี่เป็น **assistant-operated HTTP rehearsal** ที่รันผ่าน script ไม่ใช่หลักฐานว่ามนุษย์ส่ง Postman/curl เอง หากทีมต้องการ human Manual API ให้ผู้ทดสอบรันซ้ำและบันทึกชื่อ/เวลาจริงเพิ่มเติมก่อนปิดงาน
รอบแรก assertions HTTP ผ่านแต่เขียน artifact ไม่ได้เพราะ docs ไม่ได้ mount จึงแก้ preflight และรันใหม่ในฐานว่างอีกชื่อ ไม่ reset/delete ฐานเดิม; JSON/log ที่แนบเป็นรอบรันซ้ำที่บันทึกสำเร็จ

## วิธีรันซ้ำ

ต้องใช้ database ว่างชื่อ `s2_task74_*`, DEBUG=true และ mount docs; script ปฏิเสธชื่อ DB อื่นหรือ DB ที่มีข้อมูลผู้ใช้/Party ไม่ reset ข้อมูล
ตัวอย่างตั้ง project/พอร์ตให้ไม่ชน environment ปกติ:

```bash
POSTGRES_DB=s2_task74_http_new POSTGRES_HOST_PORT=55474 docker compose -p s2-task74 up -d --wait database
POSTGRES_DB=s2_task74_http_new POSTGRES_HOST_PORT=55474 docker compose -p s2-task74 run --rm -T --no-deps -v "$PWD/docs:/app/docs" -e POSTGRES_DB=s2_task74_http_new -e TASK74_SOURCE="$(git rev-parse HEAD)" backend python scripts/us4-api-evidence.py
```

POSTGRES_DB ของ PostgreSQL มีผลเฉพาะ initialize volume ใหม่ หาก project มี volume เดิมแล้วให้ใช้ project ใหม่/พอร์ตใหม่ หรือสร้างฐานว่างใหม่ใน project ทดสอบก่อน อย่าเปลี่ยนชื่อแล้วคาดว่าจะสร้างฐานให้อัตโนมัติ
script เขียนทับเฉพาะ artifact `http-sql.json`; เก็บหลักฐานเดิมก่อน rerun เพื่อไม่สูญเสียผลรอบก่อน

## Integration / concurrency ที่รันร่วม

```bash
docker compose run --rm -T backend python backend/manage.py test parties.test_leave_unit parties.test_leave parties.test_leave_api parties.test_leave_database --noinput --verbosity 0
```

ผ่าน **40 tests ไม่มี skipped**: unit ใหม่11 + HTTP/service/DBเดิม29 ดู [raw log](evidence/task74/integration-tests.log)
PostgreSQL integration เดิมพิสูจน์ concurrent leave/approve/cancel/edit, lock wait, rollback และการคืนที่ว่างครั้งเดียว ไม่ใช้ snapshots จาก HTTP rehearsal เพียงอย่างเดียวอ้าง race ผ่าน
รายงานเดิม [Task75](s2-us4-t-db-task75.md) เป็นหลักฐานประกอบ; ไม่แก้ historical evidence ของทีม

## งานที่ยังเหลือ

- [ ] ให้ผู้ตรวจยืนยันว่า agent-operated HTTP rehearsal เป็นหลักฐานที่รับได้สำหรับ Manual API; หากต้องการมนุษย์รันให้บันทึก human retest
- [ ] แนบ PR/GitHub CI และให้ Austin review ก่อนปิด #89

## Final local verification — 16 พฤศจิกายน 2026

ตรวจ source commit `43c1569` หลังบันทึก unit tests และ HTTP rehearsal แล้ว โดยไม่ได้แก้ runtime เพิ่ม:

| การตรวจ | ผล | หลักฐาน |
| --- | --- | --- |
| `make verify` | ผ่าน Django/migration checks, Ruff check/format และ 684 tests (skip 1) | [verification.log](evidence/task74/verification.log) |
| `make smoke` | ผ่าน HTTP, PostgreSQL readiness, Django template และ static CSS | [smoke.log](evidence/task74/smoke.log) |
| report links / evidence JSON / source hashes / whitespace | ผ่าน | ตรวจ local |

smoke เป็น runtime smoke ทั่วไป ไม่ใช่หลักฐาน human Manual API/UAT และไม่ใช่ผล GitHub CI

เคสที่ skip คือ UT-US14-API-06 เพราะ policy ไม่ยืนยันใน #100/#105 เป็นข้อจำกัดเดิมของ US14 ไม่ใช่ Task74 ไม่เปลี่ยนเป็น Pass และไม่ติ๊ก review/CI จากผล local นี้
