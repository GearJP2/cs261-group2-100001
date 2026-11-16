# Task83 — US2 API testing

งาน `S2-US2-T-API` / [Issue #98](https://github.com/GearJP2/cs261-group2-100001/issues/98)
คนหลัก Golf (@Seamui); ผู้ตรวจที่รอ Austin (@Siestashi)
วันที่รัน unit tests: 16 พฤศจิกายน 2026 (Asia/Bangkok)
สถานะ: unit และ agent-operated HTTP rehearsal ผ่านแล้ว ยังไม่ใช่ human Manual API/UAT และยังรอ final checks/review ก่อนปิด Task83
อ้างอิง [Design](us2-search-design.md), [test plan](us2-search-test-cases.md) และ [Task79](us2-b-01-test-report.md)

## ส่วนที่ reuse และส่วนเพิ่ม

Reuse `test_search_query.py` เดิม 7 tests ซึ่งใช้ SimpleTestCase ไม่ใช้ DB และไม่เรียก TU provider
เพิ่ม [test_search_unit.py](../backend/parties/test_search_unit.py) 5 tests โดย mock `Party.objects` ให้ส่งต่อไป repository ใน memory และใช้ now/fixture คงที่
SimpleTestCase ห้าม DB access; ไม่มี HTTP server หรือ SQL query จริงในชุดนี้
repository จำลองประเมิน expression/filter ที่ builder สร้างกับข้อมูลทดสอบ เพื่อแยกแถวที่ตรงเพียงบางเงื่อนไขออก ไม่สร้าง response สำเร็จตายตัวจาก mock
active_member_count เป็นค่าที่กำหนดใน fixture จึงไม่อ้างว่าชุด unit พิสูจน์ SQL count/join/pagination ของ PostgreSQL

## Checklist expected / actual

| ID | Expected | Actual | ผล |
| --- | --- | --- | --- |
| UT-US2-API-01 | query field/type ผิดได้ validation error ตาม contract | parser เดิมตรวจ unknown/repeated keys, integer/enum, empty value, text limit และช่วงเวลาผิด; PartyError INVALID_INPUT 400 พร้อม fields | Pass |
| UT-US2-API-02 | ทุกเงื่อนไขรวม AND ไม่ใช่ OR | fixture ที่ผิด sport/venue/type/text/time เพียงหนึ่งข้อไม่ผ่าน; เหลือแถวตรงทุกเงื่อนไข; ลำดับ starts_at/id คงที่ | Pass |
| UT-US2-API-03 | sport กับ venue type เป็นคนละ predicate | กีฬาเดียวพบได้หลายประเภทสนาม; ประเภทเดียวพบได้หลายกีฬา; รวมคู่ที่ไม่ตรงได้ผลว่าง; null ไม่ตรง Indoor/Outdoor | Pass |
| UT-US2-API-04 | normalize เวลา Bangkok และช่วงเริ่ม–สิ้นสุดตรง contract | Bangkok offset กับ UTC ที่ instant เดียวกันให้ผลเท่ากัน; รวม starts_from ไม่รวม starts_to; เริ่มก่อนขอบล่างแต่ overlap ไม่เข้า | Pass |
| UT-US2-API-05 | Full/started/cancelled ตรง Detail | repository ประเมิน Case แล้วเทียบ get_party_state ณ now เดียว; ตรวจ Open/Full/InProgress/Completed/Cancelled, exact starts_at/ends_at และ Cancelled ชนะเวลา/Full; all ไม่เติม state filter | Pass |

ผลจริง: **12 tests ผ่าน ไม่มี skipped** (7 reuse + 5 ใหม่) และ log ระบุ `Skipping setup of unused database(s): default.`
หลักฐาน [unit-tests.log](evidence/task83/unit-tests.log)

```bash
docker compose run --rm -T --no-deps backend python backend/manage.py test parties.test_search_query parties.test_search_unit --noinput --verbosity 2
```

Ruff check/format และ `git diff --check` ผ่าน ไม่แก้ runtime/schema และไม่แก้ historical evidence ของ Task78/84
ผล unit ถูกบันทึกใน commit `48e189c` แล้ว ไม่ใช่ GitHub CI หรือ human Manual API/UAT

## HTTP + PostgreSQL rehearsal — 16 พฤศจิกายน 2026

Reuse `SearchDatabaseAcceptanceTests` ของ Task84 ซึ่งใช้ LiveServerTestCase เปิด loopback server และส่ง urllib HTTP จริงไปยัง Django app กับ PostgreSQL test DB `test_unisport`
ฐานทดสอบถูกสร้าง/ลบโดย Django test runner ไม่ใช่ฐานข้อมูลพัฒนาปกติ Session เป็น verified local fixture ไม่เรียก TU provider
เวลาถูกควบคุมที่ `2030-11-19T12:00:00+07:00` เพื่อพิสูจน์ boundary ซ้ำได้ จึงไม่อ้างว่าเวลาจริงอยู่ปี2030 หรือมนุษย์จับเวลากดตรง microsecond
ปรับเฉพาะ metadata `TASK84_TESTER` ให้ระบุผู้รันรอบ Task83 โดย default เดิมยังเหมือนเดิม ไม่แก้ runtime และไม่เขียนทับหลักฐาน Task78/84

| หลักฐานรอบ retest | Expected | Actual / ผล |
| --- | --- | --- |
| [DB84-01](evidence/task83/http-retest/DB84-01.json) | AND filters, sport/type แยกกัน, null type, incompatible/unknown IDs | IDs/total/count ตรง fixture และ SQL; query ไม่เปลี่ยน business rows — Pass |
| [DB84-02](evidence/task83/http-retest/DB84-02.json) | [from,to), ขอบเดียว, UTC/Bangkok instant เดียวกัน | รวม lower/inside ไม่รวม upper/overlap; offset ให้ผลเท่ากัน — Pass |
| [DB84-03](evidence/task83/http-retest/DB84-03.json) | Open/Full/InProgress/Completed/Cancelled/all ตรง Detail รวม exact start/end | state/member_count/remaining_slots ตรง SQL และ Detail — Pass |
| [DB84-04](evidence/task83/http-retest/DB84-04.json) | 101 รายการเวลาเท่ากัน กรองก่อนนับ/แบ่งหน้า และหน้าที่เกิน | starts_at/id คงที่, total101, page_size20/100, หน้า999ว่าง; ไม่ซ้ำ — Pass |
| [DB84-05](evidence/task83/http-retest/DB84-05.json) | refresh หลัง approve/leave/cancel เห็นข้อมูล commit ล่าสุด | Open→Full→Open→Cancelled และ active/slots ตรง SQL — Pass |
| [DB84-06](evidence/task83/http-retest/DB84-06.json) | equal/reversed time, naive/date-only, unknown query, size101 ได้400 ไม่ mutate | INVALID_INPUT 400; business snapshot hash ก่อน/หลังตรงกัน — Pass |

ทุกไฟล์มี method/path/payload/status/response, expected fixture IDs/total, SQL comparison และ source/runtime metadata โดยตัด cookie/CSRF/session key ออก
DB84-05 มี POST เปลี่ยนสถานะที่ตั้งใจทำเพื่อพิสูจน์ refresh; ข้อสรุป no mutation อ้างเฉพาะ GET search และ invalid queries ไม่ใช่ POST approve/leave/cancel

## Failure และ retest

รอบแรกเปิดสอง test runners พร้อมกันด้วยชื่อ DB เดียว เป็นความผิดพลาดในการ orchestration: พบ database already exists/in use และ HTTP connection timeout ทำให้หนึ่งเคสได้ JSONDecodeError จาก response ที่ไม่ใช่ JSON
เก็บ [HTTP failed log](evidence/task83/http-initial-failed.log) และ [integration failed log](evidence/task83/integration-initial-failed.log) ไว้ ไม่รายงานรอบแรกว่าผ่าน; JSON บางกลุ่มใน `http/` เป็นผลบางส่วน ไม่ใช้เป็น final evidence
แก้โดยรวมทุกชุดไว้ใน test invocation เดียวและรันตามลำดับ ไม่เปลี่ยน runtime เพื่อแก้ผลทดสอบ
รอบ retest ผ่าน **38 tests ไม่มี skipped** ดู [raw log](evidence/task83/http-integration-retest.log): parser7 + mock builder5 + filter integration7 + HTTP client7 + Task78 audit6 + Task84 live HTTP6
ผลนี้ยังไม่ใช่ concurrent race test; GET search ไม่มีการจอง/เขียนที่นั่ง และงานนี้ไม่อ้างผล production load/race จาก snapshots

## วิธีรันซ้ำ

ใช้ Docker environment ตามทีม เปิด tests ทีละ invocation ไม่ให้ runner อื่นใช้ test DB เดียวกัน และ mount docs สำหรับ artifact
สร้าง directory รอบใหม่ที่ยังไม่มีไฟล์ JSON เพราะ writer ใช้ exclusive create เพื่อไม่เขียนทับผลเก่า:

```bash
mkdir -p docs/evidence/task83/http-next
docker compose run --rm -T -v "$PWD/docs:/app/docs" -e TASK84_EVIDENCE_DIR=/app/docs/evidence/task83/http-next -e TASK84_SOURCE="$(git rev-parse HEAD)" -e "TASK84_TESTER=ชื่อผู้รันจริง" backend python backend/manage.py test parties.test_search_query parties.test_search_unit parties.test_search_filters parties.test_search_api parties.test_search_query_audit parties.test_search_database_acceptance --noinput --verbosity 2
```

นี่เป็น **agent-operated HTTP rehearsal** ไม่ใช่หลักฐานว่ามนุษย์ส่ง Postman/curl เองหรือ human UI/UAT หากทีมต้องการ human Manual API ให้บันทึกชื่อ/วัน/ผล retest ของผู้ทดสอบจริงเพิ่ม ไม่เปลี่ยนผล agent เป็น human result

## ขั้นถัดไป

- [ ] แนบ PR และผล GitHub CI ก่อนปิด #98
- [ ] ให้ Austin review ความครบของ AC/contract และหลักฐาน HTTP สำหรับ Manual API; หากต้องการ human retest ให้บันทึกแยก

## Final local verification — 16 พฤศจิกายน 2026

ตรวจ source commit `f8237e8` หลังบันทึก unit และ HTTP evidence แล้ว ไม่มีการแก้ runtime เพิ่มในขั้นนี้

| การตรวจ | ผล | หลักฐาน |
| --- | --- | --- |
| `make verify` | ผ่าน Django/migration checks, Ruff check/format และ 708 tests (skip 1) | [verification.log](evidence/task83/verification.log) |
| `make smoke` | ผ่าน HTTP, PostgreSQL readiness, Django template และ static CSS | [smoke.log](evidence/task83/smoke.log) |
| evidence JSON/source hashes | ผ่าน 6 กลุ่ม รวม 303 HTTP requests; snapshot hashes ของ read-only checks ก่อน/หลังตรงกัน | ตรวจ local จาก http-retest/ |
| cookie/session values | ไม่พบค่า sessionid= หรือ csrftoken= ในไฟล์หลักฐาน | ตรวจ local |

ผล local นี้ไม่ใช่ GitHub CI, peer review หรือ human Manual API/UAT และไม่เปลี่ยนผล failed รอบแรกให้เป็น Pass

เคสที่ skip คือ UT-US14-API-06 เพราะ policy ไม่ยืนยันใน #100/#105 เป็นข้อจำกัดเดิมของ US14 ไม่ใช่ Task83 ไม่เปลี่ยนเป็น Pass; ลิงก์ไฟล์หลักฐานและ `git diff --check` ผ่าน
