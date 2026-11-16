# Task83 — US2 API testing

งาน `S2-US2-T-API` / [Issue #98](https://github.com/GearJP2/cs261-group2-100001/issues/98)
คนหลัก Golf (@Seamui); ผู้ตรวจที่รอ Austin (@Siestashi)
วันที่รัน unit tests: 16 พฤศจิกายน 2026 (Asia/Bangkok)
สถานะ: เสร็จเฉพาะขั้น unit tests; Manual HTTP API ยัง **Not run** ไม่ถือว่าปิด Task83 แล้ว
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
ผลนี้เป็น local working tree ก่อน commit ไฟล์ใหม่ ไม่ใช่ GitHub CI หรือ human Manual API/UAT

## ขั้นถัดไป

- [ ] เตรียมข้อมูลจำลองในฐานแยก และส่ง HTTP จริง: AND filters, query invalid, ขอบเวลา Bangkok, state และ pagination ตาม contract
- [ ] เก็บ expected/actual, response และหลักฐานข้อมูล ไม่บันทึก cookie/token
- [ ] รัน integration/query audit เดิมจาก Task78/84 แยกจาก unit tests ไม่สร้างหลักฐานซ้ำแทนทีม
- [ ] บันทึก bug/retest หากพบ; ส่วนที่ยังไม่รันคง Not run
- [ ] รัน checks ทั้งโปรเจกต์ แนบ commit/PR/CI และ Austin review ก่อนปิด #98
